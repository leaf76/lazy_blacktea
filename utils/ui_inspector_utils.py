"""UI Inspector utility functions for performance optimization and code reuse."""

import os
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from utils import adb_commands
from utils import common

logger = common.get_logger('ui_inspector_utils')

# Cache for parsed UI elements to avoid re-parsing
_ui_cache: Dict[str, Tuple[List[Dict], float]] = {}
_cache_timeout = 5.0  # Cache timeout in seconds


def clear_ui_cache():
    """Clear the UI elements cache."""
    global _ui_cache
    _ui_cache.clear()
    logger.info('UI cache cleared')


def _build_exec_out_command(device_serial: str, *args: str) -> List[str]:
    """Create an ADB exec-out command list for subprocess execution."""
    adb_command = adb_commands.get_adb_command()
    base_parts = shlex.split(adb_command) if isinstance(adb_command, str) else list(adb_command)
    return [*base_parts, '-s', device_serial, *args]


def capture_device_screenshot(device_serial: str, output_path: str) -> bool:
    """
    Capture screenshot from device efficiently.

    Args:
        device_serial: Device serial number
        output_path: Path to save screenshot

    Returns:
        True if successful, False otherwise
    """
    try:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        command = _build_exec_out_command(device_serial, 'exec-out', 'screencap', '-p')
        result = subprocess.run(command, check=True, capture_output=True)
        screenshot_data = result.stdout

        if not screenshot_data:
            logger.error('Failed to capture screenshot: empty response from device')
            return False

        with open(output_path, 'wb') as file_handle:
            file_handle.write(screenshot_data)

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f'Failed to capture screenshot: {e}')
        return False


def dump_ui_hierarchy(device_serial: str, output_path: str) -> bool:
    """
    Dump UI hierarchy from device efficiently.

    Args:
        device_serial: Device serial number
        output_path: Path to save UI hierarchy XML

    Returns:
        True if successful, False otherwise
    """
    try:
        # Dump UI hierarchy to device
        dump_cmd = f'adb -s {device_serial} shell uiautomator dump'
        common.sp_run_command(dump_cmd)

        # Pull the file
        pull_cmd = f'adb -s {device_serial} pull /sdcard/window_dump.xml "{output_path}"'
        common.sp_run_command(pull_cmd)

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f'Failed to dump UI hierarchy: {e}')
        return False


def parse_ui_elements_cached(xml_path: str) -> List[Dict[str, Any]]:
    """
    Parse UI elements from XML file with caching for performance.

    Args:
        xml_path: Path to UI hierarchy XML file

    Returns:
        List of UI element dictionaries
    """
    global _ui_cache

    # Check cache first
    file_mtime = os.path.getmtime(xml_path)
    cache_key = f"{xml_path}:{file_mtime}"

    current_time = common.timestamp_time()

    if cache_key in _ui_cache:
        cached_elements, cache_time = _ui_cache[cache_key]
        if float(current_time) - cache_time < _cache_timeout:
            logger.info(f'Using cached UI elements for {xml_path}')
            return cached_elements

    # Parse XML if not in cache or expired
    elements = parse_ui_elements(xml_path)
    _ui_cache[cache_key] = (elements, float(current_time))

    # Clean old cache entries
    _cleanup_cache()

    return elements


def parse_ui_elements(xml_path: str) -> List[Dict[str, Any]]:
    """
    Parse UI elements from XML file optimized for performance.

    Args:
        xml_path: Path to UI hierarchy XML file

    Returns:
        List of UI element dictionaries
    """
    elements = []

    try:
        # Use iterparse for memory efficiency with large XML files
        context = ET.iterparse(xml_path, events=('start', 'end'))
        context = iter(context)
        event, root = next(context)

        element_stack = []

        for event, elem in context:
            if event == 'start':
                element_stack.append(elem.tag)

                bounds = elem.get('bounds')
                if bounds and elem.tag == 'node':
                    # Parse bounds efficiently
                    bounds_coords = _parse_bounds_fast(bounds)
                    if bounds_coords:
                        x1, y1, x2, y2 = bounds_coords

                        # Create element info with optimized parsing
                        element_info = {
                            'bounds': (x1, y1, x2, y2),
                            'class': elem.get('class', ''),
                            'text': elem.get('text', ''),
                            'content_desc': elem.get('content-desc', ''),
                            'resource_id': elem.get('resource-id', ''),
                            'clickable': elem.get('clickable', 'false') == 'true',
                            'enabled': elem.get('enabled', 'true') == 'true',
                            'focusable': elem.get('focusable', 'false') == 'true',
                            'selected': elem.get('selected', 'false') == 'true',
                            'checked': elem.get('checked', 'false') == 'true',
                            'checkable': elem.get('checkable', 'false') == 'true',
                            'password': elem.get('password', 'false') == 'true',
                            'scrollable': elem.get('scrollable', 'false') == 'true',
                            'long_clickable': elem.get('long-clickable', 'false') == 'true',
                            'displayed': elem.get('displayed', 'true') == 'true',
                            'path': _generate_xpath_fast(element_stack, elem),
                            'element': elem
                        }

                        elements.append(element_info)

            elif event == 'end':
                if element_stack:
                    element_stack.pop()
                # Clear element to free memory
                elem.clear()

        # Clear root to free memory
        root.clear()

        logger.info(f'Parsed {len(elements)} UI elements efficiently')

    except Exception as e:
        logger.error(f'Error parsing UI hierarchy: {e}')

    return elements


