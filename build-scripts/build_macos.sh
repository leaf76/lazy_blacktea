#!/bin/bash

# Build script for macOS
echo "🍎 Building Lazy Blacktea for macOS..."

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
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
pip install -r requirements.txt

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist *.app

# Build the application
echo "🔨 Building application with PyInstaller..."
pyinstaller build_macos.spec --clean --noconfirm

# Check if build was successful
if [ -d "dist/LazyBlacktea.app" ]; then
    echo "✅ Build successful! Application created at: dist/LazyBlacktea.app"
    echo "📱 To run: open dist/LazyBlacktea.app"

    # Optional: Create DMG
    echo "📦 Creating DMG package..."
    mkdir -p dist/dmg
    cp -R dist/LazyBlacktea.app dist/dmg/
    ln -sf /Applications dist/dmg/Applications

    # Create DMG using hdiutil
    hdiutil create -volname "Lazy Blacktea" -srcfolder dist/dmg -ov -format UDZO dist/LazyBlacktea.dmg

    if [ -f "dist/LazyBlacktea.dmg" ]; then
        echo "✅ DMG created successfully: dist/LazyBlacktea.dmg"
    fi

    # Cleanup DMG temp folder
    rm -rf dist/dmg
else
    echo "❌ Build failed!"
    exit 1
fi

echo "🎉 macOS build complete!"