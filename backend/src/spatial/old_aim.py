from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence


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
    return bool(_REF_POI_ID_RE.fullmatch(poi_id))


def _reference_pois(pois: Sequence[Mapping[str, object]]) -> list[Mapping[str, o
bject]]:
    ref_pois = [poi for poi in pois if is_ref_poi_id(str(poi.get("id", "")))]
    if not ref_pois:
        raise ValueError("No ref_*_*_* POIs found for calibration.")
    return ref_pois


def _split_location(location: Mapping[str, float]) -> tuple[float, float, float]
:
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


def _tilt_angle(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
) -> float:
    fixture_x, fixture_y, fixture_z = _split_location(fixture_location)
    target_x, target_y, target_z = _split_location(target_location)
    horizontal_distance = math.hypot(target_x - fixture_x, target_y - fixture_y)
    return math.atan2(horizontal_distance, fixture_z - target_z)


def geometry_angles(
    fixture_location: Mapping[str, float],
    target_location: Mapping[str, float],
    mount: str | None,
) -> tuple[float, float]:
    return _pan_angle_for_mount(fixture_location, target_location, mount), _tilt
_angle(
        fixture_location,
        target_location,
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


def _solve_3x3(matrix: list[list[float]], vector: list[float]) -> tuple[float, f
loat, float] | None:
    # Small Gaussian elimination solver with partial pivoting.
    aug = [row[:] + [vector[idx]] for idx, row in enumerate(matrix)]

    for pivot_col in range(3):
        pivot_row = max(range(pivot_col, 3), key=lambda r: abs(aug[r][pivot_col]
))
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


def _wrapped_samples(samples: Sequence[tuple[float, float]]) -> tuple[list[tuple
[float, float]], float]:
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
        return (axis.quadratic * mapped_angle * mapped_angle) + (axis.slope * ma
pped_angle) + axis.intercept

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
            abs(((_predict_axis(model, x2) - _predict_axis(model, x1)) - (y2 - y
1)))
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
        raise ValueError("At least two samples are required to choose an axis mo
del.")

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

    return min(candidates, key=lambda model: _axis_error_key(model, samples, vec
tors))


def build_fixture_aim_calibration(
    fixture,
    pois: Sequence[Mapping[str, object]],
) -> AimCalibration:
    if getattr(fixture, "fixture_type", None) != "moving_head":
        raise ValueError(f"Fixture {getattr(fixture, 'id', '<unknown>')} is not 
a moving head.")

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
            f"Fixture {fixture.id} has insufficient ref pan samples: {len(pan_sa
mples)}"
        )
    if len(tilt_samples) < 2:
        raise ValueError(
            f"Fixture {fixture.id} has insufficient ref tilt samples: {len(tilt_
samples)}"
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


def build_aim_calibrations(
    fixtures,
    pois: Sequence[Mapping[str, object]],
) -> dict[str, AimCalibration]:
    calibrations: dict[str, AimCalibration] = {}
    ref_pois = _reference_pois(pois)

    for fixture in fixtures:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            continue

        calibration = build_fixture_aim_calibration(
            fixture,
            ref_pois,
        )
        calibrations[fixture.id] = calibration

    return calibrations


def aim_to_dmx(fixture, target_location: Mapping[str, float], calibration: AimCa
libration) -> tuple[int, int]:
    pan_angle, tilt_angle = geometry_angles(fixture.location, target_location, f
ixture.mount)

    pan_value = round(_predict_axis(calibration.pan, pan_angle))
    tilt_value = round(_predict_axis(calibration.tilt, tilt_angle))

    return max(0, min(65535, pan_value)), max(0, min(65535, tilt_value))darkange