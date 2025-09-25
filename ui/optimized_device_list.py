#!/usr/bin/env python3
"""
優化的設備列表管理器
解決大量設備時的UI卡頓問題
"""

import logging
from typing import Dict, List, Optional, Sequence, Set, Tuple
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QCheckBox,
    QLabel, QPushButton, QHBoxLayout
)
from PyQt6.QtGui import QFont

from utils import adb_models

logger = logging.getLogger('optimized_device_list')


class VirtualizedDeviceList(QObject):
    """虛擬化設備列表 - 只渲染可見的設備項目"""

    # 信號定義
    device_selection_changed = pyqtSignal(str, bool)  # serial, checked
    selection_count_changed = pyqtSignal(int)  # count

    def __init__(self, parent_widget, main_window=None):
        super().__init__()
        self.parent_widget = parent_widget
        self.main_window = main_window
        self.device_dict = {}
        self.sorted_devices: List[Tuple[str, adb_models.DeviceInfo]] = []
        self.checked_devices: Set[str] = set()

        # 虛擬化參數
        self.visible_range = 20  # 一次最多顯示20個設備
        self.batch_size = 5     # 每批處理5個設備
        self.scroll_position = 0

        # UI組件
        self.device_widgets = {}  # 實際的UI組件
        self.widget_pool = [] if main_window is None else None  # 組件池，重用QCheckBox

        # 更新控制
        self.update_timer = None

        self._setup_ui()

    def _setup_ui(self):
        """設置虛擬化UI結構"""
        # 主容器
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)

        # 統計信息
        self.stats_label = QLabel("設備: 0 | 已選擇: 0")
        self.stats_label.setFont(QFont('Arial', 9))
        self.main_layout.addWidget(self.stats_label)

        # 滾動區域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 設備容器
        self.device_container = QWidget()
        self.device_layout = QVBoxLayout(self.device_container)
        self.device_layout.addStretch()

        self.scroll_area.setWidget(self.device_container)
        self.main_layout.addWidget(self.scroll_area)

        # 連接滾動事件
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def update_device_list(self, device_dict: Dict[str, adb_models.DeviceInfo]):
        """更新設備列表，使用優化策略"""
        logger.debug(f"更新設備列表: {len(device_dict)} 個設備")

        # 保存當前選擇狀態
        old_checked = self.checked_devices.copy()

        # 更新數據
        self.device_dict = device_dict

        # 基於主視窗的搜尋與排序結果生成序列
        if self.main_window is not None:
            filtered_devices = self.main_window._get_filtered_sorted_devices(device_dict)
            self.sorted_devices = [
                (device.device_serial_num, device)
                for device in filtered_devices
                if device.device_serial_num in device_dict
            ]
            self.batch_size = DeviceListPerformanceOptimizer.calculate_batch_size(len(device_dict))
            self.visible_range = DeviceListPerformanceOptimizer.calculate_visible_range(len(device_dict))
        else:
            self.sorted_devices = list(device_dict.items())

        # 移除不存在的設備選擇
        current_serials = set(device_dict.keys())
        self.checked_devices = self.checked_devices & current_serials

        # 使用定時器批次更新UI
        self._schedule_ui_update()

        # 如果選擇狀態有變化，發送信號
        if old_checked != self.checked_devices:
            self.selection_count_changed.emit(len(self.checked_devices))

    def _schedule_ui_update(self):
        """安排UI更新，防止阻塞"""
        if self.update_timer:
            self.update_timer.stop()

        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._batch_update_ui)
        self.update_timer.start(10)  # 10ms延遲

    def _batch_update_ui(self):
        """分批更新UI，防止卡頓"""
        try:
            # 更新統計信息
            self._update_stats()

            device_source = self.sorted_devices if self.sorted_devices else list(self.device_dict.items())

            # 如果設備數量很少，直接全部顯示
            if len(device_source) <= 10:
                self._update_all_devices()
            else:
                # 使用虛擬化更新
                self._update_visible_devices()

        except Exception as e:
            logger.error(f"UI更新錯誤: {e}")

    def _update_stats(self):
        """更新統計信息"""
        total_devices = len(self.device_dict)
        visible_devices = len(self.sorted_devices)
        selected = len(self.checked_devices)
        if self.main_window is not None and self.main_window.device_search_manager.get_search_text():
            self.stats_label.setText(f"設備: {visible_devices}/{total_devices} | 已選擇: {selected}")
        else:
            self.stats_label.setText(f"設備: {total_devices} | 已選擇: {selected}")

    def _update_all_devices(self):
        """小量設備時的完整更新"""
        # 清理現有UI
        self._clear_device_widgets()

        # 批次添加設備
        device_list = self.sorted_devices if self.sorted_devices else list(self.device_dict.items())
        self._add_devices_batch(device_list, 0)

    def _update_visible_devices(self):
        """大量設備時的虛擬化更新"""
        # 計算可見範圍
        device_list = self.sorted_devices if self.sorted_devices else list(self.device_dict.items())
        total_devices = len(device_list)

        # 基於滾動位置計算顯示範圍
        start_index = max(0, self.scroll_position - 5)
        end_index = min(total_devices, start_index + self.visible_range)

        visible_devices = device_list[start_index:end_index]

        # 清理不在可見範圍內的組件
        self._cleanup_invisible_widgets(visible_devices)

        # 批次添加可見設備
        self._add_devices_batch(visible_devices, 0)

    def _add_devices_batch(self, device_list, batch_start):
        """分批添加設備UI組件"""
        batch_end = min(batch_start + self.batch_size, len(device_list))

        for i in range(batch_start, batch_end):
            serial, device = device_list[i]
            self._create_device_widget(serial, device)

        # 如果還有更多設備，安排下一批
        if batch_end < len(device_list):
            QTimer.singleShot(5, lambda: self._add_devices_batch(device_list, batch_end))

    def _create_device_widget(self, serial: str, device: adb_models.DeviceInfo):
        """創建單個設備UI組件"""
        if serial in self.device_widgets:
            checkbox = self.device_widgets[serial]
            self._update_checkbox_contents(checkbox, serial, device)
            return

        checkbox = self._get_checkbox_from_pool()

        if self.main_window is not None:
            checkbox.stateChanged.connect(lambda state, s=serial: self._on_device_check_changed(s, state))
            self.main_window._initialize_virtualized_checkbox(checkbox, serial, device, self.checked_devices)
            self.main_window.check_devices[serial] = checkbox
        else:
            checkbox.setText(self._format_device_text(device))
            checkbox.setChecked(serial in self.checked_devices)
            checkbox.stateChanged.connect(
                lambda state, s=serial: self._on_device_check_changed(s, state)
            )

        insert_index = self.device_layout.count() - 1
        self.device_layout.insertWidget(insert_index, checkbox)

        self.device_widgets[serial] = checkbox

    def _format_device_text(self, device: adb_models.DeviceInfo) -> str:
        """格式化設備顯示文字"""
        android_ver = device.android_ver or 'Unknown'
        android_api = device.android_api_level or 'Unknown'
        wifi_status = 'ON' if device.wifi_is_on else 'OFF' if device.wifi_is_on is not None else 'N/A'
        bt_status = 'ON' if device.bt_is_on else 'OFF' if device.bt_is_on is not None else 'N/A'

        return (
            f"📱 {device.device_model} | "
            f"🆔 {device.device_serial_num[:8]}... | "
            f"🤖 Android {android_ver} | "
            f"📶 WiFi:{wifi_status} | "
            f"🔵 BT:{bt_status}"
        )

    def _update_checkbox_contents(self, checkbox: QCheckBox, serial: str, device: adb_models.DeviceInfo):
        """更新現有checkbox的文字/提示"""
        if self.main_window is not None:
            self.main_window._apply_checkbox_content(checkbox, serial, device)
        else:
            checkbox.setText(self._format_device_text(device))

        should_check = serial in self.checked_devices
        if checkbox.isChecked() != should_check:
            checkbox.blockSignals(True)
            checkbox.setChecked(should_check)
            checkbox.blockSignals(False)

    def _get_checkbox_from_pool(self) -> QCheckBox:
        """從組件池獲取QCheckBox，實現組件重用"""
        if self.main_window is not None:
            return self.main_window._acquire_device_checkbox()

        if self.widget_pool:
            checkbox = self.widget_pool.pop()
            checkbox.setChecked(False)
            checkbox.setText("")
            return checkbox

        checkbox = QCheckBox()
        checkbox.setFont(QFont('Arial', 9))
        return checkbox

    def _return_checkbox_to_pool(self, checkbox: QCheckBox):
        """將QCheckBox返回到組件池"""
        if self.main_window is not None:
            self.main_window._release_device_checkbox(checkbox)
            return

        checkbox.stateChanged.disconnect()
        checkbox.setParent(None)
        self.widget_pool.append(checkbox)

    def _cleanup_invisible_widgets(self, visible_devices):
        """清理不可見的組件"""
        visible_serials = {serial for serial, _ in visible_devices}

        # 找出需要清理的組件
        to_cleanup = []
        for serial, widget in self.device_widgets.items():
            if serial not in visible_serials:
                to_cleanup.append(serial)

        # 清理組件
        for serial in to_cleanup:
            widget = self.device_widgets[serial]
            if self.main_window is not None:
                self.main_window.check_devices.pop(serial, None)
            self._return_checkbox_to_pool(widget)
            del self.device_widgets[serial]

    def _clear_device_widgets(self):
        """清理所有設備組件"""
        for serial, widget in list(self.device_widgets.items()):
            if self.main_window is not None:
                self.main_window.check_devices.pop(serial, None)
            self._return_checkbox_to_pool(widget)
        self.device_widgets.clear()

    def _on_scroll(self, value):
        """滾動事件處理"""
        # 更新滾動位置（轉換為設備索引）
        max_scroll = self.scroll_area.verticalScrollBar().maximum()
        if max_scroll > 0:
            scroll_ratio = value / max_scroll
            source_length = len(self.sorted_devices) if self.sorted_devices else len(self.device_dict)
            self.scroll_position = int(scroll_ratio * max(1, source_length))

        # 如果是大量設備，重新計算可見範圍
        if len(self.device_dict) > 10:
            self._schedule_ui_update()

    def _on_device_check_changed(self, serial: str, state: int):
        """設備選擇狀態變更"""
        is_checked = state == Qt.CheckState.Checked.value

        if is_checked:
            self.checked_devices.add(serial)
        else:
            self.checked_devices.discard(serial)

        # 更新統計
        self._update_stats()

        # 發送信號
        self.device_selection_changed.emit(serial, is_checked)
        self.selection_count_changed.emit(len(self.checked_devices))
        if self.main_window is not None:
            self.main_window._handle_virtualized_selection_change(serial, is_checked)

    def get_checked_devices(self) -> List[adb_models.DeviceInfo]:
        """獲取已選擇的設備"""
        return [self.device_dict[serial] for serial in self.checked_devices
                if serial in self.device_dict]

    def select_all_devices(self):
        """全選設備"""
        self.checked_devices = set(self.device_dict.keys())
        self._update_all_checkbox_states()
        self.selection_count_changed.emit(len(self.checked_devices))
        if self.main_window is not None:
            self.main_window.update_selection_count()

    def deselect_all_devices(self):
        """取消全選"""
        self.checked_devices.clear()
        self._update_all_checkbox_states()
        self.selection_count_changed.emit(0)
        if self.main_window is not None:
            self.main_window.update_selection_count()

    def _update_all_checkbox_states(self):
        """更新所有可見checkbox的狀態"""
        for serial, checkbox in self.device_widgets.items():
            checkbox.setChecked(serial in self.checked_devices)

    def get_widget(self) -> QWidget:
        """獲取主UI組件"""
        return self.main_widget

    def apply_search_and_sort(self):
        """重新套用搜尋排序條件並刷新顯示"""
        if self.main_window is not None:
            filtered_devices = self.main_window._get_filtered_sorted_devices(self.device_dict)
            self.sorted_devices = [
                (device.device_serial_num, device)
                for device in filtered_devices
                if device.device_serial_num in self.device_dict
            ]
            self.scroll_position = 0
            self._schedule_ui_update()

    def set_checked_serials(self, serials: Set[str]):
        """設定指定序號為勾選狀態"""
        current_serials = set(self.device_dict.keys())
        self.checked_devices = set(serials) & current_serials
        self._update_all_checkbox_states()
        self.selection_count_changed.emit(len(self.checked_devices))
        if self.main_window is not None:
            self.main_window.update_selection_count()

    def clear_widgets(self):
        """釋放目前建立的checkbox組件"""
        self._clear_device_widgets()


class DeviceListPerformanceOptimizer:
    """設備列表性能優化工具"""

    @staticmethod
    def should_use_virtualization(device_count: int) -> bool:
        """判斷是否應該使用虛擬化"""
        return device_count > 10

    @staticmethod
    def calculate_batch_size(device_count: int) -> int:
        """計算最佳批次大小"""
        if device_count <= 5:
            return device_count
        elif device_count <= 20:
            return 5
        else:
            return 3

    @staticmethod
    def calculate_visible_range(device_count: int) -> int:
        """計算可見範圍大小"""
        if device_count <= 10:
            return device_count
        elif device_count <= 50:
            return 20
        else:
            return 30
