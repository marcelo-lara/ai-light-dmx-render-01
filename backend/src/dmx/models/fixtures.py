"""
Fixture class hierarchy.

Two levels:
  BaseFixture (abstract)
  ├── MovingHead  — pan/tilt 16-bit, stepped enum wheels (color, gobo, prism)
  └── ParCan      — RGB + dim + strobe

Each class is data-driven: model differences (channel layout, mappings,
physical travel times) live in the JSON templates under data/fixtures/.
Instantiate via the factory functions at the bottom of this module.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Union

from src.config import FIXTURES_JSON

# Fixtures are mounted at /app/fixtures in Docker (docker-compose volume).
_DATA_FIXTURES_DIR = FIXTURES_JSON.parent

# ---------------------------------------------------------------------------
# Color wheel label → hex colour string
# ---------------------------------------------------------------------------

#: Maps colour-wheel label strings (as they appear in fixture mapping JSONs)
#: to their nearest perceptual hex equivalent.  Used by MovingHead.color_hex.
COLOR_WHEEL_HEX: dict[str, str] = {
    "White":      "#FFFFFF",
    "Open/White": "#FFFFFF",
    "Open":       "#FFFFFF",
    "Orange":     "#FF8800",
    "Cyan":       "#00FFFF",
    "Purple":     "#8800CC",
    "Yellow":     "#FFFF00",
    "Green":      "#00FF00",
    "Blue":       "#0000FF",
    "Red":        "#FF0000",
    "Off":        "#000000",
}


def _normalize_orientation(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None

    required = ("yaw", "pitch", "roll", "pan_sign", "tilt_reversed")
    if any(key not in raw for key in required):
        return None

    try:
        pan_sign = int(raw["pan_sign"])
        if pan_sign not in (-1, 1):
            return None

        return {
            "yaw": float(raw["yaw"]),
            "pitch": float(raw["pitch"]),
            "roll": float(raw["roll"]),
            "pan_sign": pan_sign,
            "tilt_reversed": bool(raw["tilt_reversed"]),
        }
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseFixture(ABC):
    """
    Shared contract for all fixture types.

    Parameters
    ----------
    template : dict
        Parsed contents of a `fixture.<type>.<model>.json` file.
    instance : dict
        A single row from `fixtures.json` (id, name, fixture, base_channel, location).
    """

    def __init__(self, template: dict, instance: dict) -> None:
        # Instance metadata
        self.id: str = instance["id"]
        self.name: str = instance["name"]
        self.fixture_ref: str = instance["fixture"]
        self.base_channel: int = instance["base_channel"]   # 1-based
        self.location: dict = instance["location"]
        self.mount: str | None = instance.get("mount")  # wall_left / wall_right / wall_back / None
        self.orientation: dict[str, Any] | None = _normalize_orientation(instance.get("orientation"))

        # Template data
        self.fixture_type: str = template["type"]
        self.beam_angle_degrees: float = template.get("beam_angle_degrees", 10.0)
        self.channels: dict[str, int] = template["channels"]   # name → 0-based offset
        self.meta_channels: dict = template.get("meta_channels", {})
        self.mappings: dict = template.get("mappings", {})

        # Absolute 1-based DMX addresses for every named channel
        self.absolute_channels: dict[str, int] = {
            name: self.base_channel + offset
            for name, offset in self.channels.items()
        }

        # Internal per-channel state (offset-indexed, pre-filled with arm values)
        self._state: dict[str, int] = self._init_state()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _init_state(self) -> dict[str, int]:
        """
        Seed the state dict with arm values from meta_channels.
        Channels not referenced by any meta_channel start at 0.
        """
        state: dict[str, int] = {name: 0 for name in self.channels}
        for meta in self.meta_channels.values():
            arm = meta.get("arm")
            if arm is None:
                continue
            ch = meta.get("channel")
            if ch and ch in state:
                state[ch] = int(arm) & 0xFF
        return state

    def resolve_enum(self, meta_key: str, value: Union[str, int]) -> int:
        """
        Resolve an enum meta-channel value to its raw DMX byte.

        Accepts either a label string (e.g. ``"Red"``, ``"On"``) or a raw int.
        The `step` flag (stepped wheel positions) is a UI hint only; encoding
        is identical to a non-stepped enum.

        Raises
        ------
        KeyError
            If ``value`` is a string that has no match in the mapping.
        """
        if isinstance(value, int):
            return value & 0xFF

        meta = self.meta_channels.get(meta_key, {})
        mapping_key = meta.get("mapping")
        if not mapping_key:
            raise KeyError(f"Meta channel '{meta_key}' has no mapping; pass a raw int.")

        mapping = self.mappings.get(mapping_key, {})
        for dmx_str, label in mapping.items():
            if label == value:
                return int(dmx_str)

        raise KeyError(
            f"Label '{value}' not found in mapping '{mapping_key}'. "
            f"Valid labels: {list(mapping.values())}"
        )

    def _u16_value(self, meta_key: str) -> int:
        """Return the current 16-bit value for a meta channel, or ``0`` if absent."""
        meta = self.meta_channels.get(meta_key)
        if meta is None or meta.get("kind") != "u16":
            return 0
        ch_msb, ch_lsb = meta["channels"]
        return ((self._state.get(ch_msb, 0) & 0xFF) << 8) | (self._state.get(ch_lsb, 0) & 0xFF)

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def color_hex(self) -> str:
        """
        Current output colour as a ``#RRGGBB`` hex string.

        - ``ParCan``: derived from the live RGB channel bytes.
        - ``MovingHead``: derived from the colour-wheel position via
          :data:`COLOR_WHEEL_HEX`.
        """
        ...

    @property
    @abstractmethod
    def intensity(self) -> float:
        """
        Current output intensity as a float in ``[0.0, 1.0]``,
        derived from the fixture's dim / shutter channel (``dim / 255``).
        """
        ...

    @abstractmethod
    def set(self, meta_key: str, value: Union[str, int, tuple]) -> None:
        """Set a meta-channel by label or raw value and update internal state."""
        ...

    @abstractmethod
    def to_dmx_buffer(self) -> bytearray:
        """
        Return a ``bytearray`` of length ``channel_count`` representing
        the fixture's current DMX state, indexed by 0-based channel offset.
        """
        ...

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict suitable for the WebSocket init message."""
        return {
            "id": self.id,
            "name": self.name,
            "fixture": self.fixture_ref,
            "fixture_type": self.fixture_type,
            "base_channel": self.base_channel,
            "location": self.location,
            "mount": self.mount,
            "orientation": self.orientation,
            "beam_angle_degrees": self.beam_angle_degrees,
            "channel_count": self.channel_count,
            "absolute_channels": self.absolute_channels,
            "color_hex": self.color_hex,
            "intensity": self.intensity,
        }

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.id!r} "
            f"base_ch={self.base_channel} channels={self.channel_count}>"
        )


