import re

with open("backend/src/spatial/aim.py", "r") as f:
    text = f.read()

# Modify Trilinear calibrate
old_cal = '''        corners = {}
        for poi in ref_pois:
            loc = poi.get("location", {})
            x, y, z = round(loc.get("x", 0)), round(loc.get("y", 0)), round(loc.get("z", 0))
            if "fixtures" in poi and fixture.id in poi["fixtures"]:
                target = poi["fixtures"][fixture.id]
                corners[(x, y, z)] = (target["pan"], target["tilt"])'''

new_cal = '''        corners = {}
        self.center_offset = getattr(self, "center_offset", {})
        table_center_poi = None
        for poi in ref_pois:
            if poi.get("id") == "table_center":
                table_center_poi = poi
                continue
            loc = poi.get("location", {})
            x, y, z = round(loc.get("x", 0)), round(loc.get("y", 0)), round(loc.get("z", 0))
            if "fixtures" in poi and fixture.id in poi["fixtures"]:
                target = poi["fixtures"][fixture.id]
                corners[(x, y, z)] = (target["pan"], target["tilt"])'''

text = text.replace(old_cal, new_cal)

old_fill = '''        self.corners[fixture.id] = corners'''
new_fill = '''        self.corners[fixture.id] = corners
        
        if table_center_poi and "fixtures" in table_center_poi and fixture.id in table_center_poi["fixtures"]:
            target = table_center_poi["fixtures"][fixture.id]
            calc_pan, calc_tilt = self.aim_to_dmx(fixture, table_center_poi.get("location", {}))
            self.center_offset[fixture.id] = (
                target["pan"] - calc_pan,
                target["tilt"] - calc_tilt
            )
'''
text = text.replace(old_fill, new_fill)

old_aim = '''        def interpolate(c000, c100, c010, c110, c001, c101, c011, c111):
            c00 = c000 * (1 - x) + c100 * x
            c01 = c001 * (1 - x) + c101 * x
            c10 = c010 * (1 - x) + c110 * x
            c11 = c011 * (1 - x) + c111 * x

            c0 = c00 * (1 - y) + c10 * y
            c1 = c01 * (1 - y) + c11 * y

            return c0 * (1 - z) + c1 * z

        pan = interpolate(
            corners.get((0,0,0),(32768,32768))[0], corners.get((1,0,0),(32768,32768))[0],
            corners.get((0,1,0),(32768,32768))[0], corners.get((1,1,0),(32768,32768))[0],
            corners.get((0,0,1),(32768,32768))[0], corners.get((1,0,1),(32768,32768))[0],
            corners.get((0,1,1),(32768,32768))[0], corners.get((1,1,1),(32768,32768))[0]
        )
        tilt = interpolate(
            corners.get((0,0,0),(32768,32768))[1], corners.get((1,0,0),(32768,32768))[1],
            corners.get((0,1,0),(32768,32768))[1], corners.get((1,1,0),(32768,32768))[1],
            corners.get((0,0,1),(32768,32768))[1], corners.get((1,0,1),(32768,32768))[1],
            corners.get((0,1,1),(32768,32768))[1], corners.get((1,1,1),(32768,32768))[1]
        )

        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))'''

new_aim = old_aim.replace(
'''return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))''',
'''offset_pan, offset_tilt = getattr(self, "center_offset", {}).get(fixture.id, (0, 0))

        # Add a localized Gaussian/distance-based fade, or just literal linear shift? 
        # Actually, let's just shift explicitly with distance falloff relative to the center 
        # to ensure it converges perfectly there but doesn't ruin the extreme corners.
        dist = ((x - 0.49)**2 + (y - 0.52)**2 + (z - 0.15)**2) ** 0.5
        weight = max(0, 1 - (dist / 1.0))

        pan += offset_pan * weight
        tilt += offset_tilt * weight

        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))'''
)
text = text.replace(old_aim, new_aim)

with open("backend/src/spatial/aim.py", "w") as f:
    f.write(text)
