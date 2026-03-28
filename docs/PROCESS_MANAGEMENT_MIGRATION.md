# Process Management Migration

## Overview

This document describes the migration from the old process name-based killing approach to the new PID-based process management system.

## What Changed

### Old Approach (Removed)

**File:** `utils/scripts/kill_bot_processes.py` ❌ DELETED

The old approach used `psutil` to iterate through all running processes and kill any that matched certain patterns:
- Searched for processes with `main.py`, `run_bot.py`, or `bot.py` in the command line
- Searched for processes containing bot tokens or specific identifiers
- **Problem:** Could accidentally kill unrelated Python processes
- **Problem:** Required `psutil` dependency just for process management
- **Problem:** Not reliable across different operating systems

### New Approach (Current)

**File:** `src/process_manager.py` ✅ ACTIVE

The new approach uses PID files for safe process management:
- Creates a PID file at `data/bot.pid` when the bot starts
- Stores only the current process ID
- Uses the PID file to safely terminate only the specific bot process
- **Benefit:** No risk of killing unrelated processes
- **Benefit:** Works reliably across all operating systems
- **Benefit:** No additional dependencies required

## ProcessManager API

```python
from src.process_manager import ProcessManager

# Write current process PID to file
ProcessManager.write_pid()

# Read PID from file
pid = ProcessManager.read_pid()  # Returns int or None

# Kill existing bot process (if PID file exists)
killed = ProcessManager.kill_existing()  # Returns bool

# Check if bot is currently running
running = ProcessManager.is_running()  # Returns bool

# Remove PID file
ProcessManager.remove_pid()
```

## Integration Points

### 1. Bot Startup (`bot/main.py`)

```python
# Kill any existing bot process before starting
if ProcessManager.kill_existing():
    print("[INFO] Terminated existing bot process")
    time.sleep(2)  # Give time for cleanup

# Write current process PID
ProcessManager.write_pid()
```

### 2. Graceful Shutdown (`bot/main.py`)

```python
async def shutdown(self):
    # ... close database, stop tasks, stop bot ...
    
    # Always remove PID file during shutdown
    ProcessManager.remove_pid()
```

### 3. Startup Script (`run_bot.py`)

The `run_bot.py` script simply calls `bot.main.main()`, which handles all process management internally using ProcessManager.

## Testing

All process management functionality is thoroughly tested:

### Unit Tests
- `tests/unit/test_process_manager.py` - 17 tests covering all ProcessManager methods

### Integration Tests
- `tests/integration/test_main_startup_validation.py::TestProcessManagerIntegration` - 4 tests covering:
  - PID file creation on startup
  - Killing existing processes before startup
  - PID file removal on normal exit
  - PID file removal on error

### Shutdown Tests
- `tests/unit/test_shutdown_resource_cleanup.py` - 18 tests covering graceful shutdown including PID cleanup

## Migration Checklist

- [x] Implement `ProcessManager` class with PID-based management
- [x] Update `bot/main.py` to use ProcessManager
- [x] Update `run_bot.py` documentation
- [x] Delete old `utils/scripts/kill_bot_processes.py`
- [x] Verify all tests pass
- [x] Document the new approach

## Requirements Validated

This migration satisfies the following requirements from the project-critical-fixes spec:

- **Requirement 9.1:** Safe process termination using PID files instead of process names ✅
- **Requirement 9.2:** Graceful shutdown with proper signal handling ✅
- **Requirement 9.3:** Updated startup scripts to use new approach ✅
- **Requirement 9.4:** Signal handling for SIGTERM and SIGINT ✅

## Benefits

1. **Safety:** No risk of accidentally killing unrelated processes
2. **Reliability:** Works consistently across all operating systems
3. **Simplicity:** No external dependencies (psutil) required for process management
4. **Maintainability:** Clear, simple API with comprehensive test coverage
5. **Production-Ready:** Proper error handling and logging throughout

## How It Works

### PID File Lifecycle

1. **Bot Startup:**
   - Check for existing PID file
   - If exists, attempt to kill that process (SIGTERM)
   - Wait for cleanup (2 seconds)
   - Write new PID file with current process ID

2. **Bot Running:**
   - PID file remains at `data/bot.pid`
   - Contains single line with process ID
   - Can be checked by external tools to verify bot is running

3. **Bot Shutdown:**
   - Signal handler catches SIGTERM/SIGINT
   - Graceful shutdown sequence executes:
     - Close database connections
     - Stop background tasks
     - Stop bot application
     - Remove PID file
   - PID file is always removed, even if errors occur

### Signal Handling

The bot responds to two signals:

