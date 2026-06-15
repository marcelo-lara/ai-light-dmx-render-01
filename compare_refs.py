import json

with open("backend/data/ref_coordinates.json") as f:
    pois = json.load(f)

print(f"{'POI ID':<15} | {'L PAN':<7} | {'L TILT':<7} | {'R PAN':<7} | {'R TILT':<7}")
print("-" * 55)

for p in pois:
    if str(p.get("id")).startswith("ref_"):
        l_fix = p.get("fixtures", {}).get("mini_beam_prism_l", {})
        r_fix = p.get("fixtures", {}).get("mini_beam_prism_r", {})
        
        l_pan = l_fix.get("pan", "N/A")
        l_tilt = l_fix.get("tilt", "N/A")
        
        r_pan = r_fix.get("pan", "N/A")
        r_tilt = r_fix.get("tilt", "N/A")
        
        print(f"{p['id']:<15} | {str(l_pan):<7} | {str(l_tilt):<7} | {str(r_pan):<7} | {str(r_tilt):<7}")

