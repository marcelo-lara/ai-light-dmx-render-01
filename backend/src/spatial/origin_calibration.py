from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

DMX_MAX = 65535
PAN_RANGE_DEGREES = 540.0
TILT_RANGE_DEGREES = 270.0
DEFAULT_MIN_VALID_DMX = 10
DEFAULT_MAX_VALID_DMX = 65525


@dataclass(frozen=True)
class ReverseRay:
    reference_id: str
    point: tuple[float, float, float]
    direction: tuple[float, float, float]


@dataclass(frozen=True)
class FixtureRaySet:
    fixture_id: str
    rays: tuple[ReverseRay, ...]
    rejected_reference_ids: tuple[str, ...]


@dataclass(frozen=True)
class FixtureAimSample:
    reference_id: str
    point: tuple[float, float, float]
    pan: int
    tilt: int


@dataclass(frozen=True)
class FixtureAimSampleSet:
    fixture_id: str
    samples: tuple[FixtureAimSample, ...]
    rejected_reference_ids: tuple[str, ...]


@dataclass(frozen=True)
class FixtureOriginEstimate:
    fixture_id: str
    origin: tuple[float, float, float]
    sample_count: int
    rejected_count: int
    rms_error: float
    success: bool
    cost: float
    message: str


@dataclass(frozen=True)
class FixturePoseEstimate:
    fixture_id: str
    origin: tuple[float, float, float]
    pan_offset_radians: float
    tilt_offset_radians: float
    sample_count: int
    rejected_count: int
    rms_error: float
    success: bool
    cost: float
    message: str


def _location_tuple(location: Mapping[str, Any]) -> tuple[float, float, float]:
    return (
        float(location["x"]),
        float(location["y"]),
        float(location["z"]),
    )


def dmx_to_radians(value: int, span_degrees: float) -> float:
    return (float(value) / DMX_MAX) * math.radians(span_degrees)


def radians_to_dmx(value: float, span_degrees: float) -> int:
    span_radians = math.radians(span_degrees)
    dmx_value = round((float(value) / span_radians) * DMX_MAX)
    return max(0, min(DMX_MAX, dmx_value))


def is_mechanically_valid(
    pan: int,
    tilt: int,
    *,
    min_valid_dmx: int = DEFAULT_MIN_VALID_DMX,
    max_valid_dmx: int = DEFAULT_MAX_VALID_DMX,
) -> bool:
    return (
        min_valid_dmx < int(pan) < max_valid_dmx
        and min_valid_dmx < int(tilt) < max_valid_dmx
    )


def pan_tilt_to_direction(
    pan: int,
    tilt: int,
    *,
    pan_offset_radians: float = 0.0,
    tilt_offset_radians: float = 0.0,
) -> tuple[float, float, float]:
    pan_radians = dmx_to_radians(pan, PAN_RANGE_DEGREES) + float(pan_offset_radians)
    tilt_radians = dmx_to_radians(tilt, TILT_RANGE_DEGREES) + float(tilt_offset_radians)

    horizontal = math.sin(tilt_radians)
    raw = np.array(
        [
            horizontal * math.cos(pan_radians),
            horizontal * math.sin(pan_radians),
            math.cos(tilt_radians),
        ],
        dtype=float,
    )
    magnitude = float(np.linalg.norm(raw))
    if magnitude <= 1e-12:
        raise ValueError("Pan/tilt produced a degenerate direction vector.")

    direction = raw / magnitude
    return (float(direction[0]), float(direction[1]), float(direction[2]))


def direction_to_angles(direction: Sequence[float]) -> tuple[float, float]:
    vector = np.asarray(direction, dtype=float)
    magnitude = float(np.linalg.norm(vector))
    if magnitude <= 1e-12:
        raise ValueError("Direction vector must be non-zero.")

    unit = vector / magnitude
    clamped_z = max(-1.0, min(1.0, float(unit[2])))
    pan_radians = math.atan2(float(unit[1]), float(unit[0]))
    if pan_radians < 0:
        pan_radians += 2 * math.pi
    tilt_radians = math.acos(clamped_z)
    return pan_radians, tilt_radians