# ---------------------------------------------------------------------------
# MovingHead
# ---------------------------------------------------------------------------

class MovingHead(BaseFixture):
    """
    Moving-head fixture (pan/tilt, color wheel, gobo wheel, optional prism).

    Handles:
    - 16-bit pan/tilt split across MSB + LSB channels
    - Stepped enum wheels: color, gobo, prism (label → DMX value via mappings)
    - u8 channels: dim, speed, strobe/shutter
    - Physical movement time estimation

    Models: ``mini_beam_prism``, ``head_el150`` (and any future moving-head model).
    """

    FIXTURE_TYPE = "moving_head"

    def __init__(self, template: dict, instance: dict) -> None:
        super().__init__(template, instance)

        phys = template.get("physical_movement", {})
        self.pan_full_travel_seconds: float = float(phys.get("pan_full_travel_seconds", 1.0))
        self.tilt_full_travel_seconds: float = float(phys.get("tilt_full_travel_seconds", 0.5))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, meta_key: str, value: Union[str, int]) -> None:
        """
        Set a meta-channel value.

        Parameters
        ----------
        meta_key : str
            Key from ``meta_channels`` (e.g. ``"pan"``, ``"color"``, ``"prism"``).
        value : str | int
            - ``u16`` channels (pan, tilt): int 0–65535
            - ``u8`` channels (dim, speed, strobe): int 0–255
            - ``enum`` channels (color wheel, gobo wheel, prism):
              label string (e.g. ``"Red"``, ``"On"``, ``"Rotate"``) **or** raw int

        Raises
        ------
        KeyError
            Unknown meta_key, or enum label not found in mapping.
        """
        meta = self.meta_channels.get(meta_key)
        if meta is None:
            raise KeyError(f"'{self.fixture_ref}' has no meta channel '{meta_key}'.")

        kind = meta["kind"]

        if kind == "u16":
            # 16-bit value → MSB + LSB
            raw = int(value) & 0xFFFF
            msb, lsb = divmod(raw, 256)
            ch_msb, ch_lsb = meta["channels"]
            self._state[ch_msb] = msb
            self._state[ch_lsb] = lsb

        elif kind == "enum":
            # Stepped color/gobo/prism wheel — same encoding, label-aware
            self._state[meta["channel"]] = self.resolve_enum(meta_key, value)

        elif kind == "u8":
            self._state[meta["channel"]] = int(value) & 0xFF

        else:
            raise ValueError(f"Unsupported kind '{kind}' on meta channel '{meta_key}'.")

    def to_dmx_buffer(self) -> bytearray:
        buf = bytearray(self.channel_count)
        for ch_name, offset in self.channels.items():
            buf[offset] = self._state.get(ch_name, 0)
        return buf

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------

    def _current_color_label(self) -> str:
        """Resolve the current colour-wheel position to its label string."""
        meta = self.meta_channels.get("color")
        if meta is None:
            return "White"
        ch = meta["channel"]
        current_byte = self._state.get(ch, 0)
        mapping_key = meta.get("mapping", "color")
        mapping = self.mappings.get(mapping_key, {})
        best_label = "White"
        best_val = -1
        for dmx_str, label in mapping.items():
            dmx_val = int(dmx_str)
            if dmx_val <= current_byte and dmx_val > best_val:
                best_val = dmx_val
                best_label = label
        return best_label

    @property
    def color_hex(self) -> str:
        """Current colour as ``#RRGGBB``, derived from the colour-wheel position."""
        return COLOR_WHEEL_HEX.get(self._current_color_label(), "#FFFFFF")

    @property
    def pan(self) -> int:
        """Current pan DMX value as a 16-bit integer."""
        return self._u16_value("pan")

    @property
    def tilt(self) -> int:
        """Current tilt DMX value as a 16-bit integer."""
        return self._u16_value("tilt")

    @property
    def color_wheel_current(self) -> str:
        """Label of the currently selected colour-wheel position (e.g. ``"Red"``)."""
        return self._current_color_label()

    @property
    def color_wheel_options(self) -> list[str]:
        """All colour-wheel labels in wheel order (sorted by DMX value)."""
        meta = self.meta_channels.get("color")
        if meta is None:
            return []
        mapping_key = meta.get("mapping", "color")
        mapping = self.mappings.get(mapping_key, {})
        return [label for _, label in sorted(mapping.items(), key=lambda x: int(x[0]))]

    def to_dict(self) -> dict:
        """Extend the base dict with colour-wheel metadata for the sidebar."""
        d = super().to_dict()
        d["color_wheel_options"] = self.color_wheel_options
        d["color_wheel_current"] = self.color_wheel_current
        d["pan"] = self.pan
        d["tilt"] = self.tilt
        return d

    @property
    def intensity(self) -> float:
        """Dim channel (0–255) normalised to ``[0.0, 1.0]``."""
        meta = self.meta_channels.get("dim")
        if meta is None:
            return 1.0
        ch = meta["channel"]
        return self._state.get(ch, 0) / 255.0

    def movement_time(
        self,
        from_pan: int, to_pan: int,
        from_tilt: int, to_tilt: int,
    ) -> float:
        """
        Estimate the real-world seconds needed to complete a move.

        Uses the fixture's ``physical_movement`` travel times scaled by the
        fractional distance travelled across the full 16-bit range.
        """
        pan_fraction = abs(to_pan - from_pan) / 65535
        tilt_fraction = abs(to_tilt - from_tilt) / 65535
        return max(
            pan_fraction * self.pan_full_travel_seconds,
            tilt_fraction * self.tilt_full_travel_seconds,
        )

    def has_channel(self, meta_key: str) -> bool:
        """Return True if this model includes the given meta channel (e.g. 'prism')."""
        return meta_key in self.meta_channels


