"""Fan platform for Z21 locomotives."""

from __future__ import annotations

from typing import Any

from z21aio import Loco

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Z21ConfigEntry
from .const import SIGNAL_LOCO_DISCOVERED
from .entity import Z21LocoEntity
from .models import LocoDevice, Z21RuntimeData

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Z21ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z21 fan platform."""
    runtime_data = entry.runtime_data

    @callback
    def _discover_loco(address: int) -> None:
        """Handle discovery of new locomotive."""
        loco_device = runtime_data.locomotives[address]
        async_add_entities([LocomotiveFan(runtime_data, entry.entry_id, loco_device)])

    # Register for future discoveries
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_LOCO_DISCOVERED.format(entry_id=entry.entry_id),
            _discover_loco,
        )
    )

    # Add entities for already discovered locomotives
    async_add_entities(
        [
            LocomotiveFan(runtime_data, entry.entry_id, loco_device)
            for loco_device in runtime_data.locomotives.values()
        ]
    )


class LocomotiveFan(Z21LocoEntity, FanEntity):
    """Fan entity representing a DCC locomotive."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 100
    _attr_icon = "mdi:train"
    _attr_translation_key = "locomotive"
    _attr_name = None  # Use device name

    def __init__(
        self,
        runtime_data: Z21RuntimeData,
        entry_id: str,
        loco_device: LocoDevice,
    ) -> None:
        """Initialize the locomotive."""
        super().__init__(runtime_data, entry_id, loco_device)
        self._attr_unique_id = f"{entry_id}_{self._address}_fan"
        self._loco: Loco | None = None

    async def _ensure_loco_control(self) -> Loco:
        """Ensure we have control of the locomotive."""
        if self._loco is None:
            self._loco = await Loco.control(
                self._runtime_data.station,
                self._address,
            )
        return self._loco

    @property
    def is_on(self) -> bool:
        """Return true if locomotive is moving."""
        return self._loco_device.abs_speed > 0

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return self._loco_device.abs_speed

    @property
    def current_direction(self) -> str:
        """Return the current direction."""
        return DIRECTION_FORWARD if self._loco_device.is_forward else DIRECTION_REVERSE

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        loco = await self._ensure_loco_control()
        # Maintain current direction when setting speed
        if not self._loco_device.is_forward:
            percentage = -percentage
        await loco.drive(percentage)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the locomotive."""
        loco = await self._ensure_loco_control()
        current_speed = self._loco_device.abs_speed
        if direction == DIRECTION_FORWARD:
            await loco.drive(current_speed)
        else:
            await loco.drive(-current_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the locomotive."""
        loco = await self._ensure_loco_control()
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # Default to 50% in current direction if no speed specified
            direction = 1 if self._loco_device.is_forward else -1
            await loco.drive(50 * direction)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the locomotive."""
        loco = await self._ensure_loco_control()
        await loco.stop()
