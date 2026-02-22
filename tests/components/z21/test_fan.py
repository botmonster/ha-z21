"""Test the z21 fan platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_PERCENTAGE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_fan_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test fan entity is created when locomotive is discovered."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the callback and trigger loco discovery
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    # Verify fan entity was created
    entity_id = "fan.locomotive_3"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_fan_speed_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test setting fan speed controls locomotive."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Set speed
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 75},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(75, reverse=False)


async def test_fan_direction_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test setting fan direction controls locomotive."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive with speed
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Set direction to reverse
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_DIRECTION: DIRECTION_REVERSE},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(50, reverse=True)


async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning off fan stops locomotive."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Turn off
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.stop.assert_called_once_with(reverse=False)


async def test_fan_turn_off_reverse(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning off fan in reverse stops locomotive with reverse direction."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive going in reverse
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = True
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Turn off
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.stop.assert_called_once_with(reverse=True)


async def test_fan_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test fan state updates when locomotive state changes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]

    # Initial discovery at 0 speed
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Update to moving forward
    mock_loco_state.speed_percentage = 75.0
    mock_loco_state.reverse = False
    callback(mock_loco_state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_PERCENTAGE) == 75
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_FORWARD

    # Update to moving reverse
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = True
    callback(mock_loco_state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_PERCENTAGE) == 50
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_REVERSE


async def test_fan_turn_on_with_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning on fan with specific percentage."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive at rest
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Turn on with specific percentage
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 80},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(80, reverse=False)


async def test_fan_turn_on_without_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning on fan without percentage uses default 50%."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Discover a locomotive at rest moving forward
    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = False
    mock_loco_state.functions = [False] * 32

    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Turn on without percentage
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(40, reverse=False)


async def test_fan_turn_on_resumes_last_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning on fan without percentage resumes last non-zero speed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.functions = [False] * 32

    # Locomotive runs at 75% forward — sets last_speed_percentage to 75
    mock_loco_state.speed_percentage = 75.0
    mock_loco_state.reverse = False
    callback(mock_loco_state)
    await hass.async_block_till_done()

    # Locomotive stops — last_speed_percentage stays at 75
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = None
    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on without percentage — should resume at 75%
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(75, reverse=False)


async def test_fan_turn_on_resumes_last_speed_in_reverse(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
    mock_loco: AsyncMock,
) -> None:
    """Test turning on fan without percentage resumes last speed and direction in reverse."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.functions = [False] * 32

    # Locomotive runs at 60% in reverse — sets last_speed_percentage to 60
    mock_loco_state.speed_percentage = 60.0
    mock_loco_state.reverse = True
    callback(mock_loco_state)
    await hass.async_block_till_done()

    # Locomotive stops — last_speed_percentage stays at 60, direction stays reverse
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = None
    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Turn on without percentage — should resume at 60% in reverse
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_loco.drive.assert_called_with(60, reverse=True)


async def test_fan_direction_preserved_at_zero_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_z21_station: AsyncMock,
) -> None:
    """Test that direction is preserved when locomotive stops."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_z21_station.subscribe_loco_state.call_args[0][0]
    mock_loco_state = MagicMock()
    mock_loco_state.address = 3
    mock_loco_state.functions = [False] * 32

    # Discover loco moving in reverse
    mock_loco_state.speed_percentage = 50.0
    mock_loco_state.reverse = True
    callback(mock_loco_state)
    await hass.async_block_till_done()

    entity_id = "fan.locomotive_3"

    # Stop the loco (speed goes to 0, no direction update) — direction must remain reverse
    mock_loco_state.speed_percentage = 0.0
    mock_loco_state.reverse = None
    callback(mock_loco_state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_REVERSE
