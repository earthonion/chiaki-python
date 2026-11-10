#!/bin/bash
# Build script for chiaki-python
# Creates libchiaki.so with the Python wrapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHIAKI_DIR="$SCRIPT_DIR/chiaki-ng"
BUILD_DIR="$CHIAKI_DIR/build"
SRC_DIR="$SCRIPT_DIR/src"

echo "=== Building Chiaki Python Wrapper ==="

# Check for required dependencies
echo "Checking dependencies..."
for cmd in cmake gcc pkg-config; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is required but not installed"
        exit 1
    fi
done

# Initialize submodule if needed
if [ ! -f "$CHIAKI_DIR/CMakeLists.txt" ]; then
    echo "Initializing chiaki-ng submodule..."
    git submodule update --init --recursive
fi

DEPS_DIR="$SCRIPT_DIR/.deps/root"
if [ ! -f "$DEPS_DIR/usr/lib/x86_64-linux-gnu/libjson-c.a" ] || \
   [ ! -f "$DEPS_DIR/usr/lib/x86_64-linux-gnu/libminiupnpc.a" ]; then
    for cmd in apt-get dpkg-deb; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "Error: $cmd is required to fetch local json-c/miniupnpc development files" >&2
            exit 1
        fi
    done
    mkdir -p "$SCRIPT_DIR/.deps/packages" "$DEPS_DIR"
    (
        cd "$SCRIPT_DIR/.deps/packages"
        apt-get download libjson-c-dev libminiupnpc-dev
        for package in ./*.deb; do
            dpkg-deb -x "$package" "$DEPS_DIR"
        done
    )
fi

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
export PKG_CONFIG_PATH="$DEPS_DIR/usr/lib/x86_64-linux-gnu/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$DEPS_DIR"

# Configure with CMake
echo "Configuring chiaki-ng..."
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCHIAKI_ENABLE_GUI=OFF \
    -DCHIAKI_ENABLE_CLI=OFF \
    -DCHIAKI_ENABLE_ANDROID=OFF \
    -DCHIAKI_ENABLE_TESTS=OFF \
    -DCHIAKI_ENABLE_STEAM_SHORTCUT=OFF \
    -DCHIAKI_ENABLE_STEAMDECK_NATIVE=OFF \
    -DCHIAKI_LIB_ENABLE_OPUS=OFF \
    -DCHIAKI_ENABLE_RUDP=OFF

# Build the library
echo "Building chiaki-lib..."
cmake --build . --target chiaki-lib -j$(nproc)

# Compile our Python wrapper
echo "Compiling Python wrapper..."
gcc -c -fPIC -o "$BUILD_DIR/python_wrapper.o" \
    -I"$CHIAKI_DIR/lib/include" \
    -I"$BUILD_DIR/lib/include" \
    "$SRC_DIR/python_wrapper.c"

# Create shared library with Python wrapper
echo "Creating shared library..."
gcc -shared -fPIC -o "$SCRIPT_DIR/libchiaki.so" \
    "$BUILD_DIR/python_wrapper.o" \
    -Wl,--whole-archive lib/libchiaki.a -Wl,--no-whole-archive \
    third-party/nanopb/libprotobuf-nanopb.a \
    third-party/curl/lib/libcurl.a \
    third-party/libjerasure.a third-party/libgf_complete.a \
    "$DEPS_DIR/usr/lib/x86_64-linux-gnu/libjson-c.a" \
    "$DEPS_DIR/usr/lib/x86_64-linux-gnu/libminiupnpc.a" \
    -lssl -lcrypto -lm -lpthread -lz

echo "=== Build complete ==="
echo "Library: $SCRIPT_DIR/libchiaki.so"
ls -lh "$SCRIPT_DIR/libchiaki.so"
