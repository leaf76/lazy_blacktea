# UTILS MODULE

## OVERVIEW

Shared services: ADB wrapper, logging, threading, native bridge. 18 files.

## STRUCTURE

```
utils/
├── adb_tools.py           # 2943 lines - ALL ADB operations (consider splitting)
├── adb_commands.py        # Command string builders
├── adb_models.py          # Device, AppInfo dataclasses
├── common.py              # get_logger(), trace_id, filesystem helpers
├── task_dispatcher.py     # Global thread pool for async ops
├── native_bridge.py       # Python-Rust FFI via ctypes
├── debounced_refresh.py   # UI update throttling
├── recording_utils.py     # Screen recording helpers
├── file_generation_utils.py  # Output path management
├── qt_plugin_loader.py    # Qt plugin path config (MUST call first)
├── qt_dependency_checker.py  # Validate Qt environment
└── ui_inspector_utils.py  # UI hierarchy parsing
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add ADB command | `adb_tools.py` | Add function, update tests |
| Command string | `adb_commands.py` | Builders for shell commands |
| Logging | `common.py` | `get_logger(__name__)` |
| Background task | `task_dispatcher.py` | `TaskDispatcher.submit()` |
| Native performance | `native_bridge.py` | Rust FFI |
| Debounce UI | `debounced_refresh.py` | Prevent rapid refreshes |

## CONVENTIONS

### Logging
```python
from utils.common import get_logger, trace_id_scope

logger = get_logger(__name__)

def my_operation(trace_id: str):
    with trace_id_scope(trace_id):
        logger.info("Starting operation")
        # ... work ...
```

### TaskDispatcher
```python
from utils.task_dispatcher import get_task_dispatcher

dispatcher = get_task_dispatcher()
handle = dispatcher.submit(
    fn=lambda: adb_tools.some_command(serial),
    callback=lambda result: self.on_complete(result)
)
# handle.cancel() if needed
```

### Native Bridge
```python
from utils.native_bridge import run_parallel_commands, free_result

result_ptr = run_parallel_commands(commands)
# Process result
free_result(result_ptr)  # CRITICAL: Always free!
```

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| Direct `subprocess.run` | Use `adb_tools.py` functions |
| Forget `trace_id_scope` | Always wrap for log correlation |
| Skip `free_result()` | Memory leak in native bridge |
| Block UI with ADB | Use `TaskDispatcher` |

## COMPLEXITY HOTSPOTS

| File | Lines | Issue |
|------|-------|-------|
| adb_tools.py | 2943 | 80+ functions, consider splitting by domain |

## NOTES

- `qt_plugin_loader.configure_qt_plugin_path()` MUST be called before any PyQt import
- Logs auto-cleanup: Only keeps today's logs (see `_cleanup_old_logs`)
- Trace IDs: UUID v4 hex, propagate via `ContextVar`
