#!/usr/bin/env python3
"""
PS4 Remote Play Controller Example

This example demonstrates how to:
1. Connect to a PS4 using credentials from Chiaki config
2. Send controller input (buttons, analog sticks, triggers)

Requirements:
- Chiaki credentials configured (~/.config/Chiaki/Chiaki.conf)
- PS4 in rest mode or powered on

Usage:
    python3 controller.py [console_name]

Controller Buttons (bitmask):
    CROSS       = 1 << 0
    MOON/CIRCLE = 1 << 1
    BOX/SQUARE  = 1 << 2
    PYRAMID/TRI = 1 << 3
    DPAD_LEFT   = 1 << 4
    DPAD_RIGHT  = 1 << 5
    DPAD_UP     = 1 << 6
    DPAD_DOWN   = 1 << 7
    L1          = 1 << 8
    R1          = 1 << 9
    L3          = 1 << 10
    R3          = 1 << 11
    OPTIONS     = 1 << 12
    SHARE       = 1 << 13
    TOUCHPAD    = 1 << 14
    PS          = 1 << 15
"""

import sys
import ctypes
import time
import base64
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chiaki_python import _chiaki
from chiaki_python.config_parser import get_host_by_name


# Button constants for convenience
CROSS = _chiaki.CHIAKI_CONTROLLER_BUTTON_CROSS
CIRCLE = _chiaki.CHIAKI_CONTROLLER_BUTTON_MOON
SQUARE = _chiaki.CHIAKI_CONTROLLER_BUTTON_BOX
TRIANGLE = _chiaki.CHIAKI_CONTROLLER_BUTTON_PYRAMID
DPAD_UP = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_UP
DPAD_DOWN = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN
DPAD_LEFT = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT
DPAD_RIGHT = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT
L1 = _chiaki.CHIAKI_CONTROLLER_BUTTON_L1
R1 = _chiaki.CHIAKI_CONTROLLER_BUTTON_R1
L3 = _chiaki.CHIAKI_CONTROLLER_BUTTON_L3
R3 = _chiaki.CHIAKI_CONTROLLER_BUTTON_R3
OPTIONS = _chiaki.CHIAKI_CONTROLLER_BUTTON_OPTIONS
SHARE = _chiaki.CHIAKI_CONTROLLER_BUTTON_SHARE
TOUCHPAD = _chiaki.CHIAKI_CONTROLLER_BUTTON_TOUCHPAD
PS = _chiaki.CHIAKI_CONTROLLER_BUTTON_PS


class PS4Controller:
    """Simple wrapper for PS4 controller input."""

    def __init__(self, session):
        self.session = session
        self._buttons = 0
        self._left_x = 0
        self._left_y = 0
        self._right_x = 0
        self._right_y = 0
        self._l2 = 0
        self._r2 = 0

    def _send(self):
        """Send current controller state to PS4."""
        _chiaki._lib.chiaki_python_session_set_controller(
            self.session,
            self._buttons,
            self._left_x,
            self._left_y,
            self._right_x,
            self._right_y,
            self._l2,
            self._r2
        )

    def press(self, buttons: int, duration: float = 0.1):
        """Press button(s) for specified duration."""
        self._buttons |= buttons
        self._send()
        time.sleep(duration)
        self._buttons &= ~buttons
        self._send()

    def hold(self, buttons: int):
        """Hold button(s) down."""
        self._buttons |= buttons
        self._send()

    def release(self, buttons: int):
        """Release button(s)."""
        self._buttons &= ~buttons
        self._send()

    def release_all(self):
        """Release all buttons."""
        self._buttons = 0
        self._left_x = 0
        self._left_y = 0
        self._right_x = 0
        self._right_y = 0
        self._l2 = 0
        self._r2 = 0
        self._send()

    def left_stick(self, x: int, y: int):
        """
        Set left analog stick position.
        x, y: -32768 to 32767 (0 = center)
        """
        self._left_x = max(-32768, min(32767, x))
        self._left_y = max(-32768, min(32767, y))
        self._send()

    def right_stick(self, x: int, y: int):
        """
        Set right analog stick position.
        x, y: -32768 to 32767 (0 = center)
        """
        self._right_x = max(-32768, min(32767, x))
        self._right_y = max(-32768, min(32767, y))
        self._send()

    def triggers(self, l2: int = 0, r2: int = 0):
        """
        Set trigger positions.
        l2, r2: 0 to 255 (0 = released, 255 = fully pressed)
        """
        self._l2 = max(0, min(255, l2))
        self._r2 = max(0, min(255, r2))
        self._send()


def demo_controller(console_name: str = "PS4-910"):
    """Connect and demonstrate controller input."""
    print(f"Connecting to {console_name}...")

    # Load credentials
    try:
        host_config = get_host_by_name(console_name)
    except Exception as e:
        print(f"Error loading config: {e}")
        return False

    HOST = host_config['host']
    REGIST_KEY = host_config['regist_key']
    RP_KEY = host_config['rp_key']
    # PSN Account ID (base64 encoded, 8 bytes)
    PSN_ID = host_config.get('psn_account_id', "U3hhcG9sbG8=")  # Default: "Shxpollo"
    psn_bytes = base64.b64decode(PSN_ID)
    psn_array = (ctypes.c_uint8 * 8)(*psn_bytes[:8])

    # Create and start session
    session = _chiaki._lib.chiaki_python_session_create(
        HOST.encode('utf-8'),
        REGIST_KEY.encode('utf-8'),
        RP_KEY.encode('utf-8'),
        psn_array,
        False, 3, 60
    )

    if not session:
        print("Failed to create session!")
        return False

    if not _chiaki._lib.chiaki_python_session_start(session):
        print("Failed to start session!")
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    connected = _chiaki._lib.chiaki_python_session_wait_connected(session, 15000)
    if not connected:
        print("Connection failed!")
        _chiaki._lib.chiaki_python_session_stop(session)
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    print("Connected! Running controller demo...")

    controller = PS4Controller(session)

    # Demo: Press PS button to wake
    print("  Pressing PS button...")
    controller.press(PS, 0.2)
    time.sleep(1)

    # Demo: Navigate with D-pad
    print("  D-pad navigation...")
    controller.press(DPAD_DOWN, 0.15)
    time.sleep(0.3)
    controller.press(DPAD_RIGHT, 0.15)
    time.sleep(0.3)

    # Demo: Press X to select
    print("  Pressing X...")
    controller.press(CROSS, 0.15)
    time.sleep(0.5)

    # Demo: Press Circle to go back
    print("  Pressing Circle...")
    controller.press(CIRCLE, 0.15)
    time.sleep(0.5)

    # Demo: Analog stick movement
    print("  Moving left stick...")
    controller.left_stick(20000, 0)  # Right
    time.sleep(0.3)
    controller.left_stick(0, 0)  # Center
    time.sleep(0.2)

    print("Demo complete!")

    # Cleanup
    controller.release_all()
    _chiaki._lib.chiaki_python_session_stop(session)
    _chiaki._lib.chiaki_python_session_destroy(session)

    return True


def main():
    console_name = sys.argv[1] if len(sys.argv) > 1 else "PS4-910"
    success = demo_controller(console_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
