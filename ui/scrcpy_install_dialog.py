"""Dialog for guiding users through scrcpy installation."""

from __future__ import annotations

import platform
import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from utils import common

if TYPE_CHECKING:
    from ui.main_window import WindowMain

logger = common.get_logger('scrcpy_install_dialog')


# Installation instructions by platform
_INSTRUCTIONS = {
    'darwin': {
        'title': 'scrcpy Not Found',
        'quick_cmd': 'brew install scrcpy && brew install --cask android-platform-tools',
        'install_url': 'https://github.com/Genymobile/scrcpy/blob/master/doc/macos.md',
        'markdown': """## macOS Installation

### Homebrew (Recommended)
```
brew install scrcpy
brew install --cask android-platform-tools
```

### MacPorts
```
sudo port install scrcpy
```

### Manual Download
Download from GitHub releases (aarch64 or x86_64):
https://github.com/Genymobile/scrcpy/releases

**Note:** You also need `adb` in your PATH. Homebrew's `android-platform-tools` provides this.
""",
    },
    'linux': {
        'title': 'scrcpy Not Found',
        'quick_cmd': 'sudo apt install scrcpy adb',
        'install_url': 'https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md',
        'markdown': """## Linux Installation

### Ubuntu/Debian
```
sudo apt update && sudo apt install scrcpy adb
```

### Fedora
```
sudo dnf install scrcpy android-tools
```

### Arch Linux
```
sudo pacman -S scrcpy android-tools
```

### Snap (Universal)
```
sudo snap install scrcpy
```

### Manual Download
https://github.com/Genymobile/scrcpy/releases
""",
    },
    'windows': {
        'title': 'scrcpy Not Found',
        'quick_cmd': 'winget install Genymobile.scrcpy',
        'install_url': 'https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md',
        'markdown': """## Windows Installation

### winget (Recommended)
```
winget install Genymobile.scrcpy
```

### Chocolatey
```
choco install scrcpy
```

### Scoop
```
scoop install scrcpy
```

### Manual Download
Download win64 zip from GitHub releases:
https://github.com/Genymobile/scrcpy/releases

Extract to a folder and add to your system PATH.
""",
    },
    'default': {
        'title': 'scrcpy Not Found',
        'quick_cmd': '',
        'install_url': 'https://github.com/Genymobile/scrcpy',
        'markdown': """## Installation

Visit the official GitHub repository for installation instructions:
https://github.com/Genymobile/scrcpy

scrcpy supports Linux, macOS, and Windows.
""",
    },
}


class ScrcpyInstallDialog(QDialog):
    """Dialog showing scrcpy installation instructions with actionable buttons."""

    scrcpy_detected = pyqtSignal()

    def __init__(self, parent: 'WindowMain') -> None:
        super().__init__(parent)
        self._parent_window = parent
        self._setup_ui()

    def _get_platform_info(self) -> dict:
        """Get installation info for current platform."""
        system = platform.system().lower()
        return _INSTRUCTIONS.get(system, _INSTRUCTIONS['default'])

    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        info = self._get_platform_info()

        self.setWindowTitle(info['title'])
        self.setMinimumSize(580, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)

        # Header
        header = QLabel('scrcpy is required for device mirroring')
        header.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(header)

        desc = QLabel(
            'scrcpy displays and controls Android devices via USB or TCP/IP.\n'
            'It requires no root access and works on all major platforms.'
        )
        desc.setWordWrap(True)
        desc.setStyleSheet('color: #888; margin-bottom: 8px;')
        layout.addWidget(desc)

        # Instructions text
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(info['markdown'])
        text_edit.setStyleSheet(
            'background: #1e1e1e; border: 1px solid #333; '
            'border-radius: 4px; padding: 8px;'
        )
        layout.addWidget(text_edit, 1)

        # Quick install command (copyable)
        quick_cmd = info.get('quick_cmd', '')
        if quick_cmd:
            cmd_layout = QHBoxLayout()
            cmd_layout.setSpacing(8)

            cmd_label = QLabel('Quick install:')
            cmd_label.setStyleSheet('font-weight: bold;')
            cmd_layout.addWidget(cmd_label)

            cmd_text = QLabel(f'<code>{quick_cmd}</code>')
            cmd_text.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            cmd_text.setStyleSheet(
                'background: #2d2d2d; padding: 6px 10px; '
                'border-radius: 4px; font-family: monospace;'
            )
            cmd_layout.addWidget(cmd_text, 1)

            copy_btn = QPushButton('Copy')
            copy_btn.setFixedWidth(60)
            copy_btn.clicked.connect(lambda: self._copy_to_clipboard(quick_cmd))
            cmd_layout.addWidget(copy_btn)

            layout.addLayout(cmd_layout)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        open_guide_btn = QPushButton('Installation Guide')
        open_guide_btn.setToolTip('Open platform-specific installation guide')
        open_guide_btn.clicked.connect(
            lambda: webbrowser.open(info['install_url'])
        )
        btn_layout.addWidget(open_guide_btn)

        open_releases_btn = QPushButton('GitHub Releases')
        open_releases_btn.setToolTip('Download scrcpy from official releases')
        open_releases_btn.clicked.connect(
            lambda: webbrowser.open('https://github.com/Genymobile/scrcpy/releases')
        )
        btn_layout.addWidget(open_releases_btn)

        btn_layout.addStretch()

        recheck_btn = QPushButton('Re-check scrcpy')
        recheck_btn.setToolTip('Check if scrcpy is now available after installation')
        recheck_btn.setStyleSheet(
            'background: #4CAF50; color: white; font-weight: bold; padding: 6px 16px;'
        )
        recheck_btn.clicked.connect(self._recheck_scrcpy)
        btn_layout.addWidget(recheck_btn)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            if hasattr(self._parent_window, 'show_info'):
                self._parent_window.show_info('Copied', 'Command copied to clipboard!')

    def _recheck_scrcpy(self) -> None:
        """Re-check scrcpy availability after user installation."""
        app_mgr = getattr(self._parent_window, 'app_management_manager', None)
        if app_mgr is None:
            return

        app_mgr.initialize()

        if app_mgr.scrcpy_available:
            version = app_mgr.scrcpy_major_version
            self.scrcpy_detected.emit()
            self.close()
            if hasattr(self._parent_window, 'show_info'):
                self._parent_window.show_info(
                    'scrcpy Found!',
                    f'scrcpy v{version}.x detected successfully!\n\n'
                    'You can now use device mirroring.'
                )
        else:
            if hasattr(self._parent_window, 'show_warning'):
                self._parent_window.show_warning(
                    'scrcpy Not Found',
                    'scrcpy is still not detected.\n\n'
                    'Please ensure:\n'
                    '1. scrcpy is installed\n'
                    '2. scrcpy is in your system PATH\n'
                    '3. Try opening a new terminal and running:\n'
                    '   scrcpy --version'
                )


__all__ = ['ScrcpyInstallDialog']
