"""Config flow for the z21 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from z21aio import Z21Station

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import CONF_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class Z21ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Z21."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            try:
                station = await Z21Station.connect(host, port)
                serial_number = await station.get_serial_number()
                await station.close()
            except Exception:
                _LOGGER.exception(
                    "Failed to connect to Z21 station at %s:%s", host, port
                )
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(serial_number))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Z21 ({serial_number})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
