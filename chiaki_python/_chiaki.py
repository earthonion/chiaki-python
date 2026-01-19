"""
Low-level ctypes bindings for the Chiaki C library.
"""

import ctypes
from ctypes import (
    c_void_p, c_char_p, c_uint32, c_uint16, c_uint8, c_int8, c_int16,
    c_int32, c_uint64, c_size_t, c_bool, c_float, c_double, POINTER, Structure,
    CFUNCTYPE
)

# Load the Chiaki shared library
import os
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIAKI_LIB_PATH = os.path.join(_BASE_DIR, 'libchiaki.so')
try:
    _lib = ctypes.CDLL(CHIAKI_LIB_PATH)
except OSError as e:
    raise RuntimeError(f"Failed to load Chiaki library from {CHIAKI_LIB_PATH}: {e}")

# Constants
CHIAKI_RPCRYPT_KEY_SIZE = 0x10
CHIAKI_RP_DID_SIZE = 32
CHIAKI_SESSION_AUTH_SIZE = 0x10
CHIAKI_PSN_ACCOUNT_ID_SIZE = 8
CHIAKI_CONTROLLER_TOUCHES_MAX = 2

# Error codes
CHIAKI_ERR_SUCCESS = 0
CHIAKI_ERR_UNKNOWN = 1
CHIAKI_ERR_PARSE_ADDR = 2
CHIAKI_ERR_THREAD = 3
CHIAKI_ERR_MEMORY = 4
CHIAKI_ERR_NETWORK = 7
CHIAKI_ERR_TIMEOUT = 16

# Target (PS4/PS5 version)
CHIAKI_TARGET_PS4_UNKNOWN = 0
CHIAKI_TARGET_PS4_8 = 800
CHIAKI_TARGET_PS4_9 = 900
CHIAKI_TARGET_PS4_10 = 1000
CHIAKI_TARGET_PS5_UNKNOWN = 1000000
CHIAKI_TARGET_PS5_1 = 1000100

# Video resolution presets
CHIAKI_VIDEO_RESOLUTION_PRESET_360p = 1
CHIAKI_VIDEO_RESOLUTION_PRESET_540p = 2
CHIAKI_VIDEO_RESOLUTION_PRESET_720p = 3
CHIAKI_VIDEO_RESOLUTION_PRESET_1080p = 4

# Video FPS presets
CHIAKI_VIDEO_FPS_PRESET_30 = 30
CHIAKI_VIDEO_FPS_PRESET_60 = 60

# Codec
CHIAKI_CODEC_H264 = 0
CHIAKI_CODEC_H265 = 1

# Controller buttons (bitmask)
CHIAKI_CONTROLLER_BUTTON_CROSS = (1 << 0)
CHIAKI_CONTROLLER_BUTTON_MOON = (1 << 1)
CHIAKI_CONTROLLER_BUTTON_BOX = (1 << 2)
CHIAKI_CONTROLLER_BUTTON_PYRAMID = (1 << 3)
CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT = (1 << 4)
CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT = (1 << 5)
CHIAKI_CONTROLLER_BUTTON_DPAD_UP = (1 << 6)
CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN = (1 << 7)
CHIAKI_CONTROLLER_BUTTON_L1 = (1 << 8)
CHIAKI_CONTROLLER_BUTTON_R1 = (1 << 9)
CHIAKI_CONTROLLER_BUTTON_L3 = (1 << 10)
CHIAKI_CONTROLLER_BUTTON_R3 = (1 << 11)
CHIAKI_CONTROLLER_BUTTON_OPTIONS = (1 << 12)
CHIAKI_CONTROLLER_BUTTON_SHARE = (1 << 13)
CHIAKI_CONTROLLER_BUTTON_TOUCHPAD = (1 << 14)
CHIAKI_CONTROLLER_BUTTON_PS = (1 << 15)

# Analog buttons
CHIAKI_CONTROLLER_ANALOG_BUTTON_L2 = (1 << 16)
CHIAKI_CONTROLLER_ANALOG_BUTTON_R2 = (1 << 17)

# Quit reasons
CHIAKI_QUIT_REASON_NONE = 0
CHIAKI_QUIT_REASON_STOPPED = 1
CHIAKI_QUIT_REASON_SESSION_REQUEST_CONNECTION_REFUSED = 3

# Event types
CHIAKI_EVENT_CONNECTED = 0
CHIAKI_EVENT_LOGIN_PIN_REQUEST = 1
CHIAKI_EVENT_QUIT = 9

# Log levels
CHIAKI_LOG_DEBUG = (1 << 0)
CHIAKI_LOG_VERBOSE = (1 << 1)
CHIAKI_LOG_INFO = (1 << 2)
CHIAKI_LOG_WARNING = (1 << 3)
CHIAKI_LOG_ERROR = (1 << 4)
CHIAKI_LOG_ALL = 0xffffffff


