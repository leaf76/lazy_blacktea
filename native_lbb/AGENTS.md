# NATIVE_LBB (Rust Module)

## OVERVIEW

Rust crate providing high-performance I/O and parallel command execution. Compiled as `cdylib` for Python FFI.

## STRUCTURE

```
native_lbb/
├── Cargo.toml      # Crate config, edition 2021, cdylib
├── Cargo.lock      # Locked deps
├── src/
│   └── lib.rs      # All exports: lb_* functions
└── target/         # Build artifacts
```

## FFI INTERFACE

### Exported Functions (C ABI)
| Function | Purpose |
|----------|---------|
| `lb_run_parallel_commands` | Execute ADB commands in parallel |
| `lb_start_recording` | Start screenrecord process |
| `lb_stop_recording` | Stop and retrieve recording |
| `lb_free_string` | Free Rust-allocated string |
| `lb_last_error` | Get last error message |

### Python Bridge
```python
# utils/native_bridge.py
from ctypes import cdll, c_char_p

lib = cdll.LoadLibrary("libnative_lbb.dylib")

result = lib.lb_run_parallel_commands(commands.encode())
# ... use result ...
lib.lb_free_string(result)  # CRITICAL!
```

## PROTOCOL

### Parallel Commands
- **Request**: `count\ncmd1\ncmd2\n...` (newline-separated)
- **Response**: `\u001e` (record separator) between results, `\u001f` (unit separator) within

### Error Handling
- Global `LAST_ERROR: OnceLock<Mutex<String>>`
- Check `lb_last_error()` after failed operations

### Recording Registry
- `RECORDING_PROCESSES: HashMap<String, RecordingHandle>`
- Tracks active recordings by device serial
- Manages process lifecycle (SIGINT, pkill)

## CONVENTIONS

### Naming
- All exports: `lb_<function_name>`
- Use `#[no_mangle]` and `extern "C"`

### Memory
```rust
// Allocate
let c_string = CString::new(result).unwrap();
c_string.into_raw()  // Transfers ownership to caller

// Caller MUST free via lb_free_string
#[no_mangle]
pub extern "C" fn lb_free_string(ptr: *mut c_char) {
    if !ptr.is_null() {
        unsafe { drop(CString::from_raw(ptr)); }
    }
}
```

## COMMANDS

```bash
# Build
cd native_lbb && cargo build --release

# Output
target/release/libnative_lbb.dylib  # macOS
target/release/libnative_lbb.so     # Linux
```

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| Return String directly | Return `*mut c_char`, provide free fn |
| Forget to document FFI | All exports need Python-side docs |
| Panic across FFI | Catch and set LAST_ERROR |

## NOTES

- PyInstaller bundles the .dylib/.so via `datas` or `binaries`
- Python loads via `ctypes.cdll.LoadLibrary`
- No Rust dependencies currently (minimal crate)
