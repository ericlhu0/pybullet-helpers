"""Abstract class for single armed manipulators with PyBullet helper
functions."""

import abc
from functools import cached_property
from pathlib import Path
from typing import Optional

import numpy as np
import pybullet as p
from gymnasium.spaces import Box

from pybullet_helpers.geometry import Pose
from pybullet_helpers.ikfast import IKFastInfo
from pybullet_helpers.ikfast.utils import ikfast_closest_inverse_kinematics
from pybullet_helpers.inverse_kinematics import (
    InverseKinematicsError,
    pybullet_inverse_kinematics,
)
from pybullet_helpers.joint import (
    JointInfo,
    JointPositions,
    get_joint_infos,
    get_joint_lower_limits,
    get_joint_positions,
    get_joint_upper_limits,
    get_joints,
    get_kinematic_chain,
)
from pybullet_helpers.link import BASE_LINK, get_link_state


class SingleArmPyBulletRobot(abc.ABC):
    """A single-arm fixed-base PyBullet robot with a two-finger gripper."""

    def __init__(
        self,
        physics_client_id: int,
        base_pose: Pose = Pose.identity(),
        control_mode: str = "position",
        home_joint_positions: JointPositions | None = None,
    ) -> None:
        self.physics_client_id = physics_client_id

        # Pose of base of robot.
        self._base_pose = base_pose

        # Control mode for the robot.
        self._control_mode = control_mode

        # Home joint positions.
        self._home_joint_positions = (
            home_joint_positions or self.default_home_joint_positions
        )

        # Load the robot and set base position and orientation.
        self.robot_id = p.loadURDF(
            str(self.urdf_path()),
            basePosition=self._base_pose.position,
            baseOrientation=self._base_pose.orientation,
            useFixedBase=True,
            physicsClientId=self.physics_client_id,
        )

        # Robot initially at home pose.
        self.set_joints(self.home_joint_positions)

    @classmethod
    @abc.abstractmethod
    def get_name(cls) -> str:
        """Get the name of the robot."""
        raise NotImplementedError("Override me!")

    @classmethod
    @abc.abstractmethod
    def urdf_path(cls) -> Path:
        """Get the path to the URDF file for the robot."""
        raise NotImplementedError("Override me!")

    @property
    @abc.abstractmethod
    def default_home_joint_positions(self) -> JointPositions:
        """The default joint values for the robot."""
        raise NotImplementedError("Override me!")

    @property
    def home_joint_positions(self) -> JointPositions:
        """The home joint positions for this robot."""
        return self._home_joint_positions

    @property
    def action_space(self) -> Box:
        """The action space for the robot.

        Represents position control of the arm and finger joints.
        """
        return Box(
            np.array(self.joint_lower_limits, dtype=np.float32),
            np.array(self.joint_upper_limits, dtype=np.float32),
            dtype=np.float32,
        )

    @property
    @abc.abstractmethod
    def end_effector_name(self) -> str:
        """The name of the end effector."""
        raise NotImplementedError("Override me!")

    @property
    def end_effector_id(self) -> int:
        """The PyBullet joint ID for the end effector."""
        return self.joint_from_name(self.end_effector_name)

    @property
    @abc.abstractmethod
    def tool_link_name(self) -> str:
        """The name of the end effector link (i.e., the tool link)."""
        raise NotImplementedError("Override me!")

    @cached_property
    def tool_link_id(self) -> int:
        """The PyBullet link ID for the tool link."""
        return self.link_from_name(self.tool_link_name)

    @cached_property
    def base_link_name(self) -> str:
        """Name of the base link for the robot."""
        base_info = p.getBodyInfo(self.robot_id, physicsClientId=self.physics_client_id)
        base_name = base_info[0].decode(encoding="UTF-8")
        return base_name

    @cached_property
    def arm_joints(self) -> list[int]:
        """The PyBullet joint IDs of the joints of the robot arm, including the
        fingers, as determined by the kinematic chain.

        Note these are joint indices not body IDs, and that the arm
        joints may be a subset of all the robot joints.
        """
        joint_ids = get_kinematic_chain(
            self.robot_id, self.end_effector_id, self.physics_client_id
        )
        # NOTE: pybullet tools assumes sorted arm joints.
        joint_ids = sorted(joint_ids)
        joint_ids.extend([self.left_finger_id, self.right_finger_id])
        return joint_ids

    @cached_property
    def arm_joint_names(self) -> list[str]:
        """The names of the arm joints."""
        return [
            info.jointName
            for info in get_joint_infos(
                self.robot_id, self.arm_joints, self.physics_client_id
            )
        ]

    @cached_property
    def joint_infos(self) -> list[JointInfo]:
        """Get the joint info for each joint of the robot.

        This may be a superset of the arm joints.
        """
        all_joint_ids = get_joints(self.robot_id, self.physics_client_id)
        return get_joint_infos(self.robot_id, all_joint_ids, self.physics_client_id)

    @cached_property
    def joint_names(self) -> list[str]:
        """Get the names of all the joints in the robot."""
        joint_names = [info.jointName for info in self.joint_infos]
        return joint_names

    def joint_from_name(self, joint_name: str) -> int:
        """Get the joint index for a joint name."""
        return self.joint_names.index(joint_name)

    def joint_info_from_name(self, joint_name: str) -> JointInfo:
        """Get the joint info for a joint name."""
        return self.joint_infos[self.joint_from_name(joint_name)]

    def link_from_name(self, link_name: str) -> int:
        """Get the link index for a given link name."""
        if link_name == self.base_link_name:
            return BASE_LINK

        # In PyBullet, each joint has an associated link.
        for joint_info in self.joint_infos:
            if joint_info.linkName == link_name:
                return joint_info.jointIndex
        raise ValueError(f"Could not find link {link_name}")

    @property
    @abc.abstractmethod
    def left_finger_joint_name(self) -> str:
        """The name of the left finger joint."""
        raise NotImplementedError("Override me!")

    @property
    @abc.abstractmethod
    def right_finger_joint_name(self) -> str:
        """The name of the right finger joint."""
        raise NotImplementedError("Override me!")

    @cached_property
    def left_finger_id(self) -> int:
        """The PyBullet joint ID for the left finger."""
        return self.joint_from_name(self.left_finger_joint_name)

    @cached_property
    def right_finger_id(self) -> int:
        """The PyBullet joint ID for the right finger."""
        return self.joint_from_name(self.right_finger_joint_name)

    @cached_property
    def left_finger_joint_idx(self) -> int:
        """The index into the joints corresponding to the left finger.

        Note this is not the joint ID, but the index of the joint within
        the list of arm joints.
        """
        return self.arm_joints.index(self.left_finger_id)

    @cached_property
    def right_finger_joint_idx(self) -> int:
        """The index into the joints corresponding to the right finger.

        Note this is not the joint ID, but the index of the joint within
        the list of arm joints.
        """
        return self.arm_joints.index(self.right_finger_id)

    @cached_property
    def joint_lower_limits(self) -> JointPositions:
        """Lower bound on the arm joint limits."""
        return get_joint_lower_limits(
            self.robot_id, self.arm_joints, self.physics_client_id
        )

    @cached_property
    def joint_upper_limits(self) -> JointPositions:
        """Upper bound on the arm joint limits."""
        return get_joint_upper_limits(
            self.robot_id, self.arm_joints, self.physics_client_id
        )

    @property
    @abc.abstractmethod
    def open_fingers(self) -> float:
        """The value at which the finger joints should be open."""
        raise NotImplementedError("Override me!")

    @property
    @abc.abstractmethod
    def closed_fingers(self) -> float:
        """The value at which the finger joints should be closed."""
        raise NotImplementedError("Override me!")

    def get_joints(self) -> JointPositions:
        """Get the joint positions from the current PyBullet state."""
        return get_joint_positions(
            self.robot_id, self.arm_joints, self.physics_client_id
        )

    def set_joints(self, joint_positions: JointPositions) -> None:
        """Directly set the joint positions.

        Outside of resetting to an initial state, this should not be
        used with the robot that uses stepSimulation(); it should only
        be used for motion planning, collision checks, etc., in a robot
        that does not maintain state.
        """
        assert len(joint_positions) == len(self.arm_joints)
        for joint_id, joint_val in zip(self.arm_joints, joint_positions):
            p.resetJointState(
                self.robot_id,
                joint_id,
                targetValue=joint_val,
                targetVelocity=0,
                physicsClientId=self.physics_client_id,
            )

    def get_end_effector_pose(self) -> Pose:
        """Get the robot end-effector pose based on the current PyBullet
        state."""
        ee_link_state = get_link_state(
            self.robot_id,
            self.end_effector_id,
            physics_client_id=self.physics_client_id,
        )
        return Pose(
            ee_link_state.worldLinkFramePosition,
            ee_link_state.worldLinkFrameOrientation,
        )

    def get_finger_state(self) -> float:
        """Get the state of the gripper fingers."""
        return p.getJointState(
            self.robot_id,
            self.left_finger_id,
            physicsClientId=self.physics_client_id,
        )[0]

    def set_motors(self, joint_positions: JointPositions) -> None:
        """Update the motors to move toward the given joint positions."""
        assert len(joint_positions) == len(self.arm_joints)

        # Set arm joint motors.
        if self._control_mode == "position":
            p.setJointMotorControlArray(
                bodyUniqueId=self.robot_id,
                jointIndices=self.arm_joints,
                controlMode=p.POSITION_CONTROL,
                targetPositions=joint_positions,
                physicsClientId=self.physics_client_id,
            )
        elif self._control_mode == "reset":
            self.set_joints(joint_positions)
        else:
            raise NotImplementedError(
                "Unrecognized pybullet_control_mode: " f"{self._control_mode }"
            )

    def go_home(self) -> None:
        """Move the robot to its home end-effector pose."""
        self.set_motors(self.default_home_joint_positions)

    def forward_kinematics(self, joint_positions: JointPositions) -> Pose:
        """Compute the end effector pose that would result if the robot arm
        joint positions was equal to the input joint_positions.

        WARNING: This method will make use of resetJointState(), and so it
        should NOT be used during simulation.
        """
        self.set_joints(joint_positions)
        ee_link_state = get_link_state(
            self.robot_id,
            self.end_effector_id,
            physics_client_id=self.physics_client_id,
        )
        position = ee_link_state.worldLinkFramePosition
        orientation = ee_link_state.worldLinkFrameOrientation
        return Pose(position, orientation)

    def _validate_joints_state(
        self, joint_positions: JointPositions, target_pose: Pose, validation_atol: float
    ) -> None:
        """Validate that the given joint positions matches the target pose.

        This method should NOT be used during simulation mode as it
        resets the joint states.
        """
        # Store current joint positions so we can reset
        initial_joint_states = self.get_joints()

        # Set joint states, forward kinematics to determine EE position
        self.set_joints(joint_positions)
        ee_pos = get_link_state(
            self.robot_id,
            self.end_effector_id,
            physics_client_id=self.physics_client_id,
        ).worldLinkFramePosition
        target_pos = target_pose.position
        pos_is_close = np.allclose(ee_pos, target_pos, atol=validation_atol)

        # Reset joint positions before returning/raising error
        self.set_joints(initial_joint_states)

        if not pos_is_close:
            raise ValueError(
                f"Joint states do not match target pose {target_pos} " f"from {ee_pos}"
            )

    @classmethod
    def ikfast_info(cls) -> Optional[IKFastInfo]:
        """IKFastInfo for this robot.

        If this is specified, then IK will use IKFast.
        """
        return None

    def _ikfast_inverse_kinematics(self, end_effector_pose: Pose) -> JointPositions:
        """IK using IKFast.

        Returns the joint positions.
        """
        ik_solutions = ikfast_closest_inverse_kinematics(
            self,
            world_from_target=end_effector_pose,
        )
        if not ik_solutions:
            raise InverseKinematicsError(
                f"No IK solution found for target pose {end_effector_pose} "
                "using IKFast"
            )

        # Use first solution as it is closest to current joint state
        joint_positions = ik_solutions[0]

        # Add fingers to state
        final_joint_state = list(joint_positions)
        first_finger_idx, second_finger_idx = sorted(
            [self.left_finger_joint_idx, self.right_finger_joint_idx]
        )
        final_joint_state.insert(first_finger_idx, self.open_fingers)
        final_joint_state.insert(second_finger_idx, self.open_fingers)

        return final_joint_state

    def inverse_kinematics(
        self,
        end_effector_pose: Pose,
        validate: bool,
        set_joints: bool = True,
        validation_atol: float = 1e-3,
    ) -> JointPositions:
        """Compute joint positions from a target end effector position, based
        on the robot's current joint positions. Uses IKFast if the robot has
        IKFast info specified.

        The robot's joint state is updated to the IK result. For convenience,
        the new joint positions are also returned.

        If set_joints is True, set the joints after running IK. This is
        recommended when using IKFast because IK is meant to be run
        sequentially from nearby states, since it is very sensitive to
        initialization.

        If validate is True, we guarantee that the returned joint positions
        would result in end_effector_pose if run through
        forward_kinematics.

        WARNING: if validate is True, physics may be overridden, and so it
        should not be used within simulation.
        """
        if self.ikfast_info():
            joint_positions = self._ikfast_inverse_kinematics(end_effector_pose)
            if validate:
                try:
                    self._validate_joints_state(
                        joint_positions, end_effector_pose, validation_atol
                    )
                except ValueError as e:
                    raise InverseKinematicsError(e)

        else:
            joint_positions = pybullet_inverse_kinematics(
                self.robot_id,
                self.end_effector_id,
                end_effector_pose.position,
                end_effector_pose.orientation,
                self.arm_joints,
                physics_client_id=self.physics_client_id,
                validate=validate,
            )

        if set_joints:
            self.set_joints(joint_positions)

        return joint_positions
