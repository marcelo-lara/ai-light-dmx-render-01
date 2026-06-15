import sys

with open("backend/src/spatial/old_aim.py", "r") as f:
    old_aim_lines = f.readlines()

new_aim = []
exclude_functions = ["build_aim_calibrations", "aim_to_dmx"]

skip = False
for line in old_aim_lines:
    if line.startswith("def build_aim_calibrations("):
        skip = True
    elif line.startswith("def aim_to_dmx("):
        skip = True
    elif skip and line.startswith("def "):
        skip = False
        
    if not skip:
        new_aim.append(line)

while new_aim and new_aim[-1].strip() == "":
    new_aim.pop()

strategy_code = """
from typing import Protocol

class CalculationStrategy(Protocol):
    @property
    def name(self) -> str:
        ...

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        ...

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        ...

class InverseKinematicsStrategy:
    def __init__(self):
        self._name = "Inverse Kinematics (Trigonometry)"
        self.calibrations = {}

    @property
    def name(self) -> str:
        return self._name

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return
        try:
            cal = build_fixture_aim_calibration(fixture, ref_pois)
            self.calibrations[fixture.id] = cal
        except ValueError:
            pass

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        if fixture.id not in self.calibrations:
            return 32768, 32768
            
        cal = self.calibrations[fixture.id]
        pan_angle, tilt_angle = geometry_angles(fixture.location, target_location, getattr(fixture, "mount", None))

        pan_value = round(_predict_axis(cal.pan, pan_angle))
        tilt_value = round(_predict_axis(cal.tilt, tilt_angle))

        return max(0, min(65535, pan_value)), max(0, min(65535, tilt_value))

class TrilinearInterpolationStrategy:
    def __init__(self):
        self._name = "Trilinear Interpolation"
        self.corners = {} # fixture.id -> dict of (x,y,z) -> (pan, tilt)

    @property
    def name(self) -> str:
        return self._name

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return
            
        corners = {}
        for poi in ref_pois:
            loc = poi.get("location", {})
            x, y, z = round(loc.get("x", 0)), round(loc.get("y", 0)), round(loc.get("z", 0))
            targets = poi.get("fixtures", {})
            if fixture.id in targets:
                corners[(x, y, z)] = (targets[fixture.id]["pan"], targets[fixture.id]["tilt"])
                
        # Fill missing ref_1_0_1 if 0,0,1 and 1,0,0 and 0,0,0 exist
        if (1,0,1) not in corners and (0,0,1) in corners and (1,0,0) in corners and (0,0,0) in corners:
            corners[(1,0,1)] = (
                corners[(0,0,1)][0] + corners[(1,0,0)][0] - corners[(0,0,0)][0],
                corners[(0,0,1)][1] + corners[(1,0,0)][1] - corners[(0,0,0)][1]
            )
            
        self.corners[fixture.id] = corners

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        corners = self.corners.get(fixture.id, {})
        if len(corners) < 8:
            return 32768, 32768 # Not enough corners
            
        x = max(0.0, min(1.0, float(target_location.get("x", 0))))
        y = max(0.0, min(1.0, float(target_location.get("y", 0))))
        z = max(0.0, min(1.0, float(target_location.get("z", 0))))

        def interpolate(c000, c100, c010, c110, c001, c101, c011, c111):
            c00 = c000 * (1 - x) + c100 * x
            c01 = c001 * (1 - x) + c101 * x
            c10 = c010 * (1 - x) + c110 * x
            c11 = c011 * (1 - x) + c111 * x

            c0 = c00 * (1 - y) + c10 * y
            c1 = c01 * (1 - y) + c11 * y

            return c0 * (1 - z) + c1 * z

        pan = interpolate(
            corners[(0,0,0)][0], corners[(1,0,0)][0], corners[(0,1,0)][0], corners[(1,1,0)][0],
            corners[(0,0,1)][0], corners[(1,0,1)][0], corners[(0,1,1)][0], corners[(1,1,1)][0]
        )
        tilt = interpolate(
            corners[(0,0,0)][1], corners[(1,0,0)][1], corners[(0,1,0)][1], corners[(1,1,0)][1],
            corners[(0,0,1)][1], corners[(1,0,1)][1], corners[(0,1,1)][1], corners[(1,1,1)][1]
        )
        
        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))

"""

with open("backend/src/spatial/aim.py", "w") as f:
    f.writelines(new_aim)
    f.write(strategy_code)

print("Merged!")
