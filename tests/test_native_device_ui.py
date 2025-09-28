import unittest

from utils import dump_device_ui


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout">
    <node index="1" text="Settings" resource-id="android:id/title" class="android.widget.TextView" />
    <node index="2" text="" resource-id="" class="android.widget.LinearLayout">
      <node index="3" text="Nested" resource-id="android:id/summary" class="android.widget.TextView" />
    </node>
  </node>
</hierarchy>
"""


class NativeDeviceUITests(unittest.TestCase):
    def test_render_device_ui_html_matches_python_reference(self) -> None:
        native_html = dump_device_ui.render_device_ui_html(SAMPLE_XML)
        fallback_html = dump_device_ui._render_device_ui_html_python(SAMPLE_XML)
        self.assertEqual(native_html, fallback_html)


if __name__ == '__main__':
    unittest.main()
