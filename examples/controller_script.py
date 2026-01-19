#!/usr/bin/env python3
"""
PS4 Remote Play - Controller Script Runner

Reads controller commands from a script file and executes them.
Similar to DuckyScript for PS4 controller input.

Usage:
    python3 controller_script.py [script_file] [console_name]
    python3 controller_script.py my_script.txt PS4-910

Script Format:
    BUTTON [duration]   - Press button for duration (default 0.25s)
    DELAY seconds       - Wait before next command
    # comment           - Ignored

Supported Buttons:
    PS, X, CROSS, O, CIRCLE, SQUARE, TRIANGLE
    UP, DOWN, LEFT, RIGHT (D-pad)
    L1, R1, L2, R2, L3, R3
    OPTIONS, SHARE, TOUCHPAD

Example Script:
    # Open PS menu and navigate
    PS 2.0
    DELAY 0.3
    UP
    UP
    DOWN
    DOWN
    RIGHT
    X

Press Ctrl+C to stop.
"""

import sys
import ctypes
import time
import base64
import subprocess
import os
import signal
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chiaki_python import _chiaki
from chiaki_python.config_parser import get_host_by_name

# Button name mapping
BUTTONS = {
    'PS': _chiaki.CHIAKI_CONTROLLER_BUTTON_PS,
    'X': _chiaki.CHIAKI_CONTROLLER_BUTTON_CROSS,
    'CROSS': _chiaki.CHIAKI_CONTROLLER_BUTTON_CROSS,
    'O': _chiaki.CHIAKI_CONTROLLER_BUTTON_MOON,
    'CIRCLE': _chiaki.CHIAKI_CONTROLLER_BUTTON_MOON,
    'SQUARE': _chiaki.CHIAKI_CONTROLLER_BUTTON_BOX,
    'TRIANGLE': _chiaki.CHIAKI_CONTROLLER_BUTTON_PYRAMID,
    'UP': _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_UP,
    'DOWN': _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN,
    'LEFT': _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT,
    'RIGHT': _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT,
    'L1': _chiaki.CHIAKI_CONTROLLER_BUTTON_L1,
    'R1': _chiaki.CHIAKI_CONTROLLER_BUTTON_R1,
    'L3': _chiaki.CHIAKI_CONTROLLER_BUTTON_L3,
    'R3': _chiaki.CHIAKI_CONTROLLER_BUTTON_R3,
    'OPTIONS': _chiaki.CHIAKI_CONTROLLER_BUTTON_OPTIONS,
    'SHARE': _chiaki.CHIAKI_CONTROLLER_BUTTON_SHARE,
    'TOUCHPAD': _chiaki.CHIAKI_CONTROLLER_BUTTON_TOUCHPAD,
}

DEFAULT_DURATION = 0.25
DEFAULT_GAP = 0.1  # Gap between button presses


def send_controller(session, buttons=0, l2=0, r2=0):
    """Send controller state to PS4."""
    _chiaki._lib.chiaki_python_session_set_controller(
        session, buttons, 0, 0, 0, 0, l2, r2
    )


def press_button(session, button, duration=DEFAULT_DURATION):
    """Press and release a button."""
    send_controller(session, buttons=button)
    time.sleep(duration)
    send_controller(session, buttons=0)
    time.sleep(DEFAULT_GAP)


