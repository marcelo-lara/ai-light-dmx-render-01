import json
from src.poi_store import load_ref_coordinates
from src.spatial.aim import InverseKinematicsStrategy, is_ref_poi_id

with open("/app/fixtures/fixtures.json") as f:
    fixtures = json.load(f)
pois = load_ref_coordinates()
    
class Fixture: pass
r_fix = None
for f in fixtures:
    if f["id"] == "mini_beam_prism_r":
        r_fix = Fixture()
        r_fix.id = f["id"]
        r_fix.location = f["location"]
        r_fix.mount = f["mount"]
        r_fix.fixture_type = "moving_head"
        break

# Filter out the bad pois for calibration
good_ref_pois = []
for p in pois:
    if is_ref_poi_id(p.get("id", "")):
        if p["id"] not in ["ref_0_1_0", "ref_0_1_1", "guest_desk"]:
            good_ref_pois.append(p)

S = InverseKinematicsStrategy()
S.calibrate(r_fix, good_ref_pois)

target_loc = {"x": 0, "y": 1, "z": 0}
calc_pan, calc_tilt = S.aim_to_dmx(r_fix, target_loc)
print(f"Predicted ref_0_1_0: Pan {calc_pan}, Tilt {calc_tilt}")

target_loc_ceil = {"x": 0, "y": 1, "z": 1}
calc_pan_c, calc_tilt_c = S.aim_to_dmx(r_fix, target_loc_ceil)
print(f"Predicted ref_0_1_1: Pan {calc_pan_c}, Tilt {calc_tilt_c}")
