# Vulkan Conversion Gameplan

## Overview
Convert the CUDA-based llama-cpp-model-controller to support AMD GPUs with Vulkan backend, matching the performance and configuration of the existing `start_model.sh` setup.

## Current System Configuration

### Hardware
- **GPU 1**: AMD RX 480 (card1) - "The Mule"
- **GPU 2**: AMD RX 6600 (card2) - "The Sprinter"
- **Total VRAM**: ~16GB combined

### Existing Working Setup
- **llama.cpp path**: `/usr/local/bin/llama-server`
- **Model path**: `~/models/`
- **Current model**: `qwen2.5-coder-14b-instruct-q4_k_m.gguf`
- **Monitoring tool**: nvtop (AMD-compatible)

### Working Command Parameters
```bash
/usr/local/bin/llama-server \
  -m ~/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf \
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

## Conversion Tasks

### 1. Update Configuration Variables (app.py lines 18-27)

**Current:**
```python
HOME_DIR = os.path.expanduser("~")
PROJECT_DIR = os.path.join(HOME_DIR, "llama")
MODEL_DIR = os.path.join(PROJECT_DIR, "models")
LLAMA_CPP_PATH = os.path.join(PROJECT_DIR, "llama.cpp-b4823/build/bin/llama-server")
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
```

**Updated:**
```python
HOME_DIR = os.path.expanduser("~")
LLAMA_CPP_PATH = "/usr/local/bin/llama-server"
MODEL_DIR = os.path.join(HOME_DIR, "models")
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
SLOTS_DIR = "/tmp/llama_slots"
```

### 2. Replace GPU Monitoring (app.py lines 44-62)

**Current Implementation:**
- Uses `nvidia-smi` for NVIDIA GPUs
- Returns: index, name, temperature, utilization, memory

**Option A: Use radeontop (lightweight)**
```python
def get_gpu_stats():
    """Get AMD GPU stats using radeontop"""
    try:
        # radeontop dumps to file, parse it
        subprocess.run(["radeontop", "-d", "-", "-l", "1"],
                      stdout=subprocess.PIPE, timeout=2, text=True)
        # Parse output for GPU usage
        # Format: gpu 45.00%, ee 12.00%, vgt 0.00%, etc.
    except Exception as e:
        logger.error(f"Error getting GPU stats: {e}")
        return [{"error": str(e)}]
```

**Option B: Parse /sys/class/drm (more reliable)**
```python
def get_gpu_stats():
    """Get AMD GPU stats from sysfs"""
    gpus = []
    cards = [("card1", "RX 480"), ("card2", "RX 6600")]

    for card_id, card_name in cards:
        try:
            # Temperature
            temp_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/temp1_input"
            temp_files = glob.glob(temp_path)
            temp = "N/A"
            if temp_files:
                with open(temp_files[0]) as f:
                    temp = f"{int(f.read().strip()) // 1000}°C"

            # Power usage
            power_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/power1_average"
            power_files = glob.glob(power_path)
            power = "N/A"
            if power_files:
                with open(power_files[0]) as f:
                    power = f"{int(f.read().strip()) // 1000000}W"

            # GPU usage (from busy_percent)
            busy_path = f"/sys/class/drm/{card_id}/device/gpu_busy_percent"
            usage = "N/A"
            if os.path.exists(busy_path):
                with open(busy_path) as f:
                    usage = f"{f.read().strip()}%"

            # VRAM usage (harder to get, may need to parse from llama-server logs)

            gpus.append({
                "index": card_id,
                "name": card_name,
                "temp": temp,
                "usage": usage,
                "power": power,
                "memory": "See server logs"  # Could parse from llama-server output
            })
        except Exception as e:
            logger.error(f"Error reading {card_id}: {e}")
            gpus.append({
                "index": card_id,
                "name": card_name,
                "error": str(e)
            })

    return gpus
```

**Option C: Use nvtop with JSON output (if available)**
```python
def get_gpu_stats():
    """Use nvtop for AMD GPU monitoring"""
    try:
        # Check if nvtop supports JSON output (newer versions)
        # Otherwise, parse text output or use sysfs method
        result = subprocess.run(["nvtop", "--once"],
                              stdout=subprocess.PIPE, text=True, timeout=2)
        # Parse output
    except Exception as e:
        logger.error(f"Error getting GPU stats: {e}")
        return [{"error": str(e)}]
