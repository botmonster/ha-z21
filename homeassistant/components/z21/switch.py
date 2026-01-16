"""Switch platform for Z21 locomotive functions."""

from __future__ import annotations

from typing import Any

from z21aio import Loco

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Z21ConfigEntry
from .const import FUNCTION_COUNT, SIGNAL_LOCO_DISCOVERED
from .entity import Z21LocoEntity
from .models import LocoDevice, Z21RuntimeData

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Z21ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z21 switch platform."""
    runtime_data = entry.runtime_data

    @callback
    def _discover_loco(address: int) -> None:
        """Handle discovery of new locomotive."""
        loco_device = runtime_data.locomotives[address]
        async_add_entities(
            [
                LocoFunctionSwitch(runtime_data, entry.entry_id, loco_device, fn_index)
                for fn_index in range(FUNCTION_COUNT)
            ]
        )

    # Register for future discoveries
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_LOCO_DISCOVERED.format(entry_id=entry.entry_id),
            _discover_loco,
        )
    )

    # Add entities for already discovered locomotives
    entities: list[LocoFunctionSwitch] = []
    for loco_device in runtime_data.locomotives.values():
        entities.extend(
            [
                LocoFunctionSwitch(runtime_data, entry.entry_id, loco_device, fn_index)
                for fn_index in range(FUNCTION_COUNT)
            ]
        )
    async_add_entities(entities)


class LocoFunctionSwitch(Z21LocoEntity, SwitchEntity):
    """Switch entity representing a locomotive function (F0-F31)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        runtime_data: Z21RuntimeData,
        entry_id: str,
        loco_device: LocoDevice,
        function_index: int,
    ) -> None:
        """Initialize the function switch."""
        super().__init__(runtime_data, entry_id, loco_device)
        self._function_index = function_index
        self._attr_unique_id = f"{entry_id}_{self._address}_f{function_index}"
        self._attr_translation_key = f"f{function_index}"
        self._loco: Loco | None = None

        # F0 is typically headlights, enable it by default
        # Disable F1-F31 by default to reduce clutter
        if function_index == 0:
            self._attr_icon = "mdi:car-light-dimmed"
        else:
            self._attr_entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the name of the function."""
        if self._function_index == 0:
            return "F0 (Headlights)"
        return f"F{self._function_index}"

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
        """Return true if function is on."""
        if self._function_index < len(self._loco_device.functions):
            return self._loco_device.functions[self._function_index]
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the function on."""
        loco = await self._ensure_loco_control()
        await loco.function_on(self._function_index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the function off."""
        loco = await self._ensure_loco_control()
        await loco.function_off(self._function_index)
