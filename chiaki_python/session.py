"""
Session management for PlayStation Remote Play connections.
"""

from typing import Optional, Callable
import numpy as np
import base64
import ctypes
import threading
import queue
from . import _chiaki
from .controller import Controller


class PS4Session:
    """
    PlayStation 4 Remote Play session.

    This class manages the connection to a PS4 console using credentials
    from your Chiaki configuration.
    """

    def __init__(self,
                 host: str,
                 regist_key: str,
                 rp_key: str,
                 psn_account_id: Optional[str] = None,
                 resolution: str = "720p",
                 fps: int = 60):
        """
        Initialize a PS4 session.

        Args:
            host: IP address of the PS4
            regist_key: Registration key (hex string, e.g., "d77687f8")
            rp_key: RP key (hex string, 32 chars)
            psn_account_id: PSN account ID (base64 encoded, e.g., "U3hhcG9sbG8=")
            resolution: Video resolution ("360p", "540p", "720p", "1080p")
            fps: Frame rate (30 or 60)
        """
        self.host = host
        self.regist_key = regist_key
        self.rp_key = rp_key
        self.psn_account_id = psn_account_id or "AAAAAAAAAAA="  # Default 8 zero bytes
        self.resolution = resolution
        self.fps = fps

        self._connected = False
        self._controller = Controller(self)
        self._frame_callback = None
        self._frame_queue = queue.Queue(maxsize=1)
        self._session = None
        self._log = None
        self._quit_reason = None
        self._status = {
            'online': False,
            'running_app': None,
            'running_app_id': None
        }

        # Initialize Chiaki library (only once per process)
        try:
            _chiaki.chiaki_lib_init()
        except RuntimeError:
            pass  # Already initialized

    @property
    def controller(self) -> Controller:
        """Get the controller interface."""
        return self._controller

    @property
    def status(self) -> dict:
        """Get current console status."""
        return self._status

    def _log_callback(self, user, level, msg):
        """Internal log callback from Chiaki"""
        try:
            msg_str = msg.decode('utf-8') if msg else ""
            level_names = {
                _chiaki.CHIAKI_LOG_DEBUG: "DEBUG",
                _chiaki.CHIAKI_LOG_VERBOSE: "VERBOSE",
                _chiaki.CHIAKI_LOG_INFO: "INFO",
                _chiaki.CHIAKI_LOG_WARNING: "WARNING",
                _chiaki.CHIAKI_LOG_ERROR: "ERROR",
            }
            level_name = level_names.get(level, f"LEVEL{level}")
            print(f"[Chiaki {level_name}] {msg_str}")
        except Exception as e:
            print(f"Error in log callback: {e}")

    def _event_callback(self, event_ptr, user):
        """Internal event callback from Chiaki"""
        try:
            event = ctypes.cast(event_ptr, ctypes.POINTER(_chiaki.ChiakiEvent)).contents
            if event.type == _chiaki.CHIAKI_EVENT_QUIT:
                self._quit_reason = event.quit.reason
                quit_str = event.quit.reason_str.decode('utf-8') if event.quit.reason_str else ""
                print(f"Session quit: {_chiaki.quit_reason_string(event.quit.reason)} - {quit_str}")
            elif event.type == _chiaki.CHIAKI_EVENT_CONNECTED:
                print("Session connected!")
        except Exception as e:
            print(f"Error in event callback: {e}")

    def _video_sample_callback(self, buf, buf_size, frames_lost, frame_recovered, user):
        """Internal video callback from Chiaki"""
        try:
            # For now, just acknowledge receipt
            # TODO: Decode video frames and convert to numpy arrays
            return True
        except Exception as e:
            print(f"Error in video callback: {e}")
            return False

    def connect(self):
        """
        Connect to the PS4.

        This establishes the Remote Play session.
        """
        if self._connected:
            print("Already connected")
            return

        print(f"Connecting to PS4 at {self.host}...")
        print(f"  Resolution: {self.resolution} @ {self.fps}fps")

        # Initialize logging
        self._log = _chiaki.ChiakiLog()
        log_cb = _chiaki.ChiakiLogCb(self._log_callback)
        _chiaki._lib.chiaki_log_init(
            ctypes.byref(self._log),
            _chiaki.CHIAKI_LOG_ALL,
            log_cb,
            None
        )

        # Parse resolution
        res_map = {
            "360p": _chiaki.CHIAKI_VIDEO_RESOLUTION_PRESET_360p,
            "540p": _chiaki.CHIAKI_VIDEO_RESOLUTION_PRESET_540p,
            "720p": _chiaki.CHIAKI_VIDEO_RESOLUTION_PRESET_720p,
            "1080p": _chiaki.CHIAKI_VIDEO_RESOLUTION_PRESET_1080p,
        }
        res_preset = res_map.get(self.resolution, _chiaki.CHIAKI_VIDEO_RESOLUTION_PRESET_720p)

        fps_map = {30: _chiaki.CHIAKI_VIDEO_FPS_PRESET_30, 60: _chiaki.CHIAKI_VIDEO_FPS_PRESET_60}
        fps_preset = fps_map.get(self.fps, _chiaki.CHIAKI_VIDEO_FPS_PRESET_60)

        # Set up video profile
        video_profile = _chiaki.ChiakiConnectVideoProfile()
        _chiaki._lib.chiaki_connect_video_profile_preset(
            ctypes.byref(video_profile),
            res_preset,
            fps_preset
        )

        # Set up connect info
        connect_info = _chiaki.ChiakiConnectInfo()
        connect_info.ps5 = False
        connect_info.host = self.host.encode('utf-8')

        # Parse regist key (hex string to bytes, pad to 16 bytes)
        regist_key_bytes = bytes.fromhex(self.regist_key)
        regist_key_padded = regist_key_bytes + b'\x00' * (16 - len(regist_key_bytes))
        for i, b in enumerate(regist_key_padded[:16]):
            connect_info.regist_key[i] = b

        # Parse RP key (morning field)
        rp_key_bytes = bytes.fromhex(self.rp_key)
        for i, b in enumerate(rp_key_bytes[:16]):
            connect_info.morning[i] = b

        # Parse PSN account ID (base64 to bytes)
        psn_id_bytes = base64.b64decode(self.psn_account_id)
        for i, b in enumerate(psn_id_bytes[:8]):
            connect_info.psn_account_id[i] = b

        connect_info.video_profile = video_profile
        connect_info.video_profile_auto_downgrade = True
        connect_info.enable_keyboard = False
        connect_info.enable_dualsense = False
        connect_info.audio_video_disabled = 0
        connect_info.auto_regist = False
        connect_info.holepunch_session = None
        connect_info.rudp_sock = None
        connect_info.packet_loss_max = 0.0
        connect_info.enable_idr_on_fec_failure = True

        # Initialize session - allocate enough space
        # ChiakiSession is a large structure, allocate it properly
        session_size = ctypes.sizeof(_chiaki.ChiakiSession)
        self._session = _chiaki.ChiakiSession()

        err = _chiaki._lib.chiaki_session_init(
            ctypes.byref(self._session),
            ctypes.byref(connect_info),
            ctypes.byref(self._log)
        )

        if err != _chiaki.CHIAKI_ERR_SUCCESS:
            raise RuntimeError(f"Failed to initialize session: {_chiaki.error_string(err)}")

        # Set up callbacks using wrapper functions
        # Store callbacks as instance variables to prevent garbage collection
        self._event_cb = _chiaki.ChiakiEventCallback(self._event_callback)
        _chiaki._lib.chiaki_session_set_event_cb_wrapper(
            ctypes.byref(self._session),
            self._event_cb,
            None
        )

        self._video_cb = _chiaki.ChiakiVideoSampleCallback(self._video_sample_callback)
        _chiaki._lib.chiaki_session_set_video_sample_cb_wrapper(
            ctypes.byref(self._session),
            self._video_cb,
            None
        )

        # Start session
        err = _chiaki._lib.chiaki_session_start(ctypes.byref(self._session))
        if err != _chiaki.CHIAKI_ERR_SUCCESS:
            _chiaki._lib.chiaki_session_fini(ctypes.byref(self._session))
            raise RuntimeError(f"Failed to start session: {_chiaki.error_string(err)}")

        self._connected = True
        print("✓ Session started!")

    def disconnect(self):
        """Disconnect from the PS4."""
        if not self._connected or self._session is None:
            return

        print("Disconnecting from PS4...")

        # Stop the session
        _chiaki._lib.chiaki_session_stop(ctypes.byref(self._session))

        # Wait for session thread to finish
        _chiaki._lib.chiaki_session_join(ctypes.byref(self._session))

        # Clean up session
        _chiaki._lib.chiaki_session_fini(ctypes.byref(self._session))

        self._connected = False
        self._session = None
        print("✓ Disconnected")

    def screenshot(self) -> Optional[np.ndarray]:
        """
        Capture a screenshot from the current video stream.

        Returns:
            numpy array with shape (height, width, 3) in RGB format,
            or None if no frame is available
        """
        # TODO: Implement frame capture from Chiaki video stream
        # This will extract the latest decoded frame
        return None

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """
        Set a callback to receive video frames.

        Args:
            callback: Function that takes a numpy array (height, width, 3) RGB frame
        """
        self._frame_callback = callback

    def is_online(self) -> bool:
        """Check if the PS4 is online and reachable."""
        return self._status['online']

    def get_running_app(self) -> Optional[str]:
        """
        Get the name of the currently running application.

        Returns:
            App name or None if idle
        """
        return self._status['running_app']

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class PS5Session(PS4Session):
    """
    PlayStation 5 Remote Play session.

    Inherits from PS4Session with PS5-specific features.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # PS5-specific initialization
        self._ps5_features = {
            'haptic_feedback': True,
            'adaptive_triggers': True
        }
