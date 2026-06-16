from __future__ import annotations

import math
from pathlib import Path

from src.config import FIXTURES_JSON, REF_COORDINATES_JSON, VIRTUAL_CENTER_MEASUREMENTS_JSON
from src.dmx.models.fixtures import load_all as load_fixtures
from src.poi_store import (
    build_virtual_reference_pois,
    load_pois,
    load_ref_coordinates,
    load_virtual_center_measurements,
)
from src.spatial.aim import FloorProjectedInterpolationStrategy, PoseBasedStrategy, TrilinearInterpolationStrategy
from src.spatial.origin_calibration import _world_direction_from_orientation

TARGET_FIXTURE_IDS = (
    "mini_beam_prism_l",
    "head_el150",
    "mini_beam_prism_r",
)


def _virtual_plane(location: dict[str, float]) -> tuple[str, float]:
    for axis in ("x", "y", "z"):
        value = float(location[axis])
        if abs(value - 0.0) <= 1e-9 or abs(value - 1.0) <= 1e-9:
            return axis, value
    raise ValueError(f"Location is not on a room face: {location}")


def _intersect_with_plane(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    *,
    axis: str,
    value: float,
) -> tuple[float, float, float] | None:
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    denom = float(direction[axis_index])
    if abs(denom) <= 1e-12:
        return None

    t = (value - float(origin[axis_index])) / denom
    if t <= 0:
        return None

    return (
        float(origin[0] + (direction[0] * t)),
        float(origin[1] + (direction[1] * t)),
        float(origin[2] + (direction[2] * t)),
    )


def _decode_hit_point(
    pose,
    *,
    pan: int,
    tilt: int,
    target_location: dict[str, float],
) -> tuple[float, float, float] | None:
    direction = _world_direction_from_orientation(
        pan,
        tilt,
        yaw_radians=pose.yaw_radians,
        pitch_radians=pose.pitch_radians,
        roll_radians=pose.roll_radians,
        pan_sign=pose.pan_sign,
        tilt_reversed=pose.tilt_reversed,
    )
    axis, value = _virtual_plane(target_location)
    return _intersect_with_plane(
        pose.origin,
        direction,
        axis=axis,
        value=value,
    )


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(
        ((a[0] - b[0]) ** 2)
        + ((a[1] - b[1]) ** 2)
        + ((a[2] - b[2]) ** 2)
    )


def _format_point(point: tuple[float, float, float] | None) -> str:
    if point is None:
        return "n/a"
    return f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})"


