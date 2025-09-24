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

import asyncio
import threading
import time
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker

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

    # 簡化的信號定義
    device_loaded = pyqtSignal(str, object)  # device_serial, device_info
    device_load_failed = pyqtSignal(str, str)  # device_serial, error_message
    progress_updated = pyqtSignal(int, int)  # current_count, total_count
    all_devices_loaded = pyqtSignal()

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
        """高效批量設備加載"""
        if not self.device_serials:
            return

        logger.info(f"開始高效異步加載 {len(self.device_serials)} 個設備")

        # 使用並發方式一次性加載所有設備信息
        self._load_all_devices_concurrent()

        if not self.stop_requested:
            self.all_devices_loaded.emit()
            logger.info(f"異步設備加載完成：{len(self.device_serials)} 個設備")

    def _load_all_devices_concurrent(self):
        """並發加載所有設備信息"""
        import concurrent.futures

        # 更新進度
        total_devices = len(self.device_serials)
        self.progress_updated.emit(0, total_devices)

        # 使用ThreadPoolExecutor並發處理所有設備
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交所有設備的加載任務
            future_to_serial = {
                executor.submit(self._load_complete_device_info, serial): serial
                for serial in self.device_serials
            }

            loaded_count = 0
            for future in concurrent.futures.as_completed(future_to_serial):
                if self.stop_requested:
                    break

                serial = future_to_serial[future]
                try:
                    device_info = future.result()
                    if device_info:
                        # 直接發送完整的設備信息
                        self.device_loaded.emit(serial, device_info)
                        loaded_count += 1
                    else:
                        self.device_load_failed.emit(serial, "無法加載設備信息")
                except Exception as e:
                    logger.error(f"設備 {serial} 加載失敗: {e}")
                    self.device_load_failed.emit(serial, str(e))

                # 更新進度（減少頻率）
                if loaded_count % max(1, total_devices // 10) == 0 or loaded_count == total_devices:
                    self.progress_updated.emit(loaded_count, total_devices)

    def _load_complete_device_info(self, serial: str) -> Optional[adb_models.DeviceInfo]:
        """一次性加載設備完整信息"""
        if self.stop_requested:
            return None

        try:
            # 獲取基本設備屬性
            device_model = self._get_device_property_fast(serial, 'ro.product.model')
            device_product = self._get_device_property_fast(serial, 'ro.product.name')
            android_version = self._get_device_property_fast(serial, 'ro.build.version.release')
            api_level = self._get_device_property_fast(serial, 'ro.build.version.sdk')

            # 只在需要詳細信息時才加載耗時的狀態檢查
            wifi_status = None
            bluetooth_status = None
            if self.load_detailed and not self.stop_requested:
                try:
                    wifi_status = adb_tools.check_wifi_is_on(serial)
                    bluetooth_status = adb_tools.check_bluetooth_is_on(serial)
                except:
                    pass  # 忽略狀態檢查失敗，繼續加載基本信息

            # 創建完整設備信息對象
            return adb_models.DeviceInfo(
                device_serial_num=serial,
                device_usb='USB',  # 簡化USB信息
                device_product=device_product or 'Unknown',
                device_model=device_model or 'Unknown Device',
                wifi_status=wifi_status,
                bluetooth_status=bluetooth_status,
                android_version=android_version or 'Unknown',
                android_api_level=api_level or 'Unknown',
                gms_version='Unknown',  # 簡化GMS版本檢查
                build_fingerprint='Unknown'  # 簡化指紋信息
            )
        except Exception as e:
            logger.error(f"獲取設備 {serial} 完整信息失敗: {e}")
            return None

    def _get_device_property_fast(self, serial: str, property_name: str) -> Optional[str]:
        """快速獲取設備屬性"""
        try:
            result = common.run_command(
                ['adb', '-s', serial, 'shell', 'getprop', property_name],
                timeout_seconds=2  # 更短的超時時間
            )
            if result and len(result) > 0:
                value = result[0].strip()
                return value if value and value != '' else None
        except Exception as e:
            logger.debug(f"快速獲取設備 {serial} 屬性 {property_name} 失敗: {e}")
        return None



class AsyncDeviceManager(QObject):
    """異步設備管理器"""

    # 簡化的信號定義
    device_discovery_started = pyqtSignal()
    device_info_loaded = pyqtSignal(str, object)  # device_serial, device_info
    device_load_progress = pyqtSignal(int, int, str)  # current, total, message
    all_devices_ready = pyqtSignal(dict)  # {serial: device_info}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_cache: Dict[str, adb_models.DeviceInfo] = {}
        self.device_progress: Dict[str, DeviceLoadProgress] = {}
        self.worker: Optional[AsyncDeviceWorker] = None

        # 設置
        self.max_cache_size = 50  # 最大緩存設備數
        self.detailed_loading_enabled = True

    def start_device_discovery(self, force_reload: bool = False, load_detailed: bool = True):
        """開始異步設備發現"""
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

            # 連接信號（簡化版）
            self.worker.device_loaded.connect(self._on_device_loaded)
            self.worker.device_load_failed.connect(self._on_device_load_failed)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.all_devices_loaded.connect(self._on_all_devices_loaded)

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
            result = common.run_command(['adb', 'devices'], timeout_seconds=5)
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

    def _on_device_loaded(self, serial: str, device_info: adb_models.DeviceInfo):
        """設備信息加載完成時的處理（簡化版）"""
        logger.debug(f"設備信息已加載: {serial} - {device_info.device_model}")

        # 更新緩存
        self.device_cache[serial] = device_info

        # 更新進度
        if serial in self.device_progress:
            self.device_progress[serial].status = DeviceLoadStatus.FULLY_LOADED
            self.device_progress[serial].basic_info = device_info

        # 發送信號
        self.device_info_loaded.emit(serial, device_info)

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

    def cleanup(self):
        """清理資源"""
        self.stop_current_loading()
        self.clear_cache()