# Fixture Position Sensitivity Results

## Setup

- Calibration source: `ref_*_*_*` only.
- Axis model selection uses all pairwise `ref_*_*_*` vectors (delta-angle vs delta-DMX).
- Fixture displacement bound: Euclidean distance <= 0.200.
- Non-ref hold-out guard: candidate is rejected if non-ref pan or tilt MAE exceeds 1.25x baseline.
- Secondary tie-break metric: rule-of-three pan midpoint MAE from ref y endpoints.
- Search step sequence: 0.050, 0.020, 0.010, 0.005.

## Conclusions

- Accepted fixture position updates: 0 of 3 moving heads.
- No fixture position candidate passed acceptance criteria; keep current fixture coordinates.

## Apply Mode Summary

- Target fixture data file: `fixtures.json`.
- Accepted displacement candidates: 0.
- Apply mode requested: no.
- Applied fixture updates: 0.
- Backup file created: none (dry-run mode).

## Estimated Real Fixture Positions

| fixture | accepted | x (orig) | y (orig) | z (orig) | x (est) | y (est) | z (est) | dx | dy | dz | displacement | recommendation |
| ------- | -------- | -------- | -------- | -------- | ------- | ------- | ------- | -- | -- | -- | ------------ | -------------- |
| head_el150 | no | 0.570 | 0.100 | 0.770 | 0.570 | 0.100 | 0.770 | 0.000 | 0.000 | 0.000 | 0.000 | keep current fixtures.json location |
| mini_beam_prism_l | no | 0.050 | 0.370 | 0.825 | 0.050 | 0.370 | 0.825 | 0.000 | 0.000 | 0.000 | 0.000 | keep current fixtures.json location |
| mini_beam_prism_r | no | 0.985 | 0.200 | 0.800 | 0.985 | 0.200 | 0.800 | 0.000 | 0.000 | 0.000 | 0.000 | keep current fixtures.json location |

## Rule-of-Three Midpoint Metric

| fixture | rule3 pan MAE before | rule3 pan MAE after |
| ------- | -------------------- | ------------------- |
| head_el150 | 5410.7 | 5410.7 |
| mini_beam_prism_l | 7987.7 | 7987.7 |
| mini_beam_prism_r | 8888.7 | 8888.7 |

## Ref-Only Metrics (Before vs After)

| fixture | pan MAE before | pan MAE after | pan max abs before | pan max abs after | tilt MAE before | tilt MAE after | tilt max abs before | tilt max abs after |
| ------- | -------------- | ------------- | ------------------ | ----------------- | --------------- | -------------- | ------------------- | ------------------ |
| head_el150 | 5597.3 | 5597.3 | 10837 | 10837 | 3584.6 | 3584.6 | 9862 | 9862 |
| mini_beam_prism_l | 3988.9 | 3988.9 | 6113 | 6113 | 3403.9 | 3403.9 | 7028 | 7028 |
| mini_beam_prism_r | 3794.0 | 3794.0 | 6216 | 6216 | 8384.1 | 8384.1 | 16274 | 16274 |

## Non-Ref Hold-Out Metrics (Before vs After)

| fixture | pan MAE before | pan MAE after | tilt MAE before | tilt MAE after | status | notes |
| ------- | -------------- | ------------- | --------------- | -------------- | ------ | ----- |
| head_el150 | 6425.1 | 6425.1 | 5566.5 | 5566.5 | rejected | candidate rejected: ref MAE total did not improve (10844.9 >= 9181.9) |
| mini_beam_prism_l | 3324.9 | 3324.9 | 3119.8 | 3119.8 | rejected | candidate rejected: tilt non-ref MAE 4968.6 exceeded limit 3899.8 (1.25x baseline) |
| mini_beam_prism_r | 6918.0 | 6918.0 | 5202.6 | 5202.6 | rejected | candidate rejected: ref MAE total did not improve (12318.4 >= 12178.1) |

## Delta Snapshot

- head_el150: ref pan MAE improvement 0.0%, ref tilt MAE improvement 0.0%.
- mini_beam_prism_l: ref pan MAE improvement 0.0%, ref tilt MAE improvement 0.0%.
- mini_beam_prism_r: ref pan MAE improvement 0.0%, ref tilt MAE improvement 0.0%.
