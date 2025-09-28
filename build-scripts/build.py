#!/usr/bin/env python3
"""
Cross-platform build script for Lazy Blacktea
Supports macOS and Linux builds with automatic platform detection
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from build_scripts import prepare_native_library, prepare_spec_content

def print_header(text):
    """Print a formatted header"""
    print(f"\n🚀 {text}")
    print("=" * (len(text) + 4))

def print_step(text):
    """Print a step"""
    print(f"\n📋 {text}")

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")

def run_command(cmd, shell=True, cwd=None):
    """Run a command and return success status"""
    try:
        # If cmd is a string and shell=True, keep as is
        # If cmd is a list, pass directly to subprocess
        if isinstance(cmd, list):
            result = subprocess.run(cmd, shell=False, cwd=cwd, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, shell=shell, cwd=cwd, capture_output=True, text=True)

        if result.returncode != 0:
            print_error(f"Command failed: {cmd}")
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print_error(f"Failed to run command: {cmd}")
        print(f"Exception: {e}")
        return False

def check_python():
    """Check Python version"""
    print_step("Checking Python version...")
    if sys.version_info < (3, 8):
        print_error("Python 3.8 or higher is required")
        return False
    print_success(f"Python {sys.version.split()[0]} detected")
    return True

def check_dependencies():
    """Check required dependencies"""
    print_step("Checking dependencies...")

    # Check if PyQt6 is available
    try:
        import PyQt6
        print_success("PyQt6 is available")
    except ImportError:
        print_error("PyQt6 is not installed. Please install it first.")
        return False

    # Check if PyInstaller is available
    try:
        import PyInstaller
        print_success("PyInstaller is available")
    except ImportError:
        print_error("PyInstaller is not installed. Please install it first.")
        return False

    return True

def fix_app_signing(app_path):
    """Fix application signing issues on macOS"""
    print_step("Fixing macOS app signing issues...")

    try:
        # Remove quarantine attributes
        print("Removing quarantine attributes...")
        run_command(["xattr", "-rd", "com.apple.quarantine", app_path])

        # Sign all dynamic libraries with ad-hoc signature
        print("Signing dynamic libraries...")
        run_command(["find", app_path, "-name", "*.dylib", "-exec", "codesign", "--force", "--sign", "-", "{}", ";"])

        # Remove problematic translations that can't be signed properly
        translations_path = os.path.join(app_path, "Contents", "Resources", "PyQt6", "Qt6", "translations")
        if os.path.exists(translations_path):
            print("Removing problematic translation files...")
            shutil.rmtree(translations_path, ignore_errors=True)

        # Sign the main executable
        print("Signing main executable...")
        main_executable = os.path.join(app_path, "Contents", "MacOS", "LazyBlacktea")
        if os.path.exists(main_executable):
            run_command(["codesign", "--force", "--sign", "-", main_executable])

        # Sign the app bundle itself
        print("Signing app bundle...")
        run_command(["codesign", "--force", "--sign", "-", app_path])

        print_success("App signing fixes applied successfully")
        return True

    except Exception as e:
        print_warning(f"Some signing fixes may have failed: {e}")
        return True  # Don't fail the build for signing issues

def install_dependencies():
    """Install dependencies"""
    print_step("Installing dependencies...")

    system = platform.system().lower()

    if system == "linux":
        # Install Linux-specific dependencies
        print("Installing Linux dependencies...")
        if not run_command("sudo apt-get update"):
            print_warning("Failed to update package list (continuing anyway)")

        if not run_command("sudo apt-get install -y python3-dev build-essential libgl1-mesa-dev libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0"):
            print_warning("Failed to install system dependencies (continuing anyway)")

    # Install Python dependencies
    if not run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"]):
        print_error("Failed to upgrade pip")
        return False

    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]):
        print_error("Failed to install Python dependencies")
        return False

    print_success("Dependencies installed successfully")
    return True


def stage_native_library(project_root: Path) -> Optional[Path]:
    """Build and stage the Rust native library for packaging."""
    print_step("Building native accelerators...")
    output_dir = project_root / 'build' / 'native-libs'
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        artifact = prepare_native_library(project_root, output_dir)
    except FileNotFoundError as exc:
        print_warning(f"Native project missing: {exc}")
        return None
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else 'no output'
        print_warning(f"Native build failed (cargo error): {stderr}")
        return None
    except Exception as exc:  # pragma: no cover - defensive
        print_warning(f"Native build failed: {exc}")
        return None

    print_success(f"Native library staged: {artifact}")
    return artifact


def clean_build():
    """Clean previous build artifacts"""
    print_step("Cleaning previous builds...")

    # Remove build directories
    for dir_name in ["build", "dist", "__pycache__"]:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed {dir_name}/")

    # Remove .pyc files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc"):
                os.remove(os.path.join(root, file))

    print_success("Build artifacts cleaned")

def build_application():
    """Build the application using PyInstaller"""
    print_step("Building application...")

    system = platform.system().lower()

    if system == "darwin":  # macOS
        spec_file = os.path.join(os.path.dirname(__file__), "build_macos.spec")
        print("Building for macOS with fixed configuration...")
    elif system == "linux":  # Linux
        spec_file = os.path.join(os.path.dirname(__file__), "build_linux.spec")
        print("Building for Linux...")
    else:
        print_error(f"Unsupported platform: {system}")
        return False

    if not os.path.exists(spec_file):
        print_error(f"Spec file not found: {spec_file}")
        return False

    # Create a temporary spec file with absolute paths
    import tempfile
    project_root = os.getcwd()

    with open(spec_file, 'r') as f:
        spec_content = f.read()

    spec_content = prepare_spec_content(spec_content, project_root)

    # Create temp spec file
    temp_spec_fd, temp_spec_path = tempfile.mkstemp(suffix='.spec', dir=os.path.dirname(spec_file))
    try:
        with os.fdopen(temp_spec_fd, 'w') as f:
            f.write(spec_content)

        # Run PyInstaller with temp spec file
        cmd = ["pyinstaller", temp_spec_path, "--clean", "--noconfirm"]
        success = run_command(cmd)
    finally:
        os.unlink(temp_spec_path)

    if not success:
        print_error("PyInstaller build failed")
        return False

    print_success("Application built successfully")
    return True

def create_distribution():
    """Create distribution packages"""
    print_step("Creating distribution packages...")

    system = platform.system().lower()

    if system == "darwin":  # macOS
        app_path = "dist/LazyBlacktea.app"
        target_arch = os.environ.get('TARGET_ARCH', platform.machine())

        if os.path.exists(app_path):
            print_success(f"macOS app bundle created: {app_path}")

            # Fix app signing issues
            fix_app_signing(app_path)

            # Verify the built app architecture
            if shutil.which("lipo"):
                print("🔍 Verifying app architecture...")
                result = run_command(["lipo", "-archs", f"{app_path}/Contents/MacOS/LazyBlacktea"])
                if result:
                    print(f"✅ Built architecture verified")

            # Create DMG (if hdiutil is available)
            if shutil.which("hdiutil"):
                print("Creating DMG...")
                dmg_name = f"LazyBlacktea-macos-{target_arch}.dmg"
                dmg_cmd = ["hdiutil", "create", "-volname", "Lazy Blacktea", "-srcfolder", app_path, "-ov", "-format", "UDZO", f"dist/{dmg_name}"]
                if run_command(dmg_cmd):
                    print_success(f"DMG created: dist/{dmg_name}")
                else:
                    print_warning("Failed to create DMG")
            else:
                print_warning("hdiutil not found, skipping DMG creation")
        else:
            print_error("macOS app bundle not found")
            return False

    elif system == "linux":  # Linux
        app_path = "dist/lazyblacktea"
        if os.path.exists(app_path):
            print_success(f"Linux executable created: {app_path}")

            # Create tarball
            print("Creating tarball...")
            if run_command(["tar", "-czf", "lazyblacktea-linux.tar.gz", "lazyblacktea/"], cwd="dist"):
                print_success("Tarball created: dist/lazyblacktea-linux.tar.gz")
            else:
                print_warning("Failed to create tarball")

            # Create AppImage (if appimagetool is available)
            if shutil.which("appimagetool"):
                print("Creating AppImage...")
                create_appimage()
            else:
                print_warning("appimagetool not found, skipping AppImage creation")
        else:
            print_error("Linux executable not found")
            return False

    return True

def create_appimage():
    """Create AppImage for Linux"""
    try:
        # Create AppDir structure
        appdir = Path("dist/LazyBlacktea.AppDir")
        appdir.mkdir(exist_ok=True)

        # Create directory structure
        (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
        (appdir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps").mkdir(parents=True, exist_ok=True)
        (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)

        # Copy binary
        shutil.copytree("dist/lazyblacktea", appdir / "usr" / "bin" / "lazyblacktea", dirs_exist_ok=True)

        # Copy icon
        icon_src = "assets/icons/icon_512x512.png"
        if os.path.exists(icon_src):
            shutil.copy(icon_src, appdir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps" / "lazyblacktea.png")
            shutil.copy(icon_src, appdir / "lazyblacktea.png")

        # Create desktop file
        desktop_content = """[Desktop Entry]
