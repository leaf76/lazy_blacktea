# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../lazy_blacktea_pyqt.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../assets', 'assets'),
        ('../config', 'config'),
        ('../ui', 'ui'),
        ('../utils', 'utils'),
    ],
    hiddenimports=[
        # Core PyQt6 modules
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtPrintSupport',
        'PyQt6.sip',
        # Application modules that might not be auto-detected
        'utils.qt_dependency_checker',
        'utils.adb_tools',
        'utils.adb_commands',
        'utils.adb_models',
        'utils.common',
        'utils.dump_device_ui',
        'utils.json_utils',
        'utils.ui_inspector_utils',
        'utils.ui_widgets',
        'config.config_manager',
        'config.constants',
        # Additional Python modules that might be missed
        'subprocess',
        'shutil',
        'glob',
        'threading',
        'concurrent.futures',
        'logging',
        'datetime',
        'platform',
        'webbrowser',
        'pathlib',
        'functools',
        'typing',
        'encodings',
        'encodings.utf_8',
        'encodings.ascii',
        'encodings.latin_1',
        # PyQt6 specific modules
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtPrintSupport',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
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
    name='LazyBlacktea',
    debug=True,  # Enable debug mode
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression to avoid issues on macOS
    console=True,  # Enable console to see error messages during debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity='-',
    entitlements_file=None,
    icon='../assets/icons/AppIcon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # Disable UPX compression
    upx_exclude=[],
    name='LazyBlacktea',
)

app = BUNDLE(
    coll,
    name='LazyBlacktea.app',
    icon='../assets/icons/AppIcon.icns',
    bundle_identifier='com.lazyblacktea.app',
    version='1.0.0',
    info_plist={
        'CFBundleDisplayName': 'Lazy Blacktea',
        'CFBundleName': 'LazyBlacktea',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDocumentTypes': [],
        'LSBackgroundOnly': False,  # Ensure app shows in Dock and can display windows
        'NSAppleEventsUsageDescription': 'This app needs to communicate with Android devices via ADB.',
        'NSSystemAdministrationUsageDescription': 'This app needs system access to run ADB commands.',
    },
)