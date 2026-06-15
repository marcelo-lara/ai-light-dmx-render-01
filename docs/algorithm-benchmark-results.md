# XYZ-to-DMX Algorithm Benchmark Results

This document contains the validation results for different Pan/Tilt calculation strategies evaluated against manually-aimed ground-truth POIs.

## Overall Performance (Mean Absolute Error)

| Strategy | Avg Pan Error (ticks) | Avg Tilt Error (ticks) |
|---|---|---|
| Trilinear Interpolation | 2021.67 | 2291.77 |
| Inverse Kinematics (Trigonometry) | 4104.35 | 4604.40 |

## Detailed POI Discrepancies

Difference between algorithm calculation and mathematically stored Pan/Tilt ticks for each validation pair.

### Trilinear Interpolation
| POI ID | Fixture | Pan Diff | Tilt Diff |
|---|---|---|---|
| server | mini_beam_prism_l | 2260 | 13 |
| server | head_el150 | 3005 | 6777 |
| server | mini_beam_prism_r | 3127 | 1375 |
| tv | mini_beam_prism_l | 2110 | 67 |
| tv | head_el150 | 2397 | 5403 |
| tv | mini_beam_prism_r | 2539 | 229 |
| mic | mini_beam_prism_l | 2525 | 53 |
| mic | head_el150 | 2804 | 6177 |
| mic | mini_beam_prism_r | 2844 | 141 |
| piano_left | mini_beam_prism_l | 1023 | 11 |
| piano_left | head_el150 | 1427 | 3517 |
| piano_left | mini_beam_prism_r | 1705 | 1009 |
| piano_center | mini_beam_prism_l | 1101 | 34 |
| piano_center | head_el150 | 1340 | 3236 |
| piano_center | mini_beam_prism_r | 1570 | 310 |
| piano_right | mini_beam_prism_l | 1185 | 51 |
| piano_right | head_el150 | 1303 | 3036 |
| piano_right | mini_beam_prism_r | 1460 | 262 |
| dark | mini_beam_prism_l | 1311 | 39 |
| dark | head_el150 | 2321 | 5437 |
| dark | mini_beam_prism_r | 2504 | 2745 |
| dark_desk | mini_beam_prism_l | 2328 | 1421 |
| dark_desk | mini_beam_prism_r | 3009 | 7165 |
| dark_desk | head_el150 | 544 | 4233 |
| table_left | mini_beam_prism_l | 299 | 26 |
| table_left | head_el150 | 250 | 632 |
| table_left | mini_beam_prism_r | 328 | 333 |
| table_center | mini_beam_prism_l | 0 | 0 |
| table_center | head_el150 | 0 | 0 |
| table_center | mini_beam_prism_r | 0 | 0 |
| table_right | mini_beam_prism_l | 256 | 98 |
| table_right | head_el150 | 267 | 196 |
| table_right | mini_beam_prism_r | 90 | 1717 |
| inblue | mini_beam_prism_l | 306 | 218 |
| inblue | head_el150 | 992 | 2652 |
| inblue | mini_beam_prism_r | 1142 | 6342 |
| inblue_desk | mini_beam_prism_l | 2440 | 136 |
| inblue_desk | mini_beam_prism_r | 5024 | 5641 |
| inblue_desk | head_el150 | 37 | 3709 |
| guest_desk | mini_beam_prism_l | 849 | 410 |
| guest_desk | head_el150 | 938 | 3346 |
| guest_desk | mini_beam_prism_r | 1521 | 3091 |
| sofa_left | mini_beam_prism_l | 821 | 126 |
| sofa_left | head_el150 | 1318 | 2242 |
| sofa_left | mini_beam_prism_r | 589 | 1381 |
| sofa_center | mini_beam_prism_l | 379 | 125 |
| sofa_center | head_el150 | 1316 | 1962 |
| sofa_center | mini_beam_prism_r | 147 | 1442 |
| sofa_right | mini_beam_prism_l | 55 | 131 |
| sofa_right | head_el150 | 1373 | 1780 |
| sofa_right | mini_beam_prism_r | 266 | 1352 |
| wall_art_left | mini_beam_prism_l | 1515 | 68 |
| wall_art_left | head_el150 | 3135 | 4205 |
| wall_art_left | mini_beam_prism_r | 1127 | 984 |
| wall_art_center | mini_beam_prism_l | 761 | 128 |
| wall_art_center | head_el150 | 3325 | 3364 |
| wall_art_center | mini_beam_prism_r | 360 | 1400 |
| wall_art_right | mini_beam_prism_l | 114 | 189 |
| wall_art_right | head_el150 | 3554 | 2744 |
| wall_art_right | mini_beam_prism_r | 274 | 1593 |
| door | mini_beam_prism_l | 1116 | 436 |
| door | head_el150 | 4618 | 2234 |
| door | mini_beam_prism_r | 1423 | 1541 |
| board_right | mini_beam_prism_l | 2298 | 422 |
| board_right | head_el150 | 3350 | 5771 |
| board_right | mini_beam_prism_r | 1745 | 10153 |
| board_center | mini_beam_prism_l | 2388 | 473 |
| board_center | head_el150 | 4445 | 4463 |
| board_center | mini_beam_prism_r | 145 | 5844 |
| board_left | mini_beam_prism_l | 2456 | 548 |
| board_left | head_el150 | 5723 | 3452 |
| board_left | mini_beam_prism_r | 1366 | 1995 |
| ceiling_station | mini_beam_prism_l | 14445 | 8274 |
| ceiling_station | mini_beam_prism_r | 18634 | 8978 |
| ceiling_station | head_el150 | 4563 | 10795 |


