from __future__ import annotations

from src.poi_store import build_virtual_reference_pois


def test_build_virtual_reference_pois_returns_six_face_centers() -> None:
    virtual_refs = build_virtual_reference_pois()

    assert [poi["id"] for poi in virtual_refs] == [
        "virtual_left_wall_center",
        "virtual_right_wall_center",
        "virtual_back_wall_center",
        "virtual_front_wall_center",
        "virtual_floor_center",
        "virtual_ceiling_center",
    ]
    assert [poi["location"] for poi in virtual_refs] == [
        {"x": 0.0, "y": 0.5, "z": 0.5},
        {"x": 1.0, "y": 0.5, "z": 0.5},
        {"x": 0.5, "y": 0.0, "z": 0.5},
        {"x": 0.5, "y": 1.0, "z": 0.5},
        {"x": 0.5, "y": 0.5, "z": 0.0},
        {"x": 0.5, "y": 0.5, "z": 1.0},
    ]