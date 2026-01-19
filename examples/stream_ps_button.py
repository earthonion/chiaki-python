#!/usr/bin/env python3
"""
PS4 Remote Play - Stream with PS Button Hold

Connects to PS4, starts video stream with ffplay, holds PS button for 2 seconds,
releases, then continues streaming.

Usage:
    python3 stream_ps_button.py [console_name]

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

# Button constants
PS = _chiaki.CHIAKI_CONTROLLER_BUTTON_PS
CROSS = _chiaki.CHIAKI_CONTROLLER_BUTTON_CROSS
DPAD_UP = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_UP
DPAD_DOWN = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN
DPAD_RIGHT = _chiaki.CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT


def send_controller(session, buttons=0, left_x=0, left_y=0, right_x=0, right_y=0, l2=0, r2=0):
    """Send controller state to PS4."""
    _chiaki._lib.chiaki_python_session_set_controller(
        session, buttons, left_x, left_y, right_x, right_y, l2, r2
    )


def press_button(session, button, duration=0.15):
    """Press and release a button."""
    send_controller(session, buttons=button)
    time.sleep(duration)
    send_controller(session, buttons=0)
    time.sleep(0.1)  # Small delay between presses


def stream_with_ps_button(console_name: str = "PS4-910"):
    """Stream video with ffplay and hold PS button for 2 seconds."""

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

    # Create session (720p @ 60fps)
    session = _chiaki._lib.chiaki_python_session_create(
        HOST.encode('utf-8'),
        REGIST_KEY.encode('utf-8'),
        RP_KEY.encode('utf-8'),
        psn_array,
        False,  # is_ps5
        3,      # 720p
        60      # 60fps
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

    # Request an IDR frame to get SPS/PPS headers
    _chiaki._lib.chiaki_python_session_request_idr(session)

    # Wait for I-frame with headers
    iframe_timeout = time.time() + 5.0
    while not _chiaki._lib.chiaki_python_session_has_iframe(session):
        if time.time() > iframe_timeout:
            print("Timeout waiting for I-frame")
            _chiaki._lib.chiaki_python_session_stop(session)
            _chiaki._lib.chiaki_python_session_destroy(session)
            return False
        time.sleep(0.01)

    # Get the I-frame with SPS/PPS headers
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

    # Send the I-frame first
    iframe_data = bytes(frame_buffer[:iframe_size])
    ffplay.stdin.write(iframe_data)
    ffplay.stdin.flush()

    # Start frame streaming in background thread
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

    print("Streaming! Waiting 1 second...")
    time.sleep(1.0)

    # Hold PS button for 2 seconds
    print("Holding PS button for 2 seconds...")
    send_controller(session, buttons=PS)
    time.sleep(2.0)
    print("Releasing PS button...")
    send_controller(session, buttons=0)

    # Press up 5 times
    print("Pressing up 5 times...")
    for _ in range(5):
        press_button(session, DPAD_UP)

    time.sleep(0.3)

    # Navigate: down, down, right, down, down, X
    print("Navigating: down, down, right, down, down, X")
    press_button(session, DPAD_DOWN)
    press_button(session, DPAD_DOWN)
    press_button(session, DPAD_RIGHT)
    press_button(session, DPAD_DOWN)
    press_button(session, DPAD_DOWN)
    press_button(session, CROSS)

    print("Continuing stream... Press Ctrl+C to stop")

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\nStopping...")
    signal.signal(signal.SIGINT, signal_handler)

    # Wait for user to stop
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
    console_name = sys.argv[1] if len(sys.argv) > 1 else "PS4-910"
    stream_with_ps_button(console_name)


if __name__ == "__main__":
    main()
