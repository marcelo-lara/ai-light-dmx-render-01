import json

with open("data/fixtures/pois.json") as f:
    pois = json.load(f)

print(f"{'POI ID':<15} | {'X':<4} | {'Y':<4} | {'Z':<4} | {'R PAN':<7} | {'R TILT':<7}")
print("-" * 55)

for p in pois:
    if not str(p.get("id")).startswith("ref_"):
        loc = p.get("location", {})
        r_fix = p.get("fixtures", {}).get("mini_beam_prism_r", {})
        
        r_pan = r_fix.get("pan", "N/A")
        r_tilt = r_fix.get("tilt", "N/A")
        
        print(f"{p['id']:<15} | {loc.get('x', '')} | {loc.get('y', '')} | {loc.get('z', '')} | {str(r_pan):<7} | {str(r_tilt):<7}")
