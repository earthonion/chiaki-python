# Chiaki Python

Python bindings for PS4/PS5 Remote Play using the [chiaki-ng](https://github.com/streetpea/chiaki-ng) library.

## Quick Start

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt install build-essential cmake pkg-config \
    libssl-dev libopus-dev libspeexdsp-dev libjson-c-dev \
    libminiupnpc-dev libjerasure-dev libavcodec-dev libavutil-dev \
    protobuf-compiler python3 ffmpeg

# Build the library
./build.sh

# Take a screenshot
python3 examples/screenshot.py PS4-910 screenshot.png

# Stream video to ffplay
python3 examples/stream.py PS4-910

# Run controller demo
python3 examples/controller.py PS4-910

# Run a controller script (DuckyScript-like)
python3 examples/controller_script.py examples/example_script.txt PS4-910
```

## Features

- Connect to PS4/PS5 consoles via Remote Play
- Send controller input (buttons, analog sticks, triggers)
- Capture screenshots (H.264 I-frame extraction)
- Uses credentials from Chiaki configuration

## Requirements

- Python 3.8+
- Chiaki installed and configured with your console
- ffmpeg (for screenshot decoding)
- Linux (tested on Ubuntu)

## Installation

```bash
# Clone the repository with submodules
git clone --recursive https://github.com/earthonion/chiaki-python.git
cd chiaki-python

# Or if already cloned, initialize submodules
git submodule update --init --recursive

# Build the library
./build.sh
```

## Configuration

The library reads credentials from Chiaki's config file:
`~/.config/Chiaki/Chiaki.conf`

Make sure you've registered your PS4/PS5 with Chiaki first.

## Usage

### Screenshot Example

```python
from examples.screenshot import take_screenshot

# Capture a screenshot from your PS4
take_screenshot("PS4-910", "my_screenshot.png")
```

Or run directly:
```bash
python3 examples/screenshot.py PS4-910 screenshot.png
```

### Controller Example

```python
from examples.controller import PS4Controller, CROSS, CIRCLE, DPAD_UP

# After connecting...
controller = PS4Controller(session)

# Press X button
controller.press(CROSS, 0.1)

# Navigate with D-pad
controller.press(DPAD_UP, 0.1)

# Move analog stick (x, y from -32768 to 32767)
controller.left_stick(20000, 0)

# Press triggers (0-255)
controller.triggers(l2=255, r2=0)
```

Or run the demo:
```bash
python3 examples/controller.py PS4-910
```

### Low-Level API

```python
import ctypes
from chiaki_python import _chiaki
from chiaki_python.config_parser import get_host_by_name

# Load config
config = get_host_by_name("PS4-910")

# Create session
session = _chiaki._lib.chiaki_python_session_create(
    config['host'].encode(),
    config['regist_key'].encode(),
    config['rp_key'].encode(),
    psn_array,  # 8-byte PSN account ID
    False,      # is_ps5
    3,          # resolution (1=360p, 2=540p, 3=720p, 4=1080p)
    60          # fps (30 or 60)
)

# Start and wait for connection
_chiaki._lib.chiaki_python_session_start(session)
_chiaki._lib.chiaki_python_session_wait_connected(session, 15000)

# Send controller input
_chiaki._lib.chiaki_python_session_set_controller(
    session,
    buttons,    # Button bitmask
    left_x,     # Left stick X (-32768 to 32767)
    left_y,     # Left stick Y
    right_x,    # Right stick X
    right_y,    # Right stick Y
    l2_state,   # L2 trigger (0-255)
    r2_state    # R2 trigger (0-255)
)

# Request and capture screenshot
_chiaki._lib.chiaki_python_session_request_idr(session)
# ... wait for frame ...
size = _chiaki._lib.chiaki_python_session_get_iframe(session, buffer, buffer_size)

# Cleanup
_chiaki._lib.chiaki_python_session_stop(session)
_chiaki._lib.chiaki_python_session_destroy(session)
```

## Button Constants

```python
CROSS       = 1 << 0
CIRCLE      = 1 << 1
SQUARE      = 1 << 2
TRIANGLE    = 1 << 3
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
```

## Project Structure

```
chiaki-python/
├── build.sh                # Build script
├── chiaki-ng/              # Chiaki source (git submodule, AGPL-3.0)
├── src/
│   └── python_wrapper.c    # Python wrapper extension
├── chiaki_python/          # Python package
│   ├── _chiaki.py          # ctypes bindings
│   ├── config_parser.py    # Chiaki config reader
│   ├── controller.py       # Controller helpers
│   ├── discovery.py        # Console discovery
│   └── session.py          # Session management
├── examples/
│   ├── controller.py       # Controller input example
│   ├── controller_script.py # DuckyScript-like controller automation
│   ├── example_script.txt  # Example controller script
│   ├── screenshot.py       # Screenshot capture example
│   ├── stream.py           # Video streaming to ffplay
│   └── stream_ps_button.py # Stream with PS button demo
├── libchiaki.so            # Compiled library (after build)
├── LICENSE                 # AGPL-3.0 License
└── README.md
```

## Building

### Dependencies (Ubuntu/Debian)

```bash
sudo apt install build-essential cmake pkg-config \
    libssl-dev libopus-dev libspeexdsp-dev libjson-c-dev \
    libminiupnpc-dev libjerasure-dev libavcodec-dev libavutil-dev \
    protobuf-compiler python3
```

### Build

```bash
# Run the build script
./build.sh
```

This will:
1. Build the chiaki-ng library with the Python wrapper (`chiaki-ng/lib/src/python_wrapper.c`)
2. Create `libchiaki.so` in the project root

### Manual Build

```bash
cd chiaki-ng
mkdir -p build && cd build

# Configure
cmake .. -DCMAKE_BUILD_TYPE=Release \
    -DCHIAKI_ENABLE_GUI=OFF -DCHIAKI_ENABLE_CLI=OFF

# Build
cmake --build . --target chiaki-lib

# Create shared library
gcc -shared -fPIC -o ../../libchiaki.so \
    -Wl,--whole-archive lib/libchiaki.a -Wl,--no-whole-archive \
    third-party/nanopb/libprotobuf-nanopb.a \
    third-party/curl/lib/libcurl.a \
    -lssl -lcrypto -lopus -lspeexdsp -ljson-c -lminiupnpc \
    -lm -lpthread -lz -lJerasure -lavcodec -lavutil
```

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This project is based on and includes code from:
- [chiaki-ng](https://github.com/streetpea/chiaki-ng) by streetpea (AGPL-3.0)
- [Chiaki](https://git.sr.ht/~thestr4ng3r/chiaki) by thestr4ng3r (AGPL-3.0)

### Modifications

This project adds a Python wrapper (`src/python_wrapper.c`) that links with the chiaki-ng library, exposing a simplified C API for Python bindings via ctypes. The wrapper is kept separate from upstream chiaki-ng to allow easy updates.

See the [LICENSE](LICENSE) file for the full license text.

