# Vulkan Conversion Summary

## Completed Changes

### 1. Configuration Management (NEW: config.py)
Created a separate configuration file for better maintainability:
- `HOME_DIR`: User home directory
- `LLAMA_CPP_PATH`: Updated to `/usr/local/bin/llama-server`
- `MODEL_DIR`: Updated to `~/models`
- `CACHE_DIR`: `~/.cache/llama`
- `SLOTS_DIR`: `/tmp/llama_slots` (NEW)
- `GPU_CARDS`: List of AMD GPU cards [(card1, RX 480), (card2, RX 6600)]

### 2. Backend Changes (app.py)

#### Imports
- Added `import glob` for sysfs path matching
- Added import from config.py for all configuration constants

#### GPU Monitoring
- Replaced `nvidia-smi` with AMD sysfs-based monitoring
- Reads temperature from `/sys/class/drm/{card}/device/hwmon/hwmon*/temp1_input`
- Reads power from `/sys/class/drm/{card}/device/hwmon/hwmon*/power1_average`
- Reads GPU usage from `/sys/class/drm/{card}/device/gpu_busy_percent`
- Returns: index, name, temp, usage, power, memory

#### Environment Variables
- Removed `CUDA_VISIBLE_DEVICES` environment variable
- Vulkan auto-detects GPUs

#### Command Generation
Completely rebuilt command with Vulkan parameters:

**Old CUDA parameters:**
- `--threads`, `-c`, `-sm`, `-np` (removed)
- `CUDA_VISIBLE_DEVICES` prefix (removed)

**New Vulkan parameters:**
- `--ctx-size {ctx_size}` (default: 16384)
- `--n-gpu-layers {ngl}` (default: 99)
- `--main-gpu {main_gpu}` (default: 0)
- `--tensor-split {tensor_split}` (default: 1,0.4)
- `--flash-attn {flash_attn}` (default: on)
- `--batch-size {batch_size}` (default: 512)
- `--ubatch-size {ubatch_size}` (default: 128)
- `--parallel {parallel}` (default: 1)
- `--slot-save-path {SLOTS_DIR}`
- `--cont-batching` (conditional, default: enabled)

### 3. Frontend Changes (templates/index.html)

#### Model Parameters Column
- Removed: "Threads" input
- Updated: "Port" default changed from 8080 to 4000
- Added: "Context Size" input (moved from Advanced Settings)
- Kept: "GPU Layers", "Port", "Host"

#### Advanced Settings Column
**Removed:**
- "Split Mode (-sm)" dropdown
- "Number of Parallel Sequences" (replaced)

**Added:**
- "Main GPU" dropdown (GPU 0: RX 480, GPU 1: RX 6600)
- "Tensor Split" text input (default: 1,0.4)
- "Batch Size" number input (default: 512)
- "UBatch Size" number input (default: 128)
- "Flash Attention" dropdown (on/off)
- "Parallel Sequences" number input (default: 1)
- "Continuous Batching" dropdown (enabled/disabled)

#### GPU Stats Display
- Updated title to "GPU Usage (AMD Radeon)"
- Updated grid to 2 columns (was 3)
- Updated JavaScript to display:
  - GPU name with card ID
  - Temperature and Usage on one line
  - Power on separate line
  - Memory (placeholder for now)

## Files Modified

1. **config.py** (NEW) - All configuration constants
2. **app.py** - Backend conversion to Vulkan
3. **templates/index.html** - Frontend UI updates

## Testing Checklist

When you test on the target machine:

- [ ] Start Flask app: `python app.py`
- [ ] Verify web UI loads at http://localhost:5000
- [ ] Check GPU stats show both RX 480 and RX 6600
- [ ] Verify temperature/power/usage readings appear
- [ ] Select a model from ~/models directory
- [ ] Try starting model with default parameters
- [ ] Check server logs stream correctly
- [ ] Verify model loads on both GPUs (check llama-server output)
- [ ] Test stopping the model
- [ ] Try different tensor-split values
- [ ] Toggle flash attention on/off
- [ ] Test continuous batching toggle

## Potential Issues

### GPU Card Mapping
If GPU stats don't appear, verify card mapping:
```bash
ls -la /sys/class/drm/
```
Ensure card1 = RX 480 and card2 = RX 6600. If different, update GPU_CARDS in config.py.

### VRAM Monitoring
VRAM is currently showing "See server logs" because sysfs doesn't easily expose VRAM usage. You can:
1. Leave as-is and check llama-server logs
2. Parse VRAM from llama-server output (future enhancement)

### Flash Attention Compatibility
If flash attention causes issues:
- Set to "off" in UI
- Check llama-server logs for errors
- May not work with all AMD GPU/driver combinations

### Tensor Split Format
Ensure tensor-split values are comma-separated floats (e.g., "1,0.4")

## Command Comparison

**Old CUDA command:**
```bash
CUDA_VISIBLE_DEVICES=0,1 ~/llama/llama.cpp-b4823/build/bin/llama-server \
  -m ~/llama/models/model.gguf --threads 16 --port 8080 --host 0.0.0.0 \
  -ngl 99 -c 32000 -sm layer -np 1
```

**New Vulkan command:**
```bash
/usr/local/bin/llama-server \
  -m ~/models/model.gguf \
  --ctx-size 16384 \
  --n-gpu-layers 99 \
  --main-gpu 0 \
  --tensor-split 1,0.4 \
  --flash-attn on \
  --batch-size 512 \
  --ubatch-size 128 \
  --port 4000 \
  --host 0.0.0.0 \
  --parallel 1 \
  --slot-save-path /tmp/llama_slots \
  --cont-batching
```

## Next Steps

After successful testing:
1. Update README.md with Vulkan-specific documentation
2. Add Vulkan verification section to docs
3. Consider adding model profiles/presets
4. Consider adding performance metrics (tokens/sec)
5. Consider parsing VRAM from llama-server logs
