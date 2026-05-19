class BallSimulator:
    """
    Simulates a ball bouncing inside the unit cube [0, 1]³.
    Velocity matches the original frontend animation (per-frame at 50 FPS).
    """

    def __init__(self) -> None:
        self.x: float = 0.5
        self.y: float = 0.5
        self.z: float = 0.5
        self._vx: float = 0.004
        self._vy: float = 0.0031
        self._vz: float = 0.0025

    def tick(self) -> None:
        """Advance one frame: move, then bounce off unit-cube walls."""
        self.x += self._vx
        self.y += self._vy
        self.z += self._vz

        if self.x <= 0.0 or self.x >= 1.0:
            self._vx *= -1
            self.x = max(0.0, min(1.0, self.x))

        if self.y <= 0.0 or self.y >= 1.0:
            self._vy *= -1
            self.y = max(0.0, min(1.0, self.y))

        if self.z <= 0.0 or self.z >= 1.0:
            self._vz *= -1
            self.z = max(0.0, min(1.0, self.z))

    def position(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}
