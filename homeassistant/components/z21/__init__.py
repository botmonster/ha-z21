"""The z21 integration."""

from __future__ import annotations

import logging

from z21aio import LocoState, Z21Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_PORT,
    DEFAULT_PORT,
    SIGNAL_LOCO_DISCOVERED,
    SIGNAL_LOCO_STATE_UPDATE,
)
from .models import LocoDevice, Z21RuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.SWITCH]

type Z21ConfigEntry = ConfigEntry[Z21RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: Z21ConfigEntry) -> bool:
    """Set up Z21 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    try:
        station = await Z21Station.connect(host, port)
    except TimeoutError as err:
        raise ConfigEntryNotReady(f"Timeout connecting to {host}:{port}") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Z21 at {host}:{port}") from err

    try:
        serial_number = await station.get_serial_number()
        firmware_version = await station.get_firmware_version()
    except TimeoutError as err:
        await station.close()
        raise ConfigEntryNotReady(
            f"Timeout getting station info from {host}:{port}"
        ) from err
    except Exception as err:
        await station.close()
        raise ConfigEntryNotReady(
            f"Failed to get station info from {host}:{port}"
        ) from err

    runtime_data = Z21RuntimeData(
        station=station,
        serial_number=serial_number,
        firmware_version=firmware_version,
    )
    entry.runtime_data = runtime_data

    @callback
    def handle_loco_state(state: LocoState) -> None:
        """Handle locomotive state updates from Z21."""
        address = state.address

        # Check if this is a new locomotive
        if address not in runtime_data.locomotives:
            _LOGGER.debug("Discovered new locomotive at address %d", address)
            runtime_data.locomotives[address] = LocoDevice(address=address)
            # Signal new device discovery
            async_dispatcher_send(
                hass,
                SIGNAL_LOCO_DISCOVERED.format(entry_id=entry.entry_id),
                address,
            )

        # Update locomotive state
        loco_device = runtime_data.locomotives[address]
        if state.speed_percentage is not None:
            loco_device.speed_percentage = state.speed_percentage
        if state.functions is not None:
            # Ensure we always have 32 functions
            loco_device.functions = list(state.functions) + [False] * (
                32 - len(state.functions)
            )

        # Signal state update for this locomotive
        async_dispatcher_send(
            hass,
            SIGNAL_LOCO_STATE_UPDATE.format(entry_id=entry.entry_id, address=address),
        )

    # Subscribe to locomotive state updates
    station.subscribe_loco_state(handle_loco_state)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register cleanup
    entry.async_on_unload(station.close)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Z21ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
