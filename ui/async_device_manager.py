#!/usr/bin/env python3
"""
異步設備管理器 - 解決大量設備時的UI凍結問題

這個模組負責：
1. 漸進式設備發現和信息加載
2. 異步設備信息提取，不阻塞UI
3. 實時進度反饋和狀態更新
4. 優先加載基本信息，詳細信息按需加載
5. 內存使用優化和設備信息緩存
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer

from utils import adb_tools, common, adb_models

logger = common.get_logger('async_device_manager')


class DeviceLoadStatus(Enum):
    """設備加載狀態"""
    DISCOVERING = "discovering"      # 發現中
    BASIC_LOADED = "basic_loaded"    # 基本信息已加載
    DETAILED_LOADING = "detailed_loading"  # 詳細信息加載中
    FULLY_LOADED = "fully_loaded"    # 完全加載
    ERROR = "error"                  # 加載錯誤


@dataclass
class DeviceLoadProgress:
    """設備加載進度信息"""
    serial: str
    status: DeviceLoadStatus
    basic_info: Optional[adb_models.DeviceInfo] = None
    detailed_info: Optional[Dict] = None
    error_message: Optional[str] = None
    load_time: float = field(default_factory=time.time)


class AsyncDeviceWorker(QThread):
    """異步設備信息加載工作線程"""

    # 漸進式加載信號定義
    device_basic_loaded = pyqtSignal(str, object)  # device_serial, basic_info
    device_detailed_loaded = pyqtSignal(str, object)  # device_serial, detailed_info
    device_load_failed = pyqtSignal(str, str)  # device_serial, error_message
    progress_updated = pyqtSignal(int, int)  # current_count, total_count
    all_basic_loaded = pyqtSignal()  # 所有基本信息加載完成
    all_detailed_loaded = pyqtSignal()  # 所有詳細信息加載完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_serials: List[str] = []
        self.load_detailed: bool = True
        self.max_concurrent: int = 3  # 限制並發數量
        self.stop_requested: bool = False
        self.mutex = QMutex()

    def set_devices(self, device_serials: List[str], load_detailed: bool = True):
        """設置要加載的設備列表"""
        with QMutexLocker(self.mutex):
            self.device_serials = device_serials.copy()
            self.load_detailed = load_detailed
            self.stop_requested = False

    def request_stop(self):
        """請求停止加載"""
        with QMutexLocker(self.mutex):
            self.stop_requested = True

    def run(self):
        """執行異步設備加載"""
        try:
            self._load_devices_efficiently()
        except Exception as e:
            logger.error(f"異步設備加載錯誤: {e}")

    def _load_devices_efficiently(self):
        """漸進式設備加載：先顯示基本信息，再異步補充詳細信息"""
        if not self.device_serials:
            return

        logger.info(f"開始漸進式異步加載 {len(self.device_serials)} 個設備")

        # Phase 1: 快速加載並顯示基本信息
        self._load_basic_info_immediately()

        if not self.stop_requested:
            self.all_basic_loaded.emit()

        # Phase 2: 異步加載詳細信息
        if self.load_detailed and not self.stop_requested:
            self._load_detailed_info_progressively()

        if not self.stop_requested:
            self.all_detailed_loaded.emit()
            logger.info(f"漸進式設備加載完成：{len(self.device_serials)} 個設備")

    def _load_basic_info_immediately(self):
        """立即加載所有設備的基本信息（僅基本信息，不執行耗時檢查）"""
        logger.info("Phase 1: 快速加載基本設備信息")

        try:
            # 使用新的快速設備列表函數
            basic_device_infos = adb_tools.get_devices_list_fast()

            loaded_count = 0
            for device_info in basic_device_infos:
                if self.stop_requested:
                    break

                # 立即發送基本信息到UI
                self.device_basic_loaded.emit(device_info.device_serial_num, device_info)
                loaded_count += 1

                # 更新進度
                self.progress_updated.emit(loaded_count, len(self.device_serials))

            logger.info(f"基本信息加載完成：{loaded_count} 個設備")

        except Exception as e:
            logger.error(f"基本信息加載失敗: {e}")

    def _load_detailed_info_progressively(self):
        """漸進式加載詳細設備信息"""
        logger.info("Phase 2: 異步加載詳細設備信息")

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交詳細信息加載任務
            future_to_serial = {
                executor.submit(adb_tools.get_device_detailed_info, serial): serial
                for serial in self.device_serials
            }

            loaded_count = 0
            for future in concurrent.futures.as_completed(future_to_serial):
                if self.stop_requested:
                    break

                serial = future_to_serial[future]
                try:
                    detailed_info = future.result()
                    if detailed_info:
                        # 發送詳細信息更新
                        self.device_detailed_loaded.emit(serial, detailed_info)
                        loaded_count += 1
                    else:
                        self.device_load_failed.emit(serial, "無法加載詳細設備信息")
                except Exception as e:
                    logger.error(f"設備 {serial} 詳細信息加載失敗: {e}")
                    self.device_load_failed.emit(serial, str(e))

                # 更新詳細信息加載進度
                if loaded_count % max(1, len(self.device_serials) // 5) == 0:
                    logger.debug(f"詳細信息加載進度: {loaded_count}/{len(self.device_serials)}")

            logger.info(f"詳細信息加載完成：{loaded_count} 個設備")




class AsyncDeviceManager(QObject):
    """異步設備管理器"""

    # 漸進式加載信號定義
    device_discovery_started = pyqtSignal()
    device_basic_loaded = pyqtSignal(str, object)  # device_serial, basic_info
    device_detailed_loaded = pyqtSignal(str, object)  # device_serial, detailed_info
    device_load_progress = pyqtSignal(int, int, str)  # current, total, message
    basic_devices_ready = pyqtSignal(dict)  # 基本信息加載完成
    all_devices_ready = pyqtSignal(dict)  # 所有信息加載完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_cache: Dict[str, adb_models.DeviceInfo] = {}
        self.device_progress: Dict[str, DeviceLoadProgress] = {}
        self.worker: Optional[AsyncDeviceWorker] = None

        # 設置
        self.max_cache_size = 50  # 最大緩存設備數
        self.detailed_loading_enabled = True

        # 定時刷新設置
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._periodic_refresh)
        self.refresh_interval = 10  # 默認10秒刷新間隔
        self.auto_refresh_enabled = True

    def start_device_discovery(self, force_reload: bool = False, load_detailed: bool = True):
        """開始異步設備發現"""
        # force_reload parameter kept for compatibility but not currently used
        logger.info("開始異步設備發現...")

        # 停止現有工作線程
        self.stop_current_loading()

        self.device_discovery_started.emit()

        try:
            # 快速獲取設備列表（不包含詳細信息）
            basic_device_serials = self._get_basic_device_serials()

            if not basic_device_serials:
                logger.warning("未發現任何設備")
                self.all_devices_ready.emit({})
                return

            logger.info(f"發現 {len(basic_device_serials)} 個設備，開始異步加載")

            # 創建工作線程
            self.worker = AsyncDeviceWorker()
            self.worker.set_devices(basic_device_serials, load_detailed)

            # 連接信號（漸進式版）
            self.worker.device_basic_loaded.connect(self._on_device_basic_loaded)
            self.worker.device_detailed_loaded.connect(self._on_device_detailed_loaded)
            self.worker.device_load_failed.connect(self._on_device_load_failed)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.all_basic_loaded.connect(self._on_all_basic_loaded)
            self.worker.all_detailed_loaded.connect(self._on_all_detailed_loaded)

            # 啟動工作線程
            self.worker.start()

        except Exception as e:
            logger.error(f"設備發現啟動失敗: {e}")

    def stop_current_loading(self):
        """停止當前的加載過程"""
        if self.worker and self.worker.isRunning():
            logger.info("停止當前設備加載過程")
            self.worker.request_stop()
            self.worker.wait(3000)  # 等待3秒
            if self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait(1000)

    def _get_basic_device_serials(self) -> List[str]:
        """快速獲取設備序號列表"""
        try:
            # 只執行基本的設備列舉，不獲取詳細信息
            result = common.run_command('adb devices')
            device_serials = []

            for line in result:
                if line and '\tdevice' in line:
                    serial = line.split('\t')[0].strip()
                    if serial:
                        device_serials.append(serial)

            return device_serials
        except Exception as e:
            logger.error(f"獲取基本設備列表失敗: {e}")
            return []

    def _on_device_basic_loaded(self, serial: str, device_info: adb_models.DeviceInfo):
        """設備基本信息加載完成時的處理"""
        logger.debug(f"設備基本信息已加載: {serial} - {device_info.device_model}")

        # 更新緩存
        self.device_cache[serial] = device_info

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.BASIC_LOADED
            self.device_progress[serial].basic_info = device_info

        # 發送信號，立即更新UI
        self.device_basic_loaded.emit(serial, device_info)

    def _on_device_detailed_loaded(self, serial: str, detailed_info: dict):
        """設備詳細信息加載完成時的處理"""
        logger.debug(f"設備詳細信息已加載: {serial}")

        # 更新設備信息
        if serial in self.device_cache:
            device_info = self.device_cache[serial]
            # 更新詳細信息（注意字段名稱匹配）
            device_info.wifi_status = detailed_info.get('wifi_status')
            device_info.bluetooth_status = detailed_info.get('bluetooth_status')
            device_info.android_ver = detailed_info.get('android_version', 'Unknown')  # 注意：android_ver 不是 android_version
            device_info.android_api_level = detailed_info.get('android_api_level', 'Unknown')
            device_info.gms_version = detailed_info.get('gms_version', 'Unknown')
            device_info.build_fingerprint = detailed_info.get('build_fingerprint', 'Unknown')

            # 更新 WiFi 和藍牙狀態的布爾字段（UI 中使用的）
            device_info.wifi_is_on = detailed_info.get('wifi_status') == 1
            device_info.bt_is_on = detailed_info.get('bluetooth_status') == 1

            # 發送更新信號
            self.device_detailed_loaded.emit(serial, device_info)

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.FULLY_LOADED
            self.device_progress[serial].detailed_info = detailed_info

    def _on_all_basic_loaded(self):
        """所有設備基本信息加載完成"""
        logger.info("所有設備基本信息加載完成")
        self.basic_devices_ready.emit(self.device_cache.copy())

    def _on_all_detailed_loaded(self):
        """所有設備詳細信息加載完成"""
        logger.info("所有設備詳細信息加載完成")
        self.all_devices_ready.emit(self.device_cache.copy())

    def _on_device_load_failed(self, serial: str, error_message: str):
        """設備加載失敗時的處理"""
        logger.warning(f"設備加載失敗: {serial} - {error_message}")

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.ERROR
            self.device_progress[serial].error_message = error_message

    def _on_progress_updated(self, current: int, total: int):
        """進度更新時的處理"""
        message = f"已加載 {current}/{total} 個設備基本信息"
        logger.debug(message)
        self.device_load_progress.emit(current, total, message)

    def _on_all_devices_loaded(self):
        """所有設備加載完成時的處理"""
        logger.info("所有設備信息加載完成")
        self.all_devices_ready.emit(self.device_cache.copy())

    def get_device_info(self, serial: str) -> Optional[adb_models.DeviceInfo]:
        """獲取設備信息"""
        return self.device_cache.get(serial)

    def get_all_devices(self) -> Dict[str, adb_models.DeviceInfo]:
        """獲取所有設備信息"""
        return self.device_cache.copy()

    def get_load_progress(self, serial: str) -> Optional[DeviceLoadProgress]:
        """獲取設備加載進度"""
        return self.device_progress.get(serial)

    def clear_cache(self):
        """清空設備緩存"""
        self.device_cache.clear()
        self.device_progress.clear()
        logger.info("設備緩存已清空")

    def start_periodic_refresh(self):
        """開始定時刷新"""
        if self.auto_refresh_enabled and not self.refresh_timer.isActive():
            self.refresh_timer.start(self.refresh_interval * 1000)  # 轉換為毫秒
            logger.info(f"定時刷新已啟動，間隔: {self.refresh_interval}秒")

    def stop_periodic_refresh(self):
        """停止定時刷新"""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            logger.info("定時刷新已停止")

    def set_refresh_interval(self, interval: int):
        """設置刷新間隔"""
        self.refresh_interval = max(5, interval)  # 最小5秒間隔
        if self.refresh_timer.isActive():
            self.refresh_timer.setInterval(self.refresh_interval * 1000)
        logger.info(f"刷新間隔設置為: {self.refresh_interval}秒")

    def set_auto_refresh_enabled(self, enabled: bool):
        """設置是否啟用自動刷新"""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.start_periodic_refresh()
        else:
            self.stop_periodic_refresh()
        logger.info(f"自動刷新: {'啟用' if enabled else '停用'}")

    def _periodic_refresh(self):
        """定時刷新回調"""
        logger.debug("執行定時設備刷新")
        try:
            # 只進行基本信息的快速刷新，避免過度負載
            self.start_device_discovery(force_reload=False, load_detailed=False)
        except Exception as e:
            logger.error(f"定時刷新失敗: {e}")

    def cleanup(self):
        """清理資源"""
        self.stop_periodic_refresh()
        self.stop_current_loading()
        self.clear_cache()