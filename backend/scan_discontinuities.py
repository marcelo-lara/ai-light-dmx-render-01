from __future__ import annotations

import argparse
from pathlib import Path

from src.config import FIXTURES_JSON, REF_COORDINATES_JSON
from src.dmx.models.fixtures import load_all as load_fixtures
from src.poi_store import load_ref_coordinates
from src.spatial.aim import TrilinearInterpolationStrategy


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan the trilinear aiming field for large adjacent DMX jumps on a 3D grid."
    )
    parser.add_argument("--fixtures-json", type=Path, default=FIXTURES_JSON)
    parser.add_argument("--ref-coordinates", type=Path, default=REF_COORDINATES_JSON)
    parser.add_argument(
        "--grid-steps",
        type=int,
        default=10,
        help="Number of segments per axis; 10 means 11 samples along each axis.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    fixtures = {
        fixture.id: fixture
        for fixture in load_fixtures(str(args.fixtures_json))
        if getattr(fixture, "fixture_type", None) == "moving_head"
    }
    ref_pois = load_ref_coordinates(args.ref_coordinates)

    strategy = TrilinearInterpolationStrategy()
    for fixture in fixtures.values():
        strategy.calibrate(fixture, ref_pois)

    steps = max(1, args.grid_steps)
    coords = [index / steps for index in range(steps + 1)]
    directions = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    for fixture_id, fixture in fixtures.items():
        best = (-1, None)
        for ix, x in enumerate(coords):
            for iy, y in enumerate(coords):
                for iz, z in enumerate(coords):
                    origin_target = {"x": x, "y": y, "z": z}
                    origin_pan, origin_tilt = strategy.aim_to_dmx(fixture, origin_target)
                    for dx, dy, dz in directions:
                        nx = ix + dx
                        ny = iy + dy
                        nz = iz + dz
                        if nx > steps or ny > steps or nz > steps:
                            continue
                        neighbor_target = {"x": coords[nx], "y": coords[ny], "z": coords[nz]}
                        neighbor_pan, neighbor_tilt = strategy.aim_to_dmx(fixture, neighbor_target)
                        dpan = abs(neighbor_pan - origin_pan)
                        dtilt = abs(neighbor_tilt - origin_tilt)
                        score = max(dpan, dtilt)
                        if score > best[0]:
                            best = (
                                score,
                                {
                                    "from": origin_target,
                                    "to": neighbor_target,
                                    "from_dmx": (origin_pan, origin_tilt),
                                    "to_dmx": (neighbor_pan, neighbor_tilt),
                                    "dpan": dpan,
                                    "dtilt": dtilt,
                                },
                            )

        print(f"{fixture_id}: max_step={best[0]}")
        if best[1] is not None:
            info = best[1]
            print(
                f"  from={info['from']} to={info['to']} "
                f"from_dmx={info['from_dmx']} to_dmx={info['to_dmx']} "
                f"dpan={info['dpan']} dtilt={info['dtilt']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())