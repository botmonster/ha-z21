"""Test the z21 connection manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.z21.connection import Z21ConnectionManager
from homeassistant.components.z21.const import (
    DEFAULT_PORT,
    DOMAIN,
    SIGNAL_Z21_CONNECTED,
    SIGNAL_Z21_DISCONNECTED,
)
from homeassistant.components.z21.models import Z21RuntimeData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from tests.common import MockConfigEntry


@pytest.fixture
def runtime_data() -> Z21RuntimeData:
    """Create a runtime data instance with a mock station."""
    station = AsyncMock()
    station.get_serial_number = AsyncMock(return_value=12345678)
    station.close = AsyncMock()
    station.subscribe_loco_state = MagicMock()
    return Z21RuntimeData(station=station)


@pytest.fixture
def connection_manager(
    hass: HomeAssistant,
    runtime_data: Z21RuntimeData,
) -> Z21ConnectionManager:
    """Create a connection manager instance."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_id",
        data={"host": "192.168.1.100", "port": DEFAULT_PORT},
    )
    entry.add_to_hass(hass)
    return Z21ConnectionManager(
        hass,
        entry,
        host="192.168.1.100",
        port=DEFAULT_PORT,
        runtime_data=runtime_data,
    )


async def test_ping_success(
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that ping returns True when station responds."""
    result = await connection_manager._ping()
    assert result is True
    runtime_data.station.get_serial_number.assert_called_once()


async def test_ping_timeout(
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that ping returns False on timeout."""
    runtime_data.station.get_serial_number = AsyncMock(side_effect=TimeoutError)
    result = await connection_manager._ping()
    assert result is False


async def test_ping_connection_error(
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that ping returns False on connection error."""
    runtime_data.station.get_serial_number = AsyncMock(side_effect=ConnectionError)
    result = await connection_manager._ping()
    assert result is False


async def test_ping_os_error(
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that ping returns False on OS error."""
    runtime_data.station.get_serial_number = AsyncMock(side_effect=OSError)
    result = await connection_manager._ping()
    assert result is False


async def test_mark_unavailable_dispatches_signal(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that marking unavailable dispatches disconnect signal."""
    signals_received: list[str] = []

    async_dispatcher_connect(
        hass,
        SIGNAL_Z21_DISCONNECTED.format(entry_id="test_entry_id"),
        lambda: signals_received.append("disconnected"),
    )

    assert runtime_data.available is True
    connection_manager._mark_unavailable()
    assert runtime_data.available is False
    assert len(signals_received) == 1


async def test_mark_available_dispatches_signal(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that marking available dispatches connect signal."""
    signals_received: list[str] = []

    async_dispatcher_connect(
        hass,
        SIGNAL_Z21_CONNECTED.format(entry_id="test_entry_id"),
        lambda: signals_received.append("connected"),
    )

    # First mark as unavailable
    runtime_data.available = False
    connection_manager._unavailable_logged = True

    connection_manager._mark_available()
    assert runtime_data.available is True
    assert len(signals_received) == 1


async def test_heartbeat_marks_unavailable_after_missed_beats(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that 2 consecutive missed heartbeats mark entities unavailable."""
    # Make ping fail
    runtime_data.station.get_serial_number = AsyncMock(side_effect=TimeoutError)

    signals_received: list[str] = []

    async_dispatcher_connect(
        hass,
        SIGNAL_Z21_DISCONNECTED.format(entry_id="test_entry_id"),
        lambda: signals_received.append("disconnected"),
    )

    sleep_count = 0

    # Run heartbeat loop but make sleep return immediately
    # and stop after marking unavailable
    async def mock_sleep(delay: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 3:
            connection_manager._shutting_down = True

    with (
        patch("homeassistant.components.z21.connection.asyncio.sleep", mock_sleep),
        patch.object(connection_manager, "_start_reconnect"),
    ):
        await connection_manager._heartbeat_loop()

    assert runtime_data.available is False
    assert len(signals_received) == 1


async def test_heartbeat_resets_on_success(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that successful heartbeat resets missed counter."""
    call_count = 0

    async def alternating_ping(*args: object, **kwargs: object) -> int:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError
        return 12345678

    runtime_data.station.get_serial_number = AsyncMock(side_effect=alternating_ping)

    sleep_count = 0

    async def mock_sleep(delay: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 3:
            connection_manager._shutting_down = True

    with patch("homeassistant.components.z21.connection.asyncio.sleep", mock_sleep):
        await connection_manager._heartbeat_loop()

    # Should still be available because the miss counter was reset
    assert runtime_data.available is True


async def test_reconnect_success(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test successful reconnection creates new station and marks available."""
    # Mark as unavailable first
    runtime_data.available = False

    new_station = AsyncMock()
    new_station.subscribe_loco_state = MagicMock()

    loco_callback = MagicMock()
    connection_manager.set_loco_state_callback(loco_callback)

    signals_received: list[str] = []

    async_dispatcher_connect(
        hass,
        SIGNAL_Z21_CONNECTED.format(entry_id="test_entry_id"),
        lambda: signals_received.append("connected"),
    )

    async def mock_sleep(delay: float) -> None:
        pass

    with (
        patch("homeassistant.components.z21.connection.asyncio.sleep", mock_sleep),
        patch(
            "homeassistant.components.z21.connection.Z21Station.connect",
            return_value=new_station,
        ),
        patch.object(connection_manager, "_heartbeat_loop"),
    ):
        await connection_manager._reconnect_loop()

    assert runtime_data.available is True
    assert runtime_data.station is new_station
    new_station.subscribe_loco_state.assert_called_once_with(loco_callback)
    assert len(signals_received) == 1


async def test_reconnect_exponential_backoff(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that reconnection uses exponential backoff delays."""
    runtime_data.available = False
    delays: list[float] = []
    attempt_count = 0

    async def mock_sleep(delay: float) -> None:
        nonlocal attempt_count
        delays.append(delay)
        attempt_count += 1
        if attempt_count >= 6:
            connection_manager._shutting_down = True

    with (
        patch("homeassistant.components.z21.connection.asyncio.sleep", mock_sleep),
        patch(
            "homeassistant.components.z21.connection.Z21Station.connect",
            side_effect=TimeoutError,
        ),
    ):
        await connection_manager._reconnect_loop()

    # Verify exponential backoff: 5, 10, 20, 40, 60, 60
    assert delays == [5, 10, 20, 40, 60, 60]


async def test_stop_cancels_heartbeat_task(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
) -> None:
    """Test that stop cancels the heartbeat task."""
    connection_manager.start()
    assert connection_manager._heartbeat_task is not None

    await connection_manager.stop()
    assert connection_manager._heartbeat_task is None
    assert connection_manager._shutting_down is True


async def test_stop_cancels_reconnect_task(
    hass: HomeAssistant,
    connection_manager: Z21ConnectionManager,
    runtime_data: Z21RuntimeData,
) -> None:
    """Test that stop cancels the reconnect task."""
    # Simulate being in reconnect state
    runtime_data.available = False
    connection_manager._start_reconnect()
    assert connection_manager._reconnect_task is not None

    await connection_manager.stop()
    assert connection_manager._reconnect_task is None
    assert connection_manager._shutting_down is True


async def test_entity_availability_follows_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that entity availability follows runtime_data.available flag."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Discover a locomotive
    loco_callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.functions = [False] * 32

    loco_callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    # Mark as unavailable via runtime data and send disconnect signal
    entry_runtime_data = mock_config_entry.runtime_data
    entry_runtime_data.available = False

    async_dispatcher_send(
        hass,
        SIGNAL_Z21_DISCONNECTED.format(entry_id=mock_config_entry.entry_id),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    # Restore availability
    entry_runtime_data.available = True
    async_dispatcher_send(
        hass,
        SIGNAL_Z21_CONNECTED.format(entry_id=mock_config_entry.entry_id),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state != "unavailable"