# Callback types
ChiakiLogCb = CFUNCTYPE(None, c_void_p, c_uint32, c_char_p)
ChiakiEventCallback = CFUNCTYPE(None, c_void_p, c_void_p)
ChiakiVideoSampleCallback = CFUNCTYPE(c_bool, POINTER(c_uint8), c_size_t, c_int32, c_bool, c_void_p)


# Structures
class ChiakiLog(Structure):
    _fields_ = [
        ("level_mask", c_uint32),
        ("cb", ChiakiLogCb),
        ("user", c_void_p)
    ]


class ChiakiControllerTouch(Structure):
    _fields_ = [
        ("x", c_uint16),
        ("y", c_uint16),
        ("id", c_int8)
    ]


class ChiakiControllerState(Structure):
    _fields_ = [
        ("buttons", c_uint32),
        ("l2_state", c_uint8),
        ("r2_state", c_uint8),
        ("left_x", c_int16),
        ("left_y", c_int16),
        ("right_x", c_int16),
        ("right_y", c_int16),
        ("touch_id_next", c_uint8),
        ("touches", ChiakiControllerTouch * CHIAKI_CONTROLLER_TOUCHES_MAX),
        ("gyro_x", c_float),
        ("gyro_y", c_float),
        ("gyro_z", c_float),
        ("accel_x", c_float),
        ("accel_y", c_float),
        ("accel_z", c_float),
        ("orient_x", c_float),
        ("orient_y", c_float),
        ("orient_z", c_float),
        ("orient_w", c_float),
    ]


class ChiakiConnectVideoProfile(Structure):
    _fields_ = [
        ("width", c_uint32),
        ("height", c_uint32),
        ("max_fps", c_uint32),
        ("bitrate", c_uint32),
        ("codec", c_uint32)
    ]


class ChiakiConnectInfo(Structure):
    _fields_ = [
        ("ps5", c_bool),
        ("host", c_char_p),
        ("regist_key", c_uint8 * CHIAKI_SESSION_AUTH_SIZE),
        ("morning", c_uint8 * 0x10),
        ("video_profile", ChiakiConnectVideoProfile),
        ("video_profile_auto_downgrade", c_bool),
        ("enable_keyboard", c_bool),
        ("enable_dualsense", c_bool),
        ("audio_video_disabled", c_uint8),  # ChiakiDisableAudioVideo enum
        ("auto_regist", c_bool),
        ("holepunch_session", c_void_p),  # Simplified, not implementing holepunch for now
        ("rudp_sock", c_void_p),
        ("psn_account_id", c_uint8 * CHIAKI_PSN_ACCOUNT_ID_SIZE),
        ("packet_loss_max", c_double),
        ("enable_idr_on_fec_failure", c_bool),
    ]


class ChiakiQuitEvent(Structure):
    _fields_ = [
        ("reason", c_uint32),
        ("reason_str", c_char_p)
    ]


class ChiakiEvent(Structure):
    """Simplified event structure - only handling quit events for now"""
    _fields_ = [
        ("type", c_uint32),
        ("quit", ChiakiQuitEvent)  # Union simplified to just quit event
    ]


# Opaque session structure - we don't need to define all fields
class ChiakiSession(Structure):
    pass


# Function declarations
_lib.chiaki_lib_init.argtypes = []
_lib.chiaki_lib_init.restype = c_uint32

_lib.chiaki_error_string.argtypes = [c_uint32]
_lib.chiaki_error_string.restype = c_char_p

_lib.chiaki_log_init.argtypes = [POINTER(ChiakiLog), c_uint32, ChiakiLogCb, c_void_p]
_lib.chiaki_log_init.restype = None

_lib.chiaki_connect_video_profile_preset.argtypes = [
    POINTER(ChiakiConnectVideoProfile), c_uint32, c_uint32
]
_lib.chiaki_connect_video_profile_preset.restype = None

_lib.chiaki_session_init.argtypes = [
    POINTER(ChiakiSession), POINTER(ChiakiConnectInfo), POINTER(ChiakiLog)
]
_lib.chiaki_session_init.restype = c_uint32

_lib.chiaki_session_fini.argtypes = [POINTER(ChiakiSession)]
_lib.chiaki_session_fini.restype = None

_lib.chiaki_session_start.argtypes = [POINTER(ChiakiSession)]
_lib.chiaki_session_start.restype = c_uint32

_lib.chiaki_session_stop.argtypes = [POINTER(ChiakiSession)]
_lib.chiaki_session_stop.restype = c_uint32

_lib.chiaki_session_join.argtypes = [POINTER(ChiakiSession)]
_lib.chiaki_session_join.restype = c_uint32

_lib.chiaki_session_set_controller_state.argtypes = [
    POINTER(ChiakiSession), POINTER(ChiakiControllerState)
]
_lib.chiaki_session_set_controller_state.restype = c_uint32

