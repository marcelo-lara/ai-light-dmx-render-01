from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence, Protocol

from src.spatial.origin_calibration import (
    FixtureOrientationPoseEstimate,
    build_fixture_aim_samples,
    estimate_fixture_orientation_pose,
    origin_is_plausible_for_mount,
    world_direction_to_dmx,
)

_REF_POI_ID_RE = re.compile(r"^ref_\d+_\d+_\d+$")


@dataclass(frozen=True)
class AxisCalibration:
    model: str
    slope: float
    intercept: float
    quadratic: float = 0.0
    wrap_center: float = 0.0


@dataclass(frozen=True)
class AimCalibration:
    pan: AxisCalibration
    tilt: AxisCalibration


def is_ref_poi_id(poi_id: str) -> bool:
    if poi_id == "table_center":
        return True
    return bool(_REF_POI_ID_RE.fullmatch(poi_id))


def _reference_pois(pois: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    ref_pois = [poi for poi in pois if is_ref_poi_id(str(poi.get("id", "")))]
    if not ref_pois:
        raise ValueError("No ref_*_*_* POIs found for calibration.")
    return ref_pois


def _split_location(location: Mapping[str, float]) -> tuple[float, float, float]:
    return float(location["x"]), float(location["y"]), float(location["z"])


def _pan_angle_for_mount(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
    mount: str | None,
) -> float:
    fixture_x, fixture_y, _ = _split_location(fixture_location)
    target_x, target_y, _ = _split_location(target_location)
    delta_x = target_x - fixture_x
    delta_y = target_y - fixture_y

    if mount == "wall_left":
        return math.atan2(delta_y, delta_x)
    if mount == "wall_right":
        # Right-wall fixtures use the mirrored pan convention so x increasing
        # moves pan in the opposite DMX direction from wall_left.
        return math.atan2(delta_y, delta_x)
    if mount == "wall_back":
        # Back-wall fixtures face along +y, so pan sweeps across x.
        return math.atan2(delta_x, delta_y)
    return math.atan2(delta_x, delta_y)


def _tilt_horizontal_distance(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
    mount: str | None,
) -> float:
    fixture_x, fixture_y, _ = _split_location(fixture_location)
    target_x, target_y, _ = _split_location(target_location)

    if mount in {"wall_left", "wall_right"}:
        return abs(target_x - fixture_x)
    if mount == "wall_back":
        return abs(target_y - fixture_y)
    return math.hypot(target_x - fixture_x, target_y - fixture_y)


def _tilt_angle(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
    mount: str | None,
) -> float:
    _, _, fixture_z = _split_location(fixture_location)
    _, _, target_z = _split_location(target_location)
    horizontal_distance = _tilt_horizontal_distance(
        fixture_location,
        target_location,
        mount,
    )
    return math.atan2(horizontal_distance, fixture_z - target_z)


def geometry_angles(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
    mount: str | None,
) -> tuple[float, float]:
    return _pan_angle_for_mount(fixture_location, target_location, mount), _tilt_angle(
        fixture_location,
        target_location,
        mount,
    )


def _fit_affine(samples: Sequence[tuple[float, float]]) -> tuple[float, float]:
    if len(samples) < 2:
        raise ValueError("At least two samples are required for affine fit.")

    xs = [x for x, _ in samples]
    ys = [y for _, y in samples]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 1e-9:
        raise ValueError("Degenerate affine fit: sample variance is too small.")

    slope = sum((x - mean_x) * (y - mean_y) for x, y in samples) / denominator
    intercept = mean_y - (slope * mean_x)
    return slope, intercept


def _solve_3x3(matrix: list[list[float]], vector: list[float]) -> tuple[float, float, float] | None:
    # Small Gaussian elimination solver with partial pivoting.
    aug = [row[:] + [vector[idx]] for idx, row in enumerate(matrix)]

    for pivot_col in range(3):
        pivot_row = max(range(pivot_col, 3), key=lambda r: abs(aug[r][pivot_col]))
        if abs(aug[pivot_row][pivot_col]) <= 1e-12:
            return None
        if pivot_row != pivot_col:
            aug[pivot_col], aug[pivot_row] = aug[pivot_row], aug[pivot_col]

        pivot = aug[pivot_col][pivot_col]
        for col in range(pivot_col, 4):
            aug[pivot_col][col] /= pivot

        for row in range(3):
            if row == pivot_col:
                continue
            factor = aug[row][pivot_col]
            for col in range(pivot_col, 4):
                aug[row][col] -= factor * aug[pivot_col][col]

    return aug[0][3], aug[1][3], aug[2][3]


def _fit_quadratic(
    samples: Sequence[tuple[float, float]],
) -> tuple[float, float, float] | None:
    if len(samples) < 3:
        return None

    xs = [x for x, _ in samples]
    ys = [y for _, y in samples]

    sum_x = sum(xs)
    sum_x2 = sum(x * x for x in xs)
    sum_x3 = sum((x * x) * x for x in xs)
    sum_x4 = sum((x * x) * (x * x) for x in xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in samples)
    sum_x2y = sum((x * x) * y for x, y in samples)

    solved = _solve_3x3(
        [
            [sum_x4, sum_x3, sum_x2],
            [sum_x3, sum_x2, sum_x],
            [sum_x2, sum_x, float(len(samples))],
        ],
        [sum_x2y, sum_xy, sum_y],
    )
    if solved is None:
        return None

    quad, slope, intercept = solved
    return quad, slope, intercept


def _wrap_to_reference(angle: float, reference: float) -> float:
    period = 2 * math.pi
    return angle + (round((reference - angle) / period) * period)


def _wrapped_samples(samples: Sequence[tuple[float, float]]) -> tuple[list[tuple[float, float]], float]:
    if not samples:
        return [], 0.0

    anchor = samples[0][0]
    first_pass = [(_wrap_to_reference(x, anchor), y) for x, y in samples]
    center = sum(x for x, _ in first_pass) / len(first_pass)
    second_pass = [(_wrap_to_reference(x, center), y) for x, y in samples]
    final_center = sum(x for x, _ in second_pass) / len(second_pass)
    return second_pass, final_center


def _predict_axis(axis: AxisCalibration, angle: float) -> float:
    mapped_angle = angle
    if axis.model == "wrapped_affine":
        mapped_angle = _wrap_to_reference(angle, axis.wrap_center)

    if axis.model == "quadratic":
        return (axis.quadratic * mapped_angle * mapped_angle) + (axis.slope * mapped_angle) + axis.intercept

    return (axis.slope * mapped_angle) + axis.intercept


def _pairwise_vector_samples(
    samples: Sequence[tuple[float, float]],
) -> list[tuple[float, float, float, float]]:
    vectors: list[tuple[float, float, float, float]] = []
    for idx, (x1, y1) in enumerate(samples):
        for x2, y2 in samples[idx + 1 :]:
            if abs(x2 - x1) <= 1e-12 and abs(y2 - y1) <= 1e-12:
                continue
            vectors.append((x1, y1, x2, y2))
    return vectors


def _axis_error_key(
    model: AxisCalibration,
    samples: Sequence[tuple[float, float]],
    vectors: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float, float, int]:
    if not samples:
        return (0.0, 0.0, 0.0, 0)

    diffs = [_predict_axis(model, x) - y for x, y in samples]
    abs_errors = [abs(diff) for diff in diffs]
    max_abs = max(abs_errors)
    mae = sum(abs_errors) / len(abs_errors)

    vector_mae = 0.0
    if vectors:
        vector_errors = [
            abs(((_predict_axis(model, x2) - _predict_axis(model, x1)) - (y2 - y1)))
            for x1, y1, x2, y2 in vectors
        ]
        vector_mae = sum(vector_errors) / len(vector_errors)

    complexity_rank = {
        "affine": 0,
        "wrapped_affine": 1,
        "quadratic": 2,
    }.get(model.model, 99)

    return (max_abs, mae, vector_mae, complexity_rank)


def _choose_axis_model(
    samples: Sequence[tuple[float, float]],
    *,
    allow_wrapped_affine: bool,
) -> AxisCalibration:
    if len(samples) < 2:
        raise ValueError("At least two samples are required to choose an axis model.")

    vectors = _pairwise_vector_samples(samples)

    affine_slope, affine_intercept = _fit_affine(samples)
    candidates: list[AxisCalibration] = [
        AxisCalibration(
            model="affine",
            slope=affine_slope,
            intercept=affine_intercept,
        )
    ]

    if allow_wrapped_affine and len(samples) >= 2:
        wrapped, center = _wrapped_samples(samples)
        wrapped_slope, wrapped_intercept = _fit_affine(wrapped)
        candidates.append(
            AxisCalibration(
                model="wrapped_affine",
                slope=wrapped_slope,
                intercept=wrapped_intercept,
                wrap_center=center,
            )
        )

    if len(samples) >= 3:
        quadratic_fit = _fit_quadratic(samples)
        if quadratic_fit is not None:
            quad, quad_slope, quad_intercept = quadratic_fit
            candidates.append(
                AxisCalibration(
                    model="quadratic",
                    slope=quad_slope,
                    intercept=quad_intercept,
                    quadratic=quad,
                )
            )

    return min(candidates, key=lambda model: _axis_error_key(model, samples, vectors))


def build_fixture_aim_calibration(
    fixture,
    pois: Sequence[Mapping[str, object]],
) -> AimCalibration:
    if getattr(fixture, "fixture_type", None) != "moving_head":
        raise ValueError(f"Fixture {getattr(fixture, 'id', '<unknown>')} is not a moving head.")

    pan_samples: list[tuple[float, float]] = []
    tilt_samples: list[tuple[float, float]] = []

    for poi in _reference_pois(pois):
        targets = poi.get("fixtures", {})
        if not isinstance(targets, Mapping):
            continue

        target = targets.get(fixture.id)
        if target is None or not isinstance(target, Mapping):
            continue

        location = poi.get("location")
        if not isinstance(location, Mapping):
            continue

        pan_angle, tilt_angle = geometry_angles(
            fixture.location,
            location,
            fixture.mount,
        )
        pan_samples.append((pan_angle, float(target["pan"])))
        tilt_samples.append((tilt_angle, float(target["tilt"])))

    if len(pan_samples) < 2:
        raise ValueError(
            f"Fixture {fixture.id} has insufficient ref pan samples: {len(pan_samples)}"
        )
    if len(tilt_samples) < 2:
        raise ValueError(
            f"Fixture {fixture.id} has insufficient ref tilt samples: {len(tilt_samples)}"
        )

    pan_axis = _choose_axis_model(
        pan_samples,
        allow_wrapped_affine=True,
    )
    tilt_axis = _choose_axis_model(
        tilt_samples,
        allow_wrapped_affine=False,
    )

    return AimCalibration(
        pan=pan_axis,
        tilt=tilt_axis,
    )

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


class HybridPanTiltStrategy:
    def __init__(self, pan_strategy: CalculationStrategy | None = None):
        self._name = "Hybrid Pan Interpolation / Local Tilt"
        self.pan_strategy = pan_strategy or TrilinearInterpolationStrategy()
        self.calibrations = {}

    @property
    def name(self) -> str:
        return self._name

    def _should_override_tilt(self, fixture, target_location: Mapping[str, float]) -> bool:
        mount = getattr(fixture, "mount", None)
        target_x = float(target_location.get("x", 0.0))
        target_y = float(target_location.get("y", 0.0))

        if mount == "wall_left":
            return abs(target_x - 0.0) <= 1e-9
        if mount == "wall_right":
            return abs(target_x - 1.0) <= 1e-9
        if mount == "wall_back":
            return abs(target_y - 0.0) <= 1e-9
        return False

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return

        self.pan_strategy.calibrate(fixture, ref_pois)
        try:
            self.calibrations[fixture.id] = build_fixture_aim_calibration(fixture, ref_pois)
        except ValueError:
            pass

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        pan, fallback_tilt = self.pan_strategy.aim_to_dmx(fixture, target_location)
        calibration = self.calibrations.get(fixture.id)
        if calibration is None or not self._should_override_tilt(fixture, target_location):
            return pan, fallback_tilt

        _, tilt_angle = geometry_angles(
            fixture.location,
            target_location,
            getattr(fixture, "mount", None),
        )
        tilt_value = round(_predict_axis(calibration.tilt, tilt_angle))
        return pan, max(0, min(65535, tilt_value))


@dataclass(frozen=True)
class FloorProjectedAnchor:
    x: float
    y: float
    pan: int
    tilt: int


class FloorProjectedInterpolationStrategy:
    def __init__(self):
        self._name = "Floor Projected Interpolation"
        self.anchors: dict[str, tuple[FloorProjectedAnchor, ...]] = {}

    @property
    def name(self) -> str:
        return self._name

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return

        anchors: list[FloorProjectedAnchor] = []
        for poi in ref_pois:
            location = poi.get("location")
            fixtures = poi.get("fixtures")
            if not isinstance(location, Mapping) or not isinstance(fixtures, Mapping):
                continue
            target = fixtures.get(fixture.id)
            if not isinstance(target, Mapping):
                continue

            anchors.append(
                FloorProjectedAnchor(
                    x=float(location.get("x", 0.0)),
                    y=float(location.get("y", 0.0)),
                    pan=int(target["pan"]),
                    tilt=int(target["tilt"]),
                )
            )

        self.anchors[fixture.id] = tuple(anchors)

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        anchors = self.anchors.get(fixture.id, ())
        if not anchors:
            return 32768, 32768

        target_x = float(target_location.get("x", 0.0))
        target_y = float(target_location.get("y", 0.0))

        weighted_pan = 0.0
        weighted_tilt = 0.0
        total_weight = 0.0
        for anchor in anchors:
            dx = target_x - anchor.x
            dy = target_y - anchor.y
            distance_sq = (dx * dx) + (dy * dy)
            if distance_sq <= 1e-8:
                return anchor.pan, anchor.tilt
            weight = 1.0 / distance_sq
            weighted_pan += anchor.pan * weight
            weighted_tilt += anchor.tilt * weight
            total_weight += weight

        if total_weight <= 1e-12:
            return 32768, 32768

        pan = round(weighted_pan / total_weight)
        tilt = round(weighted_tilt / total_weight)
        return max(0, min(65535, pan)), max(0, min(65535, tilt))


class PoseBasedStrategy:
    def __init__(self, fallback: CalculationStrategy | None = None):
        self._name = "Pose Based (Ray Calibrated)"
        self.pose_estimates = {}
        self.fallback = fallback or TrilinearInterpolationStrategy()

    @property
    def name(self) -> str:
        return self._name

    def _saved_pose(self, fixture) -> FixtureOrientationPoseEstimate | None:
        orientation = getattr(fixture, "orientation", None)
        location = getattr(fixture, "location", None)
        if not isinstance(orientation, Mapping) or not isinstance(location, Mapping):
            return None

        required = ("yaw", "pitch", "roll", "pan_sign", "tilt_reversed")
        if any(key not in orientation for key in required):
            return None

        try:
            pan_sign = int(orientation["pan_sign"])
            if pan_sign not in (-1, 1):
                return None

            origin = (
                float(location["x"]),
                float(location["y"]),
                float(location["z"]),
            )
            if not origin_is_plausible_for_mount(origin, getattr(fixture, "mount", None)):
                return None

            return FixtureOrientationPoseEstimate(
                fixture_id=fixture.id,
                origin=origin,
                yaw_radians=float(orientation["yaw"]),
                pitch_radians=float(orientation["pitch"]),
                roll_radians=float(orientation["roll"]),
                pan_sign=pan_sign,
                tilt_reversed=bool(orientation["tilt_reversed"]),
                sample_count=0,
                rejected_count=0,
                rms_error=0.0,
                success=True,
                cost=0.0,
                message="loaded from fixtures.json",
            )
        except (KeyError, TypeError, ValueError):
            return None

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return

        saved_pose = self._saved_pose(fixture)
        if saved_pose is not None:
            self.pose_estimates[fixture.id] = saved_pose
            return

        self.fallback.calibrate(fixture, ref_pois)

        try:
            sample_set = build_fixture_aim_samples(ref_pois, fixture.id)
            pose = estimate_fixture_orientation_pose(
                fixture.id,
                sample_set.samples,
                initial_origin=(
                    float(fixture.location["x"]),
                    float(fixture.location["y"]),
                    float(fixture.location["z"]),
                ),
                mount=getattr(fixture, "mount", None),
                rejected_count=len(sample_set.rejected_reference_ids),
            )
        except ValueError:
            return

        self.pose_estimates[fixture.id] = pose
        fixture.location = {
            "x": pose.origin[0],
            "y": pose.origin[1],
            "z": pose.origin[2],
        }
        fixture.orientation = {
            "yaw": pose.yaw_radians,
            "pitch": pose.pitch_radians,
            "roll": pose.roll_radians,
            "pan_sign": pose.pan_sign,
            "tilt_reversed": pose.tilt_reversed,
        }

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        pose = self.pose_estimates.get(fixture.id)
        if pose is None:
            return self.fallback.aim_to_dmx(fixture, target_location)

        delta_x = float(target_location["x"]) - pose.origin[0]
        delta_y = float(target_location["y"]) - pose.origin[1]
        delta_z = float(target_location["z"]) - pose.origin[2]
        magnitude = math.sqrt((delta_x * delta_x) + (delta_y * delta_y) + (delta_z * delta_z))
        if magnitude <= 1e-12:
            return self.fallback.aim_to_dmx(fixture, target_location)

        direction = (
            delta_x / magnitude,
            delta_y / magnitude,
            delta_z / magnitude,
        )
        return world_direction_to_dmx(
            direction,
            yaw_radians=pose.yaw_radians,
            pitch_radians=pose.pitch_radians,
            roll_radians=pose.roll_radians,
            pan_sign=pose.pan_sign,
            tilt_reversed=pose.tilt_reversed,
        )

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
        self.center_offset = getattr(self, "center_offset", {})
        table_center_poi = None
        for poi in ref_pois:
            if poi.get("id") == "table_center":
                table_center_poi = poi
                continue
            loc = poi.get("location")
            if not isinstance(loc, Mapping):
                continue
            fixtures = poi.get("fixtures")
            if not isinstance(fixtures, Mapping):
                continue
            x, y, z = round(loc.get("x", 0)), round(loc.get("y", 0)), round(loc.get("z", 0))
            if fixture.id in fixtures:
                target = fixtures[fixture.id]
                if isinstance(target, Mapping):
                    corners[(x, y, z)] = (int(target["pan"]), int(target["tilt"]))
                
        # Fill missing ref_1_0_1 if 0,0,1 and 1,0,0 and 0,0,0 exist
        if (1,0,1) not in corners and (0,0,1) in corners and (1,0,0) in corners and (0,0,0) in corners:
            corners[(1,0,1)] = (
                corners[(0,0,1)][0] + corners[(1,0,0)][0] - corners[(0,0,0)][0],
                corners[(0,0,1)][1] + corners[(1,0,0)][1] - corners[(0,0,0)][1]
            )
            
        self.corners[fixture.id] = corners
        
        if table_center_poi is not None:
            center_fixtures = table_center_poi.get("fixtures")
            center_location = table_center_poi.get("location")
            if (
                isinstance(center_fixtures, Mapping)
                and fixture.id in center_fixtures
                and isinstance(center_location, Mapping)
            ):
                target = center_fixtures[fixture.id]
                if isinstance(target, Mapping):
                    calc_pan, calc_tilt = self.aim_to_dmx(fixture, center_location)
                    self.center_offset[fixture.id] = (
                        int(target["pan"]) - calc_pan,
                        int(target["tilt"]) - calc_tilt,
                    )


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
        
        offset_pan, offset_tilt = getattr(self, "center_offset", {}).get(fixture.id, (0, 0))

        dist = ((x - 0.49)**2 + (y - 0.52)**2 + (z - 0.15)**2) ** 0.5
        weight = max(0, 1 - (dist / 1.0)) # linear falloff or just fixed if close enough?
        
        pan += offset_pan * weight
        tilt += offset_tilt * weight

        return max(0, min(65535, round(pan))), max(0, min(65535, round(tilt)))


@dataclass(frozen=True)
class MeasurementCorrectionAnchor:
    location: tuple[float, float, float]
    face_axis: str
    face_value: float
    pan_residual: float
    tilt_residual: float


class MeasuredCorrectionStrategy:
    def __init__(
        self,
        measured_pois: Sequence[Mapping[str, object]] | None = None,
        fallback: CalculationStrategy | None = None,
        correction_radius: float = 0.42,
        face_activation_threshold: float = 0.12,
    ):
        self._name = "Measured Correction (Virtual Centers)"
        self.fallback = fallback or TrilinearInterpolationStrategy()
        self.measured_pois = tuple(measured_pois or ())
        self.corrections: dict[str, tuple[MeasurementCorrectionAnchor, ...]] = {}
        self.correction_radius = float(correction_radius)
        self.face_activation_threshold = float(face_activation_threshold)

    def _face_for_location(self, location: Mapping[str, float]) -> tuple[str, float] | None:
        for axis in ("x", "y", "z"):
            value = float(location.get(axis, 0.0))
            if abs(value - 0.0) <= 1e-9 or abs(value - 1.0) <= 1e-9:
                return axis, value
        return None

    def _active_face_for_target(self, target: tuple[float, float, float]) -> tuple[str, float] | None:
        candidates = [
            (abs(target[0] - 0.0), "x", 0.0),
            (abs(target[0] - 1.0), "x", 1.0),
            (abs(target[1] - 0.0), "y", 0.0),
            (abs(target[1] - 1.0), "y", 1.0),
            (abs(target[2] - 0.0), "z", 0.0),
            (abs(target[2] - 1.0), "z", 1.0),
        ]
        distance, axis, value = min(candidates, key=lambda item: item[0])
        if distance <= self.face_activation_threshold:
            return axis, value
        return None

    @property
    def name(self) -> str:
        return self._name

    def calibrate(self, fixture, ref_pois: Sequence[Mapping[str, object]]) -> None:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            return

        self.fallback.calibrate(fixture, ref_pois)
        anchors: list[MeasurementCorrectionAnchor] = []
        for poi in self.measured_pois:
            fixtures = poi.get("fixtures")
            if not isinstance(fixtures, Mapping):
                continue
            measured = fixtures.get(fixture.id)
            if not isinstance(measured, Mapping):
                continue
            location = poi.get("location")
            if not isinstance(location, Mapping):
                continue

            base_pan, base_tilt = self.fallback.aim_to_dmx(fixture, location)
            face = self._face_for_location(location)
            if face is None:
                continue
            anchors.append(
                MeasurementCorrectionAnchor(
                    location=(
                        float(location["x"]),
                        float(location["y"]),
                        float(location["z"]),
                    ),
                    face_axis=face[0],
                    face_value=face[1],
                    pan_residual=float(int(measured["pan"]) - base_pan),
                    tilt_residual=float(int(measured["tilt"]) - base_tilt),
                )
            )

        self.corrections[fixture.id] = tuple(anchors)

    def aim_to_dmx(self, fixture, target_location: Mapping[str, float]) -> tuple[int, int]:
        base_pan, base_tilt = self.fallback.aim_to_dmx(fixture, target_location)
        anchors = self.corrections.get(fixture.id, ())
        if not anchors:
            return base_pan, base_tilt

        target = (
            float(target_location["x"]),
            float(target_location["y"]),
            float(target_location["z"]),
        )
        active_face = self._active_face_for_target(target)
        if active_face is None:
            return base_pan, base_tilt

        weighted_pan = 0.0
        weighted_tilt = 0.0
        total_weight = 0.0
        for anchor in anchors:
            if anchor.face_axis != active_face[0] or abs(anchor.face_value - active_face[1]) > 1e-9:
                continue
            dx = target[0] - anchor.location[0]
            dy = target[1] - anchor.location[1]
            dz = target[2] - anchor.location[2]
            distance_sq = (dx * dx) + (dy * dy) + (dz * dz)
            distance = math.sqrt(distance_sq)
            if distance <= 1e-8:
                return (
                    max(0, min(65535, round(base_pan + anchor.pan_residual))),
                    max(0, min(65535, round(base_tilt + anchor.tilt_residual))),
                )

            if distance >= self.correction_radius:
                continue

            # Fade corrections to zero at the edge of the local neighborhood so
            # captured virtual centers improve nearby aiming without destabilizing
            # unrelated room faces.
            local_falloff = 1.0 - (distance / self.correction_radius)
            weight = local_falloff / max(distance_sq, 1e-8)
            weighted_pan += anchor.pan_residual * weight
            weighted_tilt += anchor.tilt_residual * weight
            total_weight += weight

        if total_weight <= 1e-12:
            return base_pan, base_tilt

        corrected_pan = round(base_pan + (weighted_pan / total_weight))
        corrected_tilt = round(base_tilt + (weighted_tilt / total_weight))
        return max(0, min(65535, corrected_pan)), max(0, min(65535, corrected_tilt))

# Legacy helper implementations that aim.py used to expose publicly
def build_aim_calibrations(fixtures, pois):
    calibrations = {}
    ref_pois_list = _reference_pois(pois)
    for fix in fixtures:
        if getattr(fix, "fixture_type", None) == "moving_head":
            try:
                calibrations[fix.id] = build_fixture_aim_calibration(fix, ref_pois_list)
            except ValueError:
                pass
    return calibrations

def aim_to_dmx(fixture, target_location, calibration):
    pan_angle, tilt_angle = geometry_angles(fixture.location, target_location, fixture.mount)
    pan_value = round(_predict_axis(calibration.pan, pan_angle))
    tilt_value = round(_predict_axis(calibration.tilt, tilt_angle))
    return max(0, min(65535, pan_value)), max(0, min(65535, tilt_value))

