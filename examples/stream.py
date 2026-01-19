#!/usr/bin/env python3
"""
PS4 Remote Play Video Streaming Example

Streams video from PS4 and displays it using ffplay.

Usage:
    python3 stream.py [console_name]

Press Ctrl+C to stop.
"""

import sys
import ctypes
import time
import base64
import subprocess
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chiaki_python import _chiaki
from chiaki_python.config_parser import get_host_by_name


def stream_video(console_name: str = "PS4-910"):
    """Stream video from PS4 to ffplay."""

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

    # Wait for I-frame with headers (required for ffplay to start decoding)
    print("Requesting IDR frame...")
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

    print(f"Got I-frame: {iframe_size} bytes")

    # Start ffplay with pipe input
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

    # Send the I-frame first (contains SPS/PPS + IDR)
    try:
        iframe_data = bytes(frame_buffer[:iframe_size])
        ffplay.stdin.write(iframe_data)
        ffplay.stdin.flush()
        print("Sent initial I-frame to ffplay")
    except BrokenPipeError:
        print("ffplay closed immediately")
        _chiaki._lib.chiaki_python_session_stop(session)
        _chiaki._lib.chiaki_python_session_destroy(session)
        return False

    print("Streaming video... Press Ctrl+C to stop")

    last_seq = 0
    frames_sent = 1  # Already sent I-frame
    frames_missed = 0
    start_time = time.time()

    # Handle Ctrl+C gracefully
    running = True
    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\nStopping...")
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while running and ffplay.poll() is None:
            # Get frame with sequence number
            frame_size = _chiaki._lib.chiaki_python_session_get_frame_ex(
                session, frame_buffer, FRAME_BUFFER_SIZE, ctypes.byref(seq_out)
            )

            current_seq = seq_out.value

            # Check if this is a new frame
            if frame_size > 0 and current_seq > last_seq:
                # Track missed frames
                if last_seq > 0 and current_seq > last_seq + 1:
                    frames_missed += current_seq - last_seq - 1

                frame_data = bytes(frame_buffer[:frame_size])
                last_seq = current_seq

                try:
                    ffplay.stdin.write(frame_data)
                    ffplay.stdin.flush()
                    frames_sent += 1

                    if frames_sent <= 10 or frames_sent % 100 == 0:
                        nal = frame_data[4] & 0x1f if len(frame_data) > 4 else -1
                        elapsed = time.time() - start_time
                        fps = frames_sent / elapsed if elapsed > 0 else 0
                        print(f"Frame {frames_sent}: {frame_size} bytes, NAL={nal}, missed={frames_missed}, FPS={fps:.1f}")
                except BrokenPipeError:
                    print("ffplay closed")
                    break

            # Poll at 500Hz to catch as many frames as possible
            time.sleep(0.002)

    except Exception as e:
        print(f"Error: {e}")

    elapsed = time.time() - start_time
    fps = frames_sent / elapsed if elapsed > 0 else 0
    print(f"Sent {frames_sent} frames, missed {frames_missed}, in {elapsed:.1f}s ({fps:.1f} fps)")

    # Cleanup
    if ffplay.poll() is None:
        ffplay.terminate()
        try:
            ffplay.wait(timeout=2)
        except:
            ffplay.kill()

    _chiaki._lib.chiaki_python_session_stop(session)
    _chiaki._lib.chiaki_python_session_destroy(session)

    return True


def main():
    console_name = sys.argv[1] if len(sys.argv) > 1 else "PS4-910"
    stream_video(console_name)


if __name__ == "__main__":
    main()
