"""Test the z21 integration setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.z21.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_z21_station.get_serial_number.called
    assert mock_z21_station.get_firmware_version.called
    assert mock_z21_station.subscribe_loco_state.called


async def test_setup_entry_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure due to timeout."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        side_effect=asyncio.TimeoutError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure due to connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        side_effect=Exception("Connection refused"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_z21_station.close.called


async def test_loco_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test locomotive discovery via state callback."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the callback that was registered
    assert mock_z21_station.subscribe_loco_state.called
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]

    # Create a mock LocoState
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.functions = [True] + [False] * 31

    # Trigger the callback
    callback(mock_loco_state)
    await hass.async_block_till_done()

    # Verify locomotive was added to runtime data
    runtime_data = mock_config_entry.runtime_data
    assert 3 in runtime_data.locomotives
    assert runtime_data.locomotives[3].speed_percentage == 50.0
    assert runtime_data.locomotives[3].functions[0] is True


async def test_setup_entry_serial_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test setup success (deferred) when getting serial number times out."""
    mock_config_entry.add_to_hass(hass)

    mock_z21_station.get_serial_number.side_effect = asyncio.TimeoutError

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_z21_station.close.called
    assert mock_z21_station.get_serial_number.called


async def test_setup_entry_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test setup success (deferred) when getting serial number fails."""
    mock_config_entry.add_to_hass(hass)

    mock_z21_station.get_serial_number.side_effect = OSError("Communication error")

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_z21_station.close.called
    assert mock_z21_station.get_serial_number.called


async def test_restore_known_locos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that known locomotives are restored from device registry on startup."""
    mock_config_entry.add_to_hass(hass)

    # 1. Create a device with serial number (new format)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_3")},
        serial_number="3",
    )

    # 2. Create a device with legacy identifier (old format, fallback)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_4")},
        # No serial number
    )

    # 3. Create a device that should NOT be picked up (wrong domain)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "whatever")},
    )

    mock_loco_instance = AsyncMock()

    with (
        patch(
            "homeassistant.components.z21.Z21Station.connect",
            return_value=mock_z21_station,
        ),
        patch("homeassistant.components.z21.Loco") as mock_loco_cls,
    ):
        mock_loco_cls.control = AsyncMock(return_value=mock_loco_instance)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify Loco.control was called for both addresses
        assert mock_loco_cls.control.call_count == 2

        # Check calls regardless of order
        calls = [call.args[1] for call in mock_loco_cls.control.call_args_list]
        assert 3 in calls
        assert 4 in calls
