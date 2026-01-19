#!/usr/bin/env python3
"""
PS4 Remote Play Screenshot Example

This example demonstrates how to:
1. Connect to a PS4 using credentials from Chiaki config
2. Send controller input (PS button to wake display)
3. Request and capture a screenshot (IDR frame)
4. Decode the H.264 frame to PNG using ffmpeg

Requirements:
- ffmpeg installed (for decoding H.264 to PNG)
- Chiaki credentials configured (~/.config/Chiaki/Chiaki.conf)
- PS4 in rest mode or powered on

Usage:
    python3 screenshot.py [console_name] [output_path]

    console_name: Name of console in Chiaki config (default: PS4-910)
    output_path: Where to save the screenshot (default: ./screenshot.png)
"""

import sys
import ctypes
import time
import base64
import subprocess
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chiaki_python import _chiaki
from chiaki_python.config_parser import get_host_by_name


def take_screenshot(console_name: str = "PS4-910", output_path: str = "screenshot.png") -> bool:
    """
    Connect to PS4 and capture a screenshot.

    Args:
        console_name: Name of the console in Chiaki config
        output_path: Path to save the PNG screenshot

    Returns:
        True if screenshot was captured successfully
    """
    print(f"Connecting to {console_name}...")

    # Load credentials from Chiaki config
    try:
        host_config = get_host_by_name(console_name)
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Make sure Chiaki is configured with your PS4 credentials")
        return False

    HOST = host_config['host']
    REGIST_KEY = host_config['regist_key']
    RP_KEY = host_config['rp_key']

    # PSN Account ID (base64 encoded, 8 bytes)
    # Get from config or use default (this is the account ID linked to your PS4)
    PSN_ID = host_config.get('psn_account_id', "U3hhcG9sbG8=")  # Default: "Shxpollo"
    psn_bytes = base64.b64decode(PSN_ID)
    psn_array = (ctypes.c_uint8 * 8)(*psn_bytes[:8])

    print(f"  Host: {HOST}")

    # Create session (720p @ 60fps)
    session = _chiaki._lib.chiaki_python_session_create(
        HOST.encode('utf-8'),
        REGIST_KEY.encode('utf-8'),
        RP_KEY.encode('utf-8'),
        psn_array,
        False,  # is_ps5
        3,      # resolution: 1=360p, 2=540p, 3=720p, 4=1080p
        60      # fps: 30 or 60
    )

    if not session:
        print("Failed to create session!")
        return False

    # Start session
    if not _chiaki._lib.chiaki_python_session_start(session):
        print("Failed to start session!")
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    # Wait for connection (15 second timeout)
    print("Waiting for connection...")
    connected = _chiaki._lib.chiaki_python_session_wait_connected(session, 15000)

    if not connected:
        print("Connection failed!")
        _chiaki._lib.chiaki_python_session_stop(session)
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    print("Connected!")

    # Press PS button to wake display (in case console is in standby screen)
    PS_BUTTON = _chiaki.CHIAKI_CONTROLLER_BUTTON_PS
    _chiaki._lib.chiaki_python_session_set_controller(
        session, PS_BUTTON, 0, 0, 0, 0, 0, 0
    )
    time.sleep(0.1)
    _chiaki._lib.chiaki_python_session_set_controller(
        session, 0, 0, 0, 0, 0, 0, 0  # Release all buttons
    )

    # Wait for display to wake
    print("Waiting for display...")
    time.sleep(1.5)

    # Request a fresh IDR frame (keyframe)
    print("Requesting screenshot...")
    _chiaki._lib.chiaki_python_session_request_idr(session)

    # Wait for I-frame to arrive (up to 5 seconds)
    for i in range(50):
        if _chiaki._lib.chiaki_python_session_has_iframe(session):
            break
        time.sleep(0.1)

    # Capture the I-frame
    FRAME_BUFFER_SIZE = 4 * 1024 * 1024  # 4MB buffer
    frame_buffer = (ctypes.c_uint8 * FRAME_BUFFER_SIZE)()

    frame_size = _chiaki._lib.chiaki_python_session_get_iframe(
        session, frame_buffer, FRAME_BUFFER_SIZE
    )

    success = False
    if frame_size > 0:
        print(f"Captured frame: {frame_size} bytes")

        # Save raw H.264 frame
        frame_data = bytes(frame_buffer[:frame_size])
        h264_path = '/tmp/ps4_frame.h264'
        with open(h264_path, 'wb') as f:
            f.write(frame_data)

        # Decode to PNG using ffmpeg
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', h264_path, '-frames:v', '1', output_path],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            print(f"Screenshot saved to: {output_path}")
            success = True
        else:
            print(f"ffmpeg decode failed: {result.stderr[:200]}")

        # Cleanup temp file
        os.remove(h264_path)
    else:
        print("No frame captured!")

    # Cleanup
    _chiaki._lib.chiaki_python_session_stop(session)
    _chiaki._lib.chiaki_python_session_destroy(session)

    return success


def main():
    console_name = sys.argv[1] if len(sys.argv) > 1 else "PS4-910"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "screenshot.png"

    success = take_screenshot(console_name, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
