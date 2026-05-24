# 🔨 Build Scripts

This directory contains local build scripts and configuration files for Lazy Blacktea.

## 📁 File Structure

```
build-scripts/
├── build.py           # Main build script
├── build_macos.spec   # macOS PyInstaller configuration
├── build_linux.spec   # Linux PyInstaller configuration
├── build_macos.sh     # macOS build script (legacy)
├── build_linux.sh     # Linux build script (legacy)
├── BUILD.md           # Build documentation
└── README.md          # This file
```

## 🚀 Usage

### Method 1: Run from project root directory (Recommended)

```bash
# Execute from project root directory
cd /path/to/lazy_blacktea
python build-scripts/build.py
```

### Method 2: Run from build-scripts directory

```bash
# Enter build-scripts directory
cd build-scripts
python build.py
```

### Method 3: Direct execution (if added to PATH)

```bash
# If build-scripts is added to PATH environment variable
build.py
```

## ⚙️ Build Script Features

The `build.py` script will automatically:

1. **Check Python version** (requires 3.8+)
2. **Install dependencies** (PyQt6, PyInstaller, etc.)
3. **Clean old build files**
4. **Execute PyInstaller** to build the application
5. **Create distribution packages**
   - macOS: `.app` and `.dmg`
   - Linux: executable and `.tar.gz`, `.AppImage`

## 🎯 Supported Platforms

- **macOS** (Intel and Apple Silicon)
- **Linux** (x86_64)

## 📦 Output Files

After building, artifacts will be in the `dist/` folder in the project root:

### macOS
```
dist/
├── LazyBlacktea.app/    # macOS application bundle
└── LazyBlacktea.dmg     # Disk image (if hdiutil is available)
```

### Linux
```
dist/
├── lazyblacktea/                          # Linux executable directory
├── lazyblacktea-linux.tar.gz             # Compressed archive
└── LazyBlacktea-x86_64.AppImage          # AppImage (if appimagetool is available)
```

## 🔐 Release Checksum Manifest

Official releases that should be installable through the in-app updater must
upload a `SHA256SUMS.txt` asset to the GitHub Release. The manifest must include
each desktop artifact filename exactly as published:

```bash
cd dist
shasum -a 256 LazyBlacktea-macos-arm64.dmg LazyBlacktea-x86_64.AppImage lazyblacktea-linux.tar.gz > SHA256SUMS.txt
```

The updater refuses to open downloaded artifacts when the manifest is missing
or the downloaded file digest does not match.

## 🔧 Dependencies

### Python Dependencies (automatically installed)
- PyQt6 >= 6.4.0
- PyInstaller >= 5.13.0
- setuptools >= 65.0.0

### System Dependencies

**Linux**:
```bash
sudo apt-get update
sudo apt-get install -y python3-dev build-essential libgl1-mesa-dev libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
  libxcb-xinerama0 libxcb-xfixes0
# PyQt6 will be installed via pip from requirements.txt
```

**macOS**:
```bash
# Xcode Command Line Tools (usually already installed)
xcode-select --install
```

## 🛠️ Advanced Usage

### Manual Cleanup
```bash
# Clean build files
rm -rf build/ dist/ __pycache__/
find . -name "*.pyc" -delete
```

### Check Dependencies
```bash
# Check PyQt6
python -c "from PyQt6 import QtCore; print('PyQt6 OK')"

# Check PyInstaller
python -c "import PyInstaller; print('PyInstaller OK')"
```

### Test Application
```bash
# macOS
./dist/LazyBlacktea.app/Contents/MacOS/LazyBlacktea

# Linux
./dist/lazyblacktea/lazyblacktea
```

## 🚨 Troubleshooting

### Common Issues

1. **PyQt6 not found**
   ```bash
   pip install PyQt6
   ```

2. **PyInstaller build failed**
   - Check if spec files are correct
   - Ensure all dependencies are installed
   - Review detailed error messages

3. **Permission issues (Linux)**
   ```bash
   chmod +x dist/lazyblacktea/lazyblacktea
   ```

4. **macOS security warnings**
   - Right-click on the application and select "Open"
   - Or allow execution in System Preferences

### Debug Mode

```bash
# Run with detailed PyInstaller output
pyinstaller --clean --noconfirm build-scripts/build_macos.spec

# Or check build logs for errors
cat build/*.log 2>/dev/null || echo "No build logs found"
```

## 🔗 Related Documentation

- **GitHub Actions**: `../.github/workflows/` - Automated CI/CD builds
- **Main Documentation**: `../README.md` - Main project documentation
- **Build Documentation**: `BUILD.md` - Detailed build instructions

## 💡 Tips

1. **First-time builds** may take longer to download and install dependencies
2. **Incremental builds** are faster since dependencies are already installed
3. **Clean builds** can resolve most build issues
4. **GitHub Actions** are used for official releases, local builds for development testing

---

This build system supports both local development and GitHub Actions CI/CD, providing a complete cross-platform build solution.
