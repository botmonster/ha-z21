"""Base entity for Z21 integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_LOCO_STATE_UPDATE
from .models import LocoDevice, Z21RuntimeData


class Z21LocoEntity(Entity):
    """Base class for Z21 locomotive entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime_data: Z21RuntimeData,
        entry_id: str,
        loco_device: LocoDevice,
    ) -> None:
        """Initialize the entity."""
        self._runtime_data = runtime_data
        self._entry_id = entry_id
        self._loco_device = loco_device
        self._address = loco_device.address

        device_id = runtime_data.get_loco_device_id(entry_id, self._address)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"Locomotive {self._address}",
            manufacturer="DCC",
            model="Locomotive",
            via_device=(DOMAIN, str(runtime_data.serial_number)),
        )

    @callback
    def _handle_state_update(self) -> None:
        """Handle state update from dispatcher."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_LOCO_STATE_UPDATE.format(
                    entry_id=self._entry_id,
                    address=self._address,
                ),
                self._handle_state_update,
            )
        )
