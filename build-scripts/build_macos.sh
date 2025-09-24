#!/bin/bash

# Build script for macOS with architecture support
echo "🍎 Building Lazy Blacktea for macOS..."

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
fi

# Detect current architecture
CURRENT_ARCH=$(uname -m)
echo "📋 Current architecture: $CURRENT_ARCH"

# Allow override via command line argument
TARGET_ARCH="${1:-$CURRENT_ARCH}"

if [[ "$TARGET_ARCH" != "x86_64" && "$TARGET_ARCH" != "arm64" ]]; then
    echo "❌ Unsupported architecture: $TARGET_ARCH"
    echo "Supported architectures: x86_64, arm64"
    exit 1
fi

echo "🎯 Building for architecture: $TARGET_ARCH"

# Set architecture-specific environment variables
if [[ "$TARGET_ARCH" == "arm64" ]]; then
    export ARCHFLAGS="-arch arm64"
    export CFLAGS="-arch arm64"
    export LDFLAGS="-arch arm64"
elif [[ "$TARGET_ARCH" == "x86_64" ]]; then
    export ARCHFLAGS="-arch x86_64"
    export CFLAGS="-arch x86_64"
    export LDFLAGS="-arch x86_64"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r ../requirements.txt

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist *.app

# Build the application
echo "🔨 Building application with PyInstaller..."
pyinstaller build_macos.spec --clean --noconfirm

# Check if build was successful
if [ -d "dist/LazyBlacktea.app" ]; then
    echo "✅ Build successful! Application created at: dist/LazyBlacktea.app"
    echo "📱 Architecture: $TARGET_ARCH"
    echo "🚀 To run: open dist/LazyBlacktea.app"

    # Verify the built app architecture
    echo "🔍 Verifying app architecture..."
    if command -v lipo &> /dev/null; then
        lipo -archs "dist/LazyBlacktea.app/Contents/MacOS/LazyBlacktea" 2>/dev/null || echo "ℹ️  Architecture info unavailable"
    fi

    # Optional: Create DMG
    echo "📦 Creating DMG package..."
    mkdir -p dist/dmg
    cp -R dist/LazyBlacktea.app dist/dmg/
    ln -sf /Applications dist/dmg/Applications

    # Create DMG using hdiutil with architecture in filename
    DMG_NAME="LazyBlacktea-macos-${TARGET_ARCH}.dmg"
    hdiutil create -volname "Lazy Blacktea" -srcfolder dist/dmg -ov -format UDZO "dist/${DMG_NAME}"

    if [ -f "dist/${DMG_NAME}" ]; then
        echo "✅ DMG created successfully: dist/${DMG_NAME}"
    fi

    # Cleanup DMG temp folder
    rm -rf dist/dmg
else
    echo "❌ Build failed!"
    exit 1
fi

echo "🎉 macOS build complete!"