_lib.chiaki_controller_state_set_idle.argtypes = [POINTER(ChiakiControllerState)]
_lib.chiaki_controller_state_set_idle.restype = None

_lib.chiaki_quit_reason_string.argtypes = [c_uint32]
_lib.chiaki_quit_reason_string.restype = c_char_p

# Wrapper functions for inline functions (not needed for simplified Python API)
# These would require wrapper functions in the C library
# _lib.chiaki_session_set_event_cb_wrapper.argtypes = [
#     POINTER(ChiakiSession), ChiakiEventCallback, c_void_p
# ]
# _lib.chiaki_session_set_event_cb_wrapper.restype = None

# _lib.chiaki_session_set_video_sample_cb_wrapper.argtypes = [
#     POINTER(ChiakiSession), ChiakiVideoSampleCallback, c_void_p
# ]
# _lib.chiaki_session_set_video_sample_cb_wrapper.restype = None


# Helper functions
def chiaki_lib_init():
    """Initialize the Chiaki library"""
    err = _lib.chiaki_lib_init()
    if err != CHIAKI_ERR_SUCCESS:
        raise RuntimeError(f"Failed to initialize Chiaki library: {error_string(err)}")


def error_string(error_code):
    """Get error string from error code"""
    s = _lib.chiaki_error_string(error_code)
    return s.decode('utf-8') if s else f"Unknown error {error_code}"


def quit_reason_string(reason):
    """Get quit reason string"""
    s = _lib.chiaki_quit_reason_string(reason)
    return s.decode('utf-8') if s else f"Unknown reason {reason}"


# ============================================================
# Python Wrapper Functions (simplified API)
# ============================================================

# Define opaque pointer for PythonSession
class PythonSession(Structure):
    pass

PythonSessionPtr = POINTER(PythonSession)

# chiaki_python_session_create
_lib.chiaki_python_session_create.argtypes = [
    c_char_p,           # host
    c_char_p,           # regist_key_hex
    c_char_p,           # rp_key_hex
    POINTER(c_uint8),   # psn_account_id (8 bytes)
    c_bool,             # is_ps5
    c_int32,            # resolution_preset
    c_int32             # fps_preset
]
_lib.chiaki_python_session_create.restype = PythonSessionPtr

# chiaki_python_session_start
_lib.chiaki_python_session_start.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_start.restype = c_bool

# chiaki_python_session_wait_connected
_lib.chiaki_python_session_wait_connected.argtypes = [PythonSessionPtr, c_int32]
_lib.chiaki_python_session_wait_connected.restype = c_bool

# chiaki_python_session_is_connected
_lib.chiaki_python_session_is_connected.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_is_connected.restype = c_bool

# chiaki_python_session_set_controller
_lib.chiaki_python_session_set_controller.argtypes = [
    PythonSessionPtr,
    c_uint32,   # buttons
    c_int16,    # left_x
    c_int16,    # left_y
    c_int16,    # right_x
    c_int16,    # right_y
    c_uint8,    # l2_state
    c_uint8     # r2_state
]
_lib.chiaki_python_session_set_controller.restype = c_bool

# chiaki_python_session_get_frame
_lib.chiaki_python_session_get_frame.argtypes = [
    PythonSessionPtr,
    POINTER(c_uint8),   # buffer
    c_size_t            # buffer_size
]
_lib.chiaki_python_session_get_frame.restype = c_size_t

# chiaki_python_session_get_frame_ex - get frame with sequence number
_lib.chiaki_python_session_get_frame_ex.argtypes = [
    PythonSessionPtr,
    POINTER(c_uint8),   # buffer
    c_size_t,           # buffer_size
    POINTER(c_uint64)   # seq_out
]
_lib.chiaki_python_session_get_frame_ex.restype = c_size_t

# chiaki_python_session_get_frame_seq - get current frame sequence
_lib.chiaki_python_session_get_frame_seq.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_get_frame_seq.restype = c_uint64

# chiaki_python_session_get_iframe - get complete I-frame for screenshots
_lib.chiaki_python_session_get_iframe.argtypes = [
    PythonSessionPtr,
    POINTER(c_uint8),   # buffer
    c_size_t            # buffer_size
]
_lib.chiaki_python_session_get_iframe.restype = c_size_t

# chiaki_python_session_has_iframe - check if I-frame is available
_lib.chiaki_python_session_has_iframe.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_has_iframe.restype = c_bool

# chiaki_python_session_clear_iframe - clear current I-frame
_lib.chiaki_python_session_clear_iframe.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_clear_iframe.restype = None

# chiaki_python_session_request_idr - request fresh IDR frame
_lib.chiaki_python_session_request_idr.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_request_idr.restype = c_bool

# chiaki_python_session_stop
_lib.chiaki_python_session_stop.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_stop.restype = None

# chiaki_python_session_destroy
_lib.chiaki_python_session_destroy.argtypes = [PythonSessionPtr]
_lib.chiaki_python_session_destroy.restype = None
