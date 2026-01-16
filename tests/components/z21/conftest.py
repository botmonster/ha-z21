"""Common fixtures for the z21 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.z21.const import CONF_PORT, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.z21.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock the config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345678",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        },
        title="Z21 (12345678)",
    )


@pytest.fixture
def mock_z21_station() -> Generator[AsyncMock]:
    """Mock a Z21Station client."""
    with (
        patch(
            "homeassistant.components.z21.Z21Station",
            autospec=True,
        ) as mock_station_cls,
        patch(
            "homeassistant.components.z21.config_flow.Z21Station",
            new=mock_station_cls,
        ),
    ):
        station = AsyncMock()
        mock_station_cls.connect = AsyncMock(return_value=station)

        station.get_serial_number = AsyncMock(return_value=12345678)
        station.get_firmware_version = AsyncMock(return_value=(1, 30))
        station.subscribe_loco_state = MagicMock()
        station.close = AsyncMock()

        yield station


@pytest.fixture
def mock_loco() -> Generator[AsyncMock]:
    """Mock a Loco controller."""
    with (
        patch(
            "homeassistant.components.z21.fan.Loco",
            autospec=True,
        ) as mock_loco_cls,
        patch(
            "homeassistant.components.z21.switch.Loco",
            new=mock_loco_cls,
        ),
    ):
        loco = AsyncMock()
        mock_loco_cls.control = AsyncMock(return_value=loco)

        loco.drive = AsyncMock()
        loco.stop = AsyncMock()
        loco.halt = AsyncMock()
        loco.function_on = AsyncMock()
        loco.function_off = AsyncMock()

        yield loco
