# Vulkan Conversion Todo List

## Phase 0: Configuration File Creation ✅ COMPLETED

- [x] Create `config.py` with centralized configuration
- [x] Add `HOME_DIR`, `LLAMA_CPP_PATH`, `MODEL_DIR`, `CACHE_DIR`, `SLOTS_DIR`
- [x] Add `GPU_CARDS` list with AMD GPU definitions
- [x] Import config in app.py

## Phase 1: Configuration & Path Updates (app.py) ✅ COMPLETED

- [x] Update `HOME_DIR` variable - keep as-is
- [x] Update `LLAMA_CPP_PATH` to `/usr/local/bin/llama-server`
- [x] Update `MODEL_DIR` to `~/models`
- [x] Remove `PROJECT_DIR` variable - moved to config.py
- [x] Add `SLOTS_DIR = "/tmp/llama_slots"`

## Phase 2: GPU Monitoring Replacement (app.py) ✅ COMPLETED

- [x] Add `import glob` to imports (needed for sysfs paths)
- [x] Delete nvidia-smi function `get_gpu_stats()`
- [x] Implement sysfs-based AMD GPU stats function:
  - [x] Add GPU card mapping from config.py: `GPU_CARDS`
  - [x] Implement temperature reading from `/sys/class/drm/{card}/device/hwmon/hwmon*/temp1_input`
  - [x] Implement power reading from `/sys/class/drm/{card}/device/hwmon/hwmon*/power1_average`
  - [x] Implement GPU usage from `/sys/class/drm/{card}/device/gpu_busy_percent`
  - [x] Add error handling for each GPU card
  - [x] Return dict with keys: index, name, temp, usage, power, memory

## Phase 3: Remove CUDA Environment (app.py) ✅ COMPLETED

- [x] Remove `env["CUDA_VISIBLE_DEVICES"] = "0,1"`
- [x] Keep `env = os.environ.copy()`
- [x] Vulkan auto-detection enabled

## Phase 4: Update Command Generation (app.py) ✅ COMPLETED

- [x] Delete old command template with CUDA parameters
- [x] Add new form parameter extraction:
  - [x] `ctx_size = request.form.get("ctx_size", "16384")`
  - [x] `batch_size = request.form.get("batch_size", "512")`
  - [x] `ubatch_size = request.form.get("ubatch_size", "128")`
  - [x] `main_gpu = request.form.get("main_gpu", "0")`
  - [x] `tensor_split = request.form.get("tensor_split", "1,0.4")`
  - [x] `flash_attn = request.form.get("flash_attn", "on")`
  - [x] `parallel = request.form.get("parallel", "1")`
  - [x] `cont_batching = request.form.get("cont_batching", "true")`
- [x] Build new command string with Vulkan parameters:
  - [x] Use `-m {MODEL_DIR}/{model}`
  - [x] Use `--ctx-size {ctx_size}`
  - [x] Use `--n-gpu-layers {ngl}` (keep ngl param)
  - [x] Use `--main-gpu {main_gpu}`
  - [x] Use `--tensor-split {tensor_split}`
  - [x] Use `--flash-attn {flash_attn}`
  - [x] Use `--batch-size {batch_size}`
  - [x] Use `--ubatch-size {ubatch_size}`
  - [x] Use `--port {port}` and `--host {host}`
  - [x] Use `--parallel {parallel}`
  - [x] Use `--slot-save-path {SLOTS_DIR}`
  - [x] Add conditional `--cont-batching` flag
- [x] Remove old `threads` parameter (not in working config)
- [x] Remove old `-c`, `-sm`, `-np` short flags
- [x] Update debug logging to show new parameters
- [x] Remove old CUDA command comparison debug code

## Phase 5: HTML Form Updates - Remove CUDA (templates/index.html) ✅ COMPLETED

- [x] Remove "Split Mode" dropdown
- [x] Remove "Threads" input - not in working config
- [x] Keep "GPU Layers" input
- [x] Keep "Port" and "Host" inputs (updated port default to 4000)
- [x] Move "Context Size" to Model Parameters column

