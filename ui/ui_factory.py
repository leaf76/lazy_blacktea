"""UI工廠模組 - 負責創建和管理所有UI組件

這個模組將所有UI創建邏輯從主窗口中分離出來，提供：
1. 工具面板創建
2. 標籤頁創建
3. 控制台面板創建
4. 狀態欄創建
5. UI Inspector相關組件創建

重構目標：
- 減少主窗口類的複雜度
- 提高UI組件創建邏輯的可重用性
- 改善代碼組織結構
"""

from typing import Dict, List, Any, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QPushButton, QLabel, QGroupBox, QScrollArea, QTextEdit,
    QCheckBox, QLineEdit, QProgressBar, QComboBox, QListWidget,
    QStatusBar, QToolBar, QFrame, QSizePolicy, QTreeWidget, QToolButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QAction, QPixmap

from utils import common
from .style_manager import StyleManager, ButtonStyle, LabelStyle
from .tool_icon_factory import get_tile_tool_icon


class UIFactory:
    """UI組件工廠類 - 負責創建各種UI組件"""

    def __init__(self, parent_window=None):
        self.parent_window = parent_window
        self.logger = common.get_logger('ui_factory')

    # ===== 標準化UI元件工廠方法 =====

    @staticmethod
    def create_standard_button(
        text: str,
        style: ButtonStyle = ButtonStyle.PRIMARY,
        fixed_height: int = 36,
        click_handler: Optional[Callable] = None,
        tooltip: Optional[str] = None,
        enabled: bool = True,
        object_name: Optional[str] = None
    ) -> QPushButton:
        """創建標準按鈕"""
        button = QPushButton(text)
        StyleManager.apply_button_style(button, style, fixed_height)
        button.setEnabled(enabled)

        if object_name:
            button.setObjectName(object_name)

        if click_handler:
            button.clicked.connect(click_handler)

        if tooltip:
            button.setToolTip(tooltip)

        return button

    @staticmethod
    def create_standard_label(
        text: str,
        style: LabelStyle = LabelStyle.STATUS,
        word_wrap: bool = False,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
        object_name: Optional[str] = None
    ) -> QLabel:
        """創建標準標籤"""
        label = QLabel(text)
        label.setStyleSheet(StyleManager.get_label_style(style))
        label.setWordWrap(word_wrap)
        label.setAlignment(alignment)

        if object_name:
            label.setObjectName(object_name)

        return label

    @staticmethod
    def create_standard_input(
        placeholder: Optional[str] = None,
        text: str = "",
        read_only: bool = False,
        object_name: Optional[str] = None
    ) -> QLineEdit:
        """創建標準輸入框"""
        input_field = QLineEdit()
        input_field.setStyleSheet(StyleManager.get_input_style())

        if placeholder:
            input_field.setPlaceholderText(placeholder)

        if text:
            input_field.setText(text)

        input_field.setReadOnly(read_only)

        if object_name:
            input_field.setObjectName(object_name)

        return input_field

    @staticmethod
    def create_standard_checkbox(
        text: str,
        checked: bool = False,
        object_name: Optional[str] = None
    ) -> QCheckBox:
        """創建標準核取方塊"""
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(StyleManager.get_checkbox_style())
        checkbox.setChecked(checked)

        if object_name:
            checkbox.setObjectName(object_name)

        return checkbox

    # ===== 工具面板創建 =====

    def create_tools_panel(self, parent) -> QWidget:
        """創建工具面板容器"""
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setContentsMargins(5, 5, 5, 5)

        # 創建標籤頁容器
        tab_widget = QTabWidget()

        # 添加各個工具標籤頁
        self.create_adb_tools_tab(tab_widget)
        self.create_shell_commands_tab(tab_widget)
        self.create_device_file_browser_tab(tab_widget)
        self.create_device_groups_tab(tab_widget)

        tools_layout.addWidget(tab_widget)

        self.logger.debug('Tools panel created')
        return tools_widget

    def _create_tile_button(
        self,
        label: str,
        action: str,
        *,
        icon_key: Optional[str] = None,
        primary: bool = False,
    ) -> QWidget:
        """建立共享的 tile 樣式按鈕，保持與 Screen Capture 區塊一致。"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        button = QToolButton()
        button.setObjectName(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setText(label)
        button.setIcon(get_tile_tool_icon(icon_key or action, label, primary=primary))
        button.setIconSize(QSize(48, 48))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        StyleManager.apply_tile_button_style(button, primary=primary)

        container_layout.addWidget(button)
        return container

    def create_adb_tools_tab(self, tab_widget: QTabWidget) -> None:
        """創建ADB工具標籤頁"""
        adb_tab = QWidget()
        layout = QVBoxLayout(adb_tab)
        layout.setSpacing(20)

        # 設備控制區域
        device_control_group = QGroupBox("📱 Device Control")
        StyleManager.apply_panel_frame(device_control_group)
        device_control_layout = QGridLayout(device_control_group)
        device_control_layout.setContentsMargins(16, 24, 16, 16)
        device_control_layout.setHorizontalSpacing(16)
        device_control_layout.setVerticalSpacing(12)

        device_buttons = [
            ("Reboot Device", "reboot_device", "reboot", True),
            ("Reboot to Recovery", "reboot_recovery", "recovery", False),
            ("Reboot to Bootloader", "reboot_bootloader", "bootloader", False),
            ("Restart ADB", "restart_adb", "restart", False),
        ]

        for index, (label, action, icon_key, primary) in enumerate(device_buttons):
            tile = self._create_tile_button(label, action, icon_key=icon_key, primary=primary)
            row, col = divmod(index, 2)
            device_control_layout.addWidget(tile, row, col)

        layout.addWidget(device_control_group)

        # 連接性控制區域
        connectivity_group = QGroupBox("📶 Connectivity")
        StyleManager.apply_panel_frame(connectivity_group)
        connectivity_layout = QGridLayout(connectivity_group)
        connectivity_layout.setContentsMargins(16, 24, 16, 16)
        connectivity_layout.setHorizontalSpacing(16)
        connectivity_layout.setVerticalSpacing(12)

        connectivity_buttons = [
            ("Enable WiFi", "enable_wifi", "wifi_on"),
            ("Disable WiFi", "disable_wifi", "wifi_off"),
            ("Enable Bluetooth", "enable_bluetooth", "bt_on"),
            ("Disable Bluetooth", "disable_bluetooth", "bt_off"),
        ]

        for index, (label, action, icon_key) in enumerate(connectivity_buttons):
            tile = self._create_tile_button(label, action, icon_key=icon_key)
            row, col = divmod(index, 2)
            connectivity_layout.addWidget(tile, row, col)

        layout.addWidget(connectivity_group)

        # 系統工具區域
        system_group = QGroupBox("🔧 System Tools")
        StyleManager.apply_panel_frame(system_group)
        system_layout = QGridLayout(system_group)
        system_layout.setContentsMargins(16, 24, 16, 16)
        system_layout.setHorizontalSpacing(16)
        system_layout.setVerticalSpacing(12)

        system_buttons = [
            ("Device Info", "device_info", "device_info"),
            ("Go Home", "go_home", "home"),
            ("Take Screenshot", "take_screenshot", "screenshot"),
            ("Start Recording", "start_recording", "record_start"),
            ("Stop Recording", "stop_recording", "record_stop"),
            ("Launch UI Inspector", "launch_ui_inspector", "inspector"),
        ]

        for index, (label, action, icon_key) in enumerate(system_buttons):
            tile = self._create_tile_button(label, action, icon_key=icon_key, primary=(action == "take_screenshot"))
            row, col = divmod(index, 3)
            system_layout.addWidget(tile, row, col)

        layout.addWidget(system_group)

        # 安裝工具區域
        install_group = QGroupBox("📦 Installation")
        StyleManager.apply_panel_frame(install_group)
        install_layout = QGridLayout(install_group)
        install_layout.setContentsMargins(16, 24, 16, 16)
        install_layout.setHorizontalSpacing(16)
        install_layout.setVerticalSpacing(12)

        install_tile = self._create_tile_button("Install APK", "install_apk", icon_key="install_apk", primary=True)
        install_layout.addWidget(install_tile, 0, 0)

        scrcpy_tile = self._create_tile_button("Launch scrcpy", "launch_scrcpy", icon_key="scrcpy")
        install_layout.addWidget(scrcpy_tile, 0, 1)

        layout.addWidget(install_group)

        layout.addStretch()
        tab_widget.addTab(adb_tab, "ADB Tools")

    def create_shell_commands_tab(self, tab_widget: QTabWidget) -> None:
        """創建Shell命令標籤頁"""
        shell_tab = QWidget()
        layout = QVBoxLayout(shell_tab)

        # 命令輸入區域
        input_group = QGroupBox("📝 Command Input")
        input_layout = QVBoxLayout(input_group)

        # 命令文本框
        command_edit = QTextEdit()
        command_edit.setObjectName("command_edit")
        command_edit.setPlaceholderText("Enter ADB shell commands here...\nExample: pm list packages")
        command_edit.setMaximumHeight(100)
        input_layout.addWidget(command_edit)

        # 按鈕區域
        button_layout = QHBoxLayout()

        run_btn = QPushButton("▶️ Run Command")
        run_btn.setObjectName("run_command")
        run_btn.setMinimumHeight(35)
        button_layout.addWidget(run_btn)

        run_all_btn = QPushButton("⚡ Run All Commands")
        run_all_btn.setObjectName("run_all_commands")
        run_all_btn.setMinimumHeight(35)
        button_layout.addWidget(run_all_btn)

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setObjectName("clear_commands")
        clear_btn.clicked.connect(command_edit.clear)
        button_layout.addWidget(clear_btn)

        input_layout.addLayout(button_layout)
        layout.addWidget(input_group)

        # 模板命令區域
        template_group = QGroupBox("📋 Template Commands")
        template_layout = QVBoxLayout(template_group)

        template_commands = [
            ("📱 List Packages", "pm list packages"),
            ("🔋 Battery Info", "dumpsys battery"),
            ("📊 System Info", "getprop"),
            ("📱 Running Apps", "pm list packages -e"),
            ("🌐 Network Info", "ip addr show"),
            ("📱 Device Properties", "getprop ro.product.model")
        ]

        for i in range(0, len(template_commands), 2):
            row_layout = QHBoxLayout()
            for j in range(2):
                if i + j < len(template_commands):
                    text, cmd = template_commands[i + j]
                    btn = QPushButton(text)
                    btn.setObjectName(f"template_{i+j}")
                    btn.clicked.connect(lambda checked, command=cmd: self._add_template_command(command_edit, command))
                    row_layout.addWidget(btn)
            template_layout.addLayout(row_layout)

        layout.addWidget(template_group)

        # 命令歷史區域
        history_group = QGroupBox("📚 Command History")
        history_layout = QVBoxLayout(history_group)

        history_scroll = QScrollArea()
        history_scroll.setMaximumHeight(100)
        history_scroll.setObjectName("command_history")
        history_layout.addWidget(history_scroll)

        # 歷史控制按鈕
        history_controls = QHBoxLayout()

        save_history_btn = QPushButton("💾 Save History")
        save_history_btn.setObjectName("save_history")
        history_controls.addWidget(save_history_btn)

        load_history_btn = QPushButton("📂 Load History")
        load_history_btn.setObjectName("load_history")
        history_controls.addWidget(load_history_btn)

        clear_history_btn = QPushButton("🗑️ Clear History")
        clear_history_btn.setObjectName("clear_history")
        history_controls.addWidget(clear_history_btn)

        history_layout.addLayout(history_controls)
        layout.addWidget(history_group)

        layout.addStretch()
        tab_widget.addTab(shell_tab, "Shell Commands")

    def create_device_groups_tab(self, tab_widget: QTabWidget) -> None:
        """創建設備組管理標籤頁"""
        groups_tab = QWidget()
        layout = QVBoxLayout(groups_tab)

        # 設備組列表
        groups_group = QGroupBox("👥 Device Groups")
        groups_layout = QVBoxLayout(groups_group)

        groups_list = QListWidget()
        groups_list.setObjectName("device_groups_list")
        groups_list.setMaximumHeight(200)
        groups_layout.addWidget(groups_list)

        # 組控制按鈕
        group_controls = QHBoxLayout()

        new_group_btn = QPushButton("➕ New Group")
        new_group_btn.setObjectName("new_group")
        group_controls.addWidget(new_group_btn)

        edit_group_btn = QPushButton("✏️ Edit Group")
        edit_group_btn.setObjectName("edit_group")
        group_controls.addWidget(edit_group_btn)

        delete_group_btn = QPushButton("🗑️ Delete Group")
        delete_group_btn.setObjectName("delete_group")
        group_controls.addWidget(delete_group_btn)

        groups_layout.addLayout(group_controls)
        layout.addWidget(groups_group)

        # 組選擇控制
        selection_group = QGroupBox("🎯 Group Selection")
        selection_layout = QVBoxLayout(selection_group)

        select_group_combo = QComboBox()
        select_group_combo.setObjectName("select_group_combo")
        selection_layout.addWidget(select_group_combo)

        select_group_controls = QHBoxLayout()

        select_group_btn = QPushButton("✅ Select Group Devices")
        select_group_btn.setObjectName("select_group_devices")
        select_group_controls.addWidget(select_group_btn)

        add_to_group_btn = QPushButton("➕ Add Selected to Group")
        add_to_group_btn.setObjectName("add_to_group")
        select_group_controls.addWidget(add_to_group_btn)

        selection_layout.addLayout(select_group_controls)
        layout.addWidget(selection_group)

        layout.addStretch()
        tab_widget.addTab(groups_tab, "Device Groups")

    def create_device_file_browser_tab(self, tab_widget: QTabWidget) -> None:
        """創建裝置檔案瀏覽標籤頁"""
        browser_tab = QWidget()
        layout = QVBoxLayout(browser_tab)

        device_label = QLabel("Select a device from the main list to browse files.")
        device_label.setObjectName('device_file_browser_device_label')
        layout.addWidget(device_label)

        path_bar = QHBoxLayout()
        path_edit = QLineEdit()
        path_edit.setObjectName('device_file_browser_path')
        path_edit.setPlaceholderText('/sdcard')
        path_bar.addWidget(path_edit)

        up_btn = QPushButton('⬆️ Up')
        up_btn.setObjectName('device_file_browser_up')
        path_bar.addWidget(up_btn)

        refresh_btn = QPushButton('🔄 Refresh')
        refresh_btn.setObjectName('device_file_browser_refresh')
        path_bar.addWidget(refresh_btn)

        go_btn = QPushButton('Go')
        go_btn.setObjectName('device_file_browser_go')
        path_bar.addWidget(go_btn)

        layout.addLayout(path_bar)

        tree = QTreeWidget()
        tree.setObjectName('device_file_browser_tree')
        tree.setHeaderLabels(['Name', 'Type'])
        tree.setRootIsDecorated(False)
        tree.setColumnWidth(0, 320)
        tree.setMinimumHeight(260)
        layout.addWidget(tree)

        status_label = QLabel('Ready')
        status_label.setObjectName('device_file_browser_status_label')
        layout.addWidget(status_label)

        download_bar = QHBoxLayout()
        output_edit = QLineEdit()
        output_edit.setObjectName('device_file_output_path')
        output_edit.setPlaceholderText('Select download destination...')
        download_bar.addWidget(output_edit)

        browse_btn = QPushButton('📂 Browse')
        browse_btn.setObjectName('device_file_output_browse')
        download_bar.addWidget(browse_btn)

        download_btn = QPushButton('⬇️ Download Selected')
        download_btn.setObjectName('device_file_browser_download')
        download_bar.addWidget(download_btn)

        layout.addLayout(download_bar)
        layout.addStretch()

        tab_widget.addTab(browser_tab, 'Device Files')

    # ===== 控制台面板創建 =====

    def create_console_panel(self, parent_layout) -> QTextEdit:
        """創建控制台輸出面板"""
        console_group = QGroupBox("📟 Console Output")
        console_layout = QVBoxLayout(console_group)

        # 控制台文本區域
        console_text = QTextEdit()
        console_text.setObjectName("console_output")
        console_text.setReadOnly(True)
        console_text.setMinimumHeight(150)
        console_text.setFont(QFont("Consolas", 9))

        # 設置大小策略允許擴展
        console_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 設置樣式
        console_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
            }
        """)

        console_layout.addWidget(console_text)

        # 控制台控制按鈕
        controls_layout = QHBoxLayout()

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setObjectName("clear_console")
        clear_btn.clicked.connect(console_text.clear)
        controls_layout.addWidget(clear_btn)

        copy_btn = QPushButton("📋 Copy All")
        copy_btn.setObjectName("copy_console")
        copy_btn.clicked.connect(lambda: self._copy_console_text(console_text))
        controls_layout.addWidget(copy_btn)

        save_btn = QPushButton("💾 Save Log")
        save_btn.setObjectName("save_console")
        controls_layout.addWidget(save_btn)

        controls_layout.addStretch()
        console_layout.addLayout(controls_layout)

        parent_layout.addWidget(console_group)
        self.logger.debug('Console panel created')
        return console_text

    # ===== 狀態欄創建 =====

    def create_status_bar(self) -> Dict[str, Any]:
        """創建狀態欄組件"""
        widgets = {}

        # 設備數量標籤
        widgets['device_count'] = QLabel("Devices: 0")
        widgets['device_count'].setStyleSheet("QLabel { margin: 2px 5px; }")

        # 錄製狀態標籤
        widgets['recording_status'] = QLabel("No active recordings")
        StyleManager.apply_hint_label(widgets['recording_status'], margin='2px 5px')

        # 進度條
        widgets['progress_bar'] = QProgressBar()
        widgets['progress_bar'].setVisible(False)
        widgets['progress_bar'].setMaximumWidth(200)

        # 連接狀態指示器
        widgets['connection_status'] = QLabel("🔴 Disconnected")
        widgets['connection_status'].setStyleSheet("QLabel { margin: 2px 5px; }")

        self.logger.debug('Status bar widgets created')
        return widgets

    # ===== 輔助方法 =====

    def _add_template_command(self, text_edit: QTextEdit, command: str):
        """添加模板命令到文本編輯器"""
        current_text = text_edit.toPlainText()
        if current_text and not current_text.endswith('\n'):
            text_edit.append('')
        text_edit.append(command)

    def _copy_console_text(self, console_text: QTextEdit):
        """復制控制台文本到剪貼板"""
        from PyQt6.QtWidgets import QApplication

        text = console_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.logger.info('Console output copied to clipboard')


