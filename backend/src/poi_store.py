from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import POIS_JSON, REF_COORDINATES_JSON


def _load_poi_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of POIs in {path}")
    return data


def load_pois(path: Path = POIS_JSON) -> list[dict[str, Any]]:
    return _load_poi_file(path)


def load_ref_coordinates(path: Path = REF_COORDINATES_JSON) -> list[dict[str, Any]]:
    return _load_poi_file(path)


def load_all_pois(
    pois_path: Path = POIS_JSON,
    ref_coordinates_path: Path = REF_COORDINATES_JSON,
) -> list[dict[str, Any]]:
    return [*load_pois(pois_path), *load_ref_coordinates(ref_coordinates_path)]


def persist_pois(pois: list[dict[str, Any]], path: Path = POIS_JSON) -> None:
    path.write_text(json.dumps(pois, indent=4) + "\n", encoding="utf-8")