# ---------------------------------------------------------------------------
# ParCan
# ---------------------------------------------------------------------------

class ParCan(BaseFixture):
    """
    RGB par-can fixture (dim, red, green, blue, strobe, optional program channel).

    Models: ``rgb_gen``, ``rgb_proton`` (and any future parcan model).
    """

    FIXTURE_TYPE = "parcan"

    def set(self, meta_key: str, value: Union[str, int, tuple]) -> None:
        """
        Set a meta-channel value.

        Parameters
        ----------
        meta_key : str
            Key from ``meta_channels`` (e.g. ``"rgb"``, ``"dim"``).
        value : str | int | tuple[int, int, int]
            - ``rgb`` channel: color label string (e.g. ``"red"``) **or**
              ``(r, g, b)`` tuple of ints 0–255
            - ``u8`` channels (dim, strobe, program): int 0–255

        Raises
        ------
        KeyError
            Unknown meta_key, or color label not in mapping.
        """
        meta = self.meta_channels.get(meta_key)
        if meta is None:
            raise KeyError(f"'{self.fixture_ref}' has no meta channel '{meta_key}'.")

        kind = meta["kind"]

        if kind == "rgb":
            if isinstance(value, str):
                mapping = self.mappings.get(meta.get("mapping", "color"), {})
                hex_val = mapping.get(value)
                if hex_val is None:
                    raise KeyError(
                        f"Color '{value}' not in mapping. "
                        f"Valid: {list(mapping.keys())}"
                    )
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
            else:
                r, g, b = (int(c) & 0xFF for c in value)
            ch_r, ch_g, ch_b = meta["channels"]
            self._state[ch_r] = r
            self._state[ch_g] = g
            self._state[ch_b] = b

        elif kind == "u8":
            self._state[meta["channel"]] = int(value) & 0xFF

        else:
            raise ValueError(f"Unsupported kind '{kind}' on meta channel '{meta_key}'.")

    def to_dmx_buffer(self) -> bytearray:
        buf = bytearray(self.channel_count)
        for ch_name, offset in self.channels.items():
            buf[offset] = self._state.get(ch_name, 0)
        return buf

    @property
    def color_hex(self) -> str:
        """Current colour as ``#RRGGBB`` derived from the live RGB channel bytes."""
        meta = self.meta_channels.get("rgb")
        if meta is None:
            return "#000000"
        ch_r, ch_g, ch_b = meta["channels"]
        r = self._state.get(ch_r, 0)
        g = self._state.get(ch_g, 0)
        b = self._state.get(ch_b, 0)
        return f"#{r:02X}{g:02X}{b:02X}"

    @property
    def intensity(self) -> float:
        """Dim channel (0–255) normalised to ``[0.0, 1.0]``."""
        meta = self.meta_channels.get("dim")
        if meta is None:
            return 1.0
        ch = meta["channel"]
        return self._state.get(ch, 0) / 255.0


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

