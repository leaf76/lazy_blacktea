#!/bin/bash

# Lazy Blacktea Launcher Script
# This script starts the optimized Lazy Blacktea application

echo "🍵 Starting Lazy Blacktea..."
echo "==============================================="

# Change to the application directory
cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3 to run this application"
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
python3 lazy_blacktea_pyqt.py

echo ""
echo "📱 Lazy Blacktea has been closed"
echo "Thank you for using Lazy Blacktea!"