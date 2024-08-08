"""PyBullet helpers for cameras and rendering."""

import pybullet as p

from pybullet_helpers.geometry import Pose3D


def create_gui_connection(
    camera_distance: float = 1.5,
    camera_yaw: float = 0,
    camera_pitch: float = -15,
    camera_target: Pose3D = (0, 0, 0.5),
    background_rgb: tuple[float, float, float] = (0, 0, 0),
    disable_preview_windows: bool = True,
) -> int:  # pragma: no cover
    """Creates a PyBullet GUI connection and initializes the camera.

    Returns the physics client ID for the connection.

    Not covered by unit tests because unit tests need to be headless.
    """
    physics_client_id = p.connect(
        p.GUI,
        options=(
            f"--background_color_red={background_rgb[0]} "
            f"--background_color_green={background_rgb[1]} "
            f"--background_color_blue={background_rgb[2]}"
        ),
    )
    # Disable the PyBullet GUI preview windows for faster rendering.
    if disable_preview_windows:
        p.configureDebugVisualizer(
            p.COV_ENABLE_GUI, False, physicsClientId=physics_client_id
        )
        p.configureDebugVisualizer(
            p.COV_ENABLE_RGB_BUFFER_PREVIEW, False, physicsClientId=physics_client_id
        )
        p.configureDebugVisualizer(
            p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, False, physicsClientId=physics_client_id
        )
        p.configureDebugVisualizer(
            p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW,
            False,
            physicsClientId=physics_client_id,
        )
    p.resetDebugVisualizerCamera(
        camera_distance,
        camera_yaw,
        camera_pitch,
        camera_target,
        physicsClientId=physics_client_id,
    )
    return physics_client_id
