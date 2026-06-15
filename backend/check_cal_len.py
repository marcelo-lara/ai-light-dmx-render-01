from src.spatial.aim import *
import json
with open("/app/fixtures/fixtures.json") as f:
    fixtures = json.load(f)
with open("/app/fixtures/pois.json") as p:
    pois = json.load(p)

ref_pois = [p for p in pois if is_ref_poi_id(p.get("id", ""))]
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
