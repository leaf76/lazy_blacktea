"""Tool metadata system - Centralized configuration for all ADB tools."""

from __future__ import annotations
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolMetadata:
    """Metadata for a single tool button."""

    icon_key: str
    label: str
    tooltip: str
    shortcut: Optional[str] = None
    accessible_name: Optional[str] = None
    accessible_description: Optional[str] = None


# Comprehensive tool metadata with tooltips and shortcuts
TOOL_METADATA: Dict[str, ToolMetadata] = {
    # Screen Capture Tools
    'screenshot': ToolMetadata(
        icon_key='screenshot',
        label='Screenshot',
        tooltip='Take a screenshot of the device screen (Ctrl+S)',
        shortcut='Ctrl+S',
        accessible_name='Take Screenshot',
        accessible_description='Captures the current device screen and saves it to the output directory'
    ),
    'record_start': ToolMetadata(
        icon_key='record_start',
        label='Start Record',
        tooltip='Start screen recording (Ctrl+R)',
        shortcut='Ctrl+R',
        accessible_name='Start Screen Recording',
        accessible_description='Begins recording the device screen. Press Stop Record to end recording'
    ),
    'record_stop': ToolMetadata(
        icon_key='record_stop',
        label='Stop Record',
        tooltip='Stop screen recording (Ctrl+Shift+R)',
        shortcut='Ctrl+Shift+R',
        accessible_name='Stop Screen Recording',
        accessible_description='Stops the current screen recording and saves the video file'
    ),

    # Bug Report
    'bug_report': ToolMetadata(
        icon_key='bug_report',
        label='Bug Report',
        tooltip='Generate a comprehensive bug report including logs, system info, and diagnostics',
        accessible_name='Generate Bug Report',
        accessible_description='Creates a detailed bug report package with system logs and device information'
    ),

    # Device Control
    'reboot': ToolMetadata(
        icon_key='reboot',
        label='Reboot',
        tooltip='Reboot the device normally',
        accessible_name='Reboot Device',
        accessible_description='Restarts the device with a normal boot'
    ),
    'reboot_recovery': ToolMetadata(
        icon_key='recovery',
        label='Recovery',
        tooltip='Reboot device into recovery mode',
        accessible_name='Reboot to Recovery',
        accessible_description='Restarts the device in recovery mode for advanced operations'
    ),
    'reboot_bootloader': ToolMetadata(
        icon_key='bootloader',
        label='Bootloader',
        tooltip='Reboot device into bootloader/fastboot mode',
        accessible_name='Reboot to Bootloader',
        accessible_description='Restarts the device in bootloader mode for firmware operations'
    ),
    'restart_adb': ToolMetadata(
        icon_key='restart',
        label='Restart ADB',
        tooltip='Restart the ADB server to fix connection issues',
        accessible_name='Restart ADB Server',
        accessible_description='Restarts the Android Debug Bridge server to resolve connectivity problems'
    ),

    # Connectivity
    'bt_on': ToolMetadata(
        icon_key='bt_on',
        label='BT On',
        tooltip='Enable Bluetooth on the device',
        accessible_name='Enable Bluetooth',
        accessible_description='Turns on Bluetooth connectivity on the device'
    ),
    'bt_off': ToolMetadata(
        icon_key='bt_off',
        label='BT Off',
        tooltip='Disable Bluetooth on the device',
        accessible_name='Disable Bluetooth',
        accessible_description='Turns off Bluetooth connectivity on the device'
    ),
    'wifi_on': ToolMetadata(
        icon_key='wifi_on',
        label='WiFi On',
        tooltip='Enable WiFi on the device',
        accessible_name='Enable WiFi',
        accessible_description='Turns on WiFi connectivity on the device'
    ),
    'wifi_off': ToolMetadata(
        icon_key='wifi_off',
        label='WiFi Off',
        tooltip='Disable WiFi on the device',
        accessible_name='Disable WiFi',
        accessible_description='Turns off WiFi connectivity on the device'
    ),

    # Installation & Apps
    'install_apk': ToolMetadata(
        icon_key='install_apk',
        label='Install APK',
        tooltip='Install an APK file on the device (Ctrl+I)',
        shortcut='Ctrl+I',
        accessible_name='Install APK',
        accessible_description='Opens a file dialog to select and install an APK file on the device'
    ),

    # System Tools
    'device_info': ToolMetadata(
        icon_key='device_info',
        label='Device Info',
        tooltip='Show detailed device information and properties',
        accessible_name='Show Device Information',
        accessible_description='Displays comprehensive information about the device hardware and software'
    ),
    'home': ToolMetadata(
        icon_key='home',
        label='Home',
        tooltip='Navigate to the home screen (Ctrl+H)',
        shortcut='Ctrl+H',
        accessible_name='Go to Home Screen',
        accessible_description='Navigates the device to the home screen'
    ),
    'inspector': ToolMetadata(
        icon_key='inspector',
        label='UI Inspector',
        tooltip='Launch UI hierarchy inspector for analyzing app layouts',
        accessible_name='Launch UI Inspector',
        accessible_description='Opens the UI Inspector tool to examine app element hierarchies'
    ),

    # scrcpy
    'scrcpy': ToolMetadata(
        icon_key='scrcpy',
        label='scrcpy',
        tooltip='Launch scrcpy for device mirroring and control (Ctrl+M)',
        shortcut='Ctrl+M',
        accessible_name='Launch scrcpy',
        accessible_description='Starts scrcpy application for real-time device screen mirroring and control'
    ),

    # Fallback handler mappings
    'enable_bluetooth': ToolMetadata(
        icon_key='bt_on',
        label='BT On',
        tooltip='Enable Bluetooth on the device',
        accessible_name='Enable Bluetooth',
        accessible_description='Turns on Bluetooth connectivity'
    ),
    'disable_bluetooth': ToolMetadata(
        icon_key='bt_off',
        label='BT Off',
        tooltip='Disable Bluetooth on the device',
        accessible_name='Disable Bluetooth',
        accessible_description='Turns off Bluetooth connectivity'
    ),
    'launch_scrcpy': ToolMetadata(
        icon_key='scrcpy',
        label='scrcpy',
        tooltip='Launch scrcpy for device mirroring',
        accessible_name='Launch scrcpy',
        accessible_description='Starts scrcpy for screen mirroring'
    ),
}


def get_tool_metadata(tool_key: str, fallback_label: str = '') -> ToolMetadata:
    """
    Get metadata for a tool, with fallback if not found.

    Args:
        tool_key: The tool identifier
        fallback_label: Label to use if tool not found in metadata

    Returns:
        ToolMetadata object
    """
    if tool_key in TOOL_METADATA:
        return TOOL_METADATA[tool_key]

    # Create fallback metadata
    return ToolMetadata(
        icon_key=tool_key,
        label=fallback_label or tool_key.replace('_', ' ').title(),
        tooltip=f'Execute {fallback_label or tool_key}',
        accessible_name=fallback_label or tool_key,
        accessible_description=f'Performs the {fallback_label or tool_key} action'
    )


__all__ = ['ToolMetadata', 'TOOL_METADATA', 'get_tool_metadata']