def direction_to_dmx(
    direction: Sequence[float],
    *,
    pan_offset_radians: float = 0.0,
    tilt_offset_radians: float = 0.0,
) -> tuple[int, int]:
    pan_radians, tilt_radians = direction_to_angles(direction)
    return (
        radians_to_dmx(pan_radians - float(pan_offset_radians), PAN_RANGE_DEGREES),
        radians_to_dmx(tilt_radians - float(tilt_offset_radians), TILT_RANGE_DEGREES),
    )


def build_fixture_aim_samples(
    ref_pois: Sequence[Mapping[str, Any]],
    fixture_id: str,
    *,
    min_valid_dmx: int = DEFAULT_MIN_VALID_DMX,
    max_valid_dmx: int = DEFAULT_MAX_VALID_DMX,
) -> FixtureAimSampleSet:
    samples: list[FixtureAimSample] = []
    rejected_reference_ids: list[str] = []

    for poi in ref_pois:
        fixtures = poi.get("fixtures")
        if not isinstance(fixtures, Mapping) or fixture_id not in fixtures:
            continue

        target = fixtures[fixture_id]
        if not isinstance(target, Mapping):
            continue

        pan = int(target["pan"])
        tilt = int(target["tilt"])
        reference_id = str(poi.get("id", "unknown"))

        if not is_mechanically_valid(
            pan,
            tilt,
            min_valid_dmx=min_valid_dmx,
            max_valid_dmx=max_valid_dmx,
        ):
            rejected_reference_ids.append(reference_id)
            continue

        samples.append(
            FixtureAimSample(
                reference_id=reference_id,
                point=_location_tuple(poi["location"]),
                pan=pan,
                tilt=tilt,
            )
        )

    return FixtureAimSampleSet(
        fixture_id=fixture_id,
        samples=tuple(samples),
        rejected_reference_ids=tuple(rejected_reference_ids),
    )


def build_fixture_reverse_rays(
    ref_pois: Sequence[Mapping[str, Any]],
    fixture_id: str,
    *,
    min_valid_dmx: int = DEFAULT_MIN_VALID_DMX,
    max_valid_dmx: int = DEFAULT_MAX_VALID_DMX,
) -> FixtureRaySet:
    sample_set = build_fixture_aim_samples(
        ref_pois,
        fixture_id,
        min_valid_dmx=min_valid_dmx,
        max_valid_dmx=max_valid_dmx,
    )

    rays: list[ReverseRay] = []
    for sample in sample_set.samples:
        forward = np.asarray(pan_tilt_to_direction(sample.pan, sample.tilt), dtype=float)
        reverse = -forward
        reverse /= np.linalg.norm(reverse)

        rays.append(
            ReverseRay(
                reference_id=sample.reference_id,
                point=sample.point,
                direction=(
                    float(reverse[0]),
                    float(reverse[1]),
                    float(reverse[2]),
                ),
            )
        )

    return FixtureRaySet(
        fixture_id=fixture_id,
        rays=tuple(rays),
        rejected_reference_ids=sample_set.rejected_reference_ids,
    )


def _orthogonal_distance(point: np.ndarray, ray_point: np.ndarray, ray_direction: np.ndarray) -> float:
    offset = point - ray_point
    projection = np.dot(offset, ray_direction) * ray_direction
    orthogonal = offset - projection
    return float(np.linalg.norm(orthogonal))


def fixture_origin_residuals(origin: Sequence[float], rays: Sequence[ReverseRay]) -> np.ndarray:
    point = np.asarray(origin, dtype=float)
    residuals = [
        _orthogonal_distance(
            point,
            np.asarray(ray.point, dtype=float),
            np.asarray(ray.direction, dtype=float),
        )
        for ray in rays
    ]
    return np.asarray(residuals, dtype=float)


