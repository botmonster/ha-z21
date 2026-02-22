"""Switch platform for Z21 locomotive functions and turnouts."""

from __future__ import annotations

from typing import Any

from z21aio import Loco, Turnout, TurnoutPosition

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Z21ConfigEntry
from .const import FUNCTION_COUNT, SIGNAL_LOCO_DISCOVERED, SIGNAL_TURNOUT_DISCOVERED
from .entity import Z21LocoEntity, Z21TurnoutEntity
from .models import LocoDevice, TurnoutDevice, Z21RuntimeData

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
                LocoEStopSwitch(runtime_data, entry.entry_id, loco_device),
                *(
                    LocoFunctionSwitch(
                        runtime_data, entry.entry_id, loco_device, fn_index
                    )
                    for fn_index in range(FUNCTION_COUNT)
                ),
            ]
        )

    @callback
    def _discover_turnout(address: int) -> None:
        """Handle discovery of new turnout."""
        turnout_device = runtime_data.turnouts[address]
        async_add_entities(
            [TurnoutSwitch(runtime_data, entry.entry_id, turnout_device)]
        )

    # Register for future discoveries
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_LOCO_DISCOVERED.format(entry_id=entry.entry_id),
            _discover_loco,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_TURNOUT_DISCOVERED.format(entry_id=entry.entry_id),
            _discover_turnout,
        )
    )

    # Add entities for already discovered locomotives
    entities: list[LocoFunctionSwitch | LocoEStopSwitch | TurnoutSwitch] = []
    for loco_device in runtime_data.locomotives.values():
        entities.append(LocoEStopSwitch(runtime_data, entry.entry_id, loco_device))
        entities.extend(
            LocoFunctionSwitch(runtime_data, entry.entry_id, loco_device, fn_index)
            for fn_index in range(FUNCTION_COUNT)
        )
    entities.extend(
        TurnoutSwitch(runtime_data, entry.entry_id, turnout_device)
        for turnout_device in runtime_data.turnouts.values()
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
        self.entity_id = f"switch.locomotive_{self._address}_f{function_index}"
        self._attr_translation_key = f"f{function_index}"
        self._loco: Loco | None = None

        # F0 is typically headlights, enable it by default
        # Disable F1-F31 by default to reduce clutter
        if function_index == 0:
            self._attr_icon = "mdi:car-light-dimmed"
        else:
            self._attr_entity_registry_enabled_default = False

    @callback
    def _handle_disconnected(self) -> None:
        """Clear cached loco control on disconnect."""
        self._loco = None
        super()._handle_disconnected()

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


class LocoEStopSwitch(Z21LocoEntity, SwitchEntity):
    """Switch entity that triggers an emergency stop for a locomotive."""

    _attr_has_entity_name = True
    _attr_translation_key = "estop"
    _attr_icon = "mdi:alert-octagon"

    def __init__(
        self,
        runtime_data: Z21RuntimeData,
        entry_id: str,
        loco_device: LocoDevice,
    ) -> None:
        """Initialize the emergency stop switch."""
        super().__init__(runtime_data, entry_id, loco_device)
        self._attr_unique_id = f"{entry_id}_{self._address}_estop"
        self.entity_id = f"switch.locomotive_{self._address}_estop"
        self._loco: Loco | None = None

    @callback
    def _handle_disconnected(self) -> None:
        """Clear cached loco control on disconnect."""
        self._loco = None
        super()._handle_disconnected()

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
        """Return False; estop state is not tracked by the Z21 station."""
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send emergency stop command."""
        loco = await self._ensure_loco_control()
        await loco.estop(reverse=self._loco_device.reverse)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """No-op; estop cannot be cancelled via a DCC command."""


class TurnoutSwitch(Z21TurnoutEntity, SwitchEntity):
    """Switch entity for a DCC turnout (P0 = off, P1 = on)."""

    _attr_has_entity_name = True
    _attr_translation_key = "turnout"
    _attr_icon = "mdi:call-split"

    def __init__(
        self,
        runtime_data: Z21RuntimeData,
        entry_id: str,
        turnout_device: TurnoutDevice,
    ) -> None:
        """Initialize the turnout switch."""
        super().__init__(runtime_data, entry_id, turnout_device)
        self._attr_unique_id = f"{entry_id}_turnout_{self._address}"
        self.entity_id = f"switch.z21_turnout_{self._address}"
        self._turnout: Turnout | None = None

    @callback
    def _handle_disconnected(self) -> None:
        """Clear cached turnout controller on disconnect."""
        self._turnout = None
        super()._handle_disconnected()

    def _ensure_turnout(self) -> Turnout:
        """Get or create Turnout controller."""
        if self._turnout is None:
            self._turnout = Turnout(self._runtime_data.station, self._address)
        return self._turnout

    @property
    def is_on(self) -> bool:
        """Return True if turnout is in P1 position."""
        return self._turnout_device.position == TurnoutPosition.P1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch turnout to P1."""
        turnout = self._ensure_turnout()
        await turnout.switch(TurnoutPosition.P1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch turnout to P0."""
        turnout = self._ensure_turnout()
        await turnout.switch(TurnoutPosition.P0)
