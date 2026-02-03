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
import re
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QFileDialog, QInputDialog

from utils import adb_models, adb_tools, adb_commands
from config.config_manager import ScrcpySettings
from ui.signal_payloads import DeviceOperationEvent, OperationStatus, OperationType


class ScrcpyManager(QObject):
    """scrcpy鏡像管理器"""

    # 信號定義
    scrcpy_launch_signal = pyqtSignal(str, str)  # device_serial, device_model
    scrcpy_error_signal = pyqtSignal(str)  # error_message
    operation_started_signal = pyqtSignal(object)  # DeviceOperationEvent
    operation_finished_signal = pyqtSignal(object)  # DeviceOperationEvent

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.scrcpy_available = False
        self.scrcpy_major_version = 2  # 預設版本

    def check_scrcpy_availability(self):
        """檢查scrcpy可用性和版本"""
        is_available, version_output = adb_tools.check_tool_availability("scrcpy")

        if is_available:
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.info(f"scrcpy is available: {version_output}")

            # 解析版本號碼
            self.scrcpy_major_version = self._parse_scrcpy_version(version_output)
            self.scrcpy_available = True

            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.info(
                    f"Detected scrcpy major version: {self.scrcpy_major_version}"
                )
        else:
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.warning(
                    "scrcpy is not available in system PATH"
                )
            self.scrcpy_available = False

        return self.scrcpy_available

    def _parse_scrcpy_version(self, version_output: str) -> int:
        """解析scrcpy版本號碼"""
        try:
            if "scrcpy" in version_output:
                version_line = version_output.split("\n")[0]
                version_str = version_line.split()[1]
                major_version = int(version_str.split(".")[0])
                return major_version
        except (IndexError, ValueError):
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.warning(
                    "Could not parse scrcpy version, assuming v2.x"
                )

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
            self.parent_window.show_error("Error", f"Device {device_serial} not found.")

    def launch_scrcpy_for_selected_devices(self) -> None:
        """Launch scrcpy for selected devices."""
        if not self.scrcpy_available:
            self.parent_window.show_scrcpy_installation_guide()
            return

        devices = self.parent_window.get_checked_devices()
        if not devices:
            self.parent_window.show_error("Error", "No devices selected.")
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
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QCheckBox,
            QPushButton,
            QScrollArea,
            QWidget,
        )

        dialog = QDialog(self.parent_window)
        dialog.setWindowTitle("Select Devices for Mirroring")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel(
            f"{len(devices)} devices selected.\n"
            "Choose which devices to open scrcpy windows for:"
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
            cb = QCheckBox(f"{device.device_model} ({device.device_serial_num})")
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

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: set_all_checked(True))
        select_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: set_all_checked(False))
        select_layout.addWidget(select_none_btn)
        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Note about multiple windows
        note = QLabel("Note: Each selected device will open a separate scrcpy window.")
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Dialog buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        launch_btn = QPushButton("Launch scrcpy")
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

        if hasattr(self.parent_window, "logger") and self.parent_window.logger:
            self.parent_window.logger.info(
                f"Launching scrcpy for device: {device_model} ({serial})"
            )

        from ui.signal_payloads import (
            DeviceOperationEvent,
            OperationType,
            OperationStatus,
        )

        event = DeviceOperationEvent.create(
            device_serial=serial,
            operation_type=OperationType.SCRCPY,
            device_name=device_model or serial,
            message="Launching scrcpy...",
        )
        self.operation_started_signal.emit(event)

        self.parent_window.show_info(
            "scrcpy",
            f"Launching device mirroring for:\n{device_model} ({serial})\n\nscrcpy window will open shortly...",
        )

        def scrcpy_wrapper():
            try:
                cmd_args = self._build_scrcpy_command(serial)

                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.info(
                        f"Executing scrcpy with args: {' '.join(cmd_args)}"
                    )

                import subprocess

                if os.name == "nt":  # Windows
                    subprocess.Popen(
                        cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:  # Unix/Linux/macOS
                    subprocess.Popen(cmd_args)

                completed_event = event.with_status(
                    OperationStatus.COMPLETED,
                    message="scrcpy launched",
                )
                self.scrcpy_launch_signal.emit(serial, device_model)
                self.operation_finished_signal.emit(completed_event)

            except Exception as e:
                error_msg = f"Failed to launch scrcpy: {str(e)}"
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(error_msg)

                failed_event = event.with_status(
                    OperationStatus.FAILED,
                    error_message=str(e),
                )
                self.scrcpy_error_signal.emit(error_msg)
                self.operation_finished_signal.emit(failed_event)

        threading.Thread(target=scrcpy_wrapper, daemon=True).start()

    def _get_scrcpy_settings(self) -> ScrcpySettings:
        """Safely fetch scrcpy settings from the config manager."""
        config_manager = getattr(self.parent_window, "config_manager", None)
        if not config_manager:
            return ScrcpySettings()

        try:
            settings = config_manager.get_scrcpy_settings()
        except Exception as exc:  # pragma: no cover - defensive
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.warning(
                    f"Failed to load scrcpy settings, using defaults: {exc}"
                )
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

        cmd_args: List[str] = ["scrcpy"]

        if settings.enable_audio_playback and self.scrcpy_major_version >= 3:
            cmd_args.extend(["--audio-source=playback", "--audio-dup"])

        if settings.stay_awake:
            cmd_args.append("--stay-awake")

        if settings.turn_screen_off:
            cmd_args.append("--turn-screen-off")

        if settings.disable_screensaver:
            cmd_args.append("--disable-screensaver")

        bitrate = settings.bitrate.strip()
        if bitrate:
            cmd_args.append(f"--bit-rate={bitrate}")

        if settings.max_size > 0:
            cmd_args.append(f"--max-size={settings.max_size}")

        extra_args = settings.extra_args.strip()
        if extra_args:
            cmd_args.extend(token for token in shlex.split(extra_args) if token)

        cmd_args.extend(["-s", serial])

        return cmd_args

    def _backup_device_selections(self) -> Dict[str, bool]:
        """備份目前的設備選擇"""
        selections = {}
        if hasattr(self.parent_window, "check_devices"):
            for serial, checkbox in self.parent_window.check_devices.items():
                selections[serial] = checkbox.isChecked()
        return selections

    def _restore_device_selections(self, selections: Dict[str, bool]):
        """恢復設備選擇"""
        if hasattr(self.parent_window, "check_devices"):
            for serial, checkbox in self.parent_window.check_devices.items():
                if serial in selections:
                    checkbox.setChecked(selections[serial])

    def _select_only_device(self, device_serial: str):
        """只選擇指定的設備"""
        if hasattr(self.parent_window, "select_only_device"):
            self.parent_window.select_only_device(device_serial)


@dataclass
class InstallationProgressState:
    mode: str = "idle"
    current: int = 0
    total: int = 0
    message: str = ""


class ApkInstallationManager(QObject):
    """APK安裝管理器"""

    # 信號定義
    installation_progress_signal = pyqtSignal(str, int, int)  # message, current, total
    installation_completed_signal = pyqtSignal(
        int, int, str
    )  # successful, failed, apk_name
    installation_error_signal = pyqtSignal(str)  # error_message
    operation_started_signal = pyqtSignal(object)  # DeviceOperationEvent
    operation_finished_signal = pyqtSignal(object)  # DeviceOperationEvent

    _PUSH_PERCENT_RE = re.compile(r"(\d{1,3})%")
    _PUSH_SPEED_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]i?B/s)")

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._apk_cancelled = False
        self._installation_in_progress = False
        self._installation_progress_state = InstallationProgressState()
        self._operation_events: Dict[str, DeviceOperationEvent] = {}
        self._active_processes: Dict[str, object] = {}
        self._process_lock = threading.Lock()

    @staticmethod
    def _parse_adb_push_progress(text: str) -> tuple[Optional[int], Optional[str]]:
        """Parse adb push output and return (percent, speed)."""
        percent: Optional[int] = None
        speed: Optional[str] = None

        if not text:
            return None, None

        percent_matches = ApkInstallationManager._PUSH_PERCENT_RE.findall(text)
        if percent_matches:
            try:
                percent_val = int(percent_matches[-1])
                percent = max(0, min(100, percent_val))
            except ValueError:
                percent = None

        speed_matches = ApkInstallationManager._PUSH_SPEED_RE.findall(text)
        if speed_matches:
            value, unit = speed_matches[-1]
            speed = f"{value} {unit.upper().replace('IB/S', 'iB/s').replace('B/S', 'B/s')}"
            speed = speed.replace("KIB/S", "KiB/s").replace("MIB/S", "MiB/s").replace("GIB/S", "GiB/s")
            speed = speed.replace("KB/S", "KB/s").replace("MB/S", "MB/s").replace("GB/S", "GB/s")

        if percent is None and "file pushed" in text.lower():
            percent = 100

        return percent, speed

    def _terminate_active_processes(self) -> None:
        with self._process_lock:
            processes = list(self._active_processes.values())
            self._active_processes = {}

        for proc in processes:
            try:
                poll = getattr(proc, "poll", None)
                if callable(poll) and poll() is not None:
                    continue
                terminate = getattr(proc, "terminate", None)
                if callable(terminate):
                    terminate()
            except Exception as exc:
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(
                        f"Failed to terminate installation process: {exc}"
                    )

    @staticmethod
    def _sanitize_remote_filename(filename: str) -> str:
        """Return a device-safe filename for /data/local/tmp."""
        name = filename.strip() or "app.apk"
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        if not name.lower().endswith(".apk"):
            name = f"{name}.apk"
        return name

    @staticmethod
    def _filter_pm_install_extra_args(extra_args: str) -> tuple[list[str], list[str]]:
        """Filter extra args into a safe subset supported by `pm install`.

        Returns (allowed_tokens, ignored_tokens).
        """
        raw = (extra_args or "").strip()
        if not raw:
            return [], []

        try:
            tokens = [tok for tok in shlex.split(raw) if tok]
        except Exception:
            return [], [raw]

        allowed: list[str] = []
        ignored: list[str] = []
        idx = 0
        while idx < len(tokens):
            token = tokens[idx]
            if token in {"--dont-kill", "--wait"}:
                allowed.append(token)
                idx += 1
                continue
            if token in {"--user", "--install-location", "-i"}:
                if idx + 1 < len(tokens):
                    allowed.extend([token, tokens[idx + 1]])
                    idx += 2
                    continue
                ignored.append(token)
                idx += 1
                continue

            ignored.append(token)
            idx += 1

        return allowed, ignored

    def _build_pm_install_args(self, remote_apk_path: str) -> list[str]:
        """Build `adb shell pm install ...` args based on persisted settings."""
        try:
            from config.config_manager import ConfigManager

            settings = ConfigManager().get_apk_install_settings()
        except Exception:
            class _F:
                replace_existing = True
                allow_downgrade = True
                grant_permissions = True
                allow_test_packages = False
                extra_args = ""

            settings = _F()

        parts: list[str] = ["shell", "pm", "install"]
        if getattr(settings, "allow_downgrade", True):
            parts.append("-d")
        if getattr(settings, "replace_existing", True):
            parts.append("-r")
        if getattr(settings, "grant_permissions", True):
            parts.append("-g")
        if getattr(settings, "allow_test_packages", False):
            parts.append("-t")

        extra_allowed, extra_ignored = self._filter_pm_install_extra_args(
            getattr(settings, "extra_args", "") or ""
        )
        if extra_ignored:
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.warning(
                    f"Ignoring unsupported pm install args: {extra_ignored}"
                )
            if hasattr(self.parent_window, "write_to_console"):
                try:
                    self.parent_window.write_to_console(
                        f"Warning: Ignoring unsupported pm install args: {', '.join(extra_ignored)}"
                    )
                except Exception as exc:
                    if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                        self.parent_window.logger.error(
                            f"Failed to write ignored args to console: {exc}"
                        )

        parts.extend(extra_allowed)
        parts.append(remote_apk_path)
        return parts

    def _run_adb_process(
        self,
        serial: str,
        adb_args: list[str],
        *,
        label: str,
        stream_output: bool = False,
        on_chunk: Optional[Callable[[str, str], None]] = None,
    ) -> tuple[int, str]:
        """Run an adb subprocess and return (returncode, combined_output)."""
        adb_cmd = adb_commands.get_adb_command()
        args = [adb_cmd, "-s", serial] + adb_args

        if hasattr(self.parent_window, "logger") and self.parent_window.logger:
            self.parent_window.logger.info(f"Running adb command ({label}): {args}")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        with self._process_lock:
            self._active_processes[serial] = proc

        output_chunks: list[str] = []

        try:
            if not stream_output:
                stdout, _ = proc.communicate()
                combined = stdout or ""
                output_chunks.append(combined)
                return proc.returncode or 0, combined

            if proc.stdout is None:
                stdout, _ = proc.communicate()
                combined = stdout or ""
                output_chunks.append(combined)
                return proc.returncode or 0, combined

            buffer = ""
            last_callback_at = 0.0
            while True:
                if self._apk_cancelled:
                    raise RuntimeError("Installation cancelled")

                chunk = proc.stdout.read(256)
                if chunk:
                    output_chunks.append(chunk)
                    buffer += chunk
                    if len(buffer) > 8192:
                        buffer = buffer[-8192:]
                    if on_chunk is not None:
                        now = time.monotonic()
                        if now - last_callback_at >= 0.1:
                            try:
                                on_chunk(chunk, buffer)
                            except Exception as exc:
                                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                                    self.parent_window.logger.error(
                                        f"Progress callback failed ({label}): {exc}"
                                    )
                            last_callback_at = now
                    continue

                if proc.poll() is not None:
                    break
                time.sleep(0.05)

            remaining = buffer
            if remaining and on_chunk is not None:
                try:
                    on_chunk("", remaining)
                except Exception as exc:
                    if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                        self.parent_window.logger.error(
                            f"Progress callback failed ({label}): {exc}"
                        )

            return proc.returncode or 0, "".join(output_chunks)
        finally:
            with self._process_lock:
                if self._active_processes.get(serial) is proc:
                    self._active_processes.pop(serial, None)

    def install_apk_dialog(self):
        """顯示APK選擇對話框並開始安裝"""
        apk_file, _ = QFileDialog.getOpenFileName(
            self.parent_window, "Select APK File", "", "APK Files (*.apk)"
        )

        if apk_file:
            devices = self.parent_window.get_checked_devices()
            if not devices:
                self.parent_window.show_error("Error", "No devices selected.")
                return

            apk_name = os.path.basename(apk_file)
            # Use the signal-based installation method
            self.install_apk_to_devices(devices, apk_file, apk_name)

    def install_apk_to_devices(
        self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str
    ):
        """安裝APK到指定設備"""
        # 安裝前確認：顯示將執行的 adb 指令與裝置數
        if not devices:
            self.parent_window.show_error("Error", "No devices selected.")
            return

        try:
            first_serial = devices[0].device_serial_num
            preview_cmd = ""
            if apk_file.lower().endswith(".apk"):
                adb_cmd = adb_commands.get_adb_command()
                remote_name = self._sanitize_remote_filename(os.path.basename(apk_file))
                remote_path = f"/data/local/tmp/<temp>_{remote_name}"
                pm_args = self._build_pm_install_args(remote_path)
                preview_cmd = (
                    f"{adb_cmd} -s {first_serial} push -p \"{apk_file}\" {remote_path}\n"
                    f"{adb_cmd} -s {first_serial} {' '.join(pm_args)}"
                )
            else:
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
                "Confirm APK Install",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        except Exception as exc:
            # If preview fails, still allow installation, but keep the confirmation.
            preview_cmd = "(preview unavailable)"
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.warning(
                    f"Failed to build install preview command: {exc}"
                )

        # 將預覽指令輸出到 Console，便於追蹤
        try:
            if hasattr(self.parent_window, "write_to_console"):
                self.parent_window.write_to_console(
                    f"Install command preview:\n{preview_cmd}"
                )
                if len(devices) > 1:
                    self.parent_window.write_to_console(
                        f"... and {len(devices) - 1} more device(s)"
                    )
        except Exception as exc:
            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                self.parent_window.logger.error(
                    f"Failed to write install preview to console: {exc}"
                )

        total_devices = len(devices)
        self._installation_in_progress = True
        self._apk_cancelled = False
        self._operation_events = {}
        with self._process_lock:
            self._active_processes = {}

        for device in devices:
            serial = device.device_serial_num
            try:
                event = DeviceOperationEvent.create(
                    device_serial=serial,
                    operation_type=OperationType.INSTALL_APK,
                    device_name=device.device_model or serial,
                    message=f"Queued to install {apk_name}",
                    can_cancel=False,
                )
                self._operation_events[serial] = event
                self.operation_started_signal.emit(event)
            except Exception as exc:
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(
                        f"Failed to register install operation for {serial}: {exc}"
                    )

        preparing_message = f"🚀 Installing {apk_name}...\nPreparing installation..."
        self._update_progress(
            preparing_message, current=0, total=total_devices, mode="busy"
        )
        self.installation_progress_signal.emit(preparing_message, 0, total_devices)

        def install_with_progress():
            try:
                self._install_apk_with_progress(devices, apk_file, apk_name)
            except Exception as e:
                error_msg = f"APK installation failed: {str(e)}"
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(error_msg)
                self.installation_error_signal.emit(error_msg)
                self._update_progress(
                    f"❌ APK installation failed: {str(e)}",
                    current=self._installation_progress_state.current,
                    total=self._installation_progress_state.total,
                    mode="failed",
                )
                QTimer.singleShot(1500, self._ensure_installation_reset)

        # 在背景執行緒中運行
        threading.Thread(target=install_with_progress, daemon=True).start()

        if hasattr(self.parent_window, "logger") and self.parent_window.logger:
            self.parent_window.logger.info(
                f"Installing APK {apk_file} to {len(devices)} devices"
            )

    def _update_progress(
        self,
        message: str,
        current: int,
        total: int,
        *,
        mode: Optional[str] = None,
    ) -> None:
        """更新按鈕進度狀態"""
        inferred_mode = mode or ("progress" if total and total > 0 else "busy")
        safe_current = max(0, int(current))
        safe_total = max(0, int(total))
        self._installation_progress_state = InstallationProgressState(
            mode=inferred_mode,
            current=safe_current,
            total=safe_total,
            message=message,
        )

    def _ensure_installation_reset(self) -> None:
        if (
            self._installation_in_progress
            or self._installation_progress_state.mode != "idle"
        ):
            self._installation_in_progress = False
            self._apk_cancelled = False
            self._installation_progress_state = InstallationProgressState()
            self._operation_events = {}
            with self._process_lock:
                self._active_processes = {}
            try:
                refresh_cb = getattr(
                    self.parent_window, "on_apk_install_progress_reset", None
                )
                if callable(refresh_cb):
                    refresh_cb()
            except Exception as exc:
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(
                        f"Failed to refresh APK install progress UI: {exc}"
                    )

    def is_installation_in_progress(self) -> bool:
        return self._installation_in_progress

    def get_installation_progress_state(self) -> InstallationProgressState:
        return self._installation_progress_state

    def _install_apk_with_progress(
        self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str
    ):
        """帶進度的APK安裝"""
        total_devices = len(devices)
        successful_installs = 0
        failed_installs = 0

        for index, device in enumerate(devices, 1):
            try:
                # 檢查是否取消
                if self._apk_cancelled:
                    break

                serial = device.device_serial_num
                event = self._operation_events.get(serial)
                if event is not None:
                    running_event = event.with_status(
                        OperationStatus.RUNNING,
                        message=f"Installing {apk_name} ({index}/{total_devices})",
                    )
                    self._operation_events[serial] = running_event
                    self.operation_finished_signal.emit(running_event)

                device_model = device.device_model or serial
                is_regular_apk = apk_file.lower().endswith(".apk")

                if is_regular_apk:
                    unique_id = uuid.uuid4().hex[:8]
                    remote_filename = self._sanitize_remote_filename(
                        os.path.basename(apk_file)
                    )
                    remote_path = (
                        f"/data/local/tmp/lazy_blacktea_{unique_id}_{remote_filename}"
                    )

                    last_percent: int = 0
                    last_speed: Optional[str] = None
                    last_reported_percent: int = -1
                    last_reported_speed: Optional[str] = None

                    def on_push_chunk(_chunk: str, buffered: str) -> None:
                        nonlocal last_percent
                        nonlocal last_speed
                        nonlocal last_reported_percent
                        nonlocal last_reported_speed

                        percent, speed = self._parse_adb_push_progress(buffered[-4096:])
                        if percent is not None:
                            last_percent = percent
                        if speed is not None:
                            last_speed = speed

                        should_report = (
                            last_percent != last_reported_percent
                            or last_speed != last_reported_speed
                        )
                        if not should_report:
                            return

                        msg = (
                            f"Pushing {apk_name} to {device_model} "
                            f"({index}/{total_devices}) - {last_percent}%"
                        )
                        if last_speed:
                            msg += f" @ {last_speed}"

                        self._update_progress(msg, last_percent, 100, mode="progress")
                        self.installation_progress_signal.emit(msg, last_percent, 100)

                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            progress_val = max(
                                0.0, min(1.0, float(last_percent) / 100.0)
                            )
                            updated = ev.with_status(
                                OperationStatus.RUNNING,
                                progress=progress_val,
                                message=msg,
                            )
                            self._operation_events[serial] = updated
                            self.operation_finished_signal.emit(updated)

                        last_reported_percent = last_percent
                        last_reported_speed = last_speed

                    if hasattr(self.parent_window, "write_to_console"):
                        try:
                            self.parent_window.write_to_console(
                                f"Running: adb -s {serial} push -p \"{apk_file}\" {remote_path}"
                            )
                        except Exception as exc:
                            if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                                self.parent_window.logger.error(
                                    f"Failed to write adb push command to console: {exc}"
                                )

                    push_rc, push_output = self._run_adb_process(
                        serial,
                        ["push", "-p", apk_file, remote_path],
                        label="push_apk",
                        stream_output=True,
                        on_chunk=on_push_chunk,
                    )
                    if self._apk_cancelled:
                        break

                    if push_rc != 0:
                        failed_installs += 1
                        error_msg = (push_output or "").strip() or "adb push failed"
                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            failed_event = ev.with_status(
                                OperationStatus.FAILED,
                                error_message=error_msg,
                            )
                            self._operation_events[serial] = failed_event
                            self.operation_finished_signal.emit(failed_event)
                        if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                            self.parent_window.logger.warning(
                                f"APK push failed on {device_model}: {error_msg}"
                            )
                        continue

                    install_msg = (
                        f"Installing {apk_name} on {device_model} "
                        f"({index}/{total_devices})"
                    )
                    self._update_progress(install_msg, 0, 0, mode="busy")
                    self.installation_progress_signal.emit(install_msg, 0, 0)

                    ev = self._operation_events.get(serial)
                    if ev is not None:
                        updated = ev.with_status(
                            OperationStatus.RUNNING, progress=None, message=install_msg
                        )
                        self._operation_events[serial] = updated
                        self.operation_finished_signal.emit(updated)

                    pm_args = self._build_pm_install_args(remote_path)
                    pm_rc, pm_output = self._run_adb_process(
                        serial,
                        pm_args,
                        label="pm_install",
                        stream_output=False,
                    )
                    if self._apk_cancelled:
                        break

                    rm_rc, rm_output = self._run_adb_process(
                        serial,
                        ["shell", "rm", remote_path],
                        label="cleanup_tmp_apk",
                        stream_output=False,
                    )
                    if rm_rc != 0 and hasattr(self.parent_window, "logger") and self.parent_window.logger:
                        self.parent_window.logger.warning(
                            f"Failed to remove remote APK: {rm_output}"
                        )

                    success_found = pm_rc == 0 and "Success" in (pm_output or "")
                    if success_found:
                        successful_installs += 1
                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            completed_event = ev.with_status(
                                OperationStatus.COMPLETED,
                                message=f"Installed {apk_name}",
                            )
                            self._operation_events[serial] = completed_event
                            self.operation_finished_signal.emit(completed_event)
                    else:
                        failed_installs += 1
                        error_msg = (pm_output or "").strip() or "pm install failed"
                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            failed_event = ev.with_status(
                                OperationStatus.FAILED,
                                error_message=error_msg,
                            )
                            self._operation_events[serial] = failed_event
                            self.operation_finished_signal.emit(failed_event)
                        if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                            self.parent_window.logger.warning(
                                f"APK install failed on {device_model}: {error_msg}"
                            )
                else:
                    # Fallback to legacy path for non-APK files (e.g., split bundles)
                    result = adb_tools.install_the_apk([serial], apk_file)
                    success_found = False
                    device_result = result[0] if isinstance(result, list) and result else []
                    if isinstance(device_result, list):
                        success_found = any("Success" in str(line) for line in device_result)
                    if success_found:
                        successful_installs += 1
                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            completed_event = ev.with_status(
                                OperationStatus.COMPLETED,
                                message=f"Installed {apk_name}",
                            )
                            self._operation_events[serial] = completed_event
                            self.operation_finished_signal.emit(completed_event)
                    else:
                        failed_installs += 1
                        error_msg = " | ".join(str(line) for line in device_result) if isinstance(device_result, list) else str(device_result)
                        ev = self._operation_events.get(serial)
                        if ev is not None:
                            failed_event = ev.with_status(
                                OperationStatus.FAILED,
                                error_message=error_msg,
                            )
                            self._operation_events[serial] = failed_event
                            self.operation_finished_signal.emit(failed_event)

            except Exception as device_error:
                if self._apk_cancelled:
                    break
                failed_installs += 1
                serial = getattr(device, "device_serial_num", None)
                if serial:
                    event = self._operation_events.get(serial)
                    if event is not None:
                        failed_event = event.with_status(
                            OperationStatus.FAILED,
                            error_message=str(device_error),
                        )
                        self._operation_events[serial] = failed_event
                        self.operation_finished_signal.emit(failed_event)
                if hasattr(self.parent_window, "logger") and self.parent_window.logger:
                    self.parent_window.logger.error(
                        f"Exception during APK installation on {device.device_model}: {device_error}"
                    )

        if self._apk_cancelled:
            for device in devices:
                serial = device.device_serial_num
                event = self._operation_events.get(serial)
                if event is not None and not event.is_terminal:
                    cancelled_event = event.with_status(
                        OperationStatus.CANCELLED,
                        message="Cancelled",
                    )
                    self._operation_events[serial] = cancelled_event
                    self.operation_finished_signal.emit(cancelled_event)

        # 顯示完成狀態
        if self._apk_cancelled:
            cancel_msg = "⏹️ APK installation cancelled by user"
            self._update_progress(
                cancel_msg,
                current=successful_installs,
                total=total_devices,
                mode="cancelled",
            )
            self.installation_progress_signal.emit(
                cancel_msg, successful_installs, total_devices
            )
        else:
            completion_msg = (
                f"✅ Installation Complete!\n\n"
                f"📦 APK: {apk_name}\n"
                f"✅ Successful: {successful_installs}\n"
                f"❌ Failed: {failed_installs}\n"
                f"📊 Total: {total_devices}"
            )
            self._update_progress(
                completion_msg,
                current=total_devices,
                total=total_devices,
                mode="completed",
            )
            self.installation_progress_signal.emit(
                completion_msg, total_devices, total_devices
            )
        QTimer.singleShot(1500, self._ensure_installation_reset)

        # 發送完成信號
        self.installation_completed_signal.emit(
            successful_installs, failed_installs, apk_name
        )

    def cancel_installation(self):
        """使用者取消安裝時的 UI 與狀態更新"""
        if not self._installation_in_progress:
            return
        self._apk_cancelled = True
        self._terminate_active_processes()
        cancel_msg = "Cancelling APK installation..."
        self._update_progress(
            cancel_msg,
            current=self._installation_progress_state.current,
            total=self._installation_progress_state.total,
            mode="cancelling",
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
        if hasattr(self.parent_window, "_handle_scrcpy_launch"):
            self.scrcpy_manager.scrcpy_launch_signal.connect(
                self.parent_window._handle_scrcpy_launch
            )

        if hasattr(self.parent_window, "_handle_scrcpy_error"):
            self.scrcpy_manager.scrcpy_error_signal.connect(
                self.parent_window._handle_scrcpy_error
            )

        if hasattr(self.parent_window, "_on_operation_started"):
            self.scrcpy_manager.operation_started_signal.connect(
                self.parent_window._on_operation_started,
                Qt.ConnectionType.QueuedConnection,
            )

        if hasattr(self.parent_window, "_on_operation_finished"):
            self.scrcpy_manager.operation_finished_signal.connect(
                self.parent_window._on_operation_finished,
                Qt.ConnectionType.QueuedConnection,
            )

        # APK安裝信號 (使用 QueuedConnection 確保跨線程安全)
        if hasattr(self.parent_window, "_handle_installation_progress"):
            self.apk_manager.installation_progress_signal.connect(
                self.parent_window._handle_installation_progress,
                Qt.ConnectionType.QueuedConnection,
            )
        if hasattr(self.parent_window, "_on_operation_started"):
            self.apk_manager.operation_started_signal.connect(
                self.parent_window._on_operation_started,
                Qt.ConnectionType.QueuedConnection,
            )
        if hasattr(self.parent_window, "_on_operation_finished"):
            self.apk_manager.operation_finished_signal.connect(
                self.parent_window._on_operation_finished,
                Qt.ConnectionType.QueuedConnection,
            )

        if hasattr(self.parent_window, "_handle_installation_completed"):
            self.apk_manager.installation_completed_signal.connect(
                self.parent_window._handle_installation_completed,
                Qt.ConnectionType.QueuedConnection,
            )

        if hasattr(self.parent_window, "_handle_installation_error"):
            self.apk_manager.installation_error_signal.connect(
                self.parent_window._handle_installation_error,
                Qt.ConnectionType.QueuedConnection,
            )

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

    def install_apk_to_devices(
        self, devices: List[adb_models.DeviceInfo], apk_file: str, apk_name: str
    ):
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
