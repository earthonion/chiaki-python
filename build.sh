#!/bin/bash
# Build script for chiaki-python
# Creates libchiaki.so with the Python wrapper

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHIAKI_DIR="$SCRIPT_DIR/chiaki-ng"
BUILD_DIR="$CHIAKI_DIR/build"

echo "=== Building Chiaki Python Wrapper ==="

# Check for required dependencies
echo "Checking dependencies..."
for cmd in cmake gcc pkg-config; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is required but not installed"
        exit 1
    fi
done

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure with CMake
echo "Configuring..."
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCHIAKI_ENABLE_GUI=OFF \
    -DCHIAKI_ENABLE_CLI=OFF \
    -DCHIAKI_ENABLE_ANDROID=OFF \
    -DCHIAKI_ENABLE_TESTS=OFF

# Build the library
echo "Building chiaki-lib..."
cmake --build . --target chiaki-lib -j$(nproc)

# Create shared library with Python wrapper
echo "Creating shared library..."
gcc -shared -fPIC -o "$SCRIPT_DIR/libchiaki.so" \
    -Wl,--whole-archive lib/libchiaki.a -Wl,--no-whole-archive \
    third-party/nanopb/libprotobuf-nanopb.a \
    third-party/curl/lib/libcurl.a \
    -lssl -lcrypto -lopus -lspeexdsp -ljson-c -lminiupnpc \
    -lm -lpthread -lz -lJerasure -lavcodec -lavutil

echo "=== Build complete ==="
echo "Library: $SCRIPT_DIR/libchiaki.so"
ls -lh "$SCRIPT_DIR/libchiaki.so"
