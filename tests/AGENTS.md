# TESTS MODULE

## OVERVIEW

102 test files. Hybrid unittest/pytest. Custom runner with emoji reporting.

## STRUCTURE

```
tests/
├── run_tests.py            # Central orchestrator, subprocess-based
├── test_all_functions.py   # Comprehensive unit tests (unittest)
├── test_integration.py     # Cross-component workflows
├── test_functional.py      # Requires physical device
├── test_async_device_performance.py  # Concurrency stress tests
├── refactoring_framework.py  # Baseline comparison tools
├── smoke/                  # Quick verification scripts (pytest)
├── logs/                   # Test execution artifacts
└── test_*.py               # Feature-specific tests
```

## WHERE TO LOOK

| Task | File |
|------|------|
| Run all tests | `run_tests.py` |
| Add unit test | Create `test_<feature>.py` |
| ADB mock patterns | `test_all_functions.py` |
| Performance test | `test_async_device_performance.py` |
| Quick smoke test | `smoke/` directory |

## CONVENTIONS

### Test Naming
```python
# unittest style
class TestFeatureName(unittest.TestCase):
    def test_scenario_expected_result(self):
        pass

# pytest style
class TestFeatureName:
    def test_scenario_expected_result(self):
        pass
```

### Mocking ADB
```python
from unittest.mock import patch, MagicMock

@patch('utils.adb_tools.run_adb_command')
def test_device_list(mock_run):
    mock_run.return_value = "device1\tdevice\ndevice2\toffline"
    # ... test logic
```

### Qt Testing
```python
# Manual QApplication handling (no pytest-qt)
app = QApplication.instance() or QApplication([])
# ... widget tests
```

### Sandbox Detection
Tests check for "smartsocket" or "operation not permitted" to skip in restricted environments.

## COMMANDS

```bash
# Full suite
uv run python tests/run_tests.py

# Specific file
uv run pytest tests/test_logcat_filter_components.py

# Concurrency tests
uv run pytest tests/test_async_device_performance.py

# Headless
QT_QPA_PLATFORM=offscreen uv run python tests/run_tests.py
```

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| Skip tests before commit | Always run `run_tests.py` |
| Depend on real device | Mock ADB output |
| Leave temp files | Use `tempfile.TemporaryDirectory` |
| Non-deterministic tests | Control randomness, mock time |

## NOTES

- Coverage config in `.coveragerc` (tracks `utils/`, `ui/`, `config/`)
- Test artifacts in `tests/logs/` - clean periodically
- `refactoring_baseline.json` for API signature comparison
