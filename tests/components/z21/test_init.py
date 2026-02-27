"""Test the z21 integration setup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.z21.const import DOMAIN, SIGNAL_Z21_DISCONNECTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_z21_station.get_serial_number.called
    assert mock_z21_station.get_firmware_version.called
    assert mock_z21_station.subscribe_loco_state.called


async def test_setup_entry_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds even when initial connection fails (deferred retry)."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.z21.connection.Z21Station.connect",
            side_effect=asyncio.TimeoutError,
        ),
        patch(
            "homeassistant.components.z21.connection.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.z21.connection.Z21ConnectionManager._heartbeat_loop",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.z21.connection.Z21ConnectionManager._reconnect_loop",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Connection is deferred — entry still loads successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
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
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Get the callback that was registered
    assert mock_z21_station.subscribe_loco_state.called
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]

    # Create a mock LocoState
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = False
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

    # First call is _verify_connection (succeeds), second is _update_station_info (times out)
    mock_z21_station.get_serial_number.side_effect = [12345678, asyncio.TimeoutError]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_z21_station.get_serial_number.called


async def test_setup_entry_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test setup success (deferred) when getting serial number fails."""
    mock_config_entry.add_to_hass(hass)

    # First call is _verify_connection (succeeds), second is _update_station_info (fails)
    mock_z21_station.get_serial_number.side_effect = [
        12345678,
        OSError("Communication error"),
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_z21_station.get_serial_number.called


async def test_restore_known_turnouts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that known turnouts are restored from entity registry on startup."""
    mock_config_entry.add_to_hass(hass)

    # Create hub device (model="Z21") — triggers turnout restore scanning
    hub_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "12345678")},
        model="Z21",
    )

    # Register switch entities with turnout unique_id pattern
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{mock_config_entry.entry_id}_turnout_5",
        config_entry=mock_config_entry,
        device_id=hub_device.id,
    )
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{mock_config_entry.entry_id}_turnout_7",
        config_entry=mock_config_entry,
        device_id=hub_device.id,
    )

    with patch("homeassistant.components.z21.Turnout") as mock_turnout_cls:
        mock_turnout_cls.control = AsyncMock()
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_turnout_cls.control.call_count == 2
    calls = [call.args[1] for call in mock_turnout_cls.control.call_args_list]
    assert 5 in calls
    assert 7 in calls


async def test_restore_known_locos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that known locomotives are restored from device registry on startup."""
    mock_config_entry.add_to_hass(hass)

    # 1. Create a device with serial number for address 3
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_3")},
        serial_number="3",
    )

    # 2. Create a device with serial number for address 4
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_4")},
        serial_number="4",
    )

    # 3. Create a device that should NOT be picked up (wrong domain)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "whatever")},
    )

    mock_loco_instance = AsyncMock()

    with patch("homeassistant.components.z21.Loco") as mock_loco_cls:
        mock_loco_cls.control = AsyncMock(return_value=mock_loco_instance)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Verify Loco.control was called for both addresses
    assert mock_loco_cls.control.call_count == 2

    # Check calls regardless of order
    calls = [call.args[1] for call in mock_loco_cls.control.call_args_list]
    assert 3 in calls
    assert 4 in calls


async def test_reload_closes_orphaned_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that reload closes the station even when no async_on_unload close was registered.

    Regression test: previously stop() did not close the station. If a reconnect
    attempt stored a station in runtime_data without completing _restore_states
    (which registered the close callback in old code), the station would never
    be closed on unload, leaving an orphaned UDP socket.
    """
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Inject an "orphaned" station directly into runtime_data — simulating a
    # reconnect attempt that stored a station but never registered a close callback
    orphan_station = AsyncMock()
    orphan_station.close = AsyncMock()
    mock_config_entry.runtime_data.station = orphan_station

    # Reload: unload must close the orphan even with no async_on_unload close registered
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    orphan_station.close.assert_called_once()


async def test_reload_during_reconnect_backoff_no_bounce(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that reloading during reconnect backoff causes no availability bounce.

    Regression test for the double-connection bug: reloading while the reconnect
    loop is sleeping in backoff must not cause entities to flicker
    (available → unavailable → available).
    """
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Discover a locomotive so there is an entity whose availability we can track
    loco_callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32
    loco_callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"
    assert hass.states.get(entity_id).state != "unavailable"

    # Simulate the station going offline (as if MAX_MISSED_HEARTBEATS exceeded)
    runtime_data = mock_config_entry.runtime_data
    runtime_data.available = False
    async_dispatcher_send(
        hass,
        SIGNAL_Z21_DISCONNECTED.format(entry_id=mock_config_entry.entry_id),
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"

    # Start counting any further disconnect signals from this point on;
    # any such signal after reload would be the bounce bug.
    spurious_disconnects: list[int] = []

    @callback
    def on_disconnect() -> None:
        spurious_disconnects.append(1)

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_Z21_DISCONNECTED.format(entry_id=mock_config_entry.entry_id),
        on_disconnect,
    )

    # Reload the config entry (station is now reachable again — mock always succeeds)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    unsub()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # No spurious disconnect signal must have been fired during or after reload
    assert spurious_disconnects == []

    # The station that was active before reload must have been closed during unload
    mock_z21_station.close.assert_called()
