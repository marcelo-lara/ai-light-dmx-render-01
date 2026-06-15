from __future__ import annotations

import math

import pytest

from src.spatial.origin_calibration import (
    FixtureAimSample,
    ReverseRay,
    build_fixture_reverse_rays,
    direction_to_dmx,
    estimate_fixture_pose,
    estimate_fixture_origin,
)


def _reverse_ray(origin: tuple[float, float, float], point: tuple[float, float, float]) -> ReverseRay:
    direction = (
        origin[0] - point[0],
        origin[1] - point[1],
        origin[2] - point[2],
    )
    magnitude = math.sqrt(sum(axis * axis for axis in direction))
    return ReverseRay(
        reference_id=f"ray_{point[0]}_{point[1]}_{point[2]}",
        point=point,
        direction=tuple(axis / magnitude for axis in direction),
    )


def test_estimate_fixture_origin_recovers_known_origin() -> None:
    known_origin = (0.2, 0.8, 1.4)
    rays = (
        _reverse_ray(known_origin, (0.0, 0.0, 0.0)),
        _reverse_ray(known_origin, (1.0, 0.0, 0.0)),
        _reverse_ray(known_origin, (0.0, 1.0, 0.0)),
        _reverse_ray(known_origin, (1.0, 1.0, 1.0)),
    )

    estimate = estimate_fixture_origin(
        "fixture_under_test",
        rays,
        initial_guess=(0.5, 0.5, 0.5),
    )

    assert estimate.success
    assert estimate.sample_count == 4
    assert estimate.rms_error < 1e-9
    assert estimate.origin == pytest.approx(known_origin, abs=1e-7)


def _aim_sample(
    origin: tuple[float, float, float],
    point: tuple[float, float, float],
    *,
    pan_offset_radians: float,
    tilt_offset_radians: float,
) -> FixtureAimSample:
    direction = (
        point[0] - origin[0],
        point[1] - origin[1],
        point[2] - origin[2],
    )
    magnitude = math.sqrt(sum(axis * axis for axis in direction))
    unit_direction = tuple(axis / magnitude for axis in direction)
    pan, tilt = direction_to_dmx(
        unit_direction,
        pan_offset_radians=pan_offset_radians,
        tilt_offset_radians=tilt_offset_radians,
    )
    return FixtureAimSample(
        reference_id=f"sample_{point[0]}_{point[1]}_{point[2]}",
        point=point,
        pan=pan,
        tilt=tilt,
    )


def test_estimate_fixture_pose_recovers_known_origin_and_offsets() -> None:
    known_origin = (0.12, 0.15, 0.18)
    pan_offset_radians = 0.31
    tilt_offset_radians = -0.18
    samples = (
        _aim_sample(known_origin, (0.62, 0.34, 0.25), pan_offset_radians=pan_offset_radians, tilt_offset_radians=tilt_offset_radians),
        _aim_sample(known_origin, (0.85, 0.48, 0.42), pan_offset_radians=pan_offset_radians, tilt_offset_radians=tilt_offset_radians),
        _aim_sample(known_origin, (0.58, 0.88, 0.71), pan_offset_radians=pan_offset_radians, tilt_offset_radians=tilt_offset_radians),
        _aim_sample(known_origin, (0.94, 0.92, 0.96), pan_offset_radians=pan_offset_radians, tilt_offset_radians=tilt_offset_radians),
        _aim_sample(known_origin, (0.53, 0.41, 1.12), pan_offset_radians=pan_offset_radians, tilt_offset_radians=tilt_offset_radians),
    )

    estimate = estimate_fixture_pose(
        "fixture_under_test",
        samples,
        initial_origin=(0.3, 0.3, 0.3),
    )

    assert estimate.success
    assert estimate.sample_count == 5
    assert estimate.rms_error < 1e-4
    assert estimate.origin == pytest.approx(known_origin, abs=2e-4)
    assert estimate.pan_offset_radians == pytest.approx(pan_offset_radians, abs=2e-4)
    assert estimate.tilt_offset_radians == pytest.approx(tilt_offset_radians, abs=2e-4)


def test_build_fixture_reverse_rays_filters_hard_stops() -> None:
    ref_pois = [
        {
            "id": "ref_valid",
            "location": {"x": 0.0, "y": 0.0, "z": 0.0},
            "fixtures": {"fixture_under_test": {"pan": 12000, "tilt": 16000}},
        },
        {
            "id": "ref_invalid",
            "location": {"x": 1.0, "y": 0.0, "z": 0.0},
            "fixtures": {"fixture_under_test": {"pan": 65530, "tilt": 16000}},
        },
    ]

    ray_set = build_fixture_reverse_rays(ref_pois, "fixture_under_test")

    assert len(ray_set.rays) == 1
    assert ray_set.rejected_reference_ids == ("ref_invalid",)