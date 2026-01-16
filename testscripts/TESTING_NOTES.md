# GPU Crash Detection - Testing Notes

## Files Added/Modified

### Core Implementation:
1. **`process_monitor.py`** - NEW
   - D state process detection (`check_d_state_processes()`)
   - GPU sysfs health checking (`check_gpu_sysfs_health()`)
   - Journalctl error scanning (`check_journalctl_gpu_errors()`)
   - Comprehensive diagnosis (`diagnose_gpu_crash()`)

2. **`app.py`** - MODIFIED
   - Enhanced `stop_model_if_running()` with D state detection
   - Updated `/gpu` endpoint to include health information
   - New `/diagnose_gpu` endpoint for manual diagnosis

3. **`gpu_monitor.py`** - MODIFIED
   - Added periodic GPU crash checks (every 30 seconds)
   - Automatic D state process detection and logging

4. **`templates/index.html`** - MODIFIED
   - GPU health warning/error banners
   - Individual GPU error indicators (red border + 🔴 icon)
   - "Run GPU Diagnosis" button
   - Updated `updateGPUStats()` function

### Test Script:
5. **`testscripts/test_gpu_display.py`** - NEW
   - Test script for verifying functionality
   - Run with: `python testscripts/test_gpu_display.py`

## What to Test

### 1. Normal Operation:
- Start app: `python app.py`
- Open `http://localhost:5000`
- Verify GPU stats display correctly
- No warning banners should appear

### 2. GPU Error Display:
- If GPU has issues, should see:
  - Red/Yellow banner in GPU section
  - Individual GPU cards with error indicators
  - Clear error messages

### 3. Manual Diagnosis:
- Click "Run GPU Diagnosis" button
- Should show popup with detailed results

### 4. D State Detection:
- If llama-server processes get stuck in D state:
  - 🔴 CRITICAL banner appears
  - "Hard reset required" message
  - Server logs show detailed warnings

### 5. Stop Functionality:
- Start a model, then stop it
- Check logs for proper cleanup
- If D state processes exist, should warn appropriately

## Key Features

1. **Automatic Monitoring**: GPU monitor checks every 30 seconds
2. **Real-time Display**: GPU stats update every 2 seconds with health info
3. **Clear Visual Hierarchy**:
   - Critical issues → Red banner at top
   - Warnings → Yellow banner
   - Normal → Clean display
4. **Dual Display**: Errors appear in BOTH GPU section and server logs

## Expected Behavior

### When RX 470 memory crashes:
- Processes enter D (uninterruptible sleep) state
- System detects D state processes
- Shows 🔴 CRITICAL banner: "D state processes detected - hard reset required"
- Individual GPU cards show red border + 🔴 icon
- Server logs show detailed diagnosis

### When GPU sysfs becomes inaccessible:
- Shows ⚠️ WARNING banner: "GPU sysfs inaccessible - monitor closely"
- Individual GPU cards show error messages
- System continues to function but warns of instability

## Files to Commit:
```bash
git add app.py gpu_monitor.py templates/index.html process_monitor.py testscripts/test_gpu_display.py
```