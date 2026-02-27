"""The z21 integration."""

from __future__ import annotations

import asyncio
import logging

from z21aio import Loco, LocoState, Turnout, TurnoutState, Z21Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .connection import Z21ConnectionManager
from .const import (
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
    SIGNAL_LOCO_DISCOVERED,
    SIGNAL_LOCO_STATE_UPDATE,
    SIGNAL_TURNOUT_DISCOVERED,
    SIGNAL_TURNOUT_STATE_UPDATE,
)
from .models import LocoDevice, TurnoutDevice, Z21RuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.SWITCH]

type Z21ConfigEntry = ConfigEntry[Z21RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: Z21ConfigEntry) -> bool:
    """Set up Z21 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    runtime_data = Z21RuntimeData()
    entry.runtime_data = runtime_data

    connection_manager = Z21ConnectionManager(hass, entry, host, port, runtime_data)
    dev_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    @callback
    def handle_loco_state(state: LocoState) -> None:
        """Handle locomotive state updates from Z21."""
        address = state.address
        _LOGGER.debug("Updating state for locomotive at address %d: %s", address, state)

        if address not in runtime_data.locomotives:
            _LOGGER.debug("Discovered new locomotive at address %d", address)
            runtime_data.locomotives[address] = LocoDevice(address=address)
            async_dispatcher_send(
                hass,
                SIGNAL_LOCO_DISCOVERED.format(entry_id=entry.entry_id),
                address,
            )

        loco_device = runtime_data.locomotives[address]
        if state.speed_percentage is not None:
            loco_device.speed_percentage = state.speed_percentage
            if state.speed_percentage > 0:
                loco_device.last_speed_percentage = state.speed_percentage
        if state.reverse is not None:
            loco_device.reverse = state.reverse
        if state.functions is not None:
            loco_device.functions = list(state.functions) + [False] * (
                32 - len(state.functions)
            )

        async_dispatcher_send(
            hass,
            SIGNAL_LOCO_STATE_UPDATE.format(entry_id=entry.entry_id, address=address),
        )

    async def _update_station_info(station: Z21Station) -> None:
        """Fetch station info and register device."""
        try:
            serial_number, firmware_version = await asyncio.gather(
                station.get_serial_number(),
                station.get_firmware_version(),
            )
            runtime_data.serial_number = serial_number
            runtime_data.firmware_version = firmware_version

            # Register the Z21 hub device
            dev_reg.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, str(serial_number))},
                name="Z21 Station",
                manufacturer="Roco/Fleischmann",
                model="Z21",
                sw_version=f"{firmware_version[0]}.{firmware_version[1]}",
            )
        except (TimeoutError, ConnectionError, OSError) as err:
            _LOGGER.warning(
                "Failed to fetch station info: %s",
                err,
            )

    @callback
    def handle_turnout_state(state: TurnoutState) -> None:
        """Handle turnout state updates from Z21."""
        address = state.address
        _LOGGER.debug("Updating state for turnout at address %d: %s", address, state)

        if address not in runtime_data.turnouts:
            _LOGGER.debug("Discovered new turnout at address %d", address)
            runtime_data.turnouts[address] = TurnoutDevice(address=address)
            async_dispatcher_send(
                hass,
                SIGNAL_TURNOUT_DISCOVERED.format(entry_id=entry.entry_id),
                address,
            )

        runtime_data.turnouts[address].position = state.position

        async_dispatcher_send(
            hass,
            SIGNAL_TURNOUT_STATE_UPDATE.format(
                entry_id=entry.entry_id, address=address
            ),
        )

    connection_manager.set_loco_state_callback(handle_loco_state)
    connection_manager.set_turnout_state_callback(handle_turnout_state)

    async def _restore_states(station: Z21Station) -> None:
        await _update_station_info(station)

        for entity in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
            if entity.domain == "switch" and "_turnout_" in (entity.unique_id or ""):
                try:
                    await Turnout.control(station, int(entity.unique_id.split("_")[-1]))
                except (TimeoutError, ConnectionError, OSError, ValueError) as err:
                    _LOGGER.warning(
                        "Failed to restore state for turnout %s: %s",
                        entity.unique_id,
                        err,
                    )
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if device.model == "Z21":
                continue
            if device.serial_number and device.serial_number.isdigit():
                try:
                    await Loco.control(station, int(device.serial_number))
                except (TimeoutError, ConnectionError, OSError, ValueError) as err:
                    _LOGGER.warning(
                        "Failed to restore state for locomotive %s: %s",
                        device.serial_number,
                        err,
                    )

    connection_manager.set_restore_states_callback(_restore_states)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    connection_manager.start_connect()
    entry.async_on_unload(connection_manager.stop)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Z21ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
