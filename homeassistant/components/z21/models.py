"""Data models for the z21 integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from z21aio import Loco, Z21Station


@dataclass
class LocoDevice:
    """Represents a discovered locomotive device."""

    address: int
    loco: Loco | None = None
    speed_percentage: float = 0.0
    functions: list[bool] = field(default_factory=lambda: [False] * 32)

    @property
    def is_forward(self) -> bool:
        """Return True if locomotive is moving forward."""
        return self.speed_percentage >= 0

    @property
    def abs_speed(self) -> int:
        """Return absolute speed as percentage 0-100."""
        return int(abs(self.speed_percentage))


@dataclass
class Z21RuntimeData:
    """Runtime data for Z21 integration."""

    station: Z21Station
    serial_number: int | None = None
    firmware_version: tuple[int, int] | None = None
    locomotives: dict[int, LocoDevice] = field(default_factory=dict)

    def get_loco_device_id(self, entry_id: str, address: int) -> str:
        """Generate unique device ID for a locomotive."""
        return f"{entry_id}_{address}"
