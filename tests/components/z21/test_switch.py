"""Test the z21 switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_switch_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test switch entities are created when locomotive is discovered."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the callback and trigger loco discovery
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    # Verify F0 switch entity was created (enabled by default)
    entity_id = "switch.locomotive_3_f0_headlights"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning on a function switch."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Discover a locomotive
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "switch.locomotive_3_f0_headlights"

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.function_on.assert_called_with(0)


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning off a function switch."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Discover a locomotive with F0 on
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.functions = [True] + [False] * 31

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "switch.locomotive_3_f0_headlights"

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.function_off.assert_called_with(0)


async def test_switch_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test switch state updates when locomotive function state changes."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.z21.Z21Station.connect",
        return_value=mock_z21_station,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]

    # Initial discovery with F0 off
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "switch.locomotive_3_f0_headlights"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Update F0 to on
    mock_loco_state.functions = [True] + [False] * 31
    callback(mock_loco_state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Update F0 back to off
    mock_loco_state.functions = [False] * 32
    callback(mock_loco_state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
