"""Test the z21 config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.z21.const import CONF_PORT, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user flow creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.z21.config_flow.Z21Station.connect",
    ) as mock_connect:
        mock_station = AsyncMock()
        mock_station.get_serial_number = AsyncMock(return_value=12345678)
        mock_station.close = AsyncMock()
        mock_connect.return_value = mock_station

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: DEFAULT_PORT,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Z21 (12345678)"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.z21.config_flow.Z21Station.connect",
        side_effect=Exception("Connection failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_station(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test duplicate station aborts."""
    # Create an existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345678",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: DEFAULT_PORT,
        },
        title="Z21 (12345678)",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.z21.config_flow.Z21Station.connect",
    ) as mock_connect:
        mock_station = AsyncMock()
        mock_station.get_serial_number = AsyncMock(return_value=12345678)
        mock_station.close = AsyncMock()
        mock_connect.return_value = mock_station

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
