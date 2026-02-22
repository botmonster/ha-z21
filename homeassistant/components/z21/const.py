"""Constants for the z21 integration."""

from __future__ import annotations

DOMAIN = "z21"

# Config flow
CONF_PORT = "port"
DEFAULT_PORT = 21105

# Entity constants
FUNCTION_COUNT = 32  # F0 through F31

# Connection monitoring
HEARTBEAT_INTERVAL = 60  # seconds between heartbeat pings
HEARTBEAT_TIMEOUT = 5.0  # seconds to wait for heartbeat response
MAX_MISSED_HEARTBEATS = 2  # consecutive misses before marking unavailable
RECONNECT_BASE_DELAY = 5  # seconds for first reconnect attempt
RECONNECT_MAX_DELAY = 600  # seconds cap for exponential backoff

# Dispatcher signals
SIGNAL_LOCO_DISCOVERED = f"{DOMAIN}_loco_discovered_{{entry_id}}"
SIGNAL_LOCO_STATE_UPDATE = f"{DOMAIN}_loco_state_update_{{entry_id}}_{{address}}"
SIGNAL_TURNOUT_DISCOVERED = f"{DOMAIN}_turnout_discovered_{{entry_id}}"
SIGNAL_TURNOUT_STATE_UPDATE = f"{DOMAIN}_turnout_state_update_{{entry_id}}_{{address}}"
SIGNAL_Z21_CONNECTED = f"{DOMAIN}_connected_{{entry_id}}"
SIGNAL_Z21_DISCONNECTED = f"{DOMAIN}_disconnected_{{entry_id}}"
