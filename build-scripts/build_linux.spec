# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect Qt platform plugins and libraries
qt_plugins = collect_data_files('PyQt6.Qt6.plugins', subdir='plugins')
qt_libs = collect_dynamic_libs('PyQt6')

a = Analysis(
    ['lazy_blacktea_pyqt.py'],
    pathex=[],
    binaries=qt_libs + [
        # Include system libraries that might be missing
        ('/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0*', '.'),
        ('/usr/lib/x86_64-linux-gnu/libxcb-xkb.so.1*', '.'),
        ('/usr/lib/x86_64-linux-gnu/libxcb-xinput.so.0*', '.'),
        ('/usr/lib/x86_64-linux-gnu/libfontconfig.so.1*', '.'),
        ('/usr/lib/x86_64-linux-gnu/libfreetype.so.6*', '.'),
    ],
    datas=[
        ('assets', 'assets'),
        ('config', 'config'),
        ('ui', 'ui'),
        ('utils', 'utils'),
        ('build/native-libs', 'native'),
        ('VERSION', 'VERSION'),
    ] + qt_plugins,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtPrintSupport',
        'PyQt6.sip',
        'utils.qt_dependency_checker',  # Include the Qt dependency checker
    ],
    hookspath=[],
    hooksconfig={
        'PyQt6': {
            'plugins': ['platforms', 'platforminputcontexts', 'xcbglintegrations'],
        }
    },
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lazyblacktea',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/icon_512x512.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lazyblacktea',
)
