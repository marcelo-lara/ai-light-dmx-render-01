from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from src.config import FIXTURES_JSON, REF_COORDINATES_JSON
from src.dmx.models.fixtures import load_all as load_fixtures
from src.poi_store import load_ref_coordinates
from src.spatial.origin_calibration import (
    DEFAULT_MAX_VALID_DMX,
    DEFAULT_MIN_VALID_DMX,
    build_fixture_aim_samples,
    estimate_fixture_orientation_pose,
    origin_bounds_for_mount,
)

DEFAULT_FIXTURE_IDS = (
    "mini_beam_prism_l",
    "head_el150",
    "mini_beam_prism_r",
)


def _round_float(value: float) -> float:
    return round(float(value), 9)


def _orientation_dict(estimate) -> dict[str, Any]:
    return {
        "yaw": _round_float(estimate.yaw_radians),
        "pitch": _round_float(estimate.pitch_radians),
        "roll": _round_float(estimate.roll_radians),
        "pan_sign": int(estimate.pan_sign),
        "tilt_reversed": bool(estimate.tilt_reversed),
    }


def _location_dict(origin: tuple[float, float, float]) -> dict[str, float]:
    return {
        "x": _round_float(origin[0]),
        "y": _round_float(origin[1]),
        "z": _round_float(origin[2]),
    }


def _estimate_hits_origin_bounds(estimate, mount: str | None, *, epsilon: float = 1e-6) -> bool:
    lower, upper = origin_bounds_for_mount(mount)
    origin = estimate.origin
    for axis in range(3):
        if abs(origin[axis] - float(lower[axis])) <= epsilon:
            return True
        if abs(origin[axis] - float(upper[axis])) <= epsilon:
            return True
    return False


def _apply_estimated_fixture_pose_updates(
    fixtures_json_path: Path,
    *,
    updates: Mapping[str, Mapping[str, Any]],
) -> tuple[Path | None, list[str], list[str]]:
    if not updates:
        return None, [], []

    original_text = fixtures_json_path.read_text(encoding="utf-8")
    parsed = json.loads(original_text)
    if not isinstance(parsed, list):
        raise ValueError("fixtures.json must contain a top-level list")

    applied_ids: list[str] = []
    seen_ids: set[str] = set()

    for item in parsed:
        if not isinstance(item, dict):
            continue
        fixture_id = str(item.get("id", ""))
        update = updates.get(fixture_id)
        if update is None:
            continue

        seen_ids.add(fixture_id)
        next_location = dict(update["location"])
        next_orientation = dict(update["orientation"])
        changed = item.get("location") != next_location or item.get("orientation") != next_orientation
        if not changed:
            continue

        item["location"] = next_location
        item["orientation"] = next_orientation
        applied_ids.append(fixture_id)

    missing_ids = sorted(set(updates.keys()) - seen_ids)
    if not applied_ids:
        return None, [], missing_ids

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    backup_path = fixtures_json_path.parent / f"{fixtures_json_path.name}.bak.{timestamp}"
    backup_path.write_text(original_text, encoding="utf-8")
    fixtures_json_path.write_text(json.dumps(parsed, indent="\t") + "\n", encoding="utf-8")
    return backup_path, applied_ids, missing_ids


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate moving-head fixture origins from reference-corner pan/tilt "
            "samples using reverse-ray least squares."
        )
    )
    parser.add_argument(
        "--fixtures-json",
        type=Path,
        default=FIXTURES_JSON,
        help="Path to fixtures.json.",
    )
    parser.add_argument(
        "--ref-coordinates",
        type=Path,
        default=REF_COORDINATES_JSON,
        help="Path to ref_coordinates.json.",
    )
    parser.add_argument(
        "--fixture-id",
        dest="fixture_ids",
        action="append",
        default=[],
        help="Fixture ID to solve. Repeat to target multiple fixtures.",
    )
    parser.add_argument(
        "--min-valid-dmx",
        type=int,
        default=DEFAULT_MIN_VALID_DMX,
        help="Reject pan/tilt values at or below this DMX value.",
    )
    parser.add_argument(
        "--max-valid-dmx",
        type=int,
        default=DEFAULT_MAX_VALID_DMX,
        help="Reject pan/tilt values at or above this DMX value.",
    )
    parser.add_argument(
        "--show-rejected",
        action="store_true",
        help="Print the rejected reference IDs for each fixture.",
    )
    parser.add_argument(
        "--apply-to-fixtures",
        action="store_true",
        help="Write solved location and orientation fields back into fixtures.json with a timestamped backup.",
    )
    return parser


