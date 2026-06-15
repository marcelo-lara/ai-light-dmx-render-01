# Follow-Up Memory

This note captures the two deferred follow-ups from the last simulation pass so they can be implemented later without re-mapping the codebase.

## Current Baseline

- Simulation modes: `3d`, `floor`, `poi`
- Backend moving-head aim path: geometry-derived pan/tilt calibrated from authored POI presets
- Frontend POI behavior: `POI Glide` mode highlights the backend-reported active POI, but target selection is still automatic only

## 1. Click-To-Select POI Target

### Goal

Let the operator pick a POI directly from the canvas or sidebar instead of relying only on the automatic POI glide sequence.

### Expected Behavior

- Clicking a POI marker in the 3D view should select that POI as the active target.
- Selecting a POI from the sidebar should do the same thing.
- In `poi` mode, the simulator should move slowly toward the chosen POI.
- Grouped POIs like `_left`, `_center`, `_right` should still be supported.
- A direct selection should define whether the system:
  - jumps to a single explicit POI target only, or
  - jumps to the grouped sweep containing that POI and continues left-to-right.

### Recommended Implementation Direction

- Backend:
  - Extend the simulator control message set with an explicit POI selection command.
  - Track a selected target or selected group in app state.
  - Update `POIPathSimulator` so it can:
    - seek a specific POI immediately, or
    - rebuild its current traversal starting from a selected grouped POI.
- Frontend:
  - Make POI markers clickable.
  - Add a sidebar list or select input for POIs.
  - Show the difference between:
    - current active POI from backend frame updates
    - user-selected target POI

### Likely Files

- `backend/src/simulation/ball.py`
- `backend/src/api/websocket.py`
- `backend/src/app.py`
- `frontend/src/components/POIMarker.tsx`
- `frontend/src/components/StageCanvas.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/hooks/useFixtures.ts`

### Acceptance Criteria

- A user can select a POI from the UI.
- The backend acknowledges that selection and starts moving toward it.
- The selected POI is visibly distinct from the merely active/currently reached POI.
- Grouped POIs behave predictably and do not break the automatic glide path.

## 2. Per-Fixture Aim Trim Controls

### Goal

Add explicit per-fixture trim controls on top of the new geometry calibration so real fixture offsets can be corrected without rewriting POI data.

### Problem To Solve

The new calibration path is physically better than POI interpolation, but real fixtures may still show mechanical offsets or mounting variance. Those need fixture-local correction values.

### Expected Behavior

- Each moving head should support manual trim adjustments for pan and tilt.
- Trims should apply after geometry solve plus calibration.
- Trim values should be visible and editable from the UI.
- Trim values should persist across restart, ideally in a small config file rather than hardcoded constants.

### Recommended Implementation Direction

- Backend:
  - Add a trim store keyed by fixture id.
  - Apply trim offsets after `aim_to_dmx(...)` returns calibrated pan/tilt values.
  - Clamp the final result to `0..65535`.
  - Add websocket messages for updating trim values.
  - Persist trims in JSON under `data/fixtures/` or a neighboring config location.
- Frontend:
  - Add pan trim and tilt trim inputs per moving head in the sidebar.
  - Show current trim values.
  - Send live updates over websocket.

### Likely Files

- `backend/src/spatial/aim.py`
- `backend/src/api/websocket.py`
- `backend/src/app.py`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/hooks/useFixtures.ts`
- new trim data file, likely under `data/fixtures/`

### Acceptance Criteria

- Trim adjustments affect only the selected fixture.
- Trim adjustments stack on top of the geometry-calibrated aim path.
- Trim values survive container restart.
- Zero trims reproduce the current behavior exactly.

## 3. Manual Fixture Calibration Helper

### Goal

Provide a guided helper that estimates fixture position and orientation in the rig from operator-driven manual aiming captures, then proposes updates for `fixtures.json`.

### Problem To Solve

Mount labels (`wall_left`, `wall_right`, `wall_back`) are useful coarse orientation hints, but physical placement and orientation offsets differ per fixture. Manual aiming captures should be convertible into stable pose estimates.

### Expected Behavior

- Operator selects a fixture and enters calibration mode.
- UI prompts a sequence of known target points (`x,y,z`) and asks the operator to manually aim to each point.
- At each step, the helper captures the fixture's current pan/tilt DMX values.
- After enough captures, backend estimates fixture pose parameters:
  - position (`x`, `y`, `z`)
  - orientation (`yaw`, `pitch`, `roll`) or equivalent local-frame basis
  - optional pan/tilt zero offsets
- Helper reports residual error against all captured points plus hold-out validation points.
- Helper writes a dry-run report first, then supports explicit apply to persist accepted updates.

### Recommended Capture Sequence

- Start with easy anchors to establish rough pan direction:
  - aim to `x=0,y=0`
  - aim to `x=1,y=0`
- Continue with spread points across the room volume (including different `z`) to solve full pose.
- Minimum practical dataset: 6 points; preferred: 8+ points using `ref_*_*_*` anchors from `backend/data/ref_coordinates.json`.

### Recommended Implementation Direction

- Backend:
  - Add calibration session state keyed by fixture id.
  - Add websocket commands for `start_calibration`, `capture_point`, `solve_calibration`, `apply_calibration`.
  - Implement least-squares solver using all captured vectors between reference targets.
  - Emit residual summary and candidate fixture updates.
  - Persist only on explicit apply with backup of `fixtures.json`.
- Frontend:
  - Add wizard UI in sidebar for step-by-step capture.
  - Show current step target coordinates and capture status.
  - Show solve summary with accept/reject controls.

### Likely Files

- `backend/src/spatial/aim.py`
- `backend/src/api/websocket.py`
- `backend/src/app.py`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/hooks/useFixtures.ts`
- `data/fixtures/fixtures.json`

### Acceptance Criteria

- Wizard can capture multiple manual aim points per fixture.
- Solver outputs a candidate fixture pose with error metrics.
- Dry-run report is generated before any file mutation.
- Applying calibration updates `fixtures.json` only after explicit confirmation.
- Re-running validation (`docs/pois-validation.md`) shows measurable improvement on ref anchors.

## Open Decisions

- Whether a direct POI click should select a single stop or a grouped sweep.
- Whether trim units in the UI should be raw DMX values or angle-like user-friendly values.
- Whether trims should be saved automatically on every change or only through an explicit save action.

## Suggested Order

1. Implement explicit POI selection first.
2. Validate the interaction model for grouped POIs.
3. Add per-fixture trim storage and backend application.
4. Add UI controls for live trim editing.
5. Validate on physical heads with DMX output enabled.