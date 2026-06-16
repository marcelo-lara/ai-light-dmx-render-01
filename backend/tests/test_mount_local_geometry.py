from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spatial.aim import HybridPanTiltStrategy, geometry_angles


class Fixture:
    def __init__(self) -> None:
        self.id = "mini_beam_prism_r"
        self.location = {"x": 0.985, "y": 0.2, "z": 0.8}
        self.mount = "wall_right"
        self.fixture_type = "moving_head"


class LeftFixture:
    def __init__(self) -> None:
        self.id = "mini_beam_prism_l"
        self.location = {"x": 0.015, "y": 0.2, "z": 0.8}
        self.mount = "wall_left"
        self.fixture_type = "moving_head"


class BackFixture:
    def __init__(self) -> None:
        self.id = "head_el150"
        self.location = {"x": 0.5, "y": 0.015, "z": 0.8}
        self.mount = "wall_back"
        self.fixture_type = "moving_head"


def _load_ref_pois() -> list[dict[str, object]]:
    ref_coordinates_file = Path(__file__).resolve().parent.parent / "data" / "ref_coordinates.json"
    with ref_coordinates_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_wall_right_tilt_is_invariant_along_right_edge() -> None:
    fixture_location = {"x": 0.985, "y": 0.2, "z": 0.8}

    _, tilt_back = geometry_angles(
        fixture_location,
        {"x": 1.0, "y": 0.0, "z": 0.0},
        "wall_right",
    )
    _, tilt_front = geometry_angles(
        fixture_location,
        {"x": 1.0, "y": 1.0, "z": 0.0},
        "wall_right",
    )

    assert tilt_front == pytest.approx(tilt_back)


def test_wall_left_tilt_is_invariant_along_left_edge() -> None:
    fixture_location = {"x": 0.015, "y": 0.2, "z": 0.8}

    _, tilt_back = geometry_angles(
        fixture_location,
        {"x": 0.0, "y": 0.0, "z": 0.0},
        "wall_left",
    )
    _, tilt_front = geometry_angles(
        fixture_location,
        {"x": 0.0, "y": 1.0, "z": 0.0},
        "wall_left",
    )

    assert tilt_front == pytest.approx(tilt_back)


def test_wall_back_tilt_is_invariant_along_back_edge() -> None:
    fixture_location = {"x": 0.5, "y": 0.015, "z": 0.8}

    _, tilt_left = geometry_angles(
        fixture_location,
        {"x": 0.0, "y": 0.0, "z": 0.0},
        "wall_back",
    )
    _, tilt_right = geometry_angles(
        fixture_location,
        {"x": 1.0, "y": 0.0, "z": 0.0},
        "wall_back",
    )

    assert tilt_right == pytest.approx(tilt_left)


def test_hybrid_strategy_keeps_right_edge_tilt_constant() -> None:
    fixture = Fixture()
    strategy = HybridPanTiltStrategy()

    strategy.calibrate(fixture, _load_ref_pois())

    _, tilt_back = strategy.aim_to_dmx(fixture, {"x": 1.0, "y": 0.0, "z": 0.0})
    _, tilt_front = strategy.aim_to_dmx(fixture, {"x": 1.0, "y": 1.0, "z": 0.0})

    assert tilt_front == tilt_back


def test_hybrid_strategy_keeps_left_edge_tilt_constant() -> None:
    fixture = LeftFixture()
    strategy = HybridPanTiltStrategy()

    strategy.calibrate(fixture, _load_ref_pois())

    _, tilt_back = strategy.aim_to_dmx(fixture, {"x": 0.0, "y": 0.0, "z": 0.0})
    _, tilt_front = strategy.aim_to_dmx(fixture, {"x": 0.0, "y": 1.0, "z": 0.0})

    assert tilt_front == tilt_back


def test_hybrid_strategy_keeps_back_edge_tilt_constant() -> None:
    fixture = BackFixture()
    strategy = HybridPanTiltStrategy()

    strategy.calibrate(fixture, _load_ref_pois())

    _, tilt_left = strategy.aim_to_dmx(fixture, {"x": 0.0, "y": 0.0, "z": 0.0})
    _, tilt_right = strategy.aim_to_dmx(fixture, {"x": 1.0, "y": 0.0, "z": 0.0})

    assert tilt_right == tilt_left