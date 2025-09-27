"""Periodic battery information refresh and caching utilities."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import QTimer

from utils import adb_tools, common

if TYPE_CHECKING:  # pragma: no cover
    from lazy_blacktea_pyqt import WindowMain

logger = common.get_logger("battery_info_manager")

TimerFactory = Callable[[], QTimer]
InfoFetcher = Callable[[str], Dict[str, str]]
PostCallback = Callable[[Callable[[], None]], None]


class BatteryInfoManager:
    """Cache and periodically refresh battery data for connected devices."""

    def __init__(
        self,
        window: "WindowMain",
        refresh_interval_ms: int = 60000,
        timer_factory: Optional[TimerFactory] = None,
        info_fetcher: Optional[InfoFetcher] = None,
        post_callback: Optional[PostCallback] = None,
    ) -> None:
        self.window = window
        self.cache: Dict[str, Dict[str, str]] = {}
        self._info_fetcher = info_fetcher or adb_tools.get_additional_device_info
        self._post_callback = post_callback or self._default_post_callback

        self._timer = timer_factory() if timer_factory else QTimer(window)
        self._timer.setInterval(refresh_interval_ms)
        self._timer.timeout.connect(self.refresh_all)

    # ------------------------------------------------------------------
    # Timer control
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def refresh_all(self) -> None:
        serials = list(self.window.device_dict.keys())
        self.refresh_serials(serials)

    def refresh_serials(self, serials: Iterable[str]) -> None:
        serial_list = [s for s in serials if s in self.window.device_dict]
        if not serial_list:
            return

        def worker() -> None:
            data: Dict[str, Dict[str, str]] = {}
            for serial in serial_list:
                try:
                    info = self._info_fetcher(serial)
                    data[serial] = info
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.debug('Failed to refresh battery info for %s: %s', serial, exc)
            if data:
                self._post_callback(lambda d=data: self._apply_refresh(d))

        self.window.run_in_thread(worker)

    def remove(self, serial: str) -> None:
        self.cache.pop(serial, None)

    # ------------------------------------------------------------------
    # Cache accessors
    # ------------------------------------------------------------------
    def get_cached_info(self, serial: str) -> Dict[str, str]:
        return dict(self.cache.get(serial, {}))

    def update_cache(self, serial: str, info: Dict[str, str]) -> None:
        self.cache[serial] = info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _apply_refresh(self, data: Dict[str, Dict[str, str]]) -> None:
        self.cache.update(data)
        self.window.device_list_controller.update_device_list(self.window.device_dict)

    @staticmethod
    def _default_post_callback(callback: Callable[[], None]) -> None:
        QTimer.singleShot(0, callback)


__all__ = ["BatteryInfoManager"]