## Phase 6: HTML Form Updates - Add Vulkan Parameters (templates/index.html) ✅ COMPLETED

- [x] Update "Context Size" input to use `ctx_size` name instead of `c`
- [x] Add "Main GPU" dropdown:
  - [x] Option: "0" (RX 480)
  - [x] Option: "1" (RX 6600)
- [x] Add "Tensor Split" text input:
  - [x] Name: `tensor_split`
  - [x] Default value: "1,0.4"
  - [x] Placeholder: "1,0.4"
- [x] Add "Batch Size" number input:
  - [x] Name: `batch_size`
  - [x] Default: 512
- [x] Add "UBatch Size" number input:
  - [x] Name: `ubatch_size`
  - [x] Default: 128
- [x] Add "Flash Attention" dropdown:
  - [x] Options: "on", "off"
  - [x] Default: "on"
- [x] Add "Parallel Sequences" number input:
  - [x] Name: `parallel`
  - [x] Default: 1
- [x] Add "Continuous Batching" dropdown:
  - [x] Options: "true", "false"
  - [x] Default: "true"

## Phase 7: HTML GPU Stats Display Updates (templates/index.html) ✅ COMPLETED

- [x] Update GPU stats section title to "GPU Usage (AMD Radeon)"
- [x] Update grid to 2 columns (was 3)
- [x] Update JavaScript GPU rendering:
  - [x] Change display from `GPU ${gpu.index}` to `${gpu.index}`
  - [x] Update to show: Temp, Usage on one line
  - [x] Add Power display on separate line
  - [x] Keep memory field with conditional display

## Phase 8: Testing & Validation

- [ ] Test: Start Flask app successfully
- [ ] Test: Models directory loads correctly from ~/models
- [ ] Test: llama-server path resolves correctly
- [ ] Test: GPU stats show both RX 480 and RX 6600
- [ ] Test: Temperature readings appear
- [ ] Test: Power readings appear
- [ ] Test: GPU usage percentage appears
- [ ] Test: Start a model with default parameters
- [ ] Test: Model loads on both GPUs
- [ ] Test: Server logs stream correctly
- [ ] Test: Stop model cleans up processes
- [ ] Test: Try different tensor-split values
- [ ] Test: Try different main-gpu selections
- [ ] Test: Toggle flash attention on/off
- [ ] Test: Change batch sizes
- [ ] Test: Verify continuous batching works

## Phase 9: Documentation Updates (README.md) ✅ COMPLETED

- [x] Add high-level status report below title
- [x] Update requirements: Change "CUDA support" to "Vulkan support"
- [x] Update: Change "NVIDIA GPU(s)" to "AMD/NVIDIA/Intel GPU(s) with Vulkan"
- [x] Add Vulkan verification section:
  - [x] Add `vulkaninfo | grep deviceName` command
  - [x] Add `llama-cli --list-devices` command
  - [x] Add expected output for RX 480 and RX 6600
- [x] Update troubleshooting section for AMD GPUs
- [x] Update installation requirements
- [x] Add note about sysfs GPU monitoring
- [x] Update configuration examples with Vulkan parameters
- [x] Update usage section with new Vulkan parameters
- [x] Update project structure to include new files

## Phase 10: Optional Enhancements

- [ ] Add validation for tensor-split format (comma-separated floats)
- [ ] Add GPU preset buttons (e.g., "GPU 0 only", "Balanced split", "Favor GPU 0")
- [ ] Add tooltip/help text for tensor-split parameter
- [ ] Add model profiles/presets feature
- [ ] Consider parsing VRAM usage from llama-server logs
- [ ] Add performance metrics display (tokens/sec)

## Known Issues to Watch For

- **GPU Card Mapping**: Verify /sys/class/drm/card1 = RX 480, card2 = RX 6600
- **VRAM Display**: sysfs doesn't easily expose VRAM, may need log parsing
- **Tensor Split Format**: Ensure UI accepts comma-separated values correctly
- **Flash Attention**: May not work on all AMD GPUs/drivers, add fallback
- **Thermal Throttling**: Monitor temperature during heavy loads
