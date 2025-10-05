"""Entry point for the Lazy Blacktea PyQt application."""

from utils.qt_plugin_loader import configure_qt_plugin_path

configure_qt_plugin_path()

from PyQt6.QtWidgets import QApplication

from ui.main_window import WindowMain
from ui.constants import DEVICE_FILE_IS_DIR_ROLE, DEVICE_FILE_PATH_ROLE
from utils.qt_dependency_checker import check_and_fix_qt_dependencies
from config.constants import ApplicationConstants

import sys

__all__ = [
    "WindowMain",
    "DEVICE_FILE_PATH_ROLE",
    "DEVICE_FILE_IS_DIR_ROLE",
    "main",
]


def main() -> None:
    """Main application entry point."""
    if not check_and_fix_qt_dependencies():
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("lazy blacktea")
    app.setApplicationVersion(ApplicationConstants.APP_VERSION)

    window = WindowMain()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
