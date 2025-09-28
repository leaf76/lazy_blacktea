"""Dump device UI helpers with optional native acceleration."""

from __future__ import annotations

import time
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import Iterable

from utils import adb_commands as adb_cmd
from utils import common, native_bridge


logger = common.get_logger('dump_device_ui')


def _write_to_file(fname: str, content: str) -> None:
  with open(fname, 'w', encoding='utf-8') as file:
    file.write(content)


def _pretty_print_xml(xml_fname: str) -> None:
  dom = xml.dom.minidom.parse(xml_fname)
  pretty_xml_as_string = dom.toprettyxml()
  _write_to_file(xml_fname, pretty_xml_as_string)


def _html_css_tree() -> str:
  return """
	<style>
	body{
		font-family: Arial, sans-serif;
		line-height: 1.6;
		color: #333;
		background-color: #f4f4f4;
		padding: 20px;
	}
	
	ul {
		list-style-type: none;
		padding-left:0;
	}
	
	ul li {
		margin: 5px 0;
		position: relative;
		padding: 5px;
		border: 2px solid #ddd;
		background-color:#fffff;
	}
	
	ul li ul {
		margin-left: 20px;
		padding-left: 20px;
		border-left:1.2px dashed #888;
	}
	
	ul li:before{
		content: '➡️';
		position: absolute;
		left:-15px;
		color: #888;
	}
	
	.attributes {
		color: #0000FF;
		font-style: italic ;
	}
	
	.text {
		color: #008000;
	}
	</style>
	"""


def _format_attributes(items: Iterable[tuple[str, str]]) -> str:
  attributes = []
  for key, value in items:
    attributes.append(
        f'<span class="attributes">{key}</span>=<span class="text">"{value}"</span>'
    )
  if not attributes:
    return ''
  joined = ', '.join(attributes)
  return f' [{joined}] '


def _node_to_html(node: ET.Element) -> str:
  attributes = _format_attributes(node.attrib.items())
  html_content = f'<li>{node.tag}{attributes}'
  children = list(node)
  if children:
    html_content += '<ul>'
    for child in children:
      html_content += _node_to_html(child)
    html_content += '</ul>'
  html_content += '</li>'
  return html_content


def _render_device_ui_html_python(xml_content: str) -> str:
  try:
    root = ET.fromstring(xml_content)
  except ET.ParseError as exc:
    raise ValueError(f'Invalid XML content: {exc}') from exc
  html_tree = '<ul>' + _node_to_html(root) + '</ul>'
  css = _html_css_tree().lstrip('\n')
  return css + html_tree


def render_device_ui_html(xml_content: str) -> str:
  """Render the XML hierarchy into HTML using native acceleration if available."""
  if native_bridge.is_available():
    try:
      return native_bridge.render_device_ui_html(xml_content)
    except native_bridge.NativeBridgeError as exc:
      logger.warning('Native renderer failed (%s); falling back to Python implementation', exc)
  return _render_device_ui_html_python(xml_content)


def _generate_html_file(xml_path: str, html_path: str) -> None:
  with open(xml_path, 'r', encoding='utf-8') as xml_file:
    xml_content = xml_file.read()
  html_output = render_device_ui_html(xml_content)
  _write_to_file(html_path, html_output)


def _start_pull_android_ui_file(serial_num: str, output_path: str) -> None:
  dumps = common.run_command(
      adb_cmd.cmd_pull_the_dump_device_ui_detail(serial_num, output_path),
      0,
  )
  logger.info('Get pull message: %s', dumps)


def _start_dump_android_ui(serial_num: str) -> None:
  dumps = common.run_command(
      adb_cmd.cmd_get_dump_device_ui_detail(serial_num), 0
  )
  logger.info('Get dump message: %s', dumps)


def _restart_adb_server() -> None:
  kill = common.run_command(adb_cmd.cmd_kill_adb_server(), 0)
  logger.info('Kill message: %s', kill)
  start = common.run_command(adb_cmd.cmd_start_adb_server(), 0)
  logger.info('Start message: %s', start)


def generate_process(serial_num: str, folder_path: str) -> None:
  tic = time.perf_counter()
  _restart_adb_server()
  logger.info('Get serial number is %s.', serial_num)
  _start_dump_android_ui(serial_num)
  logger.info('Dump file okay.')
  gen_full_path = folder_path + '/' + f'window_dump_{common.current_format_time_utc()}'
  xml_path = gen_full_path + '.xml'
  html_path = gen_full_path + '.html'
  logger.info('Start to pull xml.')
  _start_pull_android_ui_file(serial_num, xml_path)
  _pretty_print_xml(xml_path)
  logger.info('Pull finished.')
  logger.info('Start to generate html.')
  _generate_html_file(xml_path, html_path)
  toc = time.perf_counter()
  logger.info('Html path: %s', html_path)
  spent_time_str = f'Spent time is {toc-tic:0.4f}s.'
  logger.info('Finished. %s', spent_time_str)


__all__ = ['generate_process', 'render_device_ui_html', '_render_device_ui_html_python']
