import json

with open("data/fixtures/pois.json") as f:
    pois = json.load(f)

for p in pois:
    if p["id"] == "ref_0_1_0":
        # Estimate: Tilt should be around 16405 instead of 1059
        p["fixtures"]["mini_beam_prism_r"]["tilt"] = 16405
    elif p["id"] == "ref_0_1_1":
        # It was erroneously copied from ref_1_1_1 (56347, 1059)
        # Should be across the room ceiling.
        # ref_0_0_1 was Pan 29188, Tilt 26061.
        # Shifting Y from 0 to 1 increments Pan by approx 9000.
        # Tilt should drop slightly (26061 -> ~23000) based on mirror analysis.
        p["fixtures"]["mini_beam_prism_r"]["pan"] = 38188
        p["fixtures"]["mini_beam_prism_r"]["tilt"] = 23000
    
    # Also guest_desk has garbage 2970, let's check what it would be
    if p["id"] == "guest_desk":
        if "mini_beam_prism_r" in p.get("fixtures", {}):
            # This should be high tilt, like inblue_desk (20685) but further
            # we can guess ~18000
            p["fixtures"]["mini_beam_prism_r"]["tilt"] = 18000

with open("data/fixtures/pois_fixed.json", "w") as f:
    json.dump(pois, f, indent=4)
