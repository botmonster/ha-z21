"""Constants for the z21 integration."""

from __future__ import annotations

DOMAIN = "z21"

# Config flow
CONF_PORT = "port"
DEFAULT_PORT = 21105

# Entity constants
FUNCTION_COUNT = 32  # F0 through F31

# Dispatcher signals
SIGNAL_LOCO_DISCOVERED = f"{DOMAIN}_loco_discovered_{{entry_id}}"
SIGNAL_LOCO_STATE_UPDATE = f"{DOMAIN}_loco_state_update_{{entry_id}}_{{address}}"
