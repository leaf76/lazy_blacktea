# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['lazy_blacktea_pyqt.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('config', 'config'),
        ('ui', 'ui'),
        ('utils', 'utils'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtPrintSupport',
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
    icon='assets/icons/AppIcon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LazyBlacktea',
)

app = BUNDLE(
    coll,
    name='LazyBlacktea.app',
    icon='assets/icons/AppIcon.icns',
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
        'NSAppleEventsUsageDescription': 'This app needs to communicate with Android devices via ADB.',
        'NSSystemAdministrationUsageDescription': 'This app needs system access to run ADB commands.',
    },
)