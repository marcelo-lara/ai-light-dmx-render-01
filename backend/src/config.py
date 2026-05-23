from pathlib import Path

# Data paths (Docker volume mounts from data/)
FIXTURES_JSON = Path("/app/fixtures/fixtures.json")
POIS_JSON = Path("/app/fixtures/pois.json")

# Simulation
FRAME_RATE = 50          # FPS
FRAME_INTERVAL = 1 / FRAME_RATE

# Art-Net
ARTNET_IP = "192.168.10.221"
ARTNET_PORT = 6454
ARTNET_UNIVERSE = 0
