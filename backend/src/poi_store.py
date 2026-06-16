from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.config import POIS_JSON, REF_COORDINATES_JSON, VIRTUAL_CENTER_MEASUREMENTS_JSON


def _load_poi_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of POIs in {path}")
    return data


def load_pois(path: Path = POIS_JSON) -> list[dict[str, Any]]:
    return _load_poi_file(path)


def load_virtual_center_measurements(
    path: Path = VIRTUAL_CENTER_MEASUREMENTS_JSON,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _load_poi_file(path)


def _virtual_measurements_by_id(
    measurements: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not measurements:
        return {}
    return {
        str(measurement.get("id", "")): measurement
        for measurement in measurements
        if isinstance(measurement, Mapping)
    }


def build_virtual_reference_pois(
    measurements: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    measured_by_id = _virtual_measurements_by_id(measurements)
    refs = [
        {
            "id": "virtual_left_wall_center",
            "name": "Virtual left wall center",
            "location": {"x": 0.0, "y": 0.5, "z": 0.5},
            "fixtures": {},
            "virtual": True,
        },
        {
            "id": "virtual_right_wall_center",
            "name": "Virtual right wall center",
            "location": {"x": 1.0, "y": 0.5, "z": 0.5},
            "fixtures": {},
            "virtual": True,
        },
        {
            "id": "virtual_back_wall_center",
            "name": "Virtual back wall center",
            "location": {"x": 0.5, "y": 0.0, "z": 0.5},
            "fixtures": {},
            "virtual": True,
        },
        {
            "id": "virtual_front_wall_center",
            "name": "Virtual front wall center",
            "location": {"x": 0.5, "y": 1.0, "z": 0.5},
            "fixtures": {},
            "virtual": True,
        },
        {
            "id": "virtual_floor_center",
            "name": "Virtual floor center",
            "location": {"x": 0.5, "y": 0.5, "z": 0.0},
            "fixtures": {},
            "virtual": True,
        },
        {
            "id": "virtual_ceiling_center",
            "name": "Virtual ceiling center",
            "location": {"x": 0.5, "y": 0.5, "z": 1.0},
            "fixtures": {},
            "virtual": True,
        },
    ]

    merged = []
    for ref in refs:
        measured = measured_by_id.get(ref["id"], {})
        merged.append(
            {
                **ref,
                "fixtures": dict(measured.get("fixtures", {})),
            }
        )
    return merged


def load_runtime_pois(path: Path = POIS_JSON) -> list[dict[str, Any]]:
    return [
        *load_pois(path),
        *build_virtual_reference_pois(load_virtual_center_measurements()),
    ]


def split_runtime_pois(path: Path = POIS_JSON) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    authored = load_pois(path)
    virtual = build_virtual_reference_pois(load_virtual_center_measurements())
    return authored, virtual


def load_ref_coordinates(path: Path = REF_COORDINATES_JSON) -> list[dict[str, Any]]:
    return _load_poi_file(path)


def load_all_pois(
    pois_path: Path = POIS_JSON,
    ref_coordinates_path: Path = REF_COORDINATES_JSON,
) -> list[dict[str, Any]]:
    return [*load_pois(pois_path), *load_ref_coordinates(ref_coordinates_path)]


def persist_pois(pois: list[dict[str, Any]], path: Path = POIS_JSON) -> None:
    path.write_text(json.dumps(pois, indent=4) + "\n", encoding="utf-8")


def persist_ref_coordinates(
    ref_coordinates: list[dict[str, Any]],
    path: Path = REF_COORDINATES_JSON,
) -> None:
    path.write_text(json.dumps(ref_coordinates, indent=4) + "\n", encoding="utf-8")


def persist_virtual_center_measurements(
    measurements: list[dict[str, Any]],
    path: Path = VIRTUAL_CENTER_MEASUREMENTS_JSON,
) -> None:
    path.write_text(json.dumps(measurements, indent=4) + "\n", encoding="utf-8")