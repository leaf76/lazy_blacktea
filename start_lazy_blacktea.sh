#!/bin/bash

# Lazy Blacktea Launcher Script
# This script starts the optimized Lazy Blacktea application

echo "🍵 Starting Lazy Blacktea..."
echo "==============================================="

# Change to the application directory
cd "$(dirname "$0")"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed or not in PATH"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if ADB is available
if ! command -v adb &> /dev/null; then
    echo "⚠️  Warning: ADB is not installed or not in PATH"
    echo "The application will show an error dialog about ADB"
    echo "Please install Android Debug Bridge (ADB) for full functionality"
fi

echo "✅ Dependencies check completed"
echo "🚀 Launching Lazy Blacktea GUI..."
echo ""

# Start the application
uv run python lazy_blacktea_pyqt.py

echo ""
echo "📱 Lazy Blacktea has been closed"
echo "Thank you for using Lazy Blacktea!"