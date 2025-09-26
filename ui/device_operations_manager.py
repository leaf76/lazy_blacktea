"""設備操作管理器 - 負責管理所有設備相關操作

這個模組將所有設備操作邏輯從主窗口中分離出來，提供：
1. 設備控制操作（重啟、藍牙控制等）
2. 媒體操作（截圖、錄屏等）
3. 應用程序操作（安裝APK、啟動工具等）
4. 設備狀態管理
5. 錯誤處理和日誌記錄

重構目標：
- 減少主窗口類的複雜度
- 提高設備操作邏輯的可重用性
- 統一設備操作的錯誤處理
- 改善代碼組織結構
"""

import os
import subprocess
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from utils import adb_models, adb_tools, common
from utils.recording_utils import RecordingManager
from utils.screenshot_utils import take_screenshots_batch


class DeviceOperationsManager(QObject):
    """設備操作管理器類 - 負責所有設備相關操作"""

    # 信號定義
    recording_stopped_signal = pyqtSignal(str, str, float, str, str)  # device_name, device_serial, duration, filename, output_path
    recording_state_cleared_signal = pyqtSignal(str)  # device_serial
    screenshot_completed_signal = pyqtSignal(str, int, list)  # output_path, device_count, device_models
    operation_completed_signal = pyqtSignal(str, str, bool, str)  # operation, device_serial, success, message

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.logger = common.get_logger('device_operations_manager')

        # 設備狀態管理
        self.device_recordings: Dict[str, Dict] = {}
        self.device_operations: Dict[str, str] = {}

        # 錄製管理器
        self.recording_manager = RecordingManager()

        # 錄製狀態更新定時器
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_status)
        self.recording_timer.start(500)

    # ===== 設備控制操作 =====

    def reboot_device(self, device_serials: List[str] = None, reboot_mode: str = "system") -> bool:
        """重啟設備

        Args:
            device_serials: 設備序列號列表，如果為None則使用選中的設備
            reboot_mode: 重啟模式 ("system", "recovery", "bootloader")
        """
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to reboot.")
            return False

        success_count = 0
        for serial in device_serials:
            try:
                self._log_console(f"Rebooting device {serial} to {reboot_mode}...")

                if reboot_mode == "recovery":
                    result = adb_tools.run_adb_command(f"-s {serial} reboot recovery")
                elif reboot_mode == "bootloader":
                    result = adb_tools.run_adb_command(f"-s {serial} reboot bootloader")
                else:
                    result = adb_tools.run_adb_command(f"-s {serial} reboot")

                if result.returncode == 0:
                    success_count += 1
                    self._log_console(f"✅ Device {serial} reboot command sent successfully")
                    self.operation_completed_signal.emit("reboot", serial, True, f"Reboot command sent to {reboot_mode}")
                else:
                    self._log_console(f"❌ Failed to reboot device {serial}: {result.stderr}")
                    self.operation_completed_signal.emit("reboot", serial, False, result.stderr)

            except Exception as e:
                self._log_console(f"❌ Error rebooting device {serial}: {str(e)}")
                self.operation_completed_signal.emit("reboot", serial, False, str(e))

        if success_count > 0:
            self._show_info("Reboot Initiated", f"Reboot command sent to {success_count} device(s).")
            return True
        else:
            self._show_error("Reboot Failed", "Failed to send reboot command to any device.")
            return False

    def reboot_single_device(self, device_serial: str, reboot_mode: str = "system") -> bool:
        """重啟單個設備"""
        return self.reboot_device([device_serial], reboot_mode)

    def enable_bluetooth(self, device_serials: List[str] = None) -> bool:
        """啟用設備藍牙"""
        return self._toggle_bluetooth(device_serials, True)

    def disable_bluetooth(self, device_serials: List[str] = None) -> bool:
        """禁用設備藍牙"""
        return self._toggle_bluetooth(device_serials, False)

    def _toggle_bluetooth(self, device_serials: List[str] = None, enable: bool = True) -> bool:
        """切換設備藍牙狀態"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            action = "enable" if enable else "disable"
            self._show_warning("No Device Selected", f"Please select at least one device to {action} Bluetooth.")
            return False

        action_text = "enabling" if enable else "disabling"
        command = "enable" if enable else "disable"
        success_count = 0

        for serial in device_serials:
            try:
                self._log_console(f"{action_text.capitalize()} Bluetooth on device {serial}...")

                result = adb_tools.run_adb_command(f"-s {serial} shell svc bluetooth {command}")

                if result.returncode == 0:
                    success_count += 1
                    status = "enabled" if enable else "disabled"
                    self._log_console(f"✅ Bluetooth {status} on device {serial}")
                    self.operation_completed_signal.emit("bluetooth", serial, True, f"Bluetooth {status}")
                else:
                    self._log_console(f"❌ Failed to {command} Bluetooth on device {serial}: {result.stderr}")
                    self.operation_completed_signal.emit("bluetooth", serial, False, result.stderr)

            except Exception as e:
                self._log_console(f"❌ Error {action_text} Bluetooth on device {serial}: {str(e)}")
                self.operation_completed_signal.emit("bluetooth", serial, False, str(e))

        if success_count > 0:
            action_past = "enabled" if enable else "disabled"
            self._show_info("Bluetooth Operation", f"Bluetooth {action_past} on {success_count} device(s).")
            return True
        else:
            action_text = "enable" if enable else "disable"
            self._show_error("Bluetooth Operation Failed", f"Failed to {action_text} Bluetooth on any device.")
            return False

    # ===== 媒體操作 =====

    def take_screenshot(self, device_serials: List[str] = None, output_path: str = None,
                       callback: Callable = None) -> bool:
        """批量截圖"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to take screenshots.")
            return False

        # 獲取輸出路徑
        if output_path is None:
            output_path = self._get_output_path()
            if not output_path:
                return False

        def screenshot_thread():
            """截圖線程函數"""
            try:
                device_models = []
                devices = self._get_devices_by_serials(device_serials)

                for device in devices:
                    device_models.append(device.device_model)

                # 使用批量截圖工具
                success = take_screenshots_batch(device_serials, output_path)

                if success:
                    self.screenshot_completed_signal.emit(output_path, len(device_serials), device_models)

                    if callback:
                        callback(output_path, len(device_serials), device_models)
                else:
                    self._log_console("❌ Screenshot operation failed")

            except Exception as e:
                self._log_console(f"❌ Error in screenshot thread: {str(e)}")

        # 在後台線程中執行截圖
        threading.Thread(target=screenshot_thread, daemon=True).start()
        return True

    def take_screenshot_single_device(self, device_serial: str, output_path: str = None) -> bool:
        """單設備截圖"""
        return self.take_screenshot([device_serial], output_path)

    def start_screen_record(self, device_serials: List[str] = None, output_path: str = None,
                          duration: int = 30, callback: Callable = None) -> bool:
        """開始屏幕錄製"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to start recording.")
            return False

        # 獲取輸出路徑
        if output_path is None:
            output_path = self._get_output_path()
            if not output_path:
                return False

        success_count = 0
        for serial in device_serials:
            try:
                # 檢查是否已在錄製
                if serial in self.device_recordings:
                    self._show_warning("Already Recording", f"Device {serial} is already recording.")
                    continue

                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"recording_{serial}_{timestamp}.mp4"

                # 開始錄製
                success = self.recording_manager.start_recording(serial, output_path, filename, duration)

                if success:
                    # 記錄錄製狀態
                    self.device_recordings[serial] = {
                        'start_time': time.time(),
                        'duration': duration,
                        'filename': filename,
                        'output_path': output_path
                    }

                    success_count += 1
                    device_info = self._get_device_info(serial)
                    device_name = device_info.device_model if device_info else serial

                    self._log_console(f"🎬 Started recording on {device_name} ({serial})")
                    self.operation_completed_signal.emit("recording_start", serial, True, "Recording started")

                    if callback:
                        callback(device_name, serial, duration, filename, output_path)

                else:
                    self._log_console(f"❌ Failed to start recording on device {serial}")
                    self.operation_completed_signal.emit("recording_start", serial, False, "Failed to start recording")

            except Exception as e:
                self._log_console(f"❌ Error starting recording on device {serial}: {str(e)}")
                self.operation_completed_signal.emit("recording_start", serial, False, str(e))

        if success_count > 0:
            self._show_info("Recording Started", f"Started recording on {success_count} device(s).")
            return True
        else:
            self._show_error("Recording Failed", "Failed to start recording on any device.")
            return False

    def stop_screen_record(self, device_serials: List[str] = None) -> bool:
        """停止屏幕錄製"""
        if device_serials is None:
            # 如果沒有指定設備，停止所有正在錄製的設備
            device_serials = list(self.device_recordings.keys())

        if not device_serials:
            self._show_warning("No Active Recordings", "No active recordings to stop.")
            return False

        success_count = 0
        for serial in device_serials:
            try:
                if serial not in self.device_recordings:
                    self._log_console(f"⚠️ Device {serial} is not recording")
                    continue

                # 停止錄製
                success = self.recording_manager.stop_recording(serial)

                if success:
                    recording_info = self.device_recordings[serial]
                    duration = time.time() - recording_info['start_time']

                    device_info = self._get_device_info(serial)
                    device_name = device_info.device_model if device_info else serial

                    # 發送信號
                    self.recording_stopped_signal.emit(
                        device_name,
                        serial,
                        duration,
                        recording_info['filename'],
                        recording_info['output_path']
                    )

                    success_count += 1
                    self._log_console(f"⏹️ Stopped recording on {device_name} ({serial})")

                else:
                    self._log_console(f"❌ Failed to stop recording on device {serial}")
                    self.operation_completed_signal.emit("recording_stop", serial, False, "Failed to stop recording")

            except Exception as e:
                self._log_console(f"❌ Error stopping recording on device {serial}: {str(e)}")
                self.operation_completed_signal.emit("recording_stop", serial, False, str(e))

        if success_count > 0:
            self._show_info("Recording Stopped", f"Stopped recording on {success_count} device(s).")
            return True
        else:
            self._show_error("Stop Recording Failed", "Failed to stop recording on any device.")
            return False

    def update_recording_status(self):
        """更新錄製狀態（定時調用）"""
        current_time = time.time()
        completed_recordings = []

        for serial, recording_info in self.device_recordings.items():
            elapsed_time = current_time - recording_info['start_time']

            # 檢查是否超過預定時間
            if elapsed_time >= recording_info['duration']:
                completed_recordings.append(serial)

        # 處理完成的錄製
        for serial in completed_recordings:
            self._handle_recording_completion(serial)

    def _handle_recording_completion(self, serial: str):
        """處理錄製完成"""
        if serial in self.device_recordings:
            recording_info = self.device_recordings[serial]
            duration = time.time() - recording_info['start_time']

            device_info = self._get_device_info(serial)
            device_name = device_info.device_model if device_info else serial

            # 發送錄製停止信號
            self.recording_stopped_signal.emit(
                device_name,
                serial,
                duration,
                recording_info['filename'],
                recording_info['output_path']
            )

            self._log_console(f"✅ Recording completed on {device_name} ({serial})")

    def clear_device_recording(self, serial: str):
        """清除設備錄製狀態"""
        if serial in self.device_recordings:
            del self.device_recordings[serial]
            self.recording_state_cleared_signal.emit(serial)
            self._log_console(f"🗑️ Cleared recording state for device {serial}")

    # ===== 應用程序操作 =====

    def install_apk(self, device_serials: List[str] = None, apk_file: str = None) -> bool:
        """安裝APK到設備"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to install APK.")
            return False

        # 選擇APK文件
        if apk_file is None:
            apk_file, _ = QFileDialog.getOpenFileName(
                self.parent_window,
                "Select APK file",
                "",
                "APK files (*.apk);;All files (*)"
            )

        if not apk_file:
            return False

        apk_name = os.path.basename(apk_file)

        def install_thread():
            """APK安裝線程"""
            try:
                self._install_apk_with_progress(device_serials, apk_file, apk_name)
            except Exception as e:
                self._log_console(f"❌ Error in APK installation thread: {str(e)}")

        # 在後台線程中執行安裝
        threading.Thread(target=install_thread, daemon=True).start()
        return True

    def _install_apk_with_progress(self, device_serials: List[str], apk_file: str, apk_name: str):
        """帶進度的APK安裝"""
        success_count = 0
        total_devices = len(device_serials)

        self._log_console(f"📱 Installing {apk_name} on {total_devices} device(s)...")

        for i, serial in enumerate(device_serials):
            try:
                device_info = self._get_device_info(serial)
                device_name = device_info.device_model if device_info else serial

                self._log_console(f"📱 [{i+1}/{total_devices}] Installing on {device_name} ({serial})...")

                # 執行安裝命令
                result = adb_tools.run_adb_command(f"-s {serial} install -r \"{apk_file}\"")

                if result.returncode == 0:
                    success_count += 1
                    self._log_console(f"✅ [{i+1}/{total_devices}] Successfully installed on {device_name}")
                    self.operation_completed_signal.emit("apk_install", serial, True, f"APK installed: {apk_name}")
                else:
                    error_msg = result.stderr or "Installation failed"
                    self._log_console(f"❌ [{i+1}/{total_devices}] Failed to install on {device_name}: {error_msg}")
                    self.operation_completed_signal.emit("apk_install", serial, False, error_msg)

            except Exception as e:
                self._log_console(f"❌ [{i+1}/{total_devices}] Error installing on device {serial}: {str(e)}")
                self.operation_completed_signal.emit("apk_install", serial, False, str(e))

        # 顯示最終結果
        if success_count > 0:
            self._show_info("APK Installation",
                          f"Successfully installed {apk_name} on {success_count}/{total_devices} device(s).")
        else:
            self._show_error("APK Installation Failed",
                           f"Failed to install {apk_name} on any device.")

    def launch_scrcpy(self, device_serials: List[str] = None) -> bool:
        """啟動scrcpy工具"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to launch scrcpy.")
            return False

        success_count = 0
        for serial in device_serials:
            if self.launch_scrcpy_single_device(serial):
                success_count += 1

        if success_count > 0:
            self._show_info("scrcpy Launched", f"scrcpy launched for {success_count} device(s).")
            return True
        else:
            self._show_error("scrcpy Launch Failed", "Failed to launch scrcpy for any device.")
            return False

    def launch_scrcpy_single_device(self, device_serial: str) -> bool:
        """為單個設備啟動scrcpy"""
        try:
            # 檢查scrcpy是否可用
            if not self._check_scrcpy_available():
                return False

            device_info = self._get_device_info(device_serial)
            device_name = device_info.device_model if device_info else device_serial

            self._log_console(f"🖥️ Launching scrcpy for {device_name} ({device_serial})...")

            # 構建scrcpy命令
            cmd = f"scrcpy -s {device_serial}"

            # 在後台啟動scrcpy
            def launch_scrcpy_thread():
                try:
                    process = subprocess.Popen(cmd.split(),
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)

                    self._log_console(f"✅ scrcpy launched for {device_name}")
                    self.operation_completed_signal.emit("scrcpy", device_serial, True, "scrcpy launched")

                except Exception as e:
                    self._log_console(f"❌ Failed to launch scrcpy for {device_name}: {str(e)}")
                    self.operation_completed_signal.emit("scrcpy", device_serial, False, str(e))

            threading.Thread(target=launch_scrcpy_thread, daemon=True).start()
            return True

        except Exception as e:
            self._log_console(f"❌ Error launching scrcpy for device {device_serial}: {str(e)}")
            self.operation_completed_signal.emit("scrcpy", device_serial, False, str(e))
            return False

    def launch_ui_inspector(self, device_serials: List[str] = None) -> bool:
        """啟動UI檢查器"""
        if device_serials is None:
            device_serials = self._get_selected_device_serials()

        if not device_serials:
            self._show_warning("No Device Selected", "Please select at least one device to launch UI Inspector.")
            return False

        success_count = 0
        for serial in device_serials:
            if self.launch_ui_inspector_for_device(serial):
                success_count += 1

        if success_count > 0:
            self._show_info("UI Inspector", f"UI Inspector launched for {success_count} device(s).")
            return True
        else:
            self._show_error("UI Inspector Failed", "Failed to launch UI Inspector for any device.")
            return False

    def launch_ui_inspector_for_device(self, device_serial: str) -> bool:
        """為單個設備啟動UI檢查器"""
        try:
            device_info = self._get_device_info(device_serial)
            device_name = device_info.device_model if device_info else device_serial

            self._log_console(f"🔍 Launching UI Inspector for {device_name} ({device_serial})...")

            # 導入並創建UI檢查器對話框
            from lazy_blacktea_pyqt import UIInspectorDialog

            dialog = UIInspectorDialog(self.parent_window, device_serial, device_name)
            dialog.show()

            self._log_console(f"✅ UI Inspector launched for {device_name}")
            self.operation_completed_signal.emit("ui_inspector", device_serial, True, "UI Inspector launched")
            return True

        except Exception as e:
            self._log_console(f"❌ Error launching UI Inspector for device {device_serial}: {str(e)}")
            self.operation_completed_signal.emit("ui_inspector", device_serial, False, str(e))
            return False

    # ===== 狀態管理和輔助方法 =====

    def get_device_operation_status(self, device_serial: str) -> str:
        """獲取設備操作狀態"""
        if device_serial in self.device_recordings:
            return "recording"
        elif device_serial in self.device_operations:
            return self.device_operations[device_serial]
        else:
            return "idle"

    def get_device_recording_status(self, device_serial: str) -> str:
        """獲取設備錄製狀態"""
        if device_serial in self.device_recordings:
            recording_info = self.device_recordings[device_serial]
            elapsed = time.time() - recording_info['start_time']
            remaining = max(0, recording_info['duration'] - elapsed)
            return f"Recording ({remaining:.0f}s remaining)"
        return ""

    def show_recording_warning(self, device_serial: str):
        """顯示錄製警告"""
        device_info = self._get_device_info(device_serial)
        device_name = device_info.device_model if device_info else device_serial

        self._show_warning(
            "Device Recording",
            f"Device {device_name} ({device_serial}) is currently recording.\n"
            "Some operations may be unavailable during recording."
        )

    # ===== 私有輔助方法 =====

    def _get_selected_device_serials(self) -> List[str]:
        """獲取選中的設備序列號列表"""
        if self.parent_window and hasattr(self.parent_window, 'get_checked_devices'):
            devices = self.parent_window.get_checked_devices()
            return [device.device_serial_num for device in devices]
        return []

    def _get_devices_by_serials(self, serials: List[str]) -> List[adb_models.DeviceInfo]:
        """根據序列號獲取設備信息列表"""
        if self.parent_window and hasattr(self.parent_window, 'device_dict'):
            devices = []
            for serial in serials:
                if serial in self.parent_window.device_dict:
                    devices.append(self.parent_window.device_dict[serial])
            return devices
        return []

    def _get_device_info(self, device_serial: str) -> Optional[adb_models.DeviceInfo]:
        """獲取設備信息"""
        if self.parent_window and hasattr(self.parent_window, 'device_dict'):
            return self.parent_window.device_dict.get(device_serial)
        return None

    def _get_output_path(self) -> str:
        """獲取輸出路徑"""
        if self.parent_window and hasattr(self.parent_window, 'get_primary_output_path'):
            path = self.parent_window.get_primary_output_path()
            if path:
                return path

        # 如果上述都未提供路徑，最後回退到檔案對話框
        directory = QFileDialog.getExistingDirectory(
            self.parent_window,
            "Select Output Directory"
        )
        if directory:
            normalized = common.make_gen_dir_path(directory)
            if self.parent_window and hasattr(self.parent_window, 'output_path_edit'):
                self.parent_window.output_path_edit.setText(normalized)
                self.parent_window.previous_output_path_value = normalized
            return normalized
        return ''

    def _check_scrcpy_available(self) -> bool:
        """檢查scrcpy是否可用"""
        try:
            result = subprocess.run(['scrcpy', '--version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            if hasattr(self.parent_window, 'logging_manager'):
                self.parent_window.logging_manager.debug(f'Scrcpy not available: {e}')
            if self.parent_window and hasattr(self.parent_window, 'show_scrcpy_installation_guide'):
                self.parent_window.show_scrcpy_installation_guide()
            else:
                self._show_error("scrcpy Not Found",
                               "scrcpy is not installed or not in PATH.\n"
                               "Please install scrcpy to use this feature.")
            return False

    def _log_console(self, message: str):
        """記錄消息到控制台"""
        self.logger.info(message)
        if self.parent_window and hasattr(self.parent_window, 'write_to_console'):
            self.parent_window.write_to_console(message)

    def _show_info(self, title: str, message: str):
        """顯示信息對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_info'):
            self.parent_window.show_info(title, message)
        else:
            QMessageBox.information(self.parent_window, title, message)

    def _show_warning(self, title: str, message: str):
        """顯示警告對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_warning'):
            self.parent_window.show_warning(title, message)
        else:
            QMessageBox.warning(self.parent_window, title, message)

    def _show_error(self, title: str, message: str):
        """顯示錯誤對話框"""
        if self.parent_window and hasattr(self.parent_window, 'show_error'):
            self.parent_window.show_error(title, message)
        else:
            QMessageBox.critical(self.parent_window, title, message)


# 工廠函數
def create_device_operations_manager(parent_window=None) -> DeviceOperationsManager:
    """創建設備操作管理器實例"""
    return DeviceOperationsManager(parent_window)
