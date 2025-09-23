"""Dump device ui."""

import time
import xml.dom.minidom
import xml.etree.ElementTree as ET

from utils import adb_commands as adb_cmd
from utils import common


logger = common.get_logger('dump_device_ui')


def _write_to_file(fname, content):
  with open(fname, 'w') as f:
    f.write(content)


def _pretty_print_xml(xml_fname):
  dom = xml.dom.minidom.parse(
      xml_fname
  )  # or xml.dom.minidom.parseString(xml_string)
  pretty_xml_as_string = dom.toprettyxml()
  _write_to_file(xml_fname, pretty_xml_as_string)


def _xml_to_html_tree(xml_file) -> str:
  """Convert xml to html tree."""
  tree = ET.parse(xml_file)
  root = tree.getroot()

  def recurse_node(node):
    attributes = ', '.join([
        f'<span class="attributes">{k}</span>=<span class="text">"{v}"</span>'
        for k, v in node.attrib.items()
    ])
    attributes_str = f' [{attributes}] ' if attributes else ''
    html_content = f'<li>{node.tag}{attributes_str}'
    if node:
      html_content += '<ul>'
      for child in node:
        html_content += recurse_node(child)
      html_content += '</ul>'
    html_content += '</li>'
    return html_content

  html_tree = '<ul>' + recurse_node(root) + '</ul>'
  return html_tree


def _html_css_tree() -> str:
  """Generate the html css tree."""
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


def _generate_html_file(xml_path, html_path):
  html_tree = _xml_to_html_tree(xml_path)
  result = _html_css_tree() + html_tree
  _write_to_file(html_path, result)


def _start_pull_android_ui_file(serial_num, o):
  dumps = common.run_command(
      adb_cmd.cmd_pull_the_dump_device_ui_detail(serial_num, o),
      0,
  )
  logger.info('Get pull message: %s', dumps)


def _start_dump_android_ui(serial_num):
  """Start dump android ui.

  Args:
    serial_num:
  """
  dumps = common.run_command(
      adb_cmd.cmd_get_dump_device_ui_detail(serial_num), 0
  )
  logger.info('Get dump message: %s', dumps)


def _restart_adb_server():
  """Restart adb server."""
  kill = common.run_command(adb_cmd.cmd_kill_adb_server(), 0)
  logger.info('Kill message: %s', kill)
  start = common.run_command(adb_cmd.cmd_start_adb_server(), 0)
  logger.info('Start message: %s', start)


def generate_process(serial_num: str, folder_path: str):
  """Generate the process."""
  tic = time.perf_counter()
  _restart_adb_server()
  logger.info('Get serial number is %s.', serial_num)
  _start_dump_android_ui(serial_num)
  logger.info('Dump file okay.')
  gen_full_path = (
      folder_path + '/' + f'window_dump_{common.current_format_time_utc()}'
  )
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