def main(
    fixtures_json: Path = FIXTURES_JSON,
    ref_coordinates: Path = REF_COORDINATES_JSON,
    measurements_path: Path = VIRTUAL_CENTER_MEASUREMENTS_JSON,
) -> int:
    ref_pois = load_ref_coordinates(ref_coordinates)
    pois = load_pois()
    virtual_measurements = load_virtual_center_measurements(measurements_path)
    virtual_refs = build_virtual_reference_pois(virtual_measurements)
    calibration_pois = [*ref_pois, *pois]

    trilinear_fixtures = {
        fixture.id: fixture
        for fixture in load_fixtures(str(fixtures_json))
        if getattr(fixture, "fixture_type", None) == "moving_head"
        and fixture.id in TARGET_FIXTURE_IDS
    }
    pose_fixtures = {
        fixture.id: fixture
        for fixture in load_fixtures(str(fixtures_json))
        if getattr(fixture, "fixture_type", None) == "moving_head"
        and fixture.id in TARGET_FIXTURE_IDS
    }
    floor_fixtures = {
        fixture.id: fixture
        for fixture in load_fixtures(str(fixtures_json))
        if getattr(fixture, "fixture_type", None) == "moving_head"
        and fixture.id in TARGET_FIXTURE_IDS
    }
    trilinear = TrilinearInterpolationStrategy()
    floor_projected = FloorProjectedInterpolationStrategy()
    pose_based = PoseBasedStrategy(fallback=TrilinearInterpolationStrategy())

    for fixture in trilinear_fixtures.values():
        trilinear.calibrate(fixture, ref_pois)
    for fixture in floor_fixtures.values():
        floor_projected.calibrate(fixture, calibration_pois)
    for fixture in pose_fixtures.values():
        pose_based.calibrate(fixture, ref_pois)

    print("Virtual center accuracy report")
    print("Model: trilinear commands decoded through solved pose as physical proxy")
    print()

    for fixture_id in TARGET_FIXTURE_IDS:
        trilinear_fixture = trilinear_fixtures.get(fixture_id)
        floor_fixture = floor_fixtures.get(fixture_id)
        pose_fixture = pose_fixtures.get(fixture_id)
        pose = pose_based.pose_estimates.get(fixture_id)
        if trilinear_fixture is None or floor_fixture is None or pose_fixture is None or pose is None:
            print(f"Fixture {fixture_id}: skipped, incomplete calibration")
            print()
            continue

        trilinear_misses: list[float] = []
        floor_misses: list[float] = []
        pose_misses: list[float] = []
        measured_pan_errors_tri: list[float] = []
        measured_tilt_errors_tri: list[float] = []
        measured_pan_errors_floor: list[float] = []
        measured_tilt_errors_floor: list[float] = []
        measured_pan_errors_pose: list[float] = []
        measured_tilt_errors_pose: list[float] = []

        print(f"Fixture {fixture_id}")
        for virtual_ref in virtual_refs:
            target = virtual_ref["location"]
            target_point = (
                float(target["x"]),
                float(target["y"]),
                float(target["z"]),
            )
            tri_pan, tri_tilt = trilinear.aim_to_dmx(trilinear_fixture, target)
            floor_pan, floor_tilt = floor_projected.aim_to_dmx(floor_fixture, target)
            pose_pan, pose_tilt = pose_based.aim_to_dmx(pose_fixture, target)

            tri_hit = _decode_hit_point(pose, pan=tri_pan, tilt=tri_tilt, target_location=target)
            floor_hit = _decode_hit_point(pose, pan=floor_pan, tilt=floor_tilt, target_location=target)
            pose_hit = _decode_hit_point(pose, pan=pose_pan, tilt=pose_tilt, target_location=target)

            tri_miss = _distance(tri_hit, target_point) if tri_hit is not None else float("inf")
            floor_miss = _distance(floor_hit, target_point) if floor_hit is not None else float("inf")
            pose_miss = _distance(pose_hit, target_point) if pose_hit is not None else float("inf")
            trilinear_misses.append(tri_miss)
            floor_misses.append(floor_miss)
            pose_misses.append(pose_miss)

            print(
                f"  {virtual_ref['id']}: tri_miss={tri_miss:.4f}, floor_miss={floor_miss:.4f}, pose_miss={pose_miss:.4f}, "
                f"tri_hit={_format_point(tri_hit)}, floor_hit={_format_point(floor_hit)}, pose_hit={_format_point(pose_hit)}"
            )

            measured = virtual_ref.get("fixtures", {}).get(fixture_id)
            if measured:
                tri_pan_error = abs(tri_pan - int(measured["pan"]))
                tri_tilt_error = abs(tri_tilt - int(measured["tilt"]))
                floor_pan_error = abs(floor_pan - int(measured["pan"]))
                floor_tilt_error = abs(floor_tilt - int(measured["tilt"]))
                pose_pan_error = abs(pose_pan - int(measured["pan"]))
                pose_tilt_error = abs(pose_tilt - int(measured["tilt"]))
                measured_pan_errors_tri.append(tri_pan_error)
                measured_tilt_errors_tri.append(tri_tilt_error)
                measured_pan_errors_floor.append(floor_pan_error)
                measured_tilt_errors_floor.append(floor_tilt_error)
                measured_pan_errors_pose.append(pose_pan_error)
                measured_tilt_errors_pose.append(pose_tilt_error)
                print(
                    f"    measured_dmx: tri_pan_err={tri_pan_error}, tri_tilt_err={tri_tilt_error}, "
                    f"floor_pan_err={floor_pan_error}, floor_tilt_err={floor_tilt_error}, "
                    f"pose_pan_err={pose_pan_error}, pose_tilt_err={pose_tilt_error}"
                )

        tri_avg = sum(trilinear_misses) / len(trilinear_misses)
        floor_avg = sum(floor_misses) / len(floor_misses)
        pose_avg = sum(pose_misses) / len(pose_misses)
        tri_max = max(trilinear_misses)
        floor_max = max(floor_misses)
        pose_max = max(pose_misses)
        print(
            f"  summary: tri_avg={tri_avg:.4f}, tri_max={tri_max:.4f}, "
            f"floor_avg={floor_avg:.4f}, floor_max={floor_max:.4f}, "
            f"pose_avg={pose_avg:.4f}, pose_max={pose_max:.4f}"
        )
        if measured_pan_errors_tri:
            print(
                "  measured summary: "
                f"tri_pan_mae={sum(measured_pan_errors_tri) / len(measured_pan_errors_tri):.1f}, "
                f"tri_tilt_mae={sum(measured_tilt_errors_tri) / len(measured_tilt_errors_tri):.1f}, "
                f"floor_pan_mae={sum(measured_pan_errors_floor) / len(measured_pan_errors_floor):.1f}, "
                f"floor_tilt_mae={sum(measured_tilt_errors_floor) / len(measured_tilt_errors_floor):.1f}, "
                f"pose_pan_mae={sum(measured_pan_errors_pose) / len(measured_pan_errors_pose):.1f}, "
                f"pose_tilt_mae={sum(measured_tilt_errors_pose) / len(measured_tilt_errors_pose):.1f}"
            )
        else:
            print(
                "  measured summary: no saved virtual-center measurements. "
                "Select a virtual reference in the UI, adjust fixtures if needed, and use Update Values to capture DMX."
            )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())