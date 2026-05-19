from pathlib import Path

# Data paths (Docker volume mounts from data/)
FIXTURES_JSON = Path("/app/fixtures/fixtures.json")
POIS_JSON = Path("/app/fixtures/pois.json")

# Simulation
FRAME_RATE = 50          # FPS
FRAME_INTERVAL = 1 / FRAME_RATE