def parse_script(script_path):
    """Parse a controller script file and return list of commands."""
    commands = []

    with open(script_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            cmd = parts[0].upper()

            if cmd == 'DELAY':
                if len(parts) < 2:
                    print(f"Warning line {line_num}: DELAY requires duration, using 0.5s")
                    duration = 0.5
                else:
                    try:
                        duration = float(parts[1])
                    except ValueError:
                        print(f"Warning line {line_num}: Invalid duration '{parts[1]}', using 0.5s")
                        duration = 0.5
                commands.append(('DELAY', duration))

            elif cmd == 'L2' or cmd == 'R2':
                # Trigger buttons (0-255 value)
                value = 255
                duration = DEFAULT_DURATION
                if len(parts) >= 2:
                    try:
                        duration = float(parts[1])
                    except ValueError:
                        pass
                commands.append((cmd, duration, value))

            elif cmd in BUTTONS:
                duration = DEFAULT_DURATION
                if len(parts) >= 2:
                    try:
                        duration = float(parts[1])
                    except ValueError:
                        print(f"Warning line {line_num}: Invalid duration '{parts[1]}', using default")
                commands.append(('BUTTON', cmd, duration))

            else:
                print(f"Warning line {line_num}: Unknown command '{cmd}'")

    return commands


def run_script(console_name: str, script_path: str):
    """Connect to PS4, run script, and stream video."""

    # Parse script first
    if not os.path.exists(script_path):
        print(f"Error: Script file not found: {script_path}")
        return False

    commands = parse_script(script_path)
    print(f"Loaded {len(commands)} commands from {script_path}")

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
    PSN_ID = host_config.get('psn_account_id', "U3hhcG9sbG8=")
    psn_bytes = base64.b64decode(PSN_ID)
    psn_array = (ctypes.c_uint8 * 8)(*psn_bytes[:8])

    # Create session
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

    print("Connected! Waiting for keyframe...")

    # Buffer for frames
    FRAME_BUFFER_SIZE = 4 * 1024 * 1024
    frame_buffer = (ctypes.c_uint8 * FRAME_BUFFER_SIZE)()
    seq_out = ctypes.c_uint64(0)

    # Request IDR frame
    _chiaki._lib.chiaki_python_session_request_idr(session)

    # Wait for I-frame
    iframe_timeout = time.time() + 5.0
    while not _chiaki._lib.chiaki_python_session_has_iframe(session):
        if time.time() > iframe_timeout:
            print("Timeout waiting for I-frame")
            _chiaki._lib.chiaki_python_session_stop(session)
            _chiaki._lib.chiaki_python_session_destroy(session)
            return False
        time.sleep(0.01)

    iframe_size = _chiaki._lib.chiaki_python_session_get_iframe(session, frame_buffer, FRAME_BUFFER_SIZE)
    if iframe_size == 0:
        print("Failed to get I-frame")
        _chiaki._lib.chiaki_python_session_stop(session)
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    print(f"Got I-frame: {iframe_size} bytes, starting ffplay...")

    # Start ffplay
    ffplay = subprocess.Popen(
        [
            'ffplay',
            '-f', 'h264',
            '-probesize', '32768',
            '-analyzeduration', '0',
            '-fflags', 'nobuffer+fastseek+flush_packets',
            '-flags', 'low_delay',
            '-framedrop',
            '-an',
            '-window_title', f'PS4 - {console_name}',
            '-i', 'pipe:0'
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    # Send I-frame
    iframe_data = bytes(frame_buffer[:iframe_size])
    ffplay.stdin.write(iframe_data)
    ffplay.stdin.flush()

    # Start streaming thread
    running = True
    last_seq = 0

    def stream_frames():
        nonlocal last_seq
        while running and ffplay.poll() is None:
            frame_size = _chiaki._lib.chiaki_python_session_get_frame_ex(
                session, frame_buffer, FRAME_BUFFER_SIZE, ctypes.byref(seq_out)
            )
            current_seq = seq_out.value
            if frame_size > 0 and current_seq > last_seq:
                frame_data = bytes(frame_buffer[:frame_size])
                last_seq = current_seq
                try:
                    ffplay.stdin.write(frame_data)
                    ffplay.stdin.flush()
                except BrokenPipeError:
                    break
            time.sleep(0.002)

    stream_thread = threading.Thread(target=stream_frames, daemon=True)
    stream_thread.start()

    print("Streaming! Waiting 1 second before running script...")
    time.sleep(1.0)

    # Execute script commands
    print("Running script...")
    for cmd in commands:
        if cmd[0] == 'DELAY':
            print(f"  DELAY {cmd[1]}s")
            time.sleep(cmd[1])
        elif cmd[0] == 'BUTTON':
            button_name = cmd[1]
            duration = cmd[2]
            print(f"  {button_name} ({duration}s)")
            press_button(session, BUTTONS[button_name], duration)
        elif cmd[0] == 'L2':
            duration = cmd[1]
            print(f"  L2 ({duration}s)")
            send_controller(session, l2=255)
            time.sleep(duration)
            send_controller(session)
            time.sleep(DEFAULT_GAP)
        elif cmd[0] == 'R2':
            duration = cmd[1]
            print(f"  R2 ({duration}s)")
            send_controller(session, r2=255)
            time.sleep(duration)
            send_controller(session)
            time.sleep(DEFAULT_GAP)

    print("Script complete! Press Ctrl+C to stop streaming")

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\nStopping...")
    signal.signal(signal.SIGINT, signal_handler)

    # Keep streaming
    while running and ffplay.poll() is None:
        time.sleep(0.1)

    running = False
    stream_thread.join(timeout=1.0)

    # Cleanup
    if ffplay.poll() is None:
        ffplay.terminate()
        try:
            ffplay.wait(timeout=2)
        except:
            ffplay.kill()

    _chiaki._lib.chiaki_python_session_stop(session)
    _chiaki._lib.chiaki_python_session_destroy(session)
    print("Disconnected.")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 controller_script.py <script_file> [console_name]")
        print("Example: python3 controller_script.py my_script.txt PS4-910")
        sys.exit(1)

    script_path = sys.argv[1]
    console_name = sys.argv[2] if len(sys.argv) > 2 else "PS4-910"

    run_script(console_name, script_path)


if __name__ == "__main__":
    main()
