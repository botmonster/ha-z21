"""Test the z21 turnout switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from z21aio import TurnoutPosition

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.z21.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


def _make_turnout_state(address: int, position: TurnoutPosition) -> MagicMock:
    """Create a mock TurnoutState."""
    state = MagicMock()
    state.address = address
    state.position = position
    return state


async def _setup_and_discover_turnout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    address: int,
    position: TurnoutPosition = TurnoutPosition.UNKNOWN,
) -> None:
    """Helper: set up integration and trigger turnout discovery."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_turnout_state.call_args[0][0]
    callback(_make_turnout_state(address, position))
    await hass.async_block_till_done()


async def test_turnout_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that a TurnoutSwitch entity is created when a turnout is discovered."""
    await _setup_and_discover_turnout(
        hass, mock_config_entry, mock_z21_station, address=5
    )

    entity_id = "switch.z21_turnout_5"
    state = hass.states.get(entity_id)
    assert state is not None


async def test_turnout_state_unknown_is_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that UNKNOWN position maps to switch off."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.UNKNOWN,
    )

    state = hass.states.get("switch.z21_turnout_5")
    assert state.state == STATE_OFF


async def test_turnout_state_p0_is_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that P0 position maps to switch off."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.P0,
    )

    state = hass.states.get("switch.z21_turnout_5")
    assert state.state == STATE_OFF


async def test_turnout_state_p1_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that P1 position maps to switch on."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.P1,
    )

    state = hass.states.get("switch.z21_turnout_5")
    assert state.state == STATE_ON


async def test_turnout_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that state updates flow through the dispatcher to the entity."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.P0,
    )

    entity_id = "switch.z21_turnout_5"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Update to P1 via callback
    callback = mock_z21_station.subscribe_turnout_state.call_args[0][0]
    callback(_make_turnout_state(5, TurnoutPosition.P1))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Update back to P0
    callback(_make_turnout_state(5, TurnoutPosition.P0))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_turnout_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_turnout: AsyncMock,
) -> None:
    """Test that turn_on sends switch(P1) to the turnout controller."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.P0,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.z21_turnout_5"},
        blocking=True,
    )

    mock_turnout.switch.assert_called_once_with(TurnoutPosition.P1)


async def test_turnout_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_turnout: AsyncMock,
) -> None:
    """Test that turn_off sends switch(P0) to the turnout controller."""
    await _setup_and_discover_turnout(
        hass,
        mock_config_entry,
        mock_z21_station,
        address=5,
        position=TurnoutPosition.P1,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.z21_turnout_5"},
        blocking=True,
    )

    mock_turnout.switch.assert_called_once_with(TurnoutPosition.P0)


async def test_turnout_unavailable_on_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that the entity becomes unavailable when Z21 disconnects."""
    await _setup_and_discover_turnout(
        hass, mock_config_entry, mock_z21_station, address=5
    )

    entity_id = "switch.z21_turnout_5"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Simulate disconnect
    runtime_data = mock_config_entry.runtime_data
    runtime_data.available = False
    async_dispatcher_send(
        hass,
        f"{DOMAIN}_disconnected_{mock_config_entry.entry_id}",
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_turnout_available_on_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that the entity becomes available again when Z21 reconnects."""
    await _setup_and_discover_turnout(
        hass, mock_config_entry, mock_z21_station, address=5
    )

    entity_id = "switch.z21_turnout_5"

    # First disconnect
    runtime_data = mock_config_entry.runtime_data
    runtime_data.available = False
    async_dispatcher_send(
        hass,
        f"{DOMAIN}_disconnected_{mock_config_entry.entry_id}",
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Then reconnect
    runtime_data.available = True
    async_dispatcher_send(
        hass,
        f"{DOMAIN}_connected_{mock_config_entry.entry_id}",
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_multiple_turnouts_discovered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that multiple turnouts can be discovered independently."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_turnout_state.call_args[0][0]

    callback(_make_turnout_state(1, TurnoutPosition.P0))
    callback(_make_turnout_state(2, TurnoutPosition.P1))
    callback(_make_turnout_state(10, TurnoutPosition.UNKNOWN))
    await hass.async_block_till_done()

    assert hass.states.get("switch.z21_turnout_1").state == STATE_OFF
    assert hass.states.get("switch.z21_turnout_2").state == STATE_ON
    assert hass.states.get("switch.z21_turnout_10").state == STATE_OFF