def fixture_pose_residuals(
    params: Sequence[float],
    samples: Sequence[FixtureAimSample],
) -> np.ndarray:
    origin = np.asarray(params[:3], dtype=float)
    pan_offset_radians = float(params[3])
    tilt_offset_radians = float(params[4])
    residuals = []
    for sample in samples:
        forward = np.asarray(
            pan_tilt_to_direction(
                sample.pan,
                sample.tilt,
                pan_offset_radians=pan_offset_radians,
                tilt_offset_radians=tilt_offset_radians,
            ),
            dtype=float,
        )
        reverse = -forward
        reverse /= np.linalg.norm(reverse)
        residuals.append(
            _orthogonal_distance(
                origin,
                np.asarray(sample.point, dtype=float),
                reverse,
            )
        )
    return np.asarray(residuals, dtype=float)


def estimate_fixture_origin(
    fixture_id: str,
    rays: Sequence[ReverseRay],
    *,
    initial_guess: Sequence[float] | None = None,
    rejected_count: int = 0,
) -> FixtureOriginEstimate:
    if len(rays) < 3:
        raise ValueError(
            f"Fixture '{fixture_id}' needs at least 3 valid rays, got {len(rays)}."
        )

    if initial_guess is None:
        initial_guess_array = np.mean(
            np.asarray([ray.point for ray in rays], dtype=float),
            axis=0,
        )
    else:
        initial_guess_array = np.asarray(initial_guess, dtype=float)

    result = least_squares(
        fixture_origin_residuals,
        initial_guess_array,
        args=(tuple(rays),),
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=10000,
    )
    rms_error = float(np.sqrt(np.mean(np.square(result.fun)))) if result.fun.size else 0.0

    return FixtureOriginEstimate(
        fixture_id=fixture_id,
        origin=(float(result.x[0]), float(result.x[1]), float(result.x[2])),
        sample_count=len(rays),
        rejected_count=rejected_count,
        rms_error=rms_error,
        success=bool(result.success),
        cost=float(result.cost),
        message=str(result.message),
    )


def estimate_fixture_pose(
    fixture_id: str,
    samples: Sequence[FixtureAimSample],
    *,
    initial_origin: Sequence[float] | None = None,
    initial_pan_offset_radians: float = 0.0,
    initial_tilt_offset_radians: float = 0.0,
    rejected_count: int = 0,
) -> FixturePoseEstimate:
    if len(samples) < 3:
        raise ValueError(
            f"Fixture '{fixture_id}' needs at least 3 valid samples, got {len(samples)}."
        )

    if initial_origin is None:
        initial_origin_array = np.mean(
            np.asarray([sample.point for sample in samples], dtype=float),
            axis=0,
        )
    else:
        initial_origin_array = np.asarray(initial_origin, dtype=float)

    initial_params = np.asarray(
        [
            float(initial_origin_array[0]),
            float(initial_origin_array[1]),
            float(initial_origin_array[2]),
            float(initial_pan_offset_radians),
            float(initial_tilt_offset_radians),
        ],
        dtype=float,
    )

    result = least_squares(
        fixture_pose_residuals,
        initial_params,
        args=(tuple(samples),),
        bounds=(
            np.asarray([-np.inf, -np.inf, -np.inf, -2 * math.pi, -math.pi], dtype=float),
            np.asarray([np.inf, np.inf, np.inf, 2 * math.pi, math.pi], dtype=float),
        ),
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=20000,
    )
    rms_error = float(np.sqrt(np.mean(np.square(result.fun)))) if result.fun.size else 0.0

    return FixturePoseEstimate(
        fixture_id=fixture_id,
        origin=(float(result.x[0]), float(result.x[1]), float(result.x[2])),
        pan_offset_radians=float(result.x[3]),
        tilt_offset_radians=float(result.x[4]),
        sample_count=len(samples),
        rejected_count=rejected_count,
        rms_error=rms_error,
        success=bool(result.success),
        cost=float(result.cost),
        message=str(result.message),
    )