### Inverse Kinematics (Trigonometry)
| POI ID | Fixture | Pan Diff | Tilt Diff |
|---|---|---|---|
| server | mini_beam_prism_l | 4999 | 540 |
| server | head_el150 | 6171 | 14336 |
| server | mini_beam_prism_r | 8403 | 2228 |
| tv | mini_beam_prism_l | 1271 | 2047 |
| tv | head_el150 | 7840 | 4354 |
| tv | mini_beam_prism_r | 6639 | 1952 |
| mic | mini_beam_prism_l | 939 | 2782 |
| mic | head_el150 | 8821 | 1915 |
| mic | mini_beam_prism_r | 7665 | 737 |
| piano_left | mini_beam_prism_l | 2342 | 2784 |
| piano_left | head_el150 | 6443 | 2445 |
| piano_left | mini_beam_prism_r | 10121 | 779 |
| piano_center | mini_beam_prism_l | 76 | 4871 |
| piano_center | head_el150 | 7174 | 3688 |
| piano_center | mini_beam_prism_r | 10046 | 81 |
| piano_right | mini_beam_prism_l | 1310 | 2330 |
| piano_right | head_el150 | 7677 | 3689 |
| piano_right | mini_beam_prism_r | 9945 | 221 |
| dark | mini_beam_prism_l | 942 | 3394 |
| dark | head_el150 | 5866 | 5268 |
| dark | mini_beam_prism_r | 896 | 2659 |
| dark_desk | mini_beam_prism_l | 5863 | 0 |
| dark_desk | mini_beam_prism_r | 2158 | 9315 |
| dark_desk | head_el150 | 4402 | 1147 |
| table_left | mini_beam_prism_l | 2581 | 3341 |
| table_left | head_el150 | 5668 | 7963 |
| table_left | mini_beam_prism_r | 63 | 2022 |
| table_center | mini_beam_prism_l | 2871 | 2116 |
| table_center | head_el150 | 5414 | 5893 |
| table_center | mini_beam_prism_r | 57 | 4179 |
| table_right | mini_beam_prism_l | 2803 | 397 |
| table_right | head_el150 | 5276 | 1214 |
| table_right | mini_beam_prism_r | 202 | 6625 |
| inblue | mini_beam_prism_l | 4862 | 887 |
| inblue | head_el150 | 4558 | 5015 |
| inblue | mini_beam_prism_r | 1441 | 8096 |
| inblue_desk | mini_beam_prism_l | 4433 | 1638 |
| inblue_desk | mini_beam_prism_r | 4993 | 6342 |
| inblue_desk | head_el150 | 3264 | 45 |
| guest_desk | mini_beam_prism_l | 4311 | 8650 |
| guest_desk | head_el150 | 3648 | 5862 |
| guest_desk | mini_beam_prism_r | 2698 | 3061 |
| sofa_left | mini_beam_prism_l | 2588 | 699 |
| sofa_left | head_el150 | 3782 | 6093 |
| sofa_left | mini_beam_prism_r | 2239 | 3604 |
| sofa_center | mini_beam_prism_l | 2474 | 941 |
| sofa_center | head_el150 | 4642 | 2980 |
| sofa_center | mini_beam_prism_r | 3106 | 390 |
| sofa_right | mini_beam_prism_l | 2315 | 1395 |
| sofa_right | head_el150 | 5196 | 453 |
| sofa_right | mini_beam_prism_r | 2996 | 2771 |
| wall_art_left | mini_beam_prism_l | 2440 | 686 |
| wall_art_left | head_el150 | 4282 | 6400 |
| wall_art_left | mini_beam_prism_r | 6050 | 1915 |
| wall_art_center | mini_beam_prism_l | 1990 | 1172 |
| wall_art_center | head_el150 | 5274 | 7691 |
| wall_art_center | mini_beam_prism_r | 4725 | 3148 |
| wall_art_right | mini_beam_prism_l | 1546 | 1697 |
| wall_art_right | head_el150 | 5869 | 8570 |
| wall_art_right | mini_beam_prism_r | 3578 | 6799 |
| door | mini_beam_prism_l | 578 | 3027 |
| door | head_el150 | 6512 | 9573 |
| door | mini_beam_prism_r | 1547 | 10933 |
| board_right | mini_beam_prism_l | 2204 | 12294 |
| board_right | head_el150 | 4486 | 8826 |
| board_right | mini_beam_prism_r | 2446 | 14338 |
| board_center | mini_beam_prism_l | 1156 | 9743 |
| board_center | head_el150 | 5311 | 9023 |
| board_center | mini_beam_prism_r | 1566 | 13866 |
| board_left | mini_beam_prism_l | 369 | 6877 |
| board_left | head_el150 | 6072 | 9785 |
| board_left | mini_beam_prism_r | 590 | 13428 |
| ceiling_station | mini_beam_prism_l | 9263 | 6390 |
| ceiling_station | mini_beam_prism_r | 12409 | 5398 |
| ceiling_station | head_el150 | 1073 | 7517 |


