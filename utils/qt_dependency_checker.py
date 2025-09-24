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


def get_linux_distro():
    """Get Linux distribution name."""
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('ID='):
                    return line.split('=')[1].strip().strip('"').lower()
    except:
        pass
    return 'unknown'


def install_dependencies_ubuntu():
    """Install Qt dependencies on Ubuntu/Debian systems."""
    print("📦 Installing Qt dependencies for Ubuntu/Debian...")

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
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return False

    print("✅ Dependencies installed successfully!")
    return True


def show_manual_installation_instructions(distro):
    """Show manual installation instructions for different distributions."""
    print("\n🔧 Manual Installation Instructions")
    print("=" * 40)

    if distro in ['ubuntu', 'debian']:
        print("\nUbuntu/Debian - Run these commands:")
        print("sudo apt-get update")
        print("sudo apt-get install -y libxcb-cursor0 libxcb1 libfontconfig1 libfreetype6")
    elif distro in ['centos', 'rhel', 'fedora']:
        print("\nCentOS/RHEL/Fedora - Run these commands:")
        print("sudo dnf install -y libxcb libxcb-devel xcb-util xcb-util-cursor")
        print("sudo dnf install -y libXrender libXi fontconfig freetype libX11 dbus-libs mesa-libGL")
    elif distro in ['arch', 'manjaro']:
        print("\nArch Linux - Run this command:")
        print("sudo pacman -S libxcb xcb-util xcb-util-cursor libxrender libxi fontconfig freetype2 libx11 dbus mesa")
    else:
        print(f"\nFor {distro}, install these Qt dependencies:")
        print("- libxcb-cursor0 (or xcb-util-cursor)")
        print("- libxcb and related packages")
        print("- libX11, libXi, libXrender")
        print("- fontconfig, freetype")
        print("- dbus libraries")
        print("- Mesa OpenGL libraries")

    print("\n💡 Alternative: Run in headless mode")
    print("export QT_QPA_PLATFORM=offscreen")
    print("python lazy_blacktea_pyqt.py")


def test_qt_platform_plugin():
    """Test if Qt platform plugin is available."""
    try:
        # Test Qt platform plugin by creating minimal QApplication
        test_app = QApplication.instance()
        if test_app is None:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            test_app = QApplication([])
        return True, None
    except Exception as e:
        error_msg = str(e).lower()
        if 'xcb' in error_msg or 'platform plugin' in error_msg:
            return False, "Qt xcb platform plugin dependencies missing"
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

    # Test Qt platform plugin
    qt_ok, error_msg = test_qt_platform_plugin()
    if qt_ok:
        return True

    print("⚠️  Qt xcb platform plugin dependencies missing!")
    print("This is required for the GUI to work properly.")
    print()

    # Get distribution info
    distro = get_linux_distro()

    # Offer automatic fix for Ubuntu/Debian
    if distro in ['ubuntu', 'debian']:
        response = input("🤔 Would you like to automatically install the dependencies? (y/N): ")
        if response.lower().strip() in ['y', 'yes']:
            if install_dependencies_ubuntu():
                print("✅ Dependencies installed! Please restart the application.")
                return False  # Need restart
            else:
                print("❌ Failed to install dependencies automatically.")

    # Show manual installation instructions
    show_manual_installation_instructions(distro)

    # Ask about headless mode
    print()
    response = input("🤔 Try running in headless mode (no GUI)? (y/N): ")
    if response.lower().strip() in ['y', 'yes']:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        print("🖥️  Running in headless mode...")
        return True

    return False


def print_qt_info():
    """Print Qt environment information for debugging."""
    print("🔍 Qt Environment Information")
    print("=" * 30)

    try:
        from PyQt6 import QtCore
        print(f"PyQt6 version: {QtCore.PYQT_VERSION_STR}")
        print(f"Qt version: {QtCore.QT_VERSION_STR}")
    except ImportError:
        print("❌ PyQt6 not installed")

    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")

    if platform.system() == 'Linux':
        distro = get_linux_distro()
        print(f"Linux Distribution: {distro}")

        # Check for Qt platform plugin environment
        qpa_platform = os.environ.get('QT_QPA_PLATFORM', 'default')
        print(f"QT_QPA_PLATFORM: {qpa_platform}")


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