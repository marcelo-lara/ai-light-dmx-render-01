from pathlib import Path

# Runtime data paths in Docker.
FIXTURES_JSON = Path("/app/fixtures/fixtures.json")
POIS_JSON = Path("/app/data/pois.json")
REF_COORDINATES_JSON = Path("/app/data/ref_coordinates.json")
VIRTUAL_CENTER_MEASUREMENTS_JSON = Path("/app/data/virtual_center_measurements.json")

# Simulation
FRAME_RATE = 50          # FPS
FRAME_INTERVAL = 1 / FRAME_RATE

# Art-Net
ARTNET_IP = "192.168.10.221"
ARTNET_PORT = 6454
ARTNET_UNIVERSE = 0
