#!/bin/bash

# Build script for Linux
echo "🐧 Building Lazy Blacktea for Linux..."

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This script must be run on Linux"
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

# Install additional Linux dependencies
echo "📥 Installing Linux-specific dependencies..."
sudo apt-get update
sudo apt-get install -y \
  python3-dev \
  build-essential \
  libgl1-mesa-dev \
  libxkbcommon-x11-0 \
  libxcb-icccm4 \
  libxcb-image0 \
  libxcb-keysyms1 \
  libxcb-randr0 \
  libxcb-render-util0 \
  libxcb-xinerama0 \
  libxcb-xfixes0

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Build the application
echo "🔨 Building application with PyInstaller..."
pyinstaller build_linux.spec --clean --noconfirm

# Check if build was successful
if [ -d "dist/lazyblacktea" ]; then
    echo "✅ Build successful! Application created at: dist/lazyblacktea/"
    echo "📱 To run: ./dist/lazyblacktea/lazyblacktea"

    # Create AppImage (optional - requires appimagetool)
    if command -v appimagetool &> /dev/null; then
        echo "📦 Creating AppImage..."

        # Create AppDir structure
        mkdir -p dist/LazyBlacktea.AppDir/usr/bin
        mkdir -p dist/LazyBlacktea.AppDir/usr/share/icons/hicolor/512x512/apps
        mkdir -p dist/LazyBlacktea.AppDir/usr/share/applications

        # Copy binary
        cp -r dist/lazyblacktea/* dist/LazyBlacktea.AppDir/usr/bin/

        # Copy icon
        cp assets/icons/icon_512x512.png dist/LazyBlacktea.AppDir/usr/share/icons/hicolor/512x512/apps/lazyblacktea.png
        cp assets/icons/icon_512x512.png dist/LazyBlacktea.AppDir/lazyblacktea.png

        # Create desktop file
        cat > dist/LazyBlacktea.AppDir/lazyblacktea.desktop << EOF
[Desktop Entry]
Type=Application
Name=Lazy Blacktea
Comment=Android ADB GUI Tool
Exec=lazyblacktea
Icon=lazyblacktea
Categories=Development;Utility;
Terminal=false
EOF

        # Create AppRun
        cat > dist/LazyBlacktea.AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/lazyblacktea" "$@"
EOF
        chmod +x dist/LazyBlacktea.AppDir/AppRun

        # Build AppImage
        appimagetool dist/LazyBlacktea.AppDir dist/LazyBlacktea-x86_64.AppImage

        if [ -f "dist/LazyBlacktea-x86_64.AppImage" ]; then
            echo "✅ AppImage created successfully: dist/LazyBlacktea-x86_64.AppImage"
        fi
    else
        echo "ℹ️  appimagetool not found. Skipping AppImage creation."
        echo "   To create AppImage, install appimagetool and run this script again."
    fi

    # Create tarball
    echo "📦 Creating tarball distribution..."
    cd dist
    tar -czf lazyblacktea-linux.tar.gz lazyblacktea/
    cd ..

    if [ -f "dist/lazyblacktea-linux.tar.gz" ]; then
        echo "✅ Tarball created: dist/lazyblacktea-linux.tar.gz"
    fi

else
    echo "❌ Build failed!"
    exit 1
fi

echo "🎉 Linux build complete!"