```

**Recommended: Option B (sysfs)** - Most reliable, no external dependencies

### 3. Remove CUDA Environment Variables (app.py line 144)

**Current:**
```python
env = os.environ.copy()
env["CUDA_VISIBLE_DEVICES"] = "0,1"
```

**Updated:**
```python
env = os.environ.copy()
# Vulkan auto-detects GPUs, no need to set GGML_VK_VISIBLE_DEVICES
# Could optionally set it if you want to restrict GPU access:
# env["GGML_VK_VISIBLE_DEVICES"] = "0,1"
```

### 4. Update llama-server Command Generation (app.py lines 146-150)

**Current Command Structure:**
```python
command = f"""
CUDA_VISIBLE_DEVICES=0,1 {LLAMA_CPP_PATH} \
-m {MODEL_DIR}/{model} --threads {threads} --port {port} --host {host} \
-ngl {ngl} -c {c} -sm {sm} -np {np}
"""
```

**Updated Command Structure:**
```python
# Get parameters from form
model = request.form.get("model")
port = request.form.get("port", "4000")
host = request.form.get("host", "0.0.0.0")
ngl = request.form.get("ngl", "99")
ctx_size = request.form.get("ctx_size", "16384")
batch_size = request.form.get("batch_size", "512")
ubatch_size = request.form.get("ubatch_size", "128")
main_gpu = request.form.get("main_gpu", "0")
tensor_split = request.form.get("tensor_split", "1,0.4")
flash_attn = request.form.get("flash_attn", "on")
parallel = request.form.get("parallel", "1")
cont_batching = request.form.get("cont_batching", "true")

command = f"""{LLAMA_CPP_PATH} \
-m {MODEL_DIR}/{model} \
--ctx-size {ctx_size} \
--n-gpu-layers {ngl} \
--main-gpu {main_gpu} \
--tensor-split {tensor_split} \
--flash-attn {flash_attn} \
--batch-size {batch_size} \
--ubatch-size {ubatch_size} \
--port {port} \
--host {host} \
--parallel {parallel} \
--slot-save-path {SLOTS_DIR} \
{"--cont-batching" if cont_batching == "true" else ""}
"""
```

### 5. Update HTML Form (templates/index.html)

**Remove CUDA-specific parameters:**
- Line 73-78: Split Mode dropdown (not applicable to Vulkan tensor-split)

**Add Vulkan-specific parameters:**

```html
<!-- Model Parameters Column - Update existing -->
<div>
    <label class="block text-left mb-1">Context Size</label>
    <input type="number" id="ctx_size" name="ctx_size" form="modelForm" value="16384" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
</div>

<div>
    <label class="block text-left mb-1">GPU Layers</label>
    <input type="number" id="ngl" name="ngl" form="modelForm" value="99" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
</div>

<!-- Advanced Settings Column - Replace split mode with tensor-split -->
<div>
    <label class="block text-left mb-1">Main GPU</label>
    <select id="main_gpu" name="main_gpu" form="modelForm" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
        <option value="0">GPU 0 (RX 480)</option>
        <option value="1">GPU 1 (RX 6600)</option>
    </select>
</div>

<div>
    <label class="block text-left mb-1">Tensor Split (GPU0,GPU1)</label>
    <input type="text" id="tensor_split" name="tensor_split" form="modelForm" value="1,0.4" class="w-full bg-gray-700 text-white p-2 rounded mb-3" placeholder="1,0.4">
</div>

<div>
    <label class="block text-left mb-1">Batch Size</label>
    <input type="number" id="batch_size" name="batch_size" form="modelForm" value="512" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
</div>

<div>
    <label class="block text-left mb-1">UBatch Size</label>
    <input type="number" id="ubatch_size" name="ubatch_size" form="modelForm" value="128" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
</div>

<div>
    <label class="block text-left mb-1">Flash Attention</label>
    <select id="flash_attn" name="flash_attn" form="modelForm" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
        <option value="on">On</option>
        <option value="off">Off</option>
    </select>
</div>

<div>
    <label class="block text-left mb-1">Parallel Sequences</label>
    <input type="number" id="parallel" name="parallel" form="modelForm" value="1" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
</div>

<div>
    <label class="block text-left mb-1">Continuous Batching</label>
    <select id="cont_batching" name="cont_batching" form="modelForm" class="w-full bg-gray-700 text-white p-2 rounded mb-3">
        <option value="true">Enabled</option>
        <option value="false">Disabled</option>
    </select>
</div>
```

### 6. Update GPU Stats Display (templates/index.html lines 88-94)

**Update the display to show AMD-specific metrics:**

```html
<div class="bg-gray-800 p-6 rounded-lg shadow-lg mt-4">
    <h2 class="text-xl font-bold mb-2">GPU Usage (AMD Radeon)</h2>
    <div id="gpu-stats" class="text-sm grid grid-cols-1 sm:grid-cols-2 gap-4">
        Loading...
    </div>
</div>
```

**Update JavaScript rendering (around line 143-151):**

```javascript
gpus.forEach(gpu => {
    gpuContainer.innerHTML += `
        <div class="p-3 bg-gray-700 rounded">
            <p><strong>${gpu.name} (${gpu.index})</strong></p>
            <p>Temp: ${gpu.temp} | Usage: ${gpu.usage}</p>
            <p>Power: ${gpu.power}</p>
            ${gpu.memory ? `<p>Memory: ${gpu.memory}</p>` : ''}
        </div>
    `;
});
```

### 7. Update Documentation (README.md)

**Changes needed:**

- Line 44-45: Change "CUDA support" to "Vulkan support"
- Line 45: Change "NVIDIA GPU(s)" to "AMD/NVIDIA/Intel GPU(s) with Vulkan support"
- Lines 162-172: Update troubleshooting section for AMD GPUs
- Add section on verifying Vulkan installation

**Add Vulkan verification section:**

```markdown
## Verifying Vulkan Support

