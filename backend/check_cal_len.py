from src.spatial.aim import *
from src.poi_store import load_ref_coordinates
import json
with open("/app/fixtures/fixtures.json") as f:
    fixtures = json.load(f)
ref_pois = load_ref_coordinates()
class _Mock: pass

for f in fixtures:
    if f.get("fixture", "").startswith("fixture.moving_head"):
        fix = _Mock()
        fix.id = f["id"]
        fix.fixture_type = "moving_head"
        fix.mount = f.get("mount")
        fix.location = f.get("location")

        
        S = TrilinearInterpolationStrategy()
        S.calibrate(fix, ref_pois)
        print(f"Trilinear {fix.id}: corners len = {len(S.corners.get(fix.id, {}))}")
        
        S2 = InverseKinematicsStrategy()
        S2.calibrate(fix, ref_pois)
        print(f"IK {fix.id}: has cal = {fix.id in S2.calibrations}")
