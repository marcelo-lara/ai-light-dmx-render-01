import json

with open("backend/data/ref_coordinates.json", "r") as f:
    pois = json.load(f)

for p in pois:
    if p["id"] == "ref_0_1_0":
        # Best estimate by mathematical IK projection
        p["fixtures"]["mini_beam_prism_r"]["pan"] = 56638
        p["fixtures"]["mini_beam_prism_r"]["tilt"] = 13477

with open("backend/data/ref_coordinates.json", "w") as f:
    json.dump(pois, f, indent=4)

