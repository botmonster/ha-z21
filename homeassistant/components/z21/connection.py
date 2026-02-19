"""Connection manager for Z21 station."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging

from z21aio import Z21Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    MAX_MISSED_HEARTBEATS,
    RECONNECT_BASE_DELAY,
    RECONNECT_MAX_DELAY,
    SIGNAL_Z21_CONNECTED,
    SIGNAL_Z21_DISCONNECTED,
)
from .models import Z21RuntimeData

_LOGGER = logging.getLogger(__name__)


class Z21ConnectionManager:
    """Manage connection health and reconnection for a Z21 station."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        port: int,
        runtime_data: Z21RuntimeData,
    ) -> None:
        """Initialize the connection manager."""
        self._hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._host = host
        self._port = port
        self._runtime_data = runtime_data
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._missed_heartbeats = 0
        self._reconnect_attempts = 0
        self._unavailable_logged = False
        self._loco_state_callback: Callable | None = None
        self._shutting_down = False

    def start(self) -> None:
        """Start the heartbeat monitoring loop."""
        if self._heartbeat_task is None:
            self._heartbeat_task = self._entry.async_create_background_task(
                self._hass, self._heartbeat_loop(), "z21_heartbeat"
            )

    async def stop(self) -> None:
        """Stop monitoring and reconnection."""
        self._shutting_down = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

    def set_loco_state_callback(self, loco_state_callback: Callable) -> None:
        """Store the loco state callback for re-registration after reconnect."""
        self._loco_state_callback = loco_state_callback

    async def _ping(self) -> bool:
        """Send a serial number request as a heartbeat check.

        Returns True if a response was received, False on timeout or error.
        """
        try:
            await asyncio.wait_for(
                self._runtime_data.station.get_serial_number(),
                timeout=HEARTBEAT_TIMEOUT,
            )
        except TimeoutError, ConnectionError, OSError:
            return False
        return True

    async def _heartbeat_loop(self) -> None:
        """Periodically send heartbeat and check response."""
        while not self._shutting_down:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self._shutting_down:
                    break

                success = await self._ping()

                if success:
                    self._missed_heartbeats = 0
                    if not self._runtime_data.available:
                        self._mark_available()
                else:
                    self._missed_heartbeats += 1
                    _LOGGER.debug(
                        "Heartbeat missed (%d/%d)",
                        self._missed_heartbeats,
                        MAX_MISSED_HEARTBEATS,
                    )
                    if (
                        self._missed_heartbeats >= MAX_MISSED_HEARTBEATS
                        and self._runtime_data.available
                    ):
                        self._mark_unavailable()
                        self._start_reconnect()
                        return

            except asyncio.CancelledError:
                break

    def _mark_unavailable(self) -> None:
        """Mark connection as lost and notify entities."""
        self._runtime_data.available = False
        if not self._unavailable_logged:
            _LOGGER.warning("Lost connection to Z21 station")
            self._unavailable_logged = True
        async_dispatcher_send(
            self._hass,
            SIGNAL_Z21_DISCONNECTED.format(entry_id=self._entry_id),
        )

    def _mark_available(self) -> None:
        """Mark connection as restored and notify entities."""
        self._runtime_data.available = True
        self._missed_heartbeats = 0
        self._reconnect_attempts = 0
        if self._unavailable_logged:
            _LOGGER.warning("Connection to Z21 station restored")
            self._unavailable_logged = False
        async_dispatcher_send(
            self._hass,
            SIGNAL_Z21_CONNECTED.format(entry_id=self._entry_id),
        )

    def _start_reconnect(self) -> None:
        """Start the reconnection loop."""
        if self._reconnect_task is None and not self._shutting_down:
            self._reconnect_task = self._entry.async_create_background_task(
                self._hass, self._reconnect_loop(), "z21_reconnect"
            )

    async def _reconnect_loop(self) -> None:
        """Attempt reconnection with exponential backoff."""
        while not self._shutting_down:
            delay = min(
                RECONNECT_BASE_DELAY * (2**self._reconnect_attempts),
                RECONNECT_MAX_DELAY,
            )
            _LOGGER.debug("Attempting reconnection in %d seconds", delay)
            await asyncio.sleep(delay)

            if self._shutting_down:
                break

            try:
                old_station = self._runtime_data.station

                try:
                    await old_station.close()
                except TimeoutError, ConnectionError, OSError:
                    _LOGGER.debug("Error closing old station", exc_info=True)

                new_station = await Z21Station.connect(self._host, self._port)

                if self._loco_state_callback is not None:
                    new_station.subscribe_loco_state(self._loco_state_callback)

                self._runtime_data.station = new_station

                self._mark_available()

                # Restart heartbeat loop
                self._reconnect_task = None
                self._heartbeat_task = self._entry.async_create_background_task(
                    self._hass, self._heartbeat_loop(), "z21_heartbeat"
                )

            except TimeoutError, ConnectionError, OSError:
                self._reconnect_attempts += 1
                _LOGGER.debug(
                    "Reconnection attempt %d failed",
                    self._reconnect_attempts,
                )
            except asyncio.CancelledError:
                break
            else:
                return

        self._reconnect_task = None