Type=Application
Name=Lazy Blacktea
Comment=Android ADB GUI Tool
Exec=lazyblacktea
Icon=lazyblacktea
Categories=Development;Utility;
Terminal=false
"""
        with open(appdir / "lazyblacktea.desktop", "w") as f:
            f.write(desktop_content)

        # Create AppRun
        apprun_content = """#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/lazyblacktea/lazyblacktea" "$@"
"""
        with open(appdir / "AppRun", "w") as f:
            f.write(apprun_content)
        os.chmod(appdir / "AppRun", 0o755)

        # Build AppImage
        if run_command(["appimagetool", str(appdir), "dist/LazyBlacktea-x86_64.AppImage"]):
            print_success("AppImage created: dist/LazyBlacktea-x86_64.AppImage")
        else:
            print_warning("Failed to create AppImage")

    except Exception as e:
        print_warning(f"AppImage creation failed: {e}")

def main():
    """Main build function"""
    import argparse

    parser = argparse.ArgumentParser(description="Lazy Blacktea Cross-Platform Builder")
    parser.add_argument('--arch', choices=['x86_64', 'arm64'],
                       help='Target architecture (macOS only, defaults to current arch)')
    args = parser.parse_args()

    print_header("Lazy Blacktea Cross-Platform Builder")

    system = platform.system()
    current_arch = platform.machine()
    target_arch = args.arch or current_arch

    print(f"🖥️  Platform: {system}")
    print(f"📋 Current architecture: {current_arch}")
    print(f"🎯 Target architecture: {target_arch}")

    if system not in ["Darwin", "Linux"]:
        print_error(f"Unsupported platform: {system}")
        print("This script supports macOS and Linux only.")
        sys.exit(1)

    # Set architecture-specific environment variables for macOS
    if system == "Darwin":
        os.environ['TARGET_ARCH'] = target_arch
        if target_arch != current_arch:
            print_step(f"Setting up cross-compilation for {target_arch}...")
            os.environ['ARCHFLAGS'] = f"-arch {target_arch}"
            os.environ['CFLAGS'] = f"-arch {target_arch}"
            os.environ['LDFLAGS'] = f"-arch {target_arch}"
            print(f"✅ Cross-compilation environment configured for {target_arch}")
        else:
            print_step(f"Building for native architecture: {target_arch}")
            os.environ['ARCHFLAGS'] = f"-arch {target_arch}"
            os.environ['CFLAGS'] = f"-arch {target_arch}"
            os.environ['LDFLAGS'] = f"-arch {target_arch}"

    # Check if we're in the right directory and change to project root if needed
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # If we're in build-scripts directory, go up one level
    if os.path.basename(script_dir) == 'build-scripts':
        os.chdir(project_root)

    if not os.path.exists("lazy_blacktea_pyqt.py"):
        print_error("Cannot find lazy_blacktea_pyqt.py. Please run from project directory or build-scripts/")
        sys.exit(1)

    # Step 1: Check Python
    if not check_python():
        sys.exit(1)

    # Step 2: Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies")
        sys.exit(1)

    # Step 3: Check dependencies
    if not check_dependencies():
        print_error("Dependencies check failed")
        sys.exit(1)

    # Step 4: Clean previous builds
    clean_build()

    # Step 5: Build native library
    stage_native_library(Path(os.getcwd()))

    # Step 6: Build application
    if not build_application():
        print_error("Build failed")
        sys.exit(1)

    # Step 7: Create distribution
    if not create_distribution():
        print_error("Distribution creation failed")
        sys.exit(1)

    print_header("Build Complete! 🎉")

    # Show results
    if system == "Darwin":
        print("📦 macOS Distribution Files:")
        if os.path.exists("dist/LazyBlacktea.app"):
            print("   • dist/LazyBlacktea.app (App Bundle)")
        if os.path.exists("dist/LazyBlacktea.dmg"):
            print("   • dist/LazyBlacktea.dmg (Disk Image)")

        print("\n🚀 To run:")
        print("   open dist/LazyBlacktea.app")

    elif system == "Linux":
        print("📦 Linux Distribution Files:")
        if os.path.exists("dist/lazyblacktea"):
            print("   • dist/lazyblacktea/ (Executable)")
        if os.path.exists("dist/lazyblacktea-linux.tar.gz"):
            print("   • dist/lazyblacktea-linux.tar.gz (Tarball)")
        if os.path.exists("dist/LazyBlacktea-x86_64.AppImage"):
            print("   • dist/LazyBlacktea-x86_64.AppImage (AppImage)")

        print("\n🚀 To run:")
        print("   ./dist/lazyblacktea/lazyblacktea")
        if os.path.exists("dist/LazyBlacktea-x86_64.AppImage"):
            print("   or")
            print("   ./dist/LazyBlacktea-x86_64.AppImage")

if __name__ == "__main__":
    main()