Before using this controller, verify your Vulkan installation:

```bash
# Check Vulkan devices
vulkaninfo | grep deviceName

# List available compute devices in llama.cpp
/usr/local/bin/llama-cli --list-devices

# Expected output:
# ggml_vulkan: Found 2 Vulkan devices:
# ggml_vulkan: 0 = AMD Radeon RX 480 ...
# ggml_vulkan: 1 = AMD Radeon RX 6600 ...
```
```

## Implementation Order

1. **Phase 1: Basic Conversion (Core Functionality)**
   - Update configuration paths (Task 1)
   - Remove CUDA environment variables (Task 3)
   - Update command generation for basic Vulkan support (Task 4)
   - Test with single model

2. **Phase 2: GPU Monitoring**
   - Implement AMD GPU monitoring (Task 2)
   - Update frontend display (Task 6)
   - Test monitoring accuracy

3. **Phase 3: Advanced Features**
   - Add all advanced parameters to UI (Task 5)
   - Add model presets/profiles
   - Test multi-GPU tensor-split configurations

4. **Phase 4: Documentation & Polish**
   - Update README (Task 7)
   - Add troubleshooting for AMD-specific issues
   - Create example configurations

## Testing Checklist

- [ ] llama-server starts successfully with Vulkan
- [ ] Model loads on both GPUs with tensor-split
- [ ] GPU monitoring shows accurate temperature/usage
- [ ] Server logs display correctly in web UI
- [ ] Can start/stop models without orphaned processes
- [ ] Cache cleanup works correctly
- [ ] Flash attention enabled/disabled works
- [ ] Continuous batching works
- [ ] Different batch sizes work
- [ ] Port/host configuration works
- [ ] Model switching works without restart

## Potential Issues & Solutions

### Issue 1: GPU Detection
**Problem**: GPUs not detected or wrong order
**Solution**: Check `/sys/class/drm/` card mapping, may need to adjust card IDs in code

### Issue 2: VRAM Monitoring
**Problem**: Can't easily read VRAM usage from sysfs
**Solution**: Parse from llama-server logs (it reports VRAM allocation on startup)

### Issue 3: Tensor Split Not Working
**Problem**: Improper tensor split causing OOM or poor performance
**Solution**: Adjust split ratio based on actual VRAM (RX 480 has more VRAM, gets higher ratio)

### Issue 4: Flash Attention Compatibility
**Problem**: Flash attention may not work with all GPU/driver combinations
**Solution**: Add toggle in UI, detect if it fails and suggest disabling

### Issue 5: Performance Lower Than Expected
**Problem**: Not matching direct command-line performance
**Solution**:
- Verify all parameters match working config
- Check for lingering processes (`pkill -9 -f llama-server`)
- Ensure GPU tweaks from start_model.sh are applied
- Monitor for thermal throttling

## Advanced Features (Future)

- **GPU Tweak Integration**: Run the GPU optimization commands from start_model.sh before model start
- **Model Profiles**: Save different configurations per model
- **Auto-tuning**: Automatically determine optimal tensor-split based on model size
- **Performance Metrics**: Track tokens/sec, display in dashboard
- **Multi-Model Support**: Run multiple models on different ports
- **Benchmark Mode**: Run standardized prompts to test performance

## Dependencies

### Python Packages
```bash
pip install flask
```

### System Tools (for GPU monitoring)

**Option 1: sysfs only (no additional deps)**
- Already available on Linux

**Option 2: radeontop**
```bash
sudo pacman -S radeontop  # Arch/Manjaro
sudo apt install radeontop  # Debian/Ubuntu
```

**Option 3: nvtop with JSON support**
```bash
sudo pacman -S nvtop  # Already installed based on usage
```

## File Changes Summary

| File | Lines Changed | Description |
|------|--------------|-------------|
| app.py | 23-27 | Update config paths |
| app.py | 44-62 | Replace nvidia-smi with AMD GPU monitoring |
| app.py | 144 | Remove CUDA env var |
| app.py | 106-222 | Update command generation and parameters |
| templates/index.html | 39-85 | Update form parameters |
| templates/index.html | 88-151 | Update GPU stats display |
| README.md | Multiple | Update documentation for Vulkan/AMD |

## Notes

- The existing log streaming functionality should work as-is
- Cache clearing mechanism works the same
- Process management (start/stop) unchanged
- Port configuration unchanged
- The UI framework (Flask + Tailwind) requires no changes

## Success Criteria

The conversion is successful when:

1. Can start models from web UI matching current CLI performance
2. GPU monitoring shows accurate real-time stats for both AMD GPUs
3. All parameters from working config are configurable via UI
4. Server logs stream to browser in real-time
5. Can switch between models without manual intervention
6. No performance degradation vs direct command-line usage
