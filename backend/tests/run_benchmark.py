import json
import math
from pathlib import Path
from dataclasses import dataclass
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
    repo_root = Path(__file__).parent.parent.parent
    FIXTURES_FILE = repo_root / "data" / "fixtures" / "fixtures.json"
    POIS_FILE = repo_root / "backend" / "data" / "pois.json"
    REF_COORDINATES_FILE = repo_root / "backend" / "data" / "ref_coordinates.json"

with FIXTURES_FILE.open("r", encoding="utf-8") as f:
    fixtures_data = json.load(f)
pois_data = load_all_pois(POIS_FILE, REF_COORDINATES_FILE)

@dataclass
class Fixture:
    id: str
    location: dict

fixtures_map = {f["id"]: Fixture(id=f["id"], location=f["location"]) for f in fixtures_data}

ref_pois = [p for p in pois_data if is_ref_poi_id(p.get("id", ""))]
val_pois = [p for p in pois_data if not is_ref_poi_id(p.get("id", ""))]

strategies = [TrilinearInterpolationStrategy(), InverseKinematicsStrategy()]

results_md = "# Algorithm Benchmark Results\n\n"

for strategy in strategies:
    pan_diffs = []
    tilt_diffs = []
    for poi in val_pois:
        for fixture_id, target in poi.get("fixtures", {}).items():
            if fixture_id in fixtures_map:
                fixture = fixtures_map[fixture_id]
                strategy.calibrate(fixture, ref_pois)
                calc_pan, calc_tilt = strategy.aim_to_dmx(fixture, poi["location"])
                pan_diffs.append(abs(calc_pan - target["pan"]))
                tilt_diffs.append(abs(calc_tilt - target["tilt"]))
                
    avg_pan = sum(pan_diffs) / len(pan_diffs) if pan_diffs else 0
    avg_tilt = sum(tilt_diffs) / len(tilt_diffs) if tilt_diffs else 0
    
    results_md += f"## {strategy.name}\n"
    results_md += f"- **Average Pan Error**: {avg_pan:.2f} DMX ticks\n"
    results_md += f"- **Average Tilt Error**: {avg_tilt:.2f} DMX ticks\n\n"

with open("/app/docs_out.md", "w") as f:
    f.write(results_md)

print("Benchmark complete")
