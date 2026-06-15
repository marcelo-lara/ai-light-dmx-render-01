from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import FIXTURES_JSON, REF_COORDINATES_JSON
from src.dmx.models.fixtures import load_all as load_fixtures
from src.poi_store import load_ref_coordinates
from src.spatial.origin_calibration import (
    DEFAULT_MAX_VALID_DMX,
    DEFAULT_MIN_VALID_DMX,
    build_fixture_aim_samples,
    estimate_fixture_pose,
)

DEFAULT_FIXTURE_IDS = (
    "mini_beam_prism_l",
    "head_el150",
    "mini_beam_prism_r",
)


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

        estimate = estimate_fixture_pose(
            fixture_id,
            sample_set.samples,
            initial_origin=(
                float(fixture.location["x"]),
                float(fixture.location["y"]),
                float(fixture.location["z"]),
            ),
            rejected_count=len(sample_set.rejected_reference_ids),
        )

        print(f"Fixture {fixture_id}")
        print(f"  Estimated origin: {_format_origin(estimate.origin)}")
        print(
            f"  Valid rays: {estimate.sample_count} | "
            f"Rejected rays: {estimate.rejected_count}"
        )
        print(f"  Pan offset: {_format_degrees(estimate.pan_offset_radians)}")
        print(f"  Tilt offset: {_format_degrees(estimate.tilt_offset_radians)}")
        print(f"  RMS orthogonal distance: {estimate.rms_error:.9f}")
        print(f"  Solver cost: {estimate.cost:.9f}")
        print(f"  Solver success: {estimate.success} ({estimate.message})")
        if args.show_rejected and sample_set.rejected_reference_ids:
            print(
                "  Rejected references: "
                + ", ".join(sample_set.rejected_reference_ids)
            )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())