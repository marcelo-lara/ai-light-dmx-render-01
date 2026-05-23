class BallSimulator:
    """
    Simulates a ball bouncing inside the unit cube [0, 1]³.
    Velocity matches the original frontend animation (per-frame at 50 FPS).
    """

    def __init__(self, speed_multiplier: float = 1.0) -> None:
        self.x: float = 0.5
        self.y: float = 0.5
        self.z: float = 0.5
        self._base_vx: float = 0.004
        self._base_vy: float = 0.0031
        self._base_vz: float = 0.0025
        self.speed_multiplier: float = 1.0
        self.set_speed_multiplier(speed_multiplier)

    def set_speed_multiplier(self, speed_multiplier: float) -> None:
        self.speed_multiplier = max(0.1, min(4.0, float(speed_multiplier)))

    def tick(self) -> None:
        """Advance one frame: move, then bounce off unit-cube walls."""
        vx = self._base_vx * self.speed_multiplier
        vy = self._base_vy * self.speed_multiplier
        vz = self._base_vz * self.speed_multiplier

        self.x += vx
        self.y += vy
        self.z += vz

        if self.x <= 0.0 or self.x >= 1.0:
            self._base_vx *= -1
            self.x = max(0.0, min(1.0, self.x))

        if self.y <= 0.0 or self.y >= 1.0:
            self._base_vy *= -1
            self.y = max(0.0, min(1.0, self.y))

        if self.z <= 0.0 or self.z >= 1.0:
            self._base_vz *= -1
            self.z = max(0.0, min(1.0, self.z))

    def position(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


class FloorBallSimulator:
    """
    Simulates a ball bouncing on the floor (z = 0), moving only in x and y.
    """

    def __init__(self, speed_multiplier: float = 1.0) -> None:
        self.x: float = 0.5
        self.y: float = 0.5
        self.z: float = 0.0
        self._base_vx: float = 0.004
        self._base_vy: float = 0.0031
        self.speed_multiplier: float = 1.0
        self.set_speed_multiplier(speed_multiplier)

    def set_speed_multiplier(self, speed_multiplier: float) -> None:
        self.speed_multiplier = max(0.1, min(4.0, float(speed_multiplier)))

    def tick(self) -> None:
        """Advance one frame: move in x/y, bounce off unit-square walls."""
        vx = self._base_vx * self.speed_multiplier
        vy = self._base_vy * self.speed_multiplier

        self.x += vx
        self.y += vy

        if self.x <= 0.0 or self.x >= 1.0:
            self._base_vx *= -1
            self.x = max(0.0, min(1.0, self.x))

        if self.y <= 0.0 or self.y >= 1.0:
            self._base_vy *= -1
            self.y = max(0.0, min(1.0, self.y))

    def position(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}
