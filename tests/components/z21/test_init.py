"""Test the z21 integration setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
    """Test setup failure when getting serial number times out."""
    mock_config_entry.add_to_hass(hass)

    mock_z21_station.get_serial_number.side_effect = asyncio.TimeoutError

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_z21_station.close.called


async def test_setup_entry_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test setup failure when getting serial number fails."""
    mock_config_entry.add_to_hass(hass)

    mock_z21_station.get_serial_number.side_effect = Exception("Communication error")

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_z21_station.close.called
