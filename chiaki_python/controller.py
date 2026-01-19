"""
Controller input module for sending button presses and joystick movements.
"""

from typing import Tuple
import ctypes
import time
from . import _chiaki


# Use Chiaki's button constants directly
class Button:
    """PlayStation controller buttons (using Chiaki constants)."""
    CROSS = _chiaki.CHIAKI_CONTROLLER_BUTTON_CROSS
    CIRCLE = _chiaki.CHIAKI_CONTROLLER_BUTTON_MOON
    SQUARE = _chiaki.CHIAKI_CONTROLLER_BUTTON_BOX
    TRIANGLE = _chiaki.CHIAKI_CONTROLLER_BUTTON_PYRAMID
    L1 = _chiaki.CHIAKI_CONTROLLER_BUTTON_L1
    R1 = _chiaki.CHIAKI_CONTROLLER_BUTTON_R1
    L3 = _chiaki.CHIAKI_CONTROLLER_BUTTON_L3
    R3 = _chiaki.CHIAKI_CONTROLLER_BUTTON_R3
    OPTIONS = _chiaki.CHIAKI_CONTROLLER_BUTTON_OPTIONS
    SHARE = _chiaki.CHIAKI_CONTROLLER_BUTTON_SHARE
    PS = _chiaki.CHIAKI_CONTROLLER_BUTTON_PS
    TOUCHPAD = _chiaki.CHIAKI_CONTROLLER_BUTTON_TOUCHPAD
    DPAD_UP = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_UP
    DPAD_DOWN = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN
    DPAD_LEFT = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT
    DPAD_RIGHT = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT


class Controller:
    """
    Controller interface for sending input to the PS4/PS5.
    """

    def __init__(self, session):
        """
        Initialize controller for a session.

        Args:
            session: The active PS4Session or PS5Session
        """
        self.session = session
        self._state = _chiaki.ChiakiControllerState()
        _chiaki._lib.chiaki_controller_state_set_idle(ctypes.byref(self._state))

    def press(self, button: str):
        """
        Press a button (and release immediately).

        Args:
            button: Button name (e.g., "cross", "circle", "square")
        """
        button_map = {
            "cross": Button.CROSS,
            "circle": Button.CIRCLE,
            "square": Button.SQUARE,
            "triangle": Button.TRIANGLE,
            "l1": Button.L1,
            "r1": Button.R1,
            "l3": Button.L3,
            "r3": Button.R3,
            "options": Button.OPTIONS,
            "share": Button.SHARE,
            "ps": Button.PS,
            "touchpad": Button.TOUCHPAD,
            "up": Button.DPAD_UP,
            "down": Button.DPAD_DOWN,
            "left": Button.DPAD_LEFT,
            "right": Button.DPAD_RIGHT,
        }

        btn = button_map.get(button.lower())
        if btn is not None:
            self.button_down(btn)
            time.sleep(0.1)  # Brief press duration
            self.button_up(btn)
        elif button.lower() == "l2":
            self.set_triggers(l2=1.0)
            time.sleep(0.1)
            self.set_triggers(l2=0.0)
        elif button.lower() == "r2":
            self.set_triggers(r2=1.0)
            time.sleep(0.1)
            self.set_triggers(r2=0.0)

    def button_down(self, button: int):
        """Hold a button down."""
        self._state.buttons |= button
        self._send_state()

    def button_up(self, button: int):
        """Release a button."""
        self._state.buttons &= ~button
        self._send_state()

    def set_left_stick(self, x: float, y: float):
        """
        Set left stick position.

        Args:
            x: Horizontal position (-1.0 to 1.0)
            y: Vertical position (-1.0 to 1.0)
        """
        # Chiaki uses int16_t range (-32768 to 32767)
        self._state.left_x = int(max(-1.0, min(1.0, x)) * 32767)
        self._state.left_y = int(max(-1.0, min(1.0, y)) * 32767)
        self._send_state()

    def set_right_stick(self, x: float, y: float):
        """
        Set right stick position.

        Args:
            x: Horizontal position (-1.0 to 1.0)
            y: Vertical position (-1.0 to 1.0)
        """
        # Chiaki uses int16_t range (-32768 to 32767)
        self._state.right_x = int(max(-1.0, min(1.0, x)) * 32767)
        self._state.right_y = int(max(-1.0, min(1.0, y)) * 32767)
        self._send_state()

    def set_triggers(self, l2: float = 0.0, r2: float = 0.0):
        """
        Set trigger values.

        Args:
            l2: L2 trigger pressure (0.0 to 1.0)
            r2: R2 trigger pressure (0.0 to 1.0)
        """
        # Chiaki uses uint8_t (0-255)
        self._state.l2_state = int(max(0.0, min(1.0, l2)) * 255)
        self._state.r2_state = int(max(0.0, min(1.0, r2)) * 255)
        self._send_state()

    def _send_state(self):
        """Send current controller state to the session."""
        if self.session._connected and self.session._session is not None:
            err = _chiaki._lib.chiaki_session_set_controller_state(
                ctypes.byref(self.session._session),
                ctypes.byref(self._state)
            )
            if err != _chiaki.CHIAKI_ERR_SUCCESS:
                print(f"Warning: Failed to send controller state: {_chiaki.error_string(err)}")
