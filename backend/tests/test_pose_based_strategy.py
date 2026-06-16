from __future__ import annotations

import math

import pytest

from src.spatial.aim import PoseBasedStrategy, TrilinearInterpolationStrategy
from src.spatial.origin_calibration import world_direction_to_dmx


class Fixture:
    def __init__(self, fixture_id: str, location: dict[str, float]) -> None:
        self.id = fixture_id
        self.location = location
        self.mount = None
        self.orientation = None
        self.fixture_type = "moving_head"


def _fixture_target(
    origin: tuple[float, float, float],
    point: tuple[float, float, float],
    *,
    yaw_radians: float,
    pitch_radians: float,
    roll_radians: float,
    pan_sign: int,
    tilt_reversed: bool,
) -> dict[str, int]:
    delta = (
        point[0] - origin[0],
        point[1] - origin[1],
        point[2] - origin[2],
    )
    magnitude = math.sqrt(sum(axis * axis for axis in delta))
    pan, tilt = world_direction_to_dmx(
        tuple(axis / magnitude for axis in delta),
        yaw_radians=yaw_radians,
        pitch_radians=pitch_radians,
        roll_radians=roll_radians,
        pan_sign=pan_sign,
        tilt_reversed=tilt_reversed,
    )
    return {"pan": pan, "tilt": tilt}


def test_pose_based_strategy_aims_from_calibrated_orientation_pose() -> None:
    known_origin = (0.12, 0.15, 0.18)
    yaw_radians = 0.42
    pitch_radians = -0.27
    roll_radians = 0.18
    pan_sign = -1
    tilt_reversed = False
    fixture = Fixture("fixture_under_test", {"x": 0.3, "y": 0.3, "z": 0.3})
    ref_points = [
        (0.62, 0.34, 0.25),
        (0.85, 0.48, 0.42),
        (0.58, 0.88, 0.71),
        (0.94, 0.92, 0.96),
        (0.53, 0.41, 1.12),
    ]
    ref_pois = [
        {
            "id": f"ref_{index}",
            "location": {"x": point[0], "y": point[1], "z": point[2]},
            "fixtures": {
                fixture.id: _fixture_target(
                    known_origin,
                    point,
                    yaw_radians=yaw_radians,
                    pitch_radians=pitch_radians,
                    roll_radians=roll_radians,
                    pan_sign=pan_sign,
                    tilt_reversed=tilt_reversed,
                )
            },
        }
        for index, point in enumerate(ref_points)
    ]

    strategy = PoseBasedStrategy(fallback=TrilinearInterpolationStrategy())
    strategy.calibrate(fixture, ref_pois)

    target = {"x": 0.77, "y": 0.61, "z": 0.66}
    pan, tilt = strategy.aim_to_dmx(fixture, target)

    expected = _fixture_target(
        known_origin,
        (target["x"], target["y"], target["z"]),
        yaw_radians=yaw_radians,
        pitch_radians=pitch_radians,
        roll_radians=roll_radians,
        pan_sign=pan_sign,
        tilt_reversed=tilt_reversed,
    )

    assert fixture.location == pytest.approx(
        {"x": known_origin[0], "y": known_origin[1], "z": known_origin[2]},
        abs=2e-4,
    )
    assert pan == pytest.approx(expected["pan"], abs=2)
    assert tilt == pytest.approx(expected["tilt"], abs=2)


def test_pose_based_strategy_uses_saved_orientation_without_recalibrating() -> None:
    known_origin = (0.12, 0.15, 0.18)
    yaw_radians = 0.42
    pitch_radians = -0.27
    roll_radians = 0.18
    pan_sign = -1
    tilt_reversed = False
    fixture = Fixture(
        "fixture_under_test",
        {"x": known_origin[0], "y": known_origin[1], "z": known_origin[2]},
    )
    fixture.orientation = {
        "yaw": yaw_radians,
        "pitch": pitch_radians,
        "roll": roll_radians,
        "pan_sign": pan_sign,
        "tilt_reversed": tilt_reversed,
    }

    strategy = PoseBasedStrategy(fallback=TrilinearInterpolationStrategy())
    strategy.calibrate(fixture, [])

    target = {"x": 0.77, "y": 0.61, "z": 0.66}
    pan, tilt = strategy.aim_to_dmx(fixture, target)

    expected = _fixture_target(
        known_origin,
        (target["x"], target["y"], target["z"]),
        yaw_radians=yaw_radians,
        pitch_radians=pitch_radians,
        roll_radians=roll_radians,
        pan_sign=pan_sign,
        tilt_reversed=tilt_reversed,
    )

    assert pan == pytest.approx(expected["pan"], abs=1)
    assert tilt == pytest.approx(expected["tilt"], abs=1)