def _parse_bounds_fast(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Fast bounds parsing optimized for performance.

    Args:
        bounds_str: Bounds string like '[x1,y1][x2,y2]'

    Returns:
        Tuple of (x1, y1, x2, y2) or None if invalid
    """
    try:
        # Remove brackets and split
        coords = bounds_str.replace('[', '').replace(']', ',').split(',')
        if len(coords) >= 4:
            return int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
    except (ValueError, IndexError):
        pass
    return None


def _generate_xpath_fast(element_stack: List[str], elem) -> str:
    """
    Generate XPath efficiently without deep recursion.

    Args:
        element_stack: Current element hierarchy
        elem: Current XML element

    Returns:
        XPath string
    """
    # Generate simple XPath based on class and attributes
    class_name = elem.get('class', '')
    resource_id = elem.get('resource-id', '')
    text = elem.get('text', '')

    xpath_parts = []

    if class_name:
        class_short = class_name.split('.')[-1]
        xpath_parts.append(f"//{class_short}")
    else:
        xpath_parts.append("//node")

    if resource_id:
        xpath_parts.append(f"[@resource-id='{resource_id}']")
    elif text:
        xpath_parts.append(f"[@text='{text[:20]}']")  # Limit text length

    return ''.join(xpath_parts)


def _cleanup_cache():
    """Clean up expired cache entries."""
    global _ui_cache
    current_time = float(common.timestamp_time())

    expired_keys = []
    for key, (_, cache_time) in _ui_cache.items():
        if current_time - cache_time > _cache_timeout * 2:  # Double timeout for cleanup
            expired_keys.append(key)

    for key in expired_keys:
        del _ui_cache[key]

    if expired_keys:
        logger.info(f'Cleaned up {len(expired_keys)} expired cache entries')


def find_elements_at_position(elements: List[Dict], x: int, y: int) -> List[Dict]:
    """
    Find all UI elements at a given position, sorted by area (smallest first).

    Args:
        elements: List of UI elements
        x: X coordinate
        y: Y coordinate

    Returns:
        List of elements at position, sorted by area
    """
    candidates = []

    for element in elements:
        bounds = element['bounds']
        if bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]:
            # Calculate element area
            area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            candidates.append((element, area))

    # Sort by area (smallest first) for precision
    candidates.sort(key=lambda x: x[1])
    return [element for element, area in candidates]


def elements_match(element1: Dict, element2: Dict) -> bool:
    """
    Check if two elements are the same using optimized comparison.

    Args:
        element1: First element
        element2: Second element

    Returns:
        True if elements match
    """
    if not element1 or not element2:
        return False

    # Fast bounds comparison (most reliable)
    if element1.get('bounds') == element2.get('bounds'):
        return True

    # Fallback: compare key attributes
    key_attrs = ['class', 'resource_id', 'text', 'content_desc']
    matches = sum(1 for attr in key_attrs
                 if element1.get(attr) and element1.get(attr) == element2.get(attr))

    return matches >= 2  # At least 2 attributes must match


def create_temp_files() -> Tuple[str, str, str]:
    """
    Create temporary files for UI Inspector operations.

    Returns:
        Tuple of (temp_dir, screenshot_path, xml_path)
    """
    temp_dir = tempfile.mkdtemp()
    screenshot_path = os.path.join(temp_dir, 'screenshot.png')
    xml_path = os.path.join(temp_dir, 'ui_hierarchy.xml')

    return temp_dir, screenshot_path, xml_path


def cleanup_temp_files(temp_dir: str):
    """
    Clean up temporary files.

    Args:
        temp_dir: Temporary directory to clean up
    """
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f'Cleaned up temporary directory: {temp_dir}')
    except Exception as e:
        logger.error(f'Failed to cleanup temp files: {e}')


def get_element_automation_tips(element: Dict) -> List[str]:
    """
    Generate automation tips for an element.

    Args:
        element: UI element dictionary

    Returns:
        List of automation tip strings
    """
    tips = []

    if element.get('resource_id'):
        resource_id = element['resource_id']
        best_id = resource_id.split(':id/')[-1] if ':id/' in resource_id else resource_id
        tips.append(f"🎯 Best locator: By ID ({best_id})")
    elif element.get('text'):
        tips.append(f"📝 Alternative: By text ('{element['text']}')")
    elif element.get('content_desc'):
        tips.append(f"💬 Alternative: By description ('{element['content_desc']}')")
    else:
        tips.append(f"🌳 Use XPath: {element.get('path', 'N/A')}")

    # Add interaction tips
    if element.get('clickable'):
        tips.append("🖱️ Element is clickable")
    if element.get('scrollable'):
        tips.append("📜 Element supports scrolling")
    if element.get('long_clickable'):
        tips.append("🖱️ Element supports long click")

    return tips


def calculate_element_stats(elements: List[Dict]) -> Dict[str, Any]:
    """
    Calculate statistics about UI elements for performance insights.

    Args:
        elements: List of UI elements

    Returns:
        Dictionary of statistics
    """
    if not elements:
        return {}

    stats = {
        'total_elements': len(elements),
        'clickable_count': sum(1 for e in elements if e.get('clickable')),
        'with_text_count': sum(1 for e in elements if e.get('text')),
        'with_id_count': sum(1 for e in elements if e.get('resource_id')),
        'scrollable_count': sum(1 for e in elements if e.get('scrollable')),
        'enabled_count': sum(1 for e in elements if e.get('enabled')),
    }

    # Calculate element types
    class_counts = {}
    for element in elements:
        class_name = element.get('class', 'Unknown')
        short_class = class_name.split('.')[-1] if class_name else 'Unknown'
        class_counts[short_class] = class_counts.get(short_class, 0) + 1

    stats['class_distribution'] = class_counts
    stats['unique_classes'] = len(class_counts)

    return stats
