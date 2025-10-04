import os
import types
import unittest
from collections import OrderedDict
from unittest.mock import Mock

from PyQt6.QtWidgets import (
    QApplication,
    QTabWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QGroupBox,
    QWidget,
    QVBoxLayout,
)

from utils import adb_models
from ui.device_selection_manager import DeviceSelectionManager
from ui.tools_panel_controller import ToolsPanelController

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class DeviceOverviewPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        class _StubWindow(QWidget):
            pass

        stub = _StubWindow()
        stub.device_selection_manager = DeviceSelectionManager()
        stub.device_dict = {}
        stub.refresh_active_device_overview = lambda: None
        stub.copy_active_device_overview = lambda: None
        stub.show_logcat = lambda: None
        stub.launch_ui_inspector = lambda: None
        stub.monitor_bluetooth = lambda: None
        stub.group_name_edit = QLineEdit()
        stub.groups_listbox = QListWidget()
        stub.output_path_edit = QLineEdit()
        stub.file_gen_output_path_edit = QLineEdit()
        stub.save_group = lambda: None
        stub.select_devices_in_group = lambda: None
        stub.delete_group = lambda: None
        stub.on_group_select = lambda: None
        stub.browse_output_path = lambda: None
        stub.take_screenshot = lambda: None
        stub.start_screen_record = lambda: None
        stub.stop_screen_record = lambda: None
        stub.reboot_device = lambda: None
        stub.install_apk = lambda: None
        stub.enable_bluetooth = lambda: None
        stub.disable_bluetooth = lambda: None
        stub.scrcpy_available = False
        stub.clear_logcat = lambda: None
        stub.generate_android_bug_report = lambda: None
        stub.add_template_command = lambda *_: None
        stub.run_single_command = lambda: None
        stub.run_batch_commands = lambda: None
        stub.command_execution_manager = types.SimpleNamespace(cancel_all_commands=lambda: None)
        stub.run_shell_command = lambda: None
        stub.load_from_history = lambda *_: None
        stub.clear_command_history = lambda: None
        stub.export_command_history = lambda: None
        stub.import_command_history = lambda: None
        stub.update_history_display = lambda: None

        self.stub_window = stub
        self.controller = ToolsPanelController(self.stub_window)

    def test_existing_groups_panel_has_header_spacing(self):
        tab_widget = QTabWidget()
        self.controller._create_device_groups_tab(tab_widget)

        tab = tab_widget.widget(tab_widget.count() - 1)
        section_layout = tab.layout()
        left_group = section_layout.itemAt(0).widget()
        left_layout = left_group.layout()
        left_margins = left_layout.contentsMargins()

        right_group = section_layout.itemAt(1).widget()
        right_layout = right_group.layout()
        margins = right_layout.contentsMargins()

        self.assertGreaterEqual(left_margins.top(), 20)
        self.assertGreaterEqual(left_margins.bottom(), 20)
        self.assertGreaterEqual(margins.top(), 16)
        self.assertGreaterEqual(margins.left(), 12)

    def test_device_control_panel_spacing_prevents_overlap(self):
        tab_widget = QTabWidget()
        self.controller._create_adb_tools_tab(tab_widget)

        tab = tab_widget.widget(tab_widget.count() - 1)
        content_layout = tab.layout().itemAt(0).widget().widget().layout()  # scrollarea -> widget -> layout

        panel_widget: QGroupBox | None = None
        for i in range(content_layout.count()):
            item = content_layout.itemAt(i).widget()
            if isinstance(item, QGroupBox) and item.title() == 'Device Control':
                panel_widget = item
                break

        self.assertIsNotNone(panel_widget)
        panel_layout = panel_widget.layout()
        margins = panel_layout.contentsMargins()
        self.assertGreaterEqual(margins.top(), 16)

    def test_shell_command_groups_have_clearance(self):
        tab_widget = QTabWidget()
        self.controller._create_shell_commands_tab(tab_widget)

        tab = tab_widget.widget(tab_widget.count() - 1)
        scroll_widget = tab.widget()
        main_layout = scroll_widget.layout()

        template_group = main_layout.itemAt(0).widget()
        template_margins = template_group.layout().contentsMargins()
        self.assertGreaterEqual(template_margins.top(), 16)

        batch_group = main_layout.itemAt(1).widget()
        batch_margins = batch_group.layout().contentsMargins()
        self.assertGreaterEqual(batch_margins.top(), 16)

        history_group = main_layout.itemAt(2).widget()
        history_margins = history_group.layout().contentsMargins()
        self.assertGreaterEqual(history_margins.top(), 16)

    def test_console_output_panel_has_padding(self):
        from ui.console_manager import ConsoleManager

        class _ConsoleStub(QWidget):
            def __init__(self):
                super().__init__()
                self.logging_manager = types.SimpleNamespace(
                    initialize_logging=lambda *_: None
                )

            def write_to_console(self, *_):
                return None

            def show_console_context_menu(self, *_):
                return None

            def copy_console_text(self):
                return None

            def clear_console(self):
                return None

        stub = _ConsoleStub()
        console_manager = ConsoleManager(stub)

        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        console_manager.create_console_panel(holder_layout)

        group = holder_layout.itemAt(0).widget()
        layout = group.layout()
        margins = layout.contentsMargins()

        self.assertGreaterEqual(margins.top(), 16)
        self.assertGreaterEqual(margins.left(), 14)

    def test_overview_tab_is_added_first(self):
        tab_widget = QTabWidget()
        self.controller._create_device_overview_tab(tab_widget)
        self.controller._create_adb_tools_tab(tab_widget)

        self.assertEqual(tab_widget.count(), 2)
        self.assertEqual(tab_widget.tabText(0), 'Overview')
        self.assertIs(self.stub_window.device_overview_widget, tab_widget.widget(0))

    def test_update_device_overview_refreshes_widget(self):
        from lazy_blacktea_pyqt import WindowMain
        from ui.device_overview_widget import DeviceOverviewWidget

        from PyQt6.QtWidgets import QMainWindow

        window = WindowMain.__new__(WindowMain)
        QMainWindow.__init__(window)
        window.device_selection_manager = DeviceSelectionManager()
        window.device_dict = {}
        window.show_logcat = Mock()
        window.launch_ui_inspector = Mock()
        window.monitor_bluetooth = Mock()
        window.device_list_controller = types.SimpleNamespace(
            get_device_detail_text=Mock(return_value='basic detail'),
            get_on_off_status=lambda value: 'On' if value else 'Off',
            get_device_overview_summary=lambda device, serial: OrderedDict(
                (
                    ('device', [('Model', device.device_model), ('Serial', serial)]),
                    ('connectivity', [('WiFi', 'On'), ('Bluetooth', 'Off')]),
                    ('hardware', [('CPU Architecture', 'arm64')]),
                    ('battery', [('Battery Level', '82%')]),
                    ('status', [('Audio', 'mode=NORMAL')]),
                )
            ),
        )
        window.show_warning = lambda *args, **kwargs: None
        window.show_error = lambda *args, **kwargs: None
        window.device_overview_widget = DeviceOverviewWidget(window)

        device = adb_models.DeviceInfo(
            device_serial_num='SER12345',
            device_usb='usb',
            device_prod='prod',
            device_model='Pixel',
            wifi_is_on=True,
            bt_is_on=False,
            android_ver='14',
            android_api_level='34',
            gms_version='1.2',
            build_fingerprint='fp',
        )
        window.device_dict[device.device_serial_num] = device
        window.device_selection_manager.apply_toggle(device.device_serial_num, True)

        window.update_device_overview()

        detail_mock = window.device_list_controller.get_device_detail_text
        self.assertEqual(detail_mock.call_count, 1)
        _, kwargs = detail_mock.call_args
        self.assertIn('include_additional', kwargs)
        self.assertFalse(kwargs['include_additional'])
        self.assertIn('include_identity', kwargs)
        self.assertFalse(kwargs['include_identity'])
        self.assertIn('include_connectivity', kwargs)
        self.assertFalse(kwargs['include_connectivity'])
        self.assertIn('include_status', kwargs)
        self.assertTrue(kwargs['include_status'])
        self.assertIn('basic detail', window.device_overview_widget.get_current_detail_text())
        model_label = window.device_overview_widget.findChild(QLabel, 'device_overview_value_device_model')
        self.assertIsNotNone(model_label)
        self.assertEqual(model_label.text(), 'Pixel')

        hardware_label = window.device_overview_widget.findChild(
            QLabel, 'device_overview_value_hardware_cpu_architecture'
        )
        self.assertIsNotNone(hardware_label)
        self.assertEqual(hardware_label.text(), 'arm64')

        status_label = window.device_overview_widget.findChild(
            QLabel, 'device_overview_value_status_audio'
        )
        self.assertIsNotNone(status_label)
        self.assertEqual(status_label.text(), 'mode=NORMAL')

        condensed_text = window.device_overview_widget.get_current_detail_text()
        self.assertNotIn('Model:', condensed_text)
        self.assertNotIn('Serial:', condensed_text)

        self.assertTrue(window.device_overview_widget.refresh_button.isEnabled())
        self.assertTrue(window.device_overview_widget.copy_button.isEnabled())
        self.assertTrue(window.device_overview_widget.logcat_button.isEnabled())
        self.assertTrue(window.device_overview_widget.ui_inspector_button.isEnabled())
        self.assertTrue(window.device_overview_widget.bluetooth_button.isEnabled())

        # Clear selection should reset the widget state
        window.device_selection_manager.clear()
        window.update_device_overview()
        self.assertFalse(window.device_overview_widget.refresh_button.isEnabled())
        self.assertFalse(window.device_overview_widget.logcat_button.isEnabled())
        self.assertFalse(window.device_overview_widget.ui_inspector_button.isEnabled())
        self.assertFalse(window.device_overview_widget.bluetooth_button.isEnabled())
        self.assertIn('Select a device', window.device_overview_widget.get_current_detail_text())


if __name__ == '__main__':
    unittest.main()
