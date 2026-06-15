from src.spatial.aim import geometry_angles, build_fixture_aim_calibration, is_ref_poi_id, _predict_axis
import json

with open("/app/fixtures/fixtures.json") as f:
    fixtures = json.load(f)
with open("/app/fixtures/pois.json") as p:
    pois = json.load(p)

class Fixture: pass
r_fix = next(f for f in fixtures if f["id"] == "mini_beam_prism_r")
fix = Fixture()
fix.id = r_fix["id"]
fix.location = r_fix["location"]
fix.mount = r_fix["mount"]

print("ref_0_0_0:")
print("Angle:", geometry_angles(fix.location, {"x":0, "y":0, "z":0}, fix.mount))
print("DMX:", next(p for p in pois if p["id"] == "ref_0_0_0")["fixtures"]["mini_beam_prism_r"])

print("\nref_0_1_0:")
print("Angle:", geometry_angles(fix.location, {"x":0, "y":1, "z":0}, fix.mount))
print("DMX:", next(p for p in pois if p["id"] == "ref_0_1_0")["fixtures"]["mini_beam_prism_r"])


print("\nref_1_0_0:")
print("Angle:", geometry_angles(fix.location, {"x":1, "y":0, "z":0}, fix.mount))
print("DMX:", next(p for p in pois if p["id"] == "ref_1_0_0")["fixtures"]["mini_beam_prism_r"])

print("\nref_1_1_0:")
print("Angle:", geometry_angles(fix.location, {"x":1, "y":1, "z":0}, fix.mount))
print("DMX:", next(p for p in pois if p["id"] == "ref_1_1_0")["fixtures"]["mini_beam_prism_r"])
