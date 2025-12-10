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
import shlex
import threading
from dataclasses import dataclass
from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QInputDialog

from utils import adb_models, adb_tools, adb_commands
from config.config_manager import ScrcpySettings


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

    def launch_scrcpy_for_selected_devices(self) -> None:
        """Launch scrcpy for selected devices."""
        if not self.scrcpy_available:
            self.parent_window.show_scrcpy_installation_guide()
            return

        devices = self.parent_window.get_checked_devices()
        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        # Single device - launch directly
        if len(devices) == 1:
            self._launch_scrcpy_process(devices[0])
            return

        # Multiple devices - ask user what to do
        selected_devices = self._select_devices_for_mirroring(devices)
        if not selected_devices:
            return

        for device in selected_devices:
            self._launch_scrcpy_process(device)

    def _select_devices_for_mirroring(
        self, devices: List[adb_models.DeviceInfo]
    ) -> List[adb_models.DeviceInfo]:
        """Show dialog for selecting which devices to mirror."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QCheckBox, QPushButton, QScrollArea, QWidget
        )

        dialog = QDialog(self.parent_window)
        dialog.setWindowTitle('Select Devices for Mirroring')
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel(
            f'{len(devices)} devices selected.\n'
            'Choose which devices to open scrcpy windows for:'
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Scrollable device list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(6)

        checkboxes: List[tuple[QCheckBox, adb_models.DeviceInfo]] = []
        for device in devices:
            cb = QCheckBox(f'{device.device_model} ({device.device_serial_num})')
            cb.setChecked(True)
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, device))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Select all / none buttons
        select_layout = QHBoxLayout()
        def set_all_checked(checked: bool) -> None:
            for cb, _ in checkboxes:
                cb.setChecked(checked)

        select_all_btn = QPushButton('Select All')
        select_all_btn.clicked.connect(lambda: set_all_checked(True))
        select_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton('Select None')
        select_none_btn.clicked.connect(lambda: set_all_checked(False))
        select_layout.addWidget(select_none_btn)
        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Note about multiple windows
        note = QLabel(
            'Note: Each selected device will open a separate scrcpy window.'
        )
        note.setStyleSheet('color: #888; font-size: 11px;')
        note.setWordWrap(True)
        layout.addWidget(note)

        # Dialog buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        launch_btn = QPushButton('Launch scrcpy')
        launch_btn.setDefault(True)
        launch_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(launch_btn)

        layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []

        return [device for cb, device in checkboxes if cb.isChecked()]

    def _launch_scrcpy_process(self, device: adb_models.DeviceInfo) -> None:
        """Launch scrcpy process for a single device."""
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
                cmd_args = self._build_scrcpy_command(serial)

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

    def _get_scrcpy_settings(self) -> ScrcpySettings:
        """Safely fetch scrcpy settings from the config manager."""
        config_manager = getattr(self.parent_window, 'config_manager', None)
        if not config_manager:
            return ScrcpySettings()

        try:
            settings = config_manager.get_scrcpy_settings()
        except Exception as exc:  # pragma: no cover - defensive
            if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                self.parent_window.logger.warning(f'Failed to load scrcpy settings, using defaults: {exc}')
            return ScrcpySettings()

        if isinstance(settings, ScrcpySettings):
            return settings

        # Handle legacy dictionaries for safety
        if isinstance(settings, dict):  # pragma: no cover - legacy safeguard
            return ScrcpySettings(**settings)

        return ScrcpySettings()

    def _build_scrcpy_command(self, serial: str) -> List[str]:
        """Construct the scrcpy command arguments using current settings."""
        settings = self._get_scrcpy_settings()

        cmd_args: List[str] = ['scrcpy']

        if settings.enable_audio_playback and self.scrcpy_major_version >= 3:
            cmd_args.extend(['--audio-source=playback', '--audio-dup'])

        if settings.stay_awake:
            cmd_args.append('--stay-awake')

        if settings.turn_screen_off:
            cmd_args.append('--turn-screen-off')

        if settings.disable_screensaver:
            cmd_args.append('--disable-screensaver')

        bitrate = settings.bitrate.strip()
        if bitrate:
            cmd_args.append(f'--bit-rate={bitrate}')

        if settings.max_size > 0:
            cmd_args.append(f'--max-size={settings.max_size}')

        extra_args = settings.extra_args.strip()
        if extra_args:
            cmd_args.extend(token for token in shlex.split(extra_args) if token)

        cmd_args.extend(['-s', serial])

        return cmd_args

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


@dataclass
class InstallationProgressState:
    mode: str = 'idle'
    current: int = 0
    total: int = 0
    message: str = ''


class ApkInstallationManager(QObject):
    """APK安裝管理器"""

    # 信號定義
    installation_progress_signal = pyqtSignal(str, int, int)  # message, current, total
    installation_completed_signal = pyqtSignal(int, int, str)  # successful, failed, apk_name
    installation_error_signal = pyqtSignal(str)  # error_message

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._apk_cancelled = False
        self._installation_in_progress = False
        self._installation_progress_state = InstallationProgressState()

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
        # 安裝前確認：顯示將執行的 adb 指令與裝置數
        if not devices:
            self.parent_window.show_error('Error', 'No devices selected.')
            return

        try:
            first_serial = devices[0].device_serial_num
            preview_cmd = adb_commands.cmd_adb_install(first_serial, apk_file)
            message = (
                f"You are about to install:\n\n"
                f"  APK: {apk_name}\n"
                f"  Devices: {len(devices)}\n\n"
                f"Command preview (first device):\n"
                f"{preview_cmd}\n\n"
                f"Proceed?"
            )
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.parent_window,
                'Confirm APK Install',
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        except Exception:
            # 若預覽產生失敗，依舊允許安裝，僅略過確認
            pass

        # 將預覽指令輸出到 Console，便於追蹤
        try:
            if hasattr(self.parent_window, 'write_to_console'):
                self.parent_window.write_to_console(f"🚀 Install command: {preview_cmd}")
                if len(devices) > 1:
                    self.parent_window.write_to_console(
                        f"… and {len(devices)-1} more device(s) with respective serials"
                    )
        except Exception:
            pass

        total_devices = len(devices)
        self._installation_in_progress = True
        self._apk_cancelled = False

        preparing_message = (
            f"🚀 Installing {apk_name}...\n"
            f"Preparing installation..."
        )
        self._update_progress(preparing_message, current=0, total=total_devices, mode='busy')
        self.installation_progress_signal.emit(preparing_message, 0, total_devices)

        def install_with_progress():
            try:
                self._install_apk_with_progress(devices, apk_file, apk_name)
            except Exception as e:
                error_msg = f'APK installation failed: {str(e)}'
                if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
                    self.parent_window.logger.error(error_msg)
                self.installation_error_signal.emit(error_msg)
                self._update_progress(
                    f'❌ APK installation failed: {str(e)}',
                    current=self._installation_progress_state.current,
                    total=self._installation_progress_state.total,
                    mode='failed',
                )
                QTimer.singleShot(1500, self._ensure_installation_reset)

        # 在背景執行緒中運行
        threading.Thread(target=install_with_progress, daemon=True).start()

        if hasattr(self.parent_window, 'logger') and self.parent_window.logger:
            self.parent_window.logger.info(f'Installing APK {apk_file} to {len(devices)} devices')

    def _update_progress(
        self,
        message: str,
        current: int,
        total: int,
        *,
        mode: Optional[str] = None,
    ) -> None:
        """更新按鈕進度狀態"""
        inferred_mode = mode or ('progress' if total and total > 0 else 'busy')
        safe_current = max(0, int(current))
        safe_total = max(0, int(total))
        self._installation_progress_state = InstallationProgressState(
            mode=inferred_mode,
            current=safe_current,
            total=safe_total,
            message=message,
        )

    def _ensure_installation_reset(self) -> None:
        if self._installation_in_progress or self._installation_progress_state.mode != 'idle':
            self._installation_in_progress = False
            self._apk_cancelled = False
            self._installation_progress_state = InstallationProgressState()
            try:
                refresh_cb = getattr(self.parent_window, 'on_apk_install_progress_reset', None)
                if callable(refresh_cb):
                    refresh_cb()
            except Exception:
                pass

    def is_installation_in_progress(self) -> bool:
        return self._installation_in_progress

    def get_installation_progress_state(self) -> InstallationProgressState:
        return self._installation_progress_state

    def _install_apk_with_progress(self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str):
        """帶進度的APK安裝"""
        total_devices = len(devices)
        successful_installs = 0
        failed_installs = 0

        for index, device in enumerate(devices, 1):
            try:
                # 檢查是否取消
                if self._apk_cancelled:
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

                # 在 Console 顯示即將執行的指令
                try:
                    preview_cmd = adb_commands.cmd_adb_install(device.device_serial_num, apk_file)
                    if hasattr(self.parent_window, 'write_to_console'):
                        self.parent_window.write_to_console(f"🚀 Executing: {preview_cmd}")
                except Exception:
                    pass

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
        if self._apk_cancelled:
            cancel_msg = '⏹️ APK installation cancelled by user'
            self._update_progress(
                cancel_msg,
                current=successful_installs,
                total=total_devices,
                mode='cancelled',
            )
            self.installation_progress_signal.emit(cancel_msg, successful_installs, total_devices)
        else:
            completion_msg = (
                f'✅ Installation Complete!\n\n'
                f'📦 APK: {apk_name}\n'
                f'✅ Successful: {successful_installs}\n'
                f'❌ Failed: {failed_installs}\n'
                f'📊 Total: {total_devices}'
            )
            self._update_progress(
                completion_msg,
                current=total_devices,
                total=total_devices,
                mode='completed',
            )
            self.installation_progress_signal.emit(completion_msg, total_devices, total_devices)
        QTimer.singleShot(1500, self._ensure_installation_reset)

        # 發送完成信號
        self.installation_completed_signal.emit(successful_installs, failed_installs, apk_name)

    def cancel_installation(self):
        """使用者取消安裝時的 UI 與狀態更新"""
        if not self._installation_in_progress:
            return
        self._apk_cancelled = True
        cancel_msg = 'Cancelling APK installation...'
        self._update_progress(
            cancel_msg,
            current=self._installation_progress_state.current,
            total=self._installation_progress_state.total,
            mode='cancelling',
        )
        self.installation_progress_signal.emit(
            cancel_msg,
            self._installation_progress_state.current,
            self._installation_progress_state.total,
        )


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

    def cancel_apk_installation(self):
        """取消 APK 安裝作業"""
        self.apk_manager.cancel_installation()

    # 屬性訪問器
    @property
    def scrcpy_available(self) -> bool:
        """scrcpy是否可用"""
        return self.scrcpy_manager.scrcpy_available

    @property
    def scrcpy_major_version(self) -> int:
        """scrcpy主版本號"""
        return self.scrcpy_manager.scrcpy_major_version
