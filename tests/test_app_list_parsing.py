from unittest.mock import patch

from utils import adb_tools


def test_parse_pm_list_packages_output_basic():
    # Given typical `pm list packages -f` output lines
    lines = [
        'package:/system/app/PrebuiltGmsCore/PrebuiltGmsCore.apk=com.google.android.gms',
        'package:/data/app/~~abcd1234==/com.example.myapp-7Jk9A==/base.apk=com.example.myapp',
        'package:/product/app/SysUi/SysUi.apk=com.android.systemui',
    ]

    apps = adb_tools.parse_pm_list_packages_output(lines)

    # Then it parses package and path, and classifies system/user
    assert any(a['package'] == 'com.google.android.gms' and a['is_system'] for a in apps)
    assert any(a['package'] == 'com.example.myapp' and not a['is_system'] for a in apps)
    # Ensure apk_path is captured
    assert any(a['apk_path'].endswith('.apk') for a in apps)


def test_parse_dumpsys_package_permissions():
    # Given trimmed lines from `dumpsys package com.example.myapp`
    lines = [
        'Packages:',
        '  Package [com.example.myapp] (123abc):',
        '    requested permissions:',
        '      android.permission.CAMERA',
        '      android.permission.ACCESS_FINE_LOCATION',
        '    install permissions:',
        '      android.permission.CAMERA: granted=true',
        '      android.permission.ACCESS_COARSE_LOCATION: granted=false',
        '    runtime permissions:',
        '      android.permission.ACCESS_FINE_LOCATION: granted=true',
    ]

    parsed = adb_tools.parse_dumpsys_package_permissions(lines)

    assert 'requested' in parsed and 'granted' in parsed
    assert 'android.permission.CAMERA' in parsed['requested']
    assert 'android.permission.ACCESS_FINE_LOCATION' in parsed['requested']
    # Granted set should include granted=true entries from install/runtime sections
    assert 'android.permission.CAMERA' in parsed['granted']
    assert 'android.permission.ACCESS_FINE_LOCATION' in parsed['granted']

