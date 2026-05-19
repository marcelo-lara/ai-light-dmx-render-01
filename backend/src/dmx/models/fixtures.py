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
import os
from abc import ABC, abstractmethod
from typing import Union

# Resolved at import time; works both inside Docker (/app/data) and locally.
_DATA_FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "fixtures"
)


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

        # Template data
        self.fixture_type: str = template["type"]
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

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

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
    path = os.path.join(_DATA_FIXTURES_DIR, f"{fixture_ref}.json")
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
    with open(fixtures_json_path) as fh:
        instances = json.load(fh)
    return [instantiate(inst) for inst in instances]
