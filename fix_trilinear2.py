with open("backend/src/spatial/aim.py", "r") as f:
    text = f.read()

old_aim = """        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))"""

new_aim = """        offset_pan, offset_tilt = getattr(self, "center_offset", {}).get(fixture.id, (0, 0))

        dist = ((x - 0.49)**2 + (y - 0.52)**2 + (z - 0.15)**2) ** 0.5
        weight = max(0, 1 - (dist / 1.0)) # linear falloff or just fixed if close enough?
        
        pan += offset_pan * weight
        tilt += offset_tilt * weight

        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))"""

# find all and replace the final one that is in TrilinearInterpolationStrategy
text = text.replace(old_aim, new_aim, 1)

with open("backend/src/spatial/aim.py", "w") as f:
    f.write(text)

