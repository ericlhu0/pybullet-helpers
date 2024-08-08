"""Franka Emika Panda robot."""

from pathlib import Path
from typing import Optional

from pybullet_helpers.ikfast import IKFastInfo
from pybullet_helpers.joint import JointPositions
from pybullet_helpers.robots.single_arm import SingleArmTwoFingerGripperPyBulletRobot
from pybullet_helpers.utils import get_assets_path


class PandaPyBulletRobot(SingleArmTwoFingerGripperPyBulletRobot):
    """Franka Emika Panda which we assume is fixed on some base."""

    @classmethod
    def get_name(cls) -> str:
        return "panda"

    @classmethod
    def urdf_path(cls) -> Path:
        dir_path = get_assets_path() / "urdf"
        return dir_path / "franka_description" / "robots" / "panda_arm_hand.urdf"

    @property
    def default_home_joint_positions(self) -> JointPositions:
        return [
            -1.6760817784086874,
            -0.8633617886115512,
            1.0820023618960484,
            -1.7862427129376002,
            0.7563762599673787,
            1.3595324116603988,
            1.7604148617061273,
            0.04,
            0.04,
        ]

    @property
    def end_effector_name(self) -> str:
        """The tool joint is offset from the final arm joint such that it
        represents the point in the center of the two fingertips of the gripper
        (fingertips, NOT the entire fingers).

        This differs from the "panda_hand" joint which represents the
        center of the gripper itself including parts of the gripper
        body.
        """
        return "tool_joint"

    @property
    def tool_link_name(self) -> str:
        return "tool_link"

    @property
    def left_finger_joint_name(self) -> str:
        return "panda_finger_joint1"

    @property
    def right_finger_joint_name(self) -> str:
        return "panda_finger_joint2"

    @property
    def open_fingers(self) -> float:
        return 0.04

    @property
    def closed_fingers(self) -> float:
        return 0.03

    @classmethod
    def ikfast_info(cls) -> Optional[IKFastInfo]:
        return IKFastInfo(
            module_dir="panda_arm",
            module_name="ikfast_panda_arm",
            base_link="panda_link0",
            ee_link="panda_link8",
            free_joints=["panda_joint7"],
        )
