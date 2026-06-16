from __future__ import annotations

import json

from calibrate_fixture_positions import _apply_estimated_fixture_pose_updates


def test_apply_estimated_fixture_pose_updates_writes_location_and_orientation(tmp_path) -> None:
    fixtures_json = tmp_path / "fixtures.json"
    fixtures_json.write_text(
        json.dumps(
            [
                {
                    "id": "fixture_a",
                    "name": "Fixture A",
                    "fixture": "fixture.moving_head.test",
                    "base_channel": 1,
                    "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                }
            ]
        )
    )

    backup_path, applied_ids, missing_ids = _apply_estimated_fixture_pose_updates(
        fixtures_json,
        updates={
            "fixture_a": {
                "location": {"x": 0.1, "y": 0.2, "z": 0.3},
                "orientation": {
                    "yaw": 1.0,
                    "pitch": 2.0,
                    "roll": 3.0,
                    "pan_sign": -1,
                    "tilt_reversed": True,
                },
            }
        },
    )

    assert backup_path is not None
    assert backup_path.exists()
    assert applied_ids == ["fixture_a"]
    assert missing_ids == []

    parsed = json.loads(fixtures_json.read_text())
    assert parsed[0]["location"] == {"x": 0.1, "y": 0.2, "z": 0.3}
    assert parsed[0]["orientation"] == {
        "yaw": 1.0,
        "pitch": 2.0,
        "roll": 3.0,
        "pan_sign": -1,
        "tilt_reversed": True,
    }