- **SIGTERM (15):** Graceful shutdown signal (used by systemd, Docker, etc.)
- **SIGINT (2):** Interrupt signal (Ctrl+C in terminal)

Both signals trigger the same graceful shutdown sequence.

## Migration from Old Approach

### For Developers

If you have code that used the old `kill_bot_processes.py`:

**Before:**
```python
from utils.scripts.kill_bot_processes import kill_existing_bot_processes

# Kill any existing bot processes
kill_existing_bot_processes()
```

**After:**
```python
from src.process_manager import ProcessManager

# Kill existing bot process (if any)
if ProcessManager.kill_existing():
    print("Terminated existing bot process")
    time.sleep(2)  # Give time for cleanup
```

### For System Administrators

If you have deployment scripts or systemd services:

**Old approach issues:**
- Required `psutil` package
- Could kill wrong processes
- Platform-specific behavior

**New approach benefits:**
- No external dependencies
- Safe and reliable
- Works on all platforms

**Systemd service example:**
```ini
[Unit]
Description=LucasTeam Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/lucasteam-bot
ExecStart=/opt/lucasteam-bot/venv/bin/python bot/main.py
Restart=on-failure
RestartSec=10

# Graceful shutdown
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

## Best Practices

### 1. Always Use ProcessManager

Never manually manage PID files. Always use the ProcessManager API:

```python
# ✅ GOOD
ProcessManager.write_pid()
ProcessManager.kill_existing()
ProcessManager.remove_pid()

# ❌ BAD - Don't do this
Path("data/bot.pid").write_text(str(os.getpid()))
```

### 2. Handle Cleanup in Finally Blocks

Always ensure PID file is removed, even if errors occur:

```python
try:
    ProcessManager.write_pid()
    # ... run bot ...
except Exception as e:
    logger.error(f"Bot failed: {e}")
finally:
    ProcessManager.remove_pid()  # Always cleanup
```

### 3. Check if Bot is Running

Before starting a new instance, check if bot is already running:

```python
if ProcessManager.is_running():
    print("Bot is already running!")
    sys.exit(1)

ProcessManager.write_pid()
# ... start bot ...
```

### 4. Wait After Killing

Give the old process time to cleanup before starting new one:

```python
if ProcessManager.kill_existing():
    print("Terminated existing bot process")
    time.sleep(2)  # Important: wait for cleanup

ProcessManager.write_pid()
```

### 5. Use Graceful Shutdown

Always implement proper signal handlers for graceful shutdown:

```python
def setup_signal_handlers():
    def handler(signum, frame):
        logger.info(f"Received signal {signum}")
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
```

## Troubleshooting

### PID File Exists But Process Not Running

**Symptom:** `data/bot.pid` exists but bot is not running

**Cause:** Bot crashed or was killed without cleanup

**Solution:** The ProcessManager handles this automatically. When you call `kill_existing()`, it checks if the process actually exists and removes stale PID files.

```python
# This is safe - handles stale PID files automatically
ProcessManager.kill_existing()
```

### Permission Denied When Killing Process

**Symptom:** `PermissionError` when calling `kill_existing()`

**Cause:** PID file contains ID of process owned by different user

**Solution:** Run bot as same user, or manually remove PID file:

```bash
# Check PID file owner
ls -l data/bot.pid

# Remove stale PID file if needed
rm data/bot.pid
```

### Multiple Bot Instances Running

**Symptom:** Multiple bot instances responding to commands

**Cause:** PID file not being created or checked properly

**Solution:** Ensure ProcessManager is used in startup sequence:

```python
# Always check and kill existing before starting
if ProcessManager.kill_existing():
    time.sleep(2)

ProcessManager.write_pid()
```

## Platform-Specific Notes

### Linux/Unix

- SIGTERM and SIGINT work as expected
- PID files are standard practice
- Works with systemd, supervisord, etc.

### macOS

- Same behavior as Linux
- Works with launchd

### Windows

- Signal handling is limited on Windows
- SIGTERM may not work (use SIGBREAK instead)
- Consider using Windows services or task scheduler

**Windows-specific code:**
```python
import platform

if platform.system() == 'Windows':
    signal.signal(signal.SIGBREAK, signal_handler)
else:
    signal.signal(signal.SIGTERM, signal_handler)
```

## See Also

- `src/process_manager.py` - Implementation
- `tests/unit/test_process_manager.py` - Unit tests
- `tests/SHUTDOWN_TEST_SUMMARY.md` - Shutdown testing documentation
- `.kiro/specs/project-critical-fixes/requirements.md` - Original requirements
- `.kiro/specs/project-critical-fixes/design.md` - Design documentation
