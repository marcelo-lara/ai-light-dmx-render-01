from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.config import FIXTURES_JSON, POIS_JSON, REF_COORDINATES_JSON
from src.dmx.models.fixtures import load_all as load_fixtures
from src.poi_store import load_all_pois
from src.spatial.aim import is_ref_poi_id #  (
    aim_to_dmx,
    build_aim_calibrations,
    build_fixture_aim_calibration,
    is_ref_poi_id,
)


DEFAULT_BOUND = 0.20
DEFAULT_NON_REF_MAX_RATIO = 1.25
DEFAULT_STEPS = (0.05, 0.02, 0.01, 0.005)
DMX_MAX_VALUE = 65535.0
PHYSICAL_Y_SAMPLES = 7
PHYSICAL_OPPOSITION_MIN_PCT = 80.0
PHYSICAL_MAG_RATIO_MIN = 0.25


@dataclass(frozen=True)
class AxisMetrics:
    mae: float
    max_abs: int
    rmse: float
    mean_signed: float
    samples: int


@dataclass(frozen=True)
class SetMetrics:
    pan: AxisMetrics
    tilt: AxisMetrics


@dataclass(frozen=True)
class FixtureEval:
    objective: tuple[float, float, float, float, float]
    ref_metrics: SetMetrics
    non_ref_metrics: SetMetrics
    rule_of_three_pan_mae: float


@dataclass(frozen=True)
class FixtureOptimizationResult:
    fixture_id: str
    accepted: bool
    reason: str
    original_location: dict[str, float]
    estimated_location: dict[str, float]
    displacement: float
    ref_before: SetMetrics
    ref_after: SetMetrics
    non_ref_before: SetMetrics
    non_ref_after: SetMetrics
    rule_of_three_pan_before: float
    rule_of_three_pan_after: float


@dataclass(frozen=True)
class AppliedFixtureLocationChange:
    fixture_id: str
    before_location: dict[str, float]
    after_location: dict[str, float]
    displacement: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _vector_norm(dx: float, dy: float, dz: float) -> float:
    return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))


def _location_delta(
    original: Mapping[str, float],
    candidate: Mapping[str, float],
) -> tuple[float, float, float]:
    return (
        float(candidate["x"]) - float(original["x"]),
        float(candidate["y"]) - float(original["y"]),
        float(candidate["z"]) - float(original["z"]),
    )


def _location_distance(
    original: Mapping[str, float],
    candidate: Mapping[str, float],
) -> float:
    dx, dy, dz = _location_delta(original, candidate)
    return _vector_norm(dx, dy, dz)


def _apply_step(
    current: Mapping[str, float],
    step_delta: tuple[float, float, float],
) -> dict[str, float]:
    dx, dy, dz = step_delta
    return {
        "x": _clamp01(float(current["x"]) + dx),
        "y": _clamp01(float(current["y"]) + dy),
        "z": _clamp01(float(current["z"]) + dz),
    }


def _direction_vectors(step: float) -> list[tuple[float, float, float]]:
    vectors: list[tuple[float, float, float]] = []
    for dx in (-step, 0.0, step):
        for dy in (-step, 0.0, step):
            for dz in (-step, 0.0, step):
                if dx == 0.0 and dy == 0.0 and dz == 0.0:
                    continue
                vectors.append((dx, dy, dz))
    vectors.sort()
    return vectors


def _axis_metrics(diffs: list[int]) -> AxisMetrics:
    if not diffs:
        return AxisMetrics(
            mae=0.0,
            max_abs=0,
            rmse=0.0,
            mean_signed=0.0,
            samples=0,
        )

    abs_errors = [abs(v) for v in diffs]
    samples = len(diffs)
    return AxisMetrics(
        mae=sum(abs_errors) / samples,
        max_abs=max(abs_errors),
        rmse=math.sqrt(sum((v * v) for v in diffs) / samples),
        mean_signed=sum(diffs) / samples,
        samples=samples,
    )


def _set_metrics(pan_diffs: list[int], tilt_diffs: list[int]) -> SetMetrics:
    return SetMetrics(
        pan=_axis_metrics(pan_diffs),
        tilt=_axis_metrics(tilt_diffs),
    )


def _error_percentage(pan_diff: int, tilt_diff: int) -> float:
    # Average normalized absolute error across pan and tilt channels.
    avg_abs_error = (abs(pan_diff) + abs(tilt_diff)) / 2.0
    return (avg_abs_error / DMX_MAX_VALUE) * 100.0


