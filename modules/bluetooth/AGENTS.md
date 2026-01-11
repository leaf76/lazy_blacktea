# BLUETOOTH MODULE

## OVERVIEW

Bluetooth monitoring via ADB dumpsys. State machine for aggregating BT status.

## STRUCTURE

```
bluetooth/
├── __init__.py          # Exports
├── models.py            # BluetoothState, BluetoothEventType enums
├── parser.py            # Parse dumpsys bluetooth_manager output
├── service.py           # BluetoothMonitorService orchestration
└── state_machine.py     # BluetoothStateMachine state aggregator
```

## WHERE TO LOOK

| Task | File |
|------|------|
| Add BT event type | `models.py` → `BluetoothEventType` |
| Parse new dumpsys field | `parser.py` |
| State transition logic | `state_machine.py` |
| Service lifecycle | `service.py` |

## STATE MACHINE PATTERN

```python
# State is a Set, allowing simultaneous states
states: Set[BluetoothState]  # e.g., {SCANNING, CONNECTED}

# Two input types:
# 1. ParsedSnapshot (polled state from dumpsys)
# 2. ParsedEvent (reactive, e.g., ADVERTISING_START)

# Outputs StateUpdate only if state/metrics actually changed
```

## CONVENTIONS

### Adding New Event
1. Add to `BluetoothEventType` in `models.py`
2. Update parser in `parser.py`
3. Add transition logic in `state_machine.py`
4. Update tests

### Timeout Handling
- Advertising/Scanning: 3s timeout to force inactive
- Use `_apply_timeouts()` in state machine

## ANTI-PATTERNS

| Forbidden | Instead |
|-----------|---------|
| String matching for state | Use enum values |
| Skip state machine | Always route through `BluetoothStateMachine` |

## NOTES

- Uses string-based profile checking as fallback (`'CONNECTED' in state.upper()`)
- Debouncing built into state machine
- Service coordinates with `AsyncDeviceManager` for device lifecycle