class UIInspectorFactory:
    """UI Inspector組件工廠類"""

    def __init__(self, parent_dialog=None):
        self.parent_dialog = parent_dialog
        self.logger = common.get_logger('ui_inspector_factory')

    def create_modern_toolbar(self, parent_layout) -> QToolBar:
        """創建現代化工具欄"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # 添加工具欄按鈕
        actions = [
            ("🔄", "Refresh", self._on_refresh_clicked),
            ("📷", "Screenshot", self._on_screenshot_clicked),
            ("🔍", "Inspect", self._on_inspect_clicked),
            ("📋", "Copy", self._on_copy_clicked),
            ("💾", "Save", self._on_save_clicked),
        ]

        for icon, text, callback in actions:
            action = QAction(icon + " " + text, self.parent_dialog)
            action.triggered.connect(callback)
            toolbar.addAction(action)

        parent_layout.addWidget(toolbar)
        return toolbar

    def create_system_button(self, text: str) -> QPushButton:
        """創建系統風格按鈕"""
        button = QPushButton(text)
        button.setMinimumHeight(30)
        button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        return button

    def create_screenshot_panel(self) -> QWidget:
        """創建截圖顯示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 截圖標籤
        screenshot_label = QLabel()
        screenshot_label.setObjectName("screenshot_display")
        screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        screenshot_label.setStyleSheet("""
            QLabel {
                border: 2px solid #cccccc;
                border-radius: 8px;
                background-color: #f5f5f5;
                min-height: 200px;
            }
        """)
        screenshot_label.setText("📱 Device screenshot will appear here")

        layout.addWidget(screenshot_label)
        return panel

    def create_inspector_panel(self) -> QWidget:
        """創建檢查器面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 創建選項卡
        tab_widget = QTabWidget()

        # 元素詳情選項卡
        details_tab = self.create_element_details_tab()
        tab_widget.addTab(details_tab, "Element Details")

        # 層次結構選項卡
        hierarchy_tab = self.create_hierarchy_tab()
        tab_widget.addTab(hierarchy_tab, "Hierarchy")

        layout.addWidget(tab_widget)
        return panel

    def create_element_details_tab(self) -> QWidget:
        """創建元素詳情選項卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 元素信息顯示
        info_group = QGroupBox("🔍 Element Information")
        info_layout = QVBoxLayout(info_group)

        details_text = QTextEdit()
        details_text.setObjectName("element_details")
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(150)
        info_layout.addWidget(details_text)

        layout.addWidget(info_group)

        # 屬性列表
        attrs_group = QGroupBox("📋 Attributes")
        attrs_layout = QVBoxLayout(attrs_group)

        attrs_text = QTextEdit()
        attrs_text.setObjectName("element_attributes")
        attrs_text.setReadOnly(True)
        attrs_layout.addWidget(attrs_text)

        layout.addWidget(attrs_group)

        return tab

    def create_hierarchy_tab(self) -> QWidget:
        """創建層次結構選項卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search:"))

        search_edit = QLineEdit()
        search_edit.setObjectName("hierarchy_search")
        search_edit.setPlaceholderText("Search elements...")
        search_layout.addWidget(search_edit)

        layout.addLayout(search_layout)

        # 層次結構樹
        hierarchy_group = QGroupBox("🌳 UI Hierarchy")
        hierarchy_layout = QVBoxLayout(hierarchy_group)

        from PyQt6.QtWidgets import QTreeWidget
        hierarchy_tree = QTreeWidget()
        hierarchy_tree.setObjectName("hierarchy_tree")
        hierarchy_tree.setHeaderLabel("Elements")
        hierarchy_layout.addWidget(hierarchy_tree)

        layout.addWidget(hierarchy_group)

        return tab

    # ===== 事件處理方法 =====

    def _on_refresh_clicked(self):
        """刷新按鈕點擊事件"""
        self.logger.info('Refresh button triggered for UI Inspector')

    def _on_screenshot_clicked(self):
        """截圖按鈕點擊事件"""
        self.logger.info('Capture device screenshot action triggered')

    def _on_inspect_clicked(self):
        """檢查按鈕點擊事件"""
        self.logger.info('Start UI inspection action triggered')

    def _on_copy_clicked(self):
        """復制按鈕點擊事件"""
        self.logger.info('Copy element information action triggered')

    def _on_save_clicked(self):
        """保存按鈕點擊事件"""
        self.logger.info('Save UI hierarchy action triggered')


# 工廠實例創建函數
def create_ui_factory(parent_window=None) -> UIFactory:
    """創建UI工廠實例"""
    return UIFactory(parent_window)


def create_ui_inspector_factory(parent_dialog=None) -> UIInspectorFactory:
    """創建UI Inspector工廠實例"""
    return UIInspectorFactory(parent_dialog)
