import json
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.poi_store import load_all_pois
from src.spatial.aim import (
    TrilinearInterpolationStrategy,
    InverseKinematicsStrategy,
    is_ref_poi_id,
)

FIXTURES_FILE = Path("/app/fixtures/fixtures.json")
POIS_FILE = Path("/app/data/pois.json")
REF_COORDINATES_FILE = Path("/app/data/ref_coordinates.json")

# Fallback values if not found (e.g. running directly on host)
if not FIXTURES_FILE.exists():
    repo_root = Path(__file__).parent.parent.parent
    FIXTURES_FILE = repo_root / "data" / "fixtures" / "fixtures.json"
    POIS_FILE = repo_root / "backend" / "data" / "pois.json"
    REF_COORDINATES_FILE = repo_root / "backend" / "data" / "ref_coordinates.json"

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# Load data once
fixtures_data = load_json(FIXTURES_FILE)
pois_data = load_all_pois(POIS_FILE, REF_COORDINATES_FILE)

@dataclass
class Fixture:
    id: str
    location: dict

fixtures_map = {
    f["id"]: Fixture(id=f["id"], location=f["location"])
    for f in fixtures_data
}

ref_pois = [p for p in pois_data if is_ref_poi_id(p.get("id", ""))]
val_pois = [p for p in pois_data if not is_ref_poi_id(p.get("id", ""))]

strategies = [
    TrilinearInterpolationStrategy(),
    InverseKinematicsStrategy(),
]

MAX_TOLERANCE = 1000

test_cases = []
for strategy in strategies:
    for poi in val_pois:
        for fixture_id, target in poi.get("fixtures", {}).items():
            if fixture_id in fixtures_map:
                test_cases.append((strategy, poi, fixture_id, target))

def test_case_id(val):
    if hasattr(val, "name"):
        return val.name
    elif isinstance(val, dict) and "id" in val:
        return val["id"]
    elif isinstance(val, str):
        return val
    return ""

@pytest.mark.parametrize("strategy, poi, fixture_id, expected_dmx", test_cases, ids=test_case_id)
def test_evaluation(strategy, poi, fixture_id, expected_dmx):
    fixture = fixtures_map[fixture_id]
    
    # 1. Calibrate (usually this might be done once per fixture/strategy, but for benchmark it works here)
    strategy.calibrate(fixture, ref_pois)
    
    # 2. Evaluate
    calc_pan, calc_tilt = strategy.aim_to_dmx(fixture, poi["location"])
    
    pan_diff = abs(calc_pan - expected_dmx["pan"])
    tilt_diff = abs(calc_tilt - expected_dmx["tilt"])
    
    assert pan_diff <= MAX_TOLERANCE, f"Pan deviation too high: {pan_diff} > {MAX_TOLERANCE}"
    assert tilt_diff <= MAX_TOLERANCE, f"Tilt deviation too high: {tilt_diff} > {MAX_TOLERANCE}"

