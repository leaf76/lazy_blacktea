#!/usr/bin/env python3
"""
應用管理器 - 處理APK安裝、scrcpy鏡像和應用程式管理

這個模組負責：
1. APK檔案的安裝和管理
2. scrcpy應用程式的檢查和啟動
3. 應用程式進度追蹤和錯誤處理
4. 設備選擇和會話管理
5. 安裝指南和幫助功能
"""

import os
import threading
from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QProgressDialog

from utils import adb_models, adb_tools


class ScrcpyManager(QObject):
    """scrcpy鏡像管理器"""

    # 信號定義
    scrcpy_launch_signal = pyqtSignal(str, str)  # device_serial, device_model
    scrcpy_error_signal = pyqtSignal(str)  # error_message

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.scrcpy_available = False
        self.scrcpy_major_version = 2  # 預設版本

    def check_scrcpy_availability(self):
        """檢查scrcpy可用性和版本"""
        is_available, version_output = adb_tools.check_tool_availability('scrcpy')

        if is_available:
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.info(f'scrcpy is available: {version_output}')

            # 解析版本號碼
            self.scrcpy_major_version = self._parse_scrcpy_version(version_output)
            self.scrcpy_available = True

            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.info(f'Detected scrcpy major version: {self.scrcpy_major_version}')
        else:
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.warning('scrcpy is not available in system PATH')
            self.scrcpy_available = False

        return self.scrcpy_available

    def _parse_scrcpy_version(self, version_output: str) -> int:
        """解析scrcpy版本號碼"""
        try:
            if 'scrcpy' in version_output:
                version_line = version_output.split('\n')[0]
                version_str = version_line.split()[1]
                major_version = int(version_str.split('.')[0])
                return major_version
        except (IndexError, ValueError):
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.warning('Could not parse scrcpy version, assuming v2.x')

        return 2  # 預設版本

    def launch_scrcpy_for_device(self, device_serial: str):
        """為單一設備啟動scrcpy"""
        if not self.scrcpy_available:
            self.parent_window.show_scrcpy_installation_guide()
            return

        if device_serial in self.parent_window.device_dict:
            device = self.parent_window.device_dict[device_serial]
            # 備份和恢復設備選擇
            original_selections = self._backup_device_selections()
            self._select_only_device(device_serial)

            # 啟動scrcpy
            self.launch_scrcpy_for_selected_devices()

            # 恢復原始選擇
            self._restore_device_selections(original_selections)
        else:
            self.parent_window.show_error('Error', f'Device {device_serial} not found.')

    def launch_scrcpy_for_selected_devices(self):
        """為選中的設備啟動scrcpy"""
        if not self.scrcpy_available:
            self.parent_window.show_scrcpy_installation_guide()
            return

        devices = self.parent_window.get_checked_devices()
        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        selected_device = self._select_device_for_mirroring(devices)
        if not selected_device:
            return

        self._launch_scrcpy_process(selected_device)

    def _select_device_for_mirroring(self, devices: List[adb_models.DeviceInfo]) -> Optional[adb_models.DeviceInfo]:
        """選擇要鏡像的設備"""
        if len(devices) == 1:
            return devices[0]

        # 多設備選擇對話框
        device_choices = [f"{d.device_model} ({d.device_serial_num})" for d in devices]
        choice, ok = QInputDialog.getItem(
            self.parent_window,
            'Select Device for Mirroring',
            'scrcpy can only mirror one device at a time.\nPlease select which device to mirror:',
            device_choices,
            0,
            False
        )

        if not ok:
            return None

        selected_index = device_choices.index(choice)
        return devices[selected_index]

    def _launch_scrcpy_process(self, device: adb_models.DeviceInfo):
        """啟動scrcpy進程"""
        serial = device.device_serial_num
        device_model = device.device_model

        if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
            self.parent_window.logger.info(f'Launching scrcpy for device: {device_model} ({serial})')

        self.parent_window.show_info(
            'scrcpy',
            f'Launching device mirroring for:\n{device_model} ({serial})\n\nscrcpy window will open shortly...'
        )

        def scrcpy_wrapper():
            try:
                # 根據版本使用不同的參數
                if self.scrcpy_major_version >= 3:
                    # scrcpy v3.x+ 使用新的audio參數
                    cmd_args = [
                        'scrcpy',
                        '--audio-source=playback',
                        '--audio-dup',
                        '--stay-awake',
                        '--turn-screen-off',
                        '--disable-screensaver',
                        '-s', serial
                    ]
                else:
                    # scrcpy v2.x 使用舊的參數
                    cmd_args = [
                        'scrcpy',
                        '--stay-awake',
                        '--turn-screen-off',
                        '--disable-screensaver',
                        '-s', serial
                    ]

                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.info(f'Executing scrcpy with args: {" ".join(cmd_args)}')

                # 啟動scrcpy進程
                import subprocess
                if os.name == 'nt':  # Windows
                    subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:  # Unix/Linux/macOS
                    subprocess.Popen(cmd_args)

                QTimer.singleShot(0, lambda: self.scrcpy_launch_signal.emit(serial, device_model))

            except Exception as e:
                error_msg = f'Failed to launch scrcpy: {str(e)}'
                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.error(error_msg)
                QTimer.singleShot(0, lambda: self.scrcpy_error_signal.emit(error_msg))

        # 在背景執行緒中啟動
        threading.Thread(target=scrcpy_wrapper, daemon=True).start()

    def _backup_device_selections(self) -> Dict[str, bool]:
        """備份目前的設備選擇"""
        selections = {}
        if hasattr(self.parent_window, 'check_devices'):
            for serial, checkbox in self.parent_window.check_devices.items():
                selections[serial] = checkbox.isChecked()
        return selections

    def _restore_device_selections(self, selections: Dict[str, bool]):
        """恢復設備選擇"""
        if hasattr(self.parent_window, 'check_devices'):
            for serial, checkbox in self.parent_window.check_devices.items():
                if serial in selections:
                    checkbox.setChecked(selections[serial])

    def _select_only_device(self, device_serial: str):
        """只選擇指定的設備"""
        if hasattr(self.parent_window, 'select_only_device'):
            self.parent_window.select_only_device(device_serial)


