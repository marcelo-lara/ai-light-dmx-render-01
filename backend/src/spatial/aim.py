from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


_GROUP_SUFFIXES = {"left", "center", "right"}


@dataclass(frozen=True)
class AimCalibration:
    pan_slope: float
    pan_intercept: float
    tilt_slope: float
    tilt_intercept: float


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
        return math.atan2(-delta_y, -delta_x)
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
    return _pan_angle_for_mount(fixture_location, target_location, mount), _tilt_angle(
        fixture_location,
        target_location,
    )


def _fit_affine(samples: Sequence[tuple[float, float]], *, fallback_slope: float, fallback_intercept: float) -> tuple[float, float]:
    if len(samples) < 2:
        return fallback_slope, fallback_intercept

    xs = [x for x, _ in samples]
    ys = [y for _, y in samples]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 1e-9:
        return fallback_slope, fallback_intercept

    slope = sum((x - mean_x) * (y - mean_y) for x, y in samples) / denominator
    intercept = mean_y - (slope * mean_x)
    return slope, intercept


def build_aim_calibrations(fixtures, pois: Sequence[Mapping[str, object]]) -> dict[str, AimCalibration]:
    calibrations: dict[str, AimCalibration] = {}
    default_pan_slope = 65535 / (2 * math.pi)
    default_pan_intercept = 32767.5
    default_tilt_slope = 65535 / math.pi
    default_tilt_intercept = 0.0

    for fixture in fixtures:
        if getattr(fixture, "fixture_type", None) != "moving_head":
            continue

        pan_samples: list[tuple[float, float]] = []
        tilt_samples: list[tuple[float, float]] = []
        for poi in pois:
            targets = poi.get("fixtures", {})
            target = targets.get(fixture.id)
            if target is None:
                continue
            pan_angle, tilt_angle = geometry_angles(fixture.location, poi["location"], fixture.mount)
            pan_samples.append((pan_angle, float(target["pan"])))
            tilt_samples.append((tilt_angle, float(target["tilt"])))

        pan_slope, pan_intercept = _fit_affine(
            pan_samples,
            fallback_slope=default_pan_slope,
            fallback_intercept=default_pan_intercept,
        )
        tilt_slope, tilt_intercept = _fit_affine(
            tilt_samples,
            fallback_slope=default_tilt_slope,
            fallback_intercept=default_tilt_intercept,
        )
        calibrations[fixture.id] = AimCalibration(
            pan_slope=pan_slope,
            pan_intercept=pan_intercept,
            tilt_slope=tilt_slope,
            tilt_intercept=tilt_intercept,
        )

    return calibrations


def aim_to_dmx(fixture, target_location: Mapping[str, float], calibration: AimCalibration | None) -> tuple[int, int]:
    pan_angle, tilt_angle = geometry_angles(fixture.location, target_location, fixture.mount)

    if calibration is None:
        pan_value = round((65535 / (2 * math.pi)) * pan_angle + 32767.5)
        tilt_value = round((65535 / math.pi) * tilt_angle)
    else:
        pan_value = round((calibration.pan_slope * pan_angle) + calibration.pan_intercept)
        tilt_value = round((calibration.tilt_slope * tilt_angle) + calibration.tilt_intercept)

    return max(0, min(65535, pan_value)), max(0, min(65535, tilt_value))