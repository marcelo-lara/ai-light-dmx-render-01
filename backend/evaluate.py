import json
import math
from pathlib import Path

from src.poi_store import load_all_pois
from src.spatial.aim import (
    TrilinearInterpolationStrategy,
    InverseKinematicsStrategy,
    is_ref_poi_id,
)

FIXTURES_FILE = Path("/app/fixtures/fixtures.json")
POIS_FILE = Path("/app/data/pois.json")
REF_COORDINATES_FILE = Path("/app/data/ref_coordinates.json")
if not FIXTURES_FILE.exists():
    FIXTURES_FILE = Path("data/fixtures/fixtures.json")
    POIS_FILE = Path("backend/data/pois.json")
    REF_COORDINATES_FILE = Path("backend/data/ref_coordinates.json")

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

fixtures_data = load_json(FIXTURES_FILE)
pois_data = load_all_pois(POIS_FILE, REF_COORDINATES_FILE)

class Fixture:
    pass

fixtures_map = {}
for f in fixtures_data:
    fix = Fixture()
    fix.id = f["id"]
    fix.fixture_type = "moving_head" if f.get("fixture", "").startswith("fixture.moving_head") else "other"
    fix.location = f.get("location")
    fix.mount = f.get("mount")
    fixtures_map[fix.id] = fix

ref_pois = [p for p in pois_data if is_ref_poi_id(p.get("id", ""))]
# We want to re-evaluate table_center as validation to prove convergence
val_pois = [p for p in pois_data if not is_ref_poi_id(p.get("id", "")) or p.get("id") == "table_center"]

strategies = [
    TrilinearInterpolationStrategy(),
    InverseKinematicsStrategy(),
]

results = []

for strategy in strategies:
    pan_diffs = []
    tilt_diffs = []
    
    # 1. Calibrate (per fixture)
    for fixture in fixtures_map.values():
        if fixture.fixture_type == "moving_head":
            strategy.calibrate(fixture, ref_pois)
        
    # 2. Evaluate
    poi_results = []
    
    for poi in val_pois:
        for fixture_id, target in poi.get("fixtures", {}).items():
            if fixture_id in fixtures_map and fixtures_map[fixture_id].fixture_type == "moving_head":
                fixture = fixtures_map[fixture_id]
                calc_pan, calc_tilt = strategy.aim_to_dmx(fixture, poi["location"])
                pan_diff = abs(calc_pan - target["pan"])
                tilt_diff = abs(calc_tilt - target["tilt"])
                pan_diffs.append(pan_diff)
                tilt_diffs.append(tilt_diff)
                poi_results.append({
                    "poi": poi.get("id", "unknown"),
                    "fixture": fixture_id,
                    "pan_diff": pan_diff,
                    "tilt_diff": tilt_diff,
                })
                
    avg_pan_error = sum(pan_diffs) / len(pan_diffs) if pan_diffs else 0
    avg_tilt_error = sum(tilt_diffs) / len(tilt_diffs) if tilt_diffs else 0
    results.append({
        "strategy": strategy.name,
        "avg_pan_error": avg_pan_error,
        "avg_tilt_error": avg_tilt_error,
        "details": poi_results,
    })

# Format to markdown
md = ["# XYZ-to-DMX Algorithm Benchmark Results\n"]
md.append("This document contains the validation results for different Pan/Tilt calculation strategies evaluated against manually-aimed ground-truth POIs.\n")

md.append("## Overall Performance (Mean Absolute Error)\n")
md.append("| Strategy | Avg Pan Error (ticks) | Avg Tilt Error (ticks) |")
md.append("|---|---|---|")
for res in results:
    md.append(f"| {res['strategy']} | {res['avg_pan_error']:.2f} | {res['avg_tilt_error']:.2f} |")

md.append("\n## Detailed POI Discrepancies\n")
md.append("Difference between algorithm calculation and mathematically stored Pan/Tilt ticks for each validation pair.\n")

for res in results:
    md.append(f"### {res['strategy']}")
    md.append("| POI ID | Fixture | Pan Diff | Tilt Diff |")
    md.append("|---|---|---|---|")
    for d in res['details']:
        md.append(f"| {d['poi']} | {d['fixture']} | {d['pan_diff']} | {d['tilt_diff']} |")
    md.append("\n")

print("\n".join(md))
