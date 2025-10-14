#!/usr/bin/env python3
"""
Qt Dependency Checker for Linux Systems
Handles Qt xcb platform plugin dependency detection and automatic fixes
"""

import os
import platform
import subprocess
import sys
from PyQt6.QtWidgets import QApplication


def _is_ci() -> bool:
    return any(env_var in os.environ for env_var in ['CI', 'GITHUB_ACTIONS', 'CONTINUOUS_INTEGRATION'])


def _is_quiet() -> bool:
    val = os.environ.get('QDC_QUIET', '').strip().lower()
    if val in {'1', 'true', 'yes', 'on'}:
        return True
    # Default to quiet in CI to reduce log noise
    return _is_ci()


def _echo(msg: str) -> None:
    if not _is_quiet():
        print(msg)


def get_linux_distro():
    """Get Linux distribution name."""
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('ID='):
                    return line.split('=')[1].strip().strip('"').lower()
    except (FileNotFoundError, IOError, IndexError):
        pass
    return 'unknown'


def install_dependencies_ubuntu():
    """Install Qt dependencies on Ubuntu/Debian systems."""
    _echo("📦 Installing Qt dependencies for Ubuntu/Debian...")

    commands = [
        ['sudo', 'apt-get', 'update'],
        [
            'sudo', 'apt-get', 'install', '-y',
            'libxcb-cursor0', 'libxcb1', 'libxcb-xkb1', 'libxcb-xinput0',
            'libfontconfig1', 'libfreetype6', 'libx11-6', 'libxi6',
            'libgl1-mesa-dev', 'libxkbcommon-x11-0'
        ]
    ]

    for cmd in commands:
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            _echo(f"❌ Command failed: {' '.join(cmd)}")
            _echo(f"Error: {e.stderr}")
            return False

    _echo("✅ Dependencies installed successfully!")
    return True


def show_manual_installation_instructions(distro):
    """Show manual installation instructions for different distributions."""
    _echo("\n🔧 Manual Installation Instructions")
    _echo("=" * 40)

    if distro in ['ubuntu', 'debian']:
        _echo("\nUbuntu/Debian - Run these commands:")
        _echo("sudo apt-get update")
        _echo("sudo apt-get install -y libxcb-cursor0 libxcb1 libfontconfig1 libfreetype6")
    elif distro in ['centos', 'rhel', 'fedora']:
        _echo("\nCentOS/RHEL/Fedora - Run these commands:")
        _echo("sudo dnf install -y libxcb libxcb-devel xcb-util xcb-util-cursor")
        _echo("sudo dnf install -y libXrender libXi fontconfig freetype libX11 dbus-libs mesa-libGL")
    elif distro in ['arch', 'manjaro']:
        _echo("\nArch Linux - Run this command:")
        _echo("sudo pacman -S libxcb xcb-util xcb-util-cursor libxrender libxi fontconfig freetype2 libx11 dbus mesa")
    else:
        _echo(f"\nFor {distro}, install these Qt dependencies:")
        _echo("- libxcb-cursor0 (or xcb-util-cursor)")
        _echo("- libxcb and related packages")
        _echo("- libX11, libXi, libXrender")
        _echo("- fontconfig, freetype")
        _echo("- dbus libraries")
        _echo("- Mesa OpenGL libraries")

    _echo("\n💡 Alternative: Run in headless mode")
    _echo("export QT_QPA_PLATFORM=offscreen")
    _echo("python lazy_blacktea_pyqt.py")


def test_qt_platform_plugin():
    """Test if Qt platform plugin is available."""
    try:
        # Check if we're in a CI environment (GitHub Actions, etc.)
        is_ci = _is_ci()

        # Test Qt platform plugin by creating minimal QApplication
        test_app = QApplication.instance()
        if test_app is None:
            # Force offscreen mode in CI environments or if display is not available
            if is_ci or not os.environ.get('DISPLAY'):
                os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            test_app = QApplication([])
        return True, None
    except Exception as e:
        error_msg = str(e).lower()
        if 'xcb' in error_msg or 'platform plugin' in error_msg:
            # Try offscreen mode as fallback
            try:
                os.environ['QT_QPA_PLATFORM'] = 'offscreen'
                fallback_app = QApplication([])
                return True, None
            except Exception as e:
                return False, f"Qt xcb platform plugin dependencies missing: {e}"
        return False, f"Qt initialization failed: {e}"


def check_and_fix_qt_dependencies():
    """
    Check Qt dependencies and offer automatic fixes on Linux.

    Returns:
        bool: True if dependencies are OK or fixed, False if manual intervention needed
    """
    # Only run on Linux systems
    if platform.system() != 'Linux':
        return True

    # Check if we're in a CI environment - if so, set offscreen mode immediately
    is_ci = _is_ci()
    if is_ci:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        return True

    # Test Qt platform plugin
    qt_ok, error_msg = test_qt_platform_plugin()
    if qt_ok:
        return True

    _echo("⚠️  Qt xcb platform plugin dependencies missing!")
    _echo("This is required for the GUI to work properly.")
    _echo("")

    # Get distribution info
    distro = get_linux_distro()

    # Offer automatic fix for Ubuntu/Debian
    if distro in ['ubuntu', 'debian']:
        response = 'n'
        if not _is_quiet():
            response = input("🤔 Would you like to automatically install the dependencies? (y/N): ")
        if response.lower().strip() in ['y', 'yes']:
            if install_dependencies_ubuntu():
                _echo("✅ Dependencies installed! Please restart the application.")
                return False  # Need restart
            else:
                _echo("❌ Failed to install dependencies automatically.")

    # Show manual installation instructions
    show_manual_installation_instructions(distro)

    # Ask about headless mode
    _echo("")
    response = 'y' if _is_quiet() else input("🤔 Try running in headless mode (no GUI)? (y/N): ")
    if response.lower().strip() in ['y', 'yes']:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        _echo("🖥️  Running in headless mode...")
        return True

    return False


def print_qt_info():
    """Print Qt environment information for debugging."""
    _echo("🔍 Qt Environment Information")
    _echo("=" * 30)

    try:
        from PyQt6 import QtCore
        _echo(f"PyQt6 version: {QtCore.PYQT_VERSION_STR}")
        _echo(f"Qt version: {QtCore.QT_VERSION_STR}")
    except ImportError:
        _echo("❌ PyQt6 not installed")

    _echo(f"Platform: {platform.system()} {platform.release()}")
    _echo(f"Architecture: {platform.machine()}")

    if platform.system() == 'Linux':
        distro = get_linux_distro()
        _echo(f"Linux Distribution: {distro}")

        # Check for Qt platform plugin environment
        qpa_platform = os.environ.get('QT_QPA_PLATFORM', 'default')
        _echo(f"QT_QPA_PLATFORM: {qpa_platform}")


if __name__ == "__main__":
    """Command-line interface for Qt dependency checking."""
    import argparse

    parser = argparse.ArgumentParser(description="Qt Dependency Checker")
    parser.add_argument('--info', action='store_true', help='Print Qt environment info')
    parser.add_argument('--check', action='store_true', help='Check and fix dependencies')

    args = parser.parse_args()

    if args.info:
        print_qt_info()
    elif args.check:
        success = check_and_fix_qt_dependencies()
        sys.exit(0 if success else 1)
    else:
        # Default: run check
        success = check_and_fix_qt_dependencies()
        sys.exit(0 if success else 1)
