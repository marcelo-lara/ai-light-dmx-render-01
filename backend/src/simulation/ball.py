from __future__ import annotations

from dataclasses import dataclass


_GROUP_SUFFIX_ORDER = {"left": 0, "center": 1, "right": 2}


@dataclass(frozen=True)
class PathTarget:
    poi_id: str
    location: dict[str, float]


class BallSimulator:
    """
    Simulates a ball bouncing inside the unit cube [0, 1]^3.
    Velocity matches the original frontend animation (per-frame at 50 FPS).
    """

    def __init__(self, speed_multiplier: float = 1.0) -> None:
        self.x: float = 0.5
        self.y: float = 0.5
        self.z: float = 0.5
        self.active_poi_id: str | None = None
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
        self.active_poi_id: str | None = None
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


class POIPathSimulator:
    """Moves the ball between authored POIs, grouping left/center/right sweeps."""

    def __init__(self, pois: list[dict], speed_multiplier: float = 1.0) -> None:
        self.x: float = 0.5
        self.y: float = 0.5
        self.z: float = 0.5
        self._path = self._build_path(pois)
        self._target_index = 0
        self._base_step = 0.0022
        self.speed_multiplier: float = 1.0
        self.active_poi_id: str | None = self._path[0].poi_id if self._path else None
        self.set_speed_multiplier(speed_multiplier)

    def _split_group(self, poi_id: str) -> tuple[str, str | None]:
        group_id, separator, suffix = poi_id.rpartition("_")
        if separator and suffix in _GROUP_SUFFIX_ORDER:
            return group_id, suffix
        return poi_id, None

    def _build_path(self, pois: list[dict]) -> list[PathTarget]:
        grouped: list[tuple[str, list[tuple[str | None, dict]]]] = []
        grouped_index: dict[str, list[tuple[str | None, dict]]] = {}

        for poi in pois:
            group_id, suffix = self._split_group(poi["id"])
            bucket = grouped_index.get(group_id)
            if bucket is None:
                bucket = []
                grouped_index[group_id] = bucket
                grouped.append((group_id, bucket))
            bucket.append((suffix, poi))

        path: list[PathTarget] = []
        for _, bucket in grouped:
            if len(bucket) == 1 and bucket[0][0] is None:
                poi = bucket[0][1]
                path.append(PathTarget(poi_id=poi["id"], location=dict(poi["location"])))
                continue

            ordered = sorted(
                bucket,
                key=lambda item: (_GROUP_SUFFIX_ORDER.get(item[0] or "", len(_GROUP_SUFFIX_ORDER)), item[1]["id"]),
            )
            for _, poi in ordered:
                path.append(PathTarget(poi_id=poi["id"], location=dict(poi["location"])))

        return path

    def set_speed_multiplier(self, speed_multiplier: float) -> None:
        self.speed_multiplier = max(0.1, min(4.0, float(speed_multiplier)))

    def tick(self) -> None:
        if not self._path:
            self.active_poi_id = None
            return

        target = self._path[self._target_index]
        self.active_poi_id = target.poi_id

        delta_x = target.location["x"] - self.x
        delta_y = target.location["y"] - self.y
        delta_z = target.location["z"] - self.z
        distance = (delta_x ** 2 + delta_y ** 2 + delta_z ** 2) ** 0.5
        step = self._base_step * self.speed_multiplier

        if distance <= max(step, 0.003):
            self.x = target.location["x"]
            self.y = target.location["y"]
            self.z = target.location["z"]
            self._target_index = (self._target_index + 1) % len(self._path)
            self.active_poi_id = self._path[self._target_index].poi_id
            return

        scale = step / distance
        self.x += delta_x * scale
        self.y += delta_y * scale
        self.z += delta_z * scale

    def position(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


def create_simulator(mode: str, speed_multiplier: float, pois: list[dict] | None = None):
    if mode == "floor":
        return FloorBallSimulator(speed_multiplier=speed_multiplier)
    if mode == "poi":
        return POIPathSimulator(pois or [], speed_multiplier=speed_multiplier)
    return BallSimulator(speed_multiplier=speed_multiplier)