class ApkInstallationManager(QObject):
    """APK安裝管理器"""

    # 信號定義
    installation_progress_signal = pyqtSignal(str, int, int)  # message, current, total
    installation_completed_signal = pyqtSignal(int, int, str)  # successful, failed, apk_name
    installation_error_signal = pyqtSignal(str)  # error_message

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.progress_dialog = None

    def install_apk_dialog(self):
        """顯示APK選擇對話框並開始安裝"""
        apk_file, _ = QFileDialog.getOpenFileName(
            self.parent_window,
            'Select APK File',
            '',
            'APK Files (*.apk)'
        )

        if apk_file:
            devices = self.parent_window.get_checked_devices()
            if not devices:
                self.parent_window.show_error('Error', 'No devices selected.')
                return

            apk_name = os.path.basename(apk_file)
            # Use the signal-based installation method
            self.install_apk_to_devices(devices, apk_file, apk_name)

    def install_apk_to_devices(self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str):
        """安裝APK到指定設備"""
        # 創建進度對話框
        self.progress_dialog = QProgressDialog(
            f"🚀 Installing {apk_name}...\n\nPreparing installation...",
            "Cancel",
            0, len(devices),
            self.parent_window
        )
        self.progress_dialog.setWindowTitle("📦 APK Installation Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)

        # 設置進度條樣式
        self.progress_dialog.setStyleSheet("""
            QProgressDialog {
                font-size: 12px;
                min-width: 400px;
                min-height: 150px;
            }
            QProgressBar {
                border: 2px solid #3498db;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)

        self.progress_dialog.show()

        def install_with_progress():
            try:
                self._install_apk_with_progress(devices, apk_file, apk_name)
            except Exception as e:
                error_msg = f'APK installation failed: {str(e)}'
                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.error(error_msg)
                self.installation_error_signal.emit(error_msg)
                QTimer.singleShot(0, self._close_progress_dialog)

        # 在背景執行緒中運行
        threading.Thread(target=install_with_progress, daemon=True).start()

        if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
            self.parent_window.logger.info(f'Installing APK {apk_file} to {len(devices)} devices')

    def _close_progress_dialog(self):
        """關閉進度對話框"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

    def _update_progress(self, message: str, current: int, total: int):
        """更新進度對話框"""
        if self.progress_dialog:
            def update_ui():
                if self.progress_dialog:  # 再次檢查，防止對話框已關閉
                    self.progress_dialog.setLabelText(message)
                    self.progress_dialog.setValue(current)
                    # total 參數用於進度對話框的最大值設置，已在初始化時設定
            QTimer.singleShot(0, update_ui)

    def _install_apk_with_progress(self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str):
        """帶進度的APK安裝"""
        total_devices = len(devices)
        successful_installs = 0
        failed_installs = 0

        for index, device in enumerate(devices, 1):
            try:
                # 檢查是否取消
                if self.progress_dialog and self.progress_dialog.wasCanceled():
                    break

                # 更新進度對話框
                progress_msg = (
                    f'🚀 Installing {apk_name}\n'
                    f'Device {index}/{total_devices}\n\n'
                    f'📱 {device.device_model}\n'
                    f'🔧 {device.device_serial_num}\n\n'
                    f'⏱️ Please wait...'
                )

                self._update_progress(progress_msg, index-1, total_devices)

                # 也發送原有信號（保持向後兼容）
                self.installation_progress_signal.emit(progress_msg, index-1, total_devices)

                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.info(
                        f'Installing APK on device {index}/{total_devices}: '
                        f'{device.device_model} ({device.device_serial_num})'
                    )

                # 執行安裝
                result = adb_tools.install_the_apk([device.device_serial_num], apk_file)

                # 檢查安裝結果 (install_the_apk 返回嵌套列表 [['Performing Streamed Install', 'Success']])
                if result and isinstance(result, list) and len(result) > 0:
                    # 取第一個設備的結果
                    device_result = result[0]
                    if isinstance(device_result, list) and len(device_result) > 0:
                        # 檢查是否包含 'Success'
                        success_found = any('Success' in str(line) for line in device_result)
                        if success_found:
                            successful_installs += 1
                            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                                self.parent_window.logger.info(
                                    f'✅ APK installation successful on {device.device_model}'
                                )
                        else:
                            failed_installs += 1
                            error_msg = ' | '.join(str(line) for line in device_result)
                            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                                self.parent_window.logger.warning(
                                    f'❌ APK installation failed on {device.device_model}: {error_msg}'
                                )
                    else:
                        failed_installs += 1
                        if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                            self.parent_window.logger.warning(
                                f'❌ APK installation failed on {device.device_model}: Invalid result format'
                            )
                else:
                    failed_installs += 1
                    if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                        self.parent_window.logger.warning(
                            f'❌ APK installation failed on {device.device_model}: No result returned'
                        )

            except Exception as device_error:
                failed_installs += 1
                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.error(
                        f'Exception during APK installation on {device.device_model}: {device_error}'
                    )

        # 顯示完成狀態
        if self.progress_dialog:
            completion_msg = (
                f'✅ Installation Complete!\n\n'
                f'📦 APK: {apk_name}\n'
                f'✅ Successful: {successful_installs}\n'
                f'❌ Failed: {failed_installs}\n'
                f'📊 Total: {total_devices}'
            )
            self._update_progress(completion_msg, total_devices, total_devices)

            # 延遲關閉對話框
            QTimer.singleShot(2000, self._close_progress_dialog)

        # 發送完成信號
        self.installation_completed_signal.emit(successful_installs, failed_installs, apk_name)


class AppManagementManager(QObject):
    """應用程式管理總管理器"""

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window

        # 初始化子管理器
        self.scrcpy_manager = ScrcpyManager(parent_window)
        self.apk_manager = ApkInstallationManager(parent_window)

        # 連接信號
        self._connect_signals()

    def _connect_signals(self):
        """連接所有信號"""
        # scrcpy信號
        if hasattr(self.parent_window, '_handle_scrcpy_launch'):
            self.scrcpy_manager.scrcpy_launch_signal.connect(self.parent_window._handle_scrcpy_launch)

        if hasattr(self.parent_window, '_handle_scrcpy_error'):
            self.scrcpy_manager.scrcpy_error_signal.connect(self.parent_window._handle_scrcpy_error)

        # APK安裝信號 (使用 QueuedConnection 確保跨線程安全)
        if hasattr(self.parent_window, '_handle_installation_progress'):
            self.apk_manager.installation_progress_signal.connect(
                self.parent_window._handle_installation_progress, Qt.ConnectionType.QueuedConnection)

        if hasattr(self.parent_window, '_handle_installation_completed'):
            self.apk_manager.installation_completed_signal.connect(
                self.parent_window._handle_installation_completed, Qt.ConnectionType.QueuedConnection)

        if hasattr(self.parent_window, '_handle_installation_error'):
            self.apk_manager.installation_error_signal.connect(
                self.parent_window._handle_installation_error, Qt.ConnectionType.QueuedConnection)

    def initialize(self):
        """初始化應用程式管理器"""
        # 檢查scrcpy可用性
        self.scrcpy_manager.check_scrcpy_availability()

    # scrcpy相關方法
    def check_scrcpy_available(self) -> bool:
        """檢查scrcpy是否可用"""
        return self.scrcpy_manager.check_scrcpy_availability()

    def launch_scrcpy_for_device(self, device_serial: str):
        """為指定設備啟動scrcpy"""
        self.scrcpy_manager.launch_scrcpy_for_device(device_serial)

    def launch_scrcpy_for_selected_devices(self):
        """為選中設備啟動scrcpy"""
        self.scrcpy_manager.launch_scrcpy_for_selected_devices()

    # APK安裝相關方法
    def install_apk_dialog(self):
        """顯示APK安裝對話框"""
        self.apk_manager.install_apk_dialog()

    def install_apk_to_devices(self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str):
        """安裝APK到設備"""
        self.apk_manager.install_apk_to_devices(devices, apk_file, apk_name)

    # 屬性訪問器
    @property
    def scrcpy_available(self) -> bool:
        """scrcpy是否可用"""
        return self.scrcpy_manager.scrcpy_available

    @property
    def scrcpy_major_version(self) -> int:
        """scrcpy主版本號"""
        return self.scrcpy_manager.scrcpy_major_version