_FIXTURE_TYPE_MAP: dict[str, type[BaseFixture]] = {
    MovingHead.FIXTURE_TYPE: MovingHead,
    ParCan.FIXTURE_TYPE: ParCan,
}


def load_template(fixture_ref: str) -> dict:
    """
    Load a fixture template dict from ``data/fixtures/<fixture_ref>.json``.

    Parameters
    ----------
    fixture_ref : str
        The ``fixture`` field from a ``fixtures.json`` instance row,
        e.g. ``"fixture.moving_head.mini_beam_prism"``.
    """
    path = _DATA_FIXTURES_DIR / f"{fixture_ref}.json"
    with open(path) as fh:
        return json.load(fh)


def instantiate(instance: dict) -> BaseFixture:
    """
    Factory: build a typed fixture from an instance record.

    Loads the referenced template, selects the correct subclass from
    the registry, and returns a fully initialised fixture object.

    Parameters
    ----------
    instance : dict
        A single row from ``fixtures.json``.

    Raises
    ------
    ValueError
        If the template's ``type`` field has no registered class.
    """
    template = load_template(instance["fixture"])
    cls = _FIXTURE_TYPE_MAP.get(template["type"])
    if cls is None:
        raise ValueError(
            f"No fixture class registered for type '{template['type']}'. "
            f"Known types: {list(_FIXTURE_TYPE_MAP)}"
        )
    return cls(template, instance)


def load_all(fixtures_json_path: str) -> list[BaseFixture]:
    """
    Convenience loader: read ``fixtures.json`` and return all fixture objects.

    Parameters
    ----------
    fixtures_json_path : str
        Absolute path to ``fixtures.json``.
    """
    with open(Path(fixtures_json_path)) as fh:
        instances = json.load(fh)
    return [instantiate(inst) for inst in instances]
