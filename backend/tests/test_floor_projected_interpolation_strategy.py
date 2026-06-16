from __future__ import annotations

from src.spatial.aim import FloorProjectedInterpolationStrategy


class Fixture:
    def __init__(self, fixture_id: str) -> None:
        self.id = fixture_id
        self.fixture_type = "moving_head"


def test_floor_projected_interpolation_matches_exact_anchor() -> None:
    fixture = Fixture("fixture_under_test")
    strategy = FloorProjectedInterpolationStrategy()
    calibration_pois = [
        {
            "id": "floor_a",
            "location": {"x": 0.25, "y": 0.75, "z": 0.3},
            "fixtures": {fixture.id: {"pan": 1234, "tilt": 5678}},
        }
    ]

    strategy.calibrate(fixture, calibration_pois)
    pan, tilt = strategy.aim_to_dmx(fixture, {"x": 0.25, "y": 0.75, "z": 0.0})

    assert pan == 1234
    assert tilt == 5678