def _format_origin(origin: tuple[float, float, float]) -> str:
    return f"x={origin[0]:.9f}, y={origin[1]:.9f}, z={origin[2]:.9f}"


def _format_degrees(radians: float) -> str:
    return f"{radians:.9f} rad ({radians * 180.0 / 3.141592653589793:.6f} deg)"


def main() -> int:
    args = _build_parser().parse_args()
    fixture_ids = tuple(args.fixture_ids or DEFAULT_FIXTURE_IDS)

    fixtures = {
        fixture.id: fixture
        for fixture in load_fixtures(str(args.fixtures_json))
        if getattr(fixture, "fixture_type", None) == "moving_head"
    }
    ref_pois = load_ref_coordinates(args.ref_coordinates)
    pose_updates: dict[str, dict[str, Any]] = {}

    exit_code = 0

    for fixture_id in fixture_ids:
        fixture = fixtures.get(fixture_id)
        if fixture is None:
            print(f"Fixture {fixture_id}: skipped, not found in {args.fixtures_json}")
            exit_code = 1
            continue

        sample_set = build_fixture_aim_samples(
            ref_pois,
            fixture_id,
            min_valid_dmx=args.min_valid_dmx,
            max_valid_dmx=args.max_valid_dmx,
        )

        if len(sample_set.samples) < 3:
            print(
                f"Fixture {fixture_id}: skipped, only {len(sample_set.samples)} valid samples "
                f"after rejecting {len(sample_set.rejected_reference_ids)} hard-stop samples"
            )
            exit_code = 1
            continue

        estimate = estimate_fixture_orientation_pose(
            fixture_id,
            sample_set.samples,
            initial_origin=(
                float(fixture.location["x"]),
                float(fixture.location["y"]),
                float(fixture.location["z"]),
            ),
            mount=getattr(fixture, "mount", None),
            rejected_count=len(sample_set.rejected_reference_ids),
        )

        hits_bounds = _estimate_hits_origin_bounds(estimate, getattr(fixture, "mount", None))
        if not hits_bounds:
            pose_updates[fixture_id] = {
                "location": _location_dict(estimate.origin),
                "orientation": _orientation_dict(estimate),
            }

        print(f"Fixture {fixture_id}")
        print(f"  Estimated origin: {_format_origin(estimate.origin)}")
        print(
            f"  Valid rays: {estimate.sample_count} | "
            f"Rejected rays: {estimate.rejected_count}"
        )
        print(f"  Yaw: {_format_degrees(estimate.yaw_radians)}")
        print(f"  Pitch: {_format_degrees(estimate.pitch_radians)}")
        print(f"  Roll: {_format_degrees(estimate.roll_radians)}")
        print(f"  Pan sign: {estimate.pan_sign:+d}")
        print(f"  Tilt reversed: {estimate.tilt_reversed}")
        print(f"  RMS orthogonal distance: {estimate.rms_error:.9f}")
        print(f"  Solver cost: {estimate.cost:.9f}")
        print(f"  Solver success: {estimate.success} ({estimate.message})")
        if hits_bounds:
            print("  Warning: origin hit mount bounds; result not eligible for --apply-to-fixtures.")
        if args.show_rejected and sample_set.rejected_reference_ids:
            print(
                "  Rejected references: "
                + ", ".join(sample_set.rejected_reference_ids)
            )

    if args.apply_to_fixtures:
        try:
            backup_path, applied_ids, missing_ids = _apply_estimated_fixture_pose_updates(
                args.fixtures_json,
                updates=pose_updates,
            )
        except OSError as exc:
            print(
                "Failed to write fixtures.json. If you are running inside Docker, "
                "the default /app/fixtures mount may be read-only. "
                "Pass a writable --fixtures-json path or add a writable bind mount."
            )
            print(f"Write error: {exc}")
            return 1
        if backup_path is not None:
            print(f"Applied pose updates to {args.fixtures_json}")
            print(f"Backup created at {backup_path}")
            print("Updated fixtures: " + ", ".join(applied_ids))
        else:
            print("No fixture pose updates were written.")
        if missing_ids:
            print("Missing fixture IDs: " + ", ".join(missing_ids))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())