def _median_non_ref_z(pois: Sequence[Mapping[str, Any]]) -> float:
    z_values = sorted(
        float(poi["location"]["z"])
        for poi in pois
        if not is_ref_poi_id(str(poi.get("id", "")))
    )
    if not z_values:
        return 0.2
    return z_values[len(z_values) // 2]


def _physical_x_sweep_validation(
    fixtures,
    calibrations: Mapping[str, Any],
    pois: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {getattr(fixture, "id", ""): fixture for fixture in fixtures}
    left = by_id.get("mini_beam_prism_l")
    right = by_id.get("mini_beam_prism_r")
    if left is None or right is None:
        return {
            "available": False,
            "reason": "missing mini_beam_prism_l or mini_beam_prism_r fixture",
            "rows": [],
            "opposite_pct": 0.0,
            "mean_mag_ratio": 0.0,
            "passed": False,
            "z": 0.0,
            "y_start": 0.0,
            "y_end": 0.0,
        }

    if left.id not in calibrations or right.id not in calibrations:
        return {
            "available": False,
            "reason": "missing calibration for mini_beam_prism_l or mini_beam_prism_r",
            "rows": [],
            "opposite_pct": 0.0,
            "mean_mag_ratio": 0.0,
            "passed": False,
            "z": 0.0,
            "y_start": 0.0,
            "y_end": 0.0,
        }

    y_start = max(float(left.location["y"]), float(right.location["y"]))
    y_end = 1.0
    if PHYSICAL_Y_SAMPLES <= 1 or abs(y_end - y_start) <= 1e-9:
        y_values = [y_start]
    else:
        y_values = [
            y_start + ((y_end - y_start) * idx / (PHYSICAL_Y_SAMPLES - 1))
            for idx in range(PHYSICAL_Y_SAMPLES)
        ]

    z_value = _median_non_ref_z(pois)

    rows: list[dict[str, Any]] = []
    for y_value in y_values:
        target_x0 = {"x": 0.0, "y": y_value, "z": z_value}
        target_x1 = {"x": 1.0, "y": y_value, "z": z_value}

        left_x0_pan, _ = aim_to_dmx(left, target_x0, calibrations[left.id])
        left_x1_pan, _ = aim_to_dmx(left, target_x1, calibrations[left.id])
        right_x0_pan, _ = aim_to_dmx(right, target_x0, calibrations[right.id])
        right_x1_pan, _ = aim_to_dmx(right, target_x1, calibrations[right.id])

        left_delta = left_x1_pan - left_x0_pan
        right_delta = right_x1_pan - right_x0_pan
        opposite = (left_delta * right_delta) < 0

        max_mag = max(abs(left_delta), abs(right_delta))
        mag_ratio = (min(abs(left_delta), abs(right_delta)) / max_mag) if max_mag > 0 else 0.0

        rows.append(
            {
                "y": y_value,
                "z": z_value,
                "left_x0_pan": left_x0_pan,
                "left_x1_pan": left_x1_pan,
                "left_delta": left_delta,
                "right_x0_pan": right_x0_pan,
                "right_x1_pan": right_x1_pan,
                "right_delta": right_delta,
                "opposite": opposite,
                "mag_ratio": mag_ratio,
            }
        )

    opposite_count = sum(1 for row in rows if row["opposite"])
    opposite_pct = (100.0 * opposite_count / len(rows)) if rows else 0.0
    mean_mag_ratio = (sum(row["mag_ratio"] for row in rows) / len(rows)) if rows else 0.0
    passed = (
        opposite_pct >= PHYSICAL_OPPOSITION_MIN_PCT
        and mean_mag_ratio >= PHYSICAL_MAG_RATIO_MIN
    )

    return {
        "available": True,
        "reason": "",
        "rows": rows,
        "opposite_pct": opposite_pct,
        "mean_mag_ratio": mean_mag_ratio,
        "passed": passed,
        "z": z_value,
        "y_start": y_values[0],
        "y_end": y_values[-1],
    }


def _objective_from_ref_metrics(
    metrics: SetMetrics,
    *,
    rule_of_three_pan_mae: float,
) -> tuple[float, float, float, float, float]:
    max_pair = sorted([metrics.pan.max_abs, metrics.tilt.max_abs], reverse=True)
    mae_pair = sorted([metrics.pan.mae, metrics.tilt.mae], reverse=True)
    return (max_pair[0], max_pair[1], mae_pair[0], mae_pair[1], rule_of_three_pan_mae)


def _rule_of_three_pan_mae(fixture, pois: Sequence[Mapping[str, Any]], calibration) -> float:
    # Heuristic: for ref y=0 and y=1 pairs with same x/z, midpoint pan should be
    # close to the linear midpoint "rule of three" value.
    by_xz: dict[tuple[float, float], dict[str, int]] = {}

    for poi in pois:
        if not is_ref_poi_id(str(poi.get("id", ""))):
            continue

        targets = poi.get("fixtures", {})
        target = targets.get(fixture.id)
        if target is None:
            continue

        location = poi.get("location", {})
        x = float(location.get("x", 0.0))
        y = float(location.get("y", 0.0))
        z = float(location.get("z", 0.0))
        key = (round(x, 6), round(z, 6))

        entry = by_xz.setdefault(key, {})
        if abs(y - 0.0) <= 1e-9:
            entry["y0"] = int(target["pan"])
        elif abs(y - 1.0) <= 1e-9:
            entry["y1"] = int(target["pan"])

    errors: list[float] = []
    for (x_key, z_key), values in by_xz.items():
        if "y0" not in values or "y1" not in values:
            continue

        midpoint_location = {
            "x": float(x_key),
            "y": 0.5,
            "z": float(z_key),
        }
        pan_pred, _ = aim_to_dmx(fixture, midpoint_location, calibration)
        pan_mid_stored = (values["y0"] + values["y1"]) / 2.0
        errors.append(abs(float(pan_pred) - pan_mid_stored))

    if not errors:
        return 0.0

    return sum(errors) / len(errors)


def _evaluate_fixture_location(
    fixture,
    pois: Sequence[Mapping[str, Any]],
    location: Mapping[str, float],
) -> FixtureEval:
    previous_location = dict(fixture.location)
    fixture.location = dict(location)
    try:
        calibration = build_fixture_aim_calibration(fixture, pois)

        ref_pan_diffs: list[int] = []
        ref_tilt_diffs: list[int] = []
        non_ref_pan_diffs: list[int] = []
        non_ref_tilt_diffs: list[int] = []

        for poi in pois:
            targets = poi.get("fixtures", {})
            target = targets.get(fixture.id)
            if target is None:
                continue

            pan_calc, tilt_calc = aim_to_dmx(
                fixture,
                poi["location"],
                calibration,
            )

            pan_stored = int(target["pan"])
            tilt_stored = int(target["tilt"])
            pan_diff = pan_calc - pan_stored
            tilt_diff = tilt_calc - tilt_stored

            if is_ref_poi_id(str(poi.get("id", ""))):
                ref_pan_diffs.append(pan_diff)
                ref_tilt_diffs.append(tilt_diff)
            else:
                non_ref_pan_diffs.append(pan_diff)
                non_ref_tilt_diffs.append(tilt_diff)

        ref_metrics = _set_metrics(ref_pan_diffs, ref_tilt_diffs)
        non_ref_metrics = _set_metrics(non_ref_pan_diffs, non_ref_tilt_diffs)
        rule_of_three_pan_mae = _rule_of_three_pan_mae(fixture, pois, calibration)

        return FixtureEval(
            objective=_objective_from_ref_metrics(
                ref_metrics,
                rule_of_three_pan_mae=rule_of_three_pan_mae,
            ),
            ref_metrics=ref_metrics,
            non_ref_metrics=non_ref_metrics,
            rule_of_three_pan_mae=rule_of_three_pan_mae,
        )
    finally:
        fixture.location = previous_location


def _float_lt(a: float, b: float, eps: float = 1e-9) -> bool:
    return a < (b - eps)


def _objectives_equal(
    left: tuple[float, ...],
    right: tuple[float, ...],
    eps: float = 1e-9,
) -> bool:
    for lv, rv in zip(left, right):
        if abs(lv - rv) > eps:
            return False
    return True


def _objective_better(
    candidate: tuple[float, ...],
    best: tuple[float, ...],
    eps: float = 1e-9,
) -> bool:
    for cand, cur in zip(candidate, best):
        if _float_lt(cand, cur, eps):
            return True
        if _float_lt(cur, cand, eps):
            return False
    return False


def _is_better_candidate(
    candidate_eval: FixtureEval,
    candidate_displacement: float,
    best_eval: FixtureEval,
    best_displacement: float,
) -> bool:
    if _objective_better(candidate_eval.objective, best_eval.objective):
        return True

    if _objectives_equal(candidate_eval.objective, best_eval.objective) and _float_lt(
        candidate_displacement,
        best_displacement,
    ):
        return True

    return False


def _passes_non_ref_guard(
    baseline: SetMetrics,
    candidate: SetMetrics,
    *,
    max_ratio: float,
) -> tuple[bool, str]:
    checks = [
        ("pan", baseline.pan.mae, candidate.pan.mae),
        ("tilt", baseline.tilt.mae, candidate.tilt.mae),
    ]

    for axis, base_mae, cand_mae in checks:
        if base_mae <= 1e-9:
            if cand_mae > 1.0:
                return False, f"{axis} non-ref MAE rose from ~0 to {cand_mae:.1f}"
            continue

        limit = base_mae * max_ratio
        if cand_mae > limit:
            return False, (
                f"{axis} non-ref MAE {cand_mae:.1f} exceeded limit {limit:.1f} "
                f"({max_ratio:.2f}x baseline)"
            )

    return True, "passed"


def _optimize_fixture(
    fixture,
    pois: Sequence[Mapping[str, Any]],
    *,
    bound: float,
    steps: Sequence[float],
    non_ref_max_ratio: float,
) -> FixtureOptimizationResult:
    original_location = dict(fixture.location)

    baseline_eval = _evaluate_fixture_location(fixture, pois, original_location)
    best_location = dict(original_location)
    best_eval = baseline_eval

    for step in steps:
        directions = _direction_vectors(step)

        while True:
            current_location = dict(best_location)
            current_eval = best_eval
            current_displacement = _location_distance(original_location, current_location)

            next_location = current_location
            next_eval = current_eval
            next_displacement = current_displacement

            for direction in directions:
                candidate_location = _apply_step(current_location, direction)

                if candidate_location == current_location:
                    continue

                displacement = _location_distance(original_location, candidate_location)
                if displacement > (bound + 1e-9):
                    continue

                candidate_eval = _evaluate_fixture_location(fixture, pois, candidate_location)
                if _is_better_candidate(
                    candidate_eval,
                    displacement,
                    next_eval,
                    next_displacement,
                ):
                    next_location = candidate_location
                    next_eval = candidate_eval
                    next_displacement = displacement

            if next_location == current_location:
                break

            best_location = next_location
            best_eval = next_eval

    improvement_found = _objective_better(best_eval.objective, baseline_eval.objective)
    if not improvement_found:
        return FixtureOptimizationResult(
            fixture_id=fixture.id,
            accepted=False,
            reason="no ref-only objective improvement",
            original_location=original_location,
            estimated_location=original_location,
            displacement=0.0,
            ref_before=baseline_eval.ref_metrics,
            ref_after=baseline_eval.ref_metrics,
            non_ref_before=baseline_eval.non_ref_metrics,
            non_ref_after=baseline_eval.non_ref_metrics,
            rule_of_three_pan_before=baseline_eval.rule_of_three_pan_mae,
            rule_of_three_pan_after=baseline_eval.rule_of_three_pan_mae,
        )

    baseline_ref_mae_total = baseline_eval.ref_metrics.pan.mae + baseline_eval.ref_metrics.tilt.mae
    candidate_ref_mae_total = best_eval.ref_metrics.pan.mae + best_eval.ref_metrics.tilt.mae
    if candidate_ref_mae_total >= baseline_ref_mae_total:
        return FixtureOptimizationResult(
            fixture_id=fixture.id,
            accepted=False,
            reason=(
                "candidate rejected: ref MAE total did not improve "
                f"({candidate_ref_mae_total:.1f} >= {baseline_ref_mae_total:.1f})"
            ),
            original_location=original_location,
            estimated_location=original_location,
            displacement=0.0,
            ref_before=baseline_eval.ref_metrics,
            ref_after=baseline_eval.ref_metrics,
            non_ref_before=baseline_eval.non_ref_metrics,
            non_ref_after=baseline_eval.non_ref_metrics,
            rule_of_three_pan_before=baseline_eval.rule_of_three_pan_mae,
            rule_of_three_pan_after=baseline_eval.rule_of_three_pan_mae,
        )

    passes_guard, reason = _passes_non_ref_guard(
        baseline_eval.non_ref_metrics,
        best_eval.non_ref_metrics,
        max_ratio=non_ref_max_ratio,
    )
    if not passes_guard:
        return FixtureOptimizationResult(
            fixture_id=fixture.id,
            accepted=False,
            reason=f"candidate rejected: {reason}",
            original_location=original_location,
            estimated_location=original_location,
            displacement=0.0,
            ref_before=baseline_eval.ref_metrics,
            ref_after=baseline_eval.ref_metrics,
            non_ref_before=baseline_eval.non_ref_metrics,
            non_ref_after=baseline_eval.non_ref_metrics,
            rule_of_three_pan_before=baseline_eval.rule_of_three_pan_mae,
            rule_of_three_pan_after=baseline_eval.rule_of_three_pan_mae,
        )

    return FixtureOptimizationResult(
        fixture_id=fixture.id,
        accepted=True,
        reason="accepted",
        original_location=original_location,
        estimated_location=best_location,
        displacement=_location_distance(original_location, best_location),
        ref_before=baseline_eval.ref_metrics,
        ref_after=best_eval.ref_metrics,
        non_ref_before=baseline_eval.non_ref_metrics,
        non_ref_after=best_eval.non_ref_metrics,
        rule_of_three_pan_before=baseline_eval.rule_of_three_pan_mae,
        rule_of_three_pan_after=best_eval.rule_of_three_pan_mae,
    )


def _moving_heads(fixtures) -> list[Any]:
    return [f for f in fixtures if getattr(f, "fixture_type", None) == "moving_head"]


def _build_validation_rows(
    fixtures,
    pois: Sequence[Mapping[str, Any]],
    calibrations,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    moving_heads = _moving_heads(fixtures)

    for poi in pois:
        poi_id = str(poi["id"])
        targets = poi.get("fixtures", {})
        location = poi["location"]

        for fixture in moving_heads:
            target = targets.get(fixture.id)
            if target is None:
                continue

            pan_stored = int(target["pan"])
            tilt_stored = int(target["tilt"])
            pan_calc, tilt_calc = aim_to_dmx(
                fixture,
                location,
                calibrations[fixture.id],
            )

            pan_diff = pan_calc - pan_stored
            tilt_diff = tilt_calc - tilt_stored

            rows.append(
                {
                    "poi": poi_id,
                    "is_ref": is_ref_poi_id(poi_id),
                    "fixture": fixture.id,
                    "x": float(location["x"]),
                    "y": float(location["y"]),
                    "z": float(location["z"]),
                    "pan_stored": pan_stored,
                    "tilt_stored": tilt_stored,
                    "pan_calculated": pan_calc,
                    "tilt_calculated": tilt_calc,
                    "pan_diff": pan_diff,
                    "tilt_diff": tilt_diff,
                    "error_pct": _error_percentage(pan_diff, tilt_diff),
                }
            )

    return rows


def _summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, SetMetrics]]:
    grouped: dict[str, dict[str, dict[str, list[int]]]] = {}

    for row in rows:
        fixture_id = str(row["fixture"])
        group_key = "ref" if row["is_ref"] else "non_ref"

        fixture_group = grouped.setdefault(
            fixture_id,
            {
                "ref": {"pan": [], "tilt": []},
                "non_ref": {"pan": [], "tilt": []},
            },
        )

        fixture_group[group_key]["pan"].append(int(row["pan_diff"]))
        fixture_group[group_key]["tilt"].append(int(row["tilt_diff"]))

    summary: dict[str, dict[str, SetMetrics]] = {}
    for fixture_id, values in grouped.items():
        summary[fixture_id] = {
            "ref": _set_metrics(values["ref"]["pan"], values["ref"]["tilt"]),
            "non_ref": _set_metrics(values["non_ref"]["pan"], values["non_ref"]["tilt"]),
        }

    return summary


def _fmt_float(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def _round_coordinate(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _format_validation_markdown(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Mapping[str, SetMetrics]],
    *,
    position_report_name: str,
    physical_x_validation: Mapping[str, Any],
) -> str:
    lines: list[str] = [
        "# POI Validation",
        "",
        "Calibration source: only `ref_*_*_*` POIs.",
        "Model fitting uses all pairwise vectors between available `ref_*_*_*` anchors.",
        "Difference columns are `calculated - stored`.",
        "Error % is the average absolute pan/tilt error normalized by 16-bit DMX range.",
        (
            "Calculated values use ref-only calibration and accepted fixture-position "
            f"estimates from `{position_report_name}`."
        ),
        "",
        "## Error Summary",
        "",
        "| fixture | set | pan MAE | pan max abs | tilt MAE | tilt max abs | samples |",
        "| ------- | --- | ------- | ----------- | -------- | ------------ | ------- |",
    ]

    for fixture_id in sorted(summary):
        for set_name in ("ref", "non_ref"):
            metrics = summary[fixture_id][set_name]
            sample_count = metrics.pan.samples
            lines.append(
                "| "
                f"{fixture_id} | {set_name} | {_fmt_float(metrics.pan.mae, 1)} | "
                f"{metrics.pan.max_abs} | {_fmt_float(metrics.tilt.mae, 1)} | "
                f"{metrics.tilt.max_abs} | {sample_count} |"
            )

    lines.extend(
        [
            "",
            "## Physical X-Sweep Validation (mini_beam_prism_l/r)",
            "",
        ]
    )

    if not bool(physical_x_validation.get("available")):
        lines.append(f"- unavailable: {physical_x_validation.get('reason', 'unknown reason')}")
    else:
        status = "PASS" if bool(physical_x_validation.get("passed")) else "FAIL"
        lines.append(
            f"- Result: **{status}** (opposite rows {_fmt_float(float(physical_x_validation['opposite_pct']), 1)}%, "
            f"mean magnitude ratio {_fmt_float(float(physical_x_validation['mean_mag_ratio']), 2)})."
        )
        lines.append(
            "- Plane: "
            f"z={_fmt_float(float(physical_x_validation['z']))}, "
            f"y in [{_fmt_float(float(physical_x_validation['y_start']))}, {_fmt_float(float(physical_x_validation['y_end']))}] "
            f"({len(physical_x_validation['rows'])} samples)."
        )
        lines.append(
            "- Pass thresholds: opposite rows >= "
            f"{_fmt_float(PHYSICAL_OPPOSITION_MIN_PCT, 1)}%, "
            f"mean magnitude ratio >= {_fmt_float(PHYSICAL_MAG_RATIO_MIN, 2)}."
        )
        lines.extend(
            [
                "",
                "| y | z | left pan @x0 | left pan @x1 | left delta | right pan @x0 | right pan @x1 | right delta | opposite | magnitude ratio |",
                "| - | - | -----------: | -----------: | ---------: | ------------: | ------------: | ----------: | :------: | --------------: |",
            ]
        )
        for row in physical_x_validation["rows"]:
            lines.append(
                "| "
                f"{_fmt_float(float(row['y']))} | {_fmt_float(float(row['z']))} | "
                f"{row['left_x0_pan']} | {row['left_x1_pan']} | {row['left_delta']:+d} | "
                f"{row['right_x0_pan']} | {row['right_x1_pan']} | {row['right_delta']:+d} | "
                f"{'yes' if row['opposite'] else 'no'} | {_fmt_float(float(row['mag_ratio']), 2)} |"
            )

    lines.extend(
        [
            "",
            "| poi | fixture | x | y | z | pan (stored) | tilt (stored) | pan (calculated) | tilt (calculated) | pan diff | tilt diff | error % |",
            "| --- | ------- | - | - | - | ------------ | ------------- | ---------------- | ----------------- | -------- | --------- | ------- |",
        ]
    )

    for row in rows:
        lines.append(
            "| "
            f"{row['poi']} | {row['fixture']} | {_fmt_float(row['x'])} | {_fmt_float(row['y'])} | {_fmt_float(row['z'])} | "
            f"{row['pan_stored']} | {row['tilt_stored']} | {row['pan_calculated']} | {row['tilt_calculated']} | "
            f"{row['pan_diff']:+d} | {row['tilt_diff']:+d} | {_fmt_float(row['error_pct'], 2)} |"
        )

    return "\n".join(lines) + "\n"


def _improvement(before: float, after: float) -> float:
    if before <= 1e-9:
        return 0.0
    return ((before - after) / before) * 100.0


def _format_results_markdown(
    results: Sequence[FixtureOptimizationResult],
    *,
    bound: float,
    non_ref_max_ratio: float,
    steps: Sequence[float],
    fixtures_json_name: str,
    apply_requested: bool,
    accepted_update_candidates: int,
    applied_changes: Sequence[AppliedFixtureLocationChange],
    missing_fixture_ids: Sequence[str],
    backup_name: str | None,
) -> str:
    accepted = [r for r in results if r.accepted]

    lines: list[str] = [
        "# Fixture Position Sensitivity Results",
        "",
        "## Setup",
        "",
        f"- Calibration source: `ref_*_*_*` only.",
        "- Axis model selection uses all pairwise `ref_*_*_*` vectors (delta-angle vs delta-DMX).",
        f"- Fixture displacement bound: Euclidean distance <= {bound:.3f}.",
        (
            "- Non-ref hold-out guard: candidate is rejected if non-ref pan or tilt "
            f"MAE exceeds {non_ref_max_ratio:.2f}x baseline."
        ),
        "- Secondary tie-break metric: rule-of-three pan midpoint MAE from ref y endpoints.",
        f"- Search step sequence: {', '.join(f'{step:.3f}' for step in steps)}.",
        "",
        "## Conclusions",
        "",
        f"- Accepted fixture position updates: {len(accepted)} of {len(results)} moving heads.",
    ]

    if accepted:
        lines.append("- Estimated real positions improved ref-anchor fit while passing non-ref guardrails.")
    else:
        lines.append("- No fixture position candidate passed acceptance criteria; keep current fixture coordinates.")

    lines.extend(
        [
            "",
            "## Apply Mode Summary",
            "",
            f"- Target fixture data file: `{fixtures_json_name}`.",
            f"- Accepted displacement candidates: {accepted_update_candidates}.",
            f"- Apply mode requested: {'yes' if apply_requested else 'no'}.",
            f"- Applied fixture updates: {len(applied_changes)}.",
        ]
    )

    if backup_name:
        lines.append(f"- Backup file created: `{backup_name}`.")
    elif apply_requested:
        lines.append("- Backup file created: none (no fixtures.json mutation performed).")
    else:
        lines.append("- Backup file created: none (dry-run mode).")

    if missing_fixture_ids:
        lines.append(
            "- Missing fixture IDs in fixtures file: " + ", ".join(sorted(missing_fixture_ids)) + "."
        )

    if applied_changes:
        lines.extend(
            [
                "",
                "| fixture | x (before) | y (before) | z (before) | x (after) | y (after) | z (after) | displacement |",
                "| ------- | ---------- | ---------- | ---------- | --------- | --------- | --------- | ------------ |",
            ]
        )
        for change in sorted(applied_changes, key=lambda item: item.fixture_id):
            lines.append(
                "| "
                f"{change.fixture_id} | {_fmt_float(change.before_location['x'])} | "
                f"{_fmt_float(change.before_location['y'])} | {_fmt_float(change.before_location['z'])} | "
                f"{_fmt_float(change.after_location['x'])} | {_fmt_float(change.after_location['y'])} | {_fmt_float(change.after_location['z'])} | "
                f"{_fmt_float(change.displacement)} |"
            )

    lines.extend(
        [
            "",
            "## Estimated Real Fixture Positions",
            "",
            "| fixture | accepted | x (orig) | y (orig) | z (orig) | x (est) | y (est) | z (est) | dx | dy | dz | displacement | recommendation |",
            "| ------- | -------- | -------- | -------- | -------- | ------- | ------- | ------- | -- | -- | -- | ------------ | -------------- |",
        ]
    )

    for result in sorted(results, key=lambda item: item.fixture_id):
        dx, dy, dz = _location_delta(result.original_location, result.estimated_location)
        recommendation = (
            "propose fixtures.json update"
            if result.accepted and result.displacement > 1e-9
            else "keep current fixtures.json location"
        )

        lines.append(
            "| "
            f"{result.fixture_id} | {'yes' if result.accepted else 'no'} | "
            f"{_fmt_float(result.original_location['x'])} | {_fmt_float(result.original_location['y'])} | {_fmt_float(result.original_location['z'])} | "
            f"{_fmt_float(result.estimated_location['x'])} | {_fmt_float(result.estimated_location['y'])} | {_fmt_float(result.estimated_location['z'])} | "
            f"{_fmt_float(dx)} | {_fmt_float(dy)} | {_fmt_float(dz)} | {_fmt_float(result.displacement)} | {recommendation} |"
        )

    lines.extend(
        [
            "",
            "## Rule-of-Three Midpoint Metric",
            "",
            "| fixture | rule3 pan MAE before | rule3 pan MAE after |",
            "| ------- | -------------------- | ------------------- |",
        ]
    )

    for result in sorted(results, key=lambda item: item.fixture_id):
        lines.append(
            "| "
            f"{result.fixture_id} | {_fmt_float(result.rule_of_three_pan_before, 1)} | "
            f"{_fmt_float(result.rule_of_three_pan_after, 1)} |"
        )

    lines.extend(
        [
            "",
            "## Ref-Only Metrics (Before vs After)",
            "",
            "| fixture | pan MAE before | pan MAE after | pan max abs before | pan max abs after | tilt MAE before | tilt MAE after | tilt max abs before | tilt max abs after |",
            "| ------- | -------------- | ------------- | ------------------ | ----------------- | --------------- | -------------- | ------------------- | ------------------ |",
        ]
    )

    for result in sorted(results, key=lambda item: item.fixture_id):
        lines.append(
            "| "
            f"{result.fixture_id} | {_fmt_float(result.ref_before.pan.mae, 1)} | {_fmt_float(result.ref_after.pan.mae, 1)} | "
            f"{result.ref_before.pan.max_abs} | {result.ref_after.pan.max_abs} | "
            f"{_fmt_float(result.ref_before.tilt.mae, 1)} | {_fmt_float(result.ref_after.tilt.mae, 1)} | "
            f"{result.ref_before.tilt.max_abs} | {result.ref_after.tilt.max_abs} |"
        )

    lines.extend(
        [
            "",
            "## Non-Ref Hold-Out Metrics (Before vs After)",
            "",
            "| fixture | pan MAE before | pan MAE after | tilt MAE before | tilt MAE after | status | notes |",
            "| ------- | -------------- | ------------- | --------------- | -------------- | ------ | ----- |",
        ]
    )

    for result in sorted(results, key=lambda item: item.fixture_id):
        status = "accepted" if result.accepted else "rejected"
        notes = result.reason
        lines.append(
            "| "
            f"{result.fixture_id} | {_fmt_float(result.non_ref_before.pan.mae, 1)} | {_fmt_float(result.non_ref_after.pan.mae, 1)} | "
            f"{_fmt_float(result.non_ref_before.tilt.mae, 1)} | {_fmt_float(result.non_ref_after.tilt.mae, 1)} | "
            f"{status} | {notes} |"
        )

    lines.extend(["", "## Delta Snapshot", ""])

    for result in sorted(results, key=lambda item: item.fixture_id):
        pan_gain = _improvement(result.ref_before.pan.mae, result.ref_after.pan.mae)
        tilt_gain = _improvement(result.ref_before.tilt.mae, result.ref_after.tilt.mae)
        lines.append(
            f"- {result.fixture_id}: ref pan MAE improvement {pan_gain:.1f}%, "
            f"ref tilt MAE improvement {tilt_gain:.1f}%."
        )

    return "\n".join(lines) + "\n"


def _accepted_location_candidates(
    results: Sequence[FixtureOptimizationResult],
) -> dict[str, dict[str, float]]:
    updates: dict[str, dict[str, float]] = {}
    for result in results:
        if not result.accepted:
            continue
        if result.displacement <= 1e-9:
            continue
        updates[result.fixture_id] = {
            "x": _round_coordinate(result.estimated_location["x"]),
            "y": _round_coordinate(result.estimated_location["y"]),
            "z": _round_coordinate(result.estimated_location["z"]),
        }
    return updates


def _apply_estimated_fixture_locations(
    fixtures_json_path: Path,
    *,
    updates: Mapping[str, Mapping[str, float]],
) -> tuple[Path | None, list[AppliedFixtureLocationChange], list[str]]:
    if not updates:
        return None, [], []

    original_text = fixtures_json_path.read_text()
    parsed = json.loads(original_text)
    if not isinstance(parsed, list):
        raise ValueError("fixtures.json must contain a top-level list")

    seen_ids: set[str] = set()
    applied_changes: list[AppliedFixtureLocationChange] = []

    for item in parsed:
        if not isinstance(item, dict):
            continue

        fixture_id = str(item.get("id", ""))
        if fixture_id not in updates:
            continue

        seen_ids.add(fixture_id)
        before_raw = item.get("location", {})
        before_location = {
            "x": _round_coordinate(before_raw.get("x", updates[fixture_id]["x"])),
            "y": _round_coordinate(before_raw.get("y", updates[fixture_id]["y"])),
            "z": _round_coordinate(before_raw.get("z", updates[fixture_id]["z"])),
        }
        after_location = {
            "x": _round_coordinate(updates[fixture_id]["x"]),
            "y": _round_coordinate(updates[fixture_id]["y"]),
            "z": _round_coordinate(updates[fixture_id]["z"]),
        }

        if _location_distance(before_location, after_location) <= 1e-9:
            continue

        item["location"] = dict(after_location)
        applied_changes.append(
            AppliedFixtureLocationChange(
                fixture_id=fixture_id,
                before_location=before_location,
                after_location=after_location,
                displacement=_location_distance(before_location, after_location),
            )
        )

    missing_ids = sorted(set(updates.keys()) - seen_ids)
    if not applied_changes:
        return None, [], missing_ids

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    backup_path = fixtures_json_path.parent / f"{fixtures_json_path.name}.bak.{timestamp}"
    backup_path.write_text(original_text)
    fixtures_json_path.write_text(json.dumps(parsed, indent="\t") + "\n")

    return backup_path, applied_changes, missing_ids


def _run(
    fixtures_json_path: Path,
    pois_json_path: Path,
    ref_coordinates_json_path: Path,
    validation_out: Path,
    results_out: Path,
    *,
    bound: float,
    non_ref_max_ratio: float,
    steps: Sequence[float],
    apply_fixture_estimates: bool,
) -> None:
    fixtures = load_fixtures(str(fixtures_json_path))
    pois = load_all_pois(pois_json_path, ref_coordinates_json_path)

    moving_heads = _moving_heads(fixtures)
    optimization_results: list[FixtureOptimizationResult] = []

    for fixture in moving_heads:
        result = _optimize_fixture(
            fixture,
            pois,
            bound=bound,
            steps=steps,
            non_ref_max_ratio=non_ref_max_ratio,
        )
        optimization_results.append(result)

        fixture.location = dict(result.estimated_location)

    candidate_updates = _accepted_location_candidates(optimization_results)
    backup_path: Path | None = None
    applied_changes: list[AppliedFixtureLocationChange] = []
    missing_fixture_ids: list[str] = []
    if apply_fixture_estimates:
        backup_path, applied_changes, missing_fixture_ids = _apply_estimated_fixture_locations(
            fixtures_json_path,
            updates=candidate_updates,
        )

    calibrations = build_aim_calibrations(fixtures, pois)
    rows = _build_validation_rows(fixtures, pois, calibrations)
    summary = _summarize_rows(rows)

    validation_out.parent.mkdir(parents=True, exist_ok=True)
    physical_x_validation = _physical_x_sweep_validation(fixtures, calibrations, pois)

    validation_out.write_text(
        _format_validation_markdown(
            rows,
            summary,
            position_report_name=results_out.name,
            physical_x_validation=physical_x_validation,
        )
    )

    results_out.parent.mkdir(parents=True, exist_ok=True)
    results_out.write_text(
        _format_results_markdown(
            optimization_results,
            bound=bound,
            non_ref_max_ratio=non_ref_max_ratio,
            steps=steps,
            fixtures_json_name=fixtures_json_path.name,
            apply_requested=apply_fixture_estimates,
            accepted_update_candidates=len(candidate_updates),
            applied_changes=applied_changes,
            missing_fixture_ids=missing_fixture_ids,
            backup_name=backup_path.name if backup_path else None,
        )
    )

    accepted_count = len([result for result in optimization_results if result.accepted])
    print(
        "Generated validation and results reports. "
        f"Accepted fixture updates: {accepted_count}/{len(optimization_results)}"
    )
    print(
        "Apply mode: "
        f"{'enabled' if apply_fixture_estimates else 'disabled'}; "
        f"candidate displacement updates: {len(candidate_updates)}; "
        f"applied updates: {len(applied_changes)}"
    )
    if backup_path:
        print(f"Fixture backup: {backup_path}")
    if missing_fixture_ids:
        print("Missing fixture IDs in fixtures.json: " + ", ".join(missing_fixture_ids))
    for change in sorted(applied_changes, key=lambda item: item.fixture_id):
        print(
            "Applied fixture location update: "
            f"{change.fixture_id} "
            f"({_fmt_float(change.before_location['x'])}, {_fmt_float(change.before_location['y'])}, {_fmt_float(change.before_location['z'])}) -> "
            f"({_fmt_float(change.after_location['x'])}, {_fmt_float(change.after_location['y'])}, {_fmt_float(change.after_location['z'])}), "
            f"displacement={_fmt_float(change.displacement)}"
        )
    print(f"Validation report: {validation_out}")
    print(f"Results report: {results_out}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate POI validation + fixture position sensitivity reports.",
    )
    parser.add_argument(
        "--fixtures-json",
        type=Path,
        default=FIXTURES_JSON,
        help="Path to fixtures.json",
    )
    parser.add_argument(
        "--pois-json",
        type=Path,
        default=POIS_JSON,
        help="Path to pois.json",
    )
    parser.add_argument(
        "--ref-coordinates-json",
        type=Path,
        default=REF_COORDINATES_JSON,
        help="Path to ref_coordinates.json",
    )
    parser.add_argument(
        "--validation-out",
        type=Path,
        default=Path("/workspace/docs/pois-validation.md"),
        help="Output path for validation markdown",
    )
    parser.add_argument(
        "--results-out",
        type=Path,
        default=Path("/workspace/docs/fixture-position-results.md"),
        help="Output path for fixture position results markdown",
    )
    parser.add_argument(
        "--bound",
        type=float,
        default=DEFAULT_BOUND,
        help="Maximum Euclidean displacement for fixture position search",
    )
    parser.add_argument(
        "--non-ref-max-ratio",
        type=float,
        default=DEFAULT_NON_REF_MAX_RATIO,
        help="Maximum allowed non-ref MAE ratio against baseline",
    )
    parser.add_argument(
        "--steps",
        type=str,
        default=",".join(str(step) for step in DEFAULT_STEPS),
        help="Comma-separated search step values",
    )
    parser.add_argument(
        "--apply-fixture-estimates",
        action="store_true",
        help=(
            "Write accepted fixture location estimates into fixtures.json. "
            "Creates a timestamped backup before mutation."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    steps = tuple(float(chunk.strip()) for chunk in args.steps.split(",") if chunk.strip())
    if not steps:
        raise ValueError("At least one search step is required.")

    _run(
        fixtures_json_path=args.fixtures_json,
        pois_json_path=args.pois_json,
        ref_coordinates_json_path=args.ref_coordinates_json,
        validation_out=args.validation_out,
        results_out=args.results_out,
        bound=float(args.bound),
        non_ref_max_ratio=float(args.non_ref_max_ratio),
        steps=steps,
        apply_fixture_estimates=bool(args.apply_fixture_estimates),
    )


if __name__ == "__main__":
    main()
