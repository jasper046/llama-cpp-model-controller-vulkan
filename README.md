# Llama.cpp Model Controller (Vulkan Edition) 🦙

## 🎯 Status Report

**Vulkan Conversion: COMPLETE** ✅

This is a Vulkan-enabled fork of [Dan-Duran's Llama.cpp Model Controller](https://github.com/Dan-Duran/llama-cpp-model-controller). The original CUDA-only implementation has been successfully converted to support AMD GPUs via Vulkan backend, enabling multi-GPU and mixed GPU configurations.

**What Changed:**
- ✅ **Backend**: CUDA → Vulkan command generation
- ✅ **GPU Monitoring**: nvidia-smi → AMD sysfs (temperature, power, usage)
- ✅ **Configuration**: Centralized config file for easy customization
- ✅ **Parameters**: Full Vulkan parameter support (tensor-split, flash attention, continuous batching, etc.)
- ✅ **UI**: Updated form controls for Vulkan-specific settings

**Current Status:** Code conversion complete, ready for testing on target hardware with RX 470 + RX 6600.

---

## 🚀 Quick Start

### 1. Clone and setup
```bash
git clone https://github.com/Dan-Duran/llama-cpp-model-controller.git
cd llama-cpp-model-controller
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure paths
Edit `config.py` to match your environment:
- `LLAMA_CPP_PATH`: Path to Vulkan-compiled llama-server
- `MODEL_DIR`: Directory containing your GGUF models
- `GPU_CARDS`: Update GPU card IDs and names (check `/sys/class/drm/`)

### 3. Start the controller
```bash
source venv/bin/activate
python app.py
```
Access the web UI at `http://localhost:5000`

### 4. Deploy your first model
1. Select a GGUF model from the dropdown
2. Use default parameters or customize as needed
3. Click "Start Model"
4. Access the model at `http://localhost:4000`

---

The Llama.cpp Model Controller is an intuitive web interface for managing local LLM deployments powered by llama.cpp. This application streamlines the process of starting, monitoring, and stopping language models through a clean, responsive UI, eliminating the need for complex command-line operations.

Key features include real-time GPU monitoring with temperature, power, and usage statistics for AMD GPUs, color-coded live server logs showing token usage and model output, and customizable Vulkan deployment parameters. Users can easily configure context size, GPU layers, tensor-split ratios, and advanced options like flash attention and continuous batching for optimal performance on their hardware.

## 📋 Requirements

- Linux environment with Vulkan support
- AMD/NVIDIA/Intel GPU(s) with Vulkan drivers
- Python 3.8+
- llama.cpp compiled with Vulkan support
- GGUF format models

### Determining GPU PCIe Slots and Card IDs

Before configuring the controller, you need to identify your GPU PCIe slots and corresponding card IDs:

```bash
# 1. List all PCIe devices and find your GPUs
lspci | grep -i vga

# Example output:
# 65:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Ellesmere [Radeon RX 470/480/570/570X/580/580X/590] (rev cf)
# b5:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi 23 [Radeon RX 6600/6600 XT/6600M] (rev c7)

# 2. Check which card IDs correspond to which PCIe slots
ls -la /sys/class/drm/card*

# Example output showing card1 and card2 exist:
# lrwxrwxrwx 1 root root 0 Jan 15 07:03 /sys/class/drm/card1 -> ../../devices/pci0000:00/0000:00:08.1/0000:03:00.0/drm/card1
# lrwxrwxrwx 1 root root 0 Jan 15 07:03 /sys/class/drm/card2 -> ../../devices/pci0000:00/0000:00:08.1/0000:03:00.0/drm/card2

# 3. Match card IDs to PCIe slots (optional but helpful for debugging)
for card in /sys/class/drm/card*; do
    if [ -d "$card/device" ]; then
        echo "Card: $(basename $card)"
        cat "$card/device/uevent" | grep PCI_SLOT_NAME
    fi
done

# Example output:
# Card: card1
# PCI_SLOT_NAME=0000:65:00.0
# Card: card2
# PCI_SLOT_NAME=0000:b5:00.0

# 4. Update config.py with your findings
# Edit config.py and update GPU_CARDS:
# GPU_CARDS = [
#     ("card1", "RX 470", 1),    # card1 = RX 470 = Vulkan device 1
#     ("card2", "RX 6600", 0)    # card2 = RX 6600 = Vulkan device 0
# ]
```

**Important Notes:**
- Card IDs (card0, card1, card2, etc.) may vary between systems
- The order in `/sys/class/drm/` determines the card ID, not the PCIe slot
- Vulkan device IDs are assigned by llama.cpp and may differ from card IDs
- Always verify with `llama-cli --list-devices` after determining card IDs

### Verifying Vulkan Support

Before using this controller, verify your Vulkan installation:

```bash
# Check Vulkan devices
vulkaninfo | grep deviceName

# List available compute devices in llama.cpp
/usr/local/bin/llama-cli --list-devices

# Expected output for dual AMD setup (order may vary):
# ggml_vulkan: Found 2 Vulkan devices:
# ggml_vulkan: 0 = AMD Radeon RX 6600 ...
# ggml_vulkan: 1 = AMD Radeon RX 470 Graphics ...
```

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Dan-Duran/llama-cpp-model-controller.git
cd llama-cpp-model-controller
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up model directory

By default, the application looks for models in a `models` directory. Make sure your GGUF models are placed there:

```bash
mkdir -p models
# Copy or download your GGUF models to the models directory
```

### 5. Configure the application

Edit `config.py` to customize the paths and GPU configuration:

```python
import os

HOME_DIR = os.path.expanduser("~")
LLAMA_CPP_PATH = "/usr/local/bin/llama-server"  # Path to Vulkan-compiled llama-server
MODEL_DIR = os.path.join(HOME_DIR, "models")    # Directory containing GGUF models
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
SLOTS_DIR = "/tmp/llama_slots"                  # Will be created automatically

# Update card IDs, names, and Vulkan device IDs based on your system
# Format: (sysfs_card_id, display_name, vulkan_device_id)
# Use `llama-cli --list-devices` to see Vulkan device order
GPU_CARDS = [
    ("card1", "RX 470", 1),    # Ellesmere [Radeon RX 470/480/570...] = Vulkan device 1
    ("card2", "RX 6600", 0)    # Navi 23 [Radeon RX 6600/6600 XT/6600M] = Vulkan device 0
]
```

You can modify these values to match your specific environment:
- `LLAMA_CPP_PATH`: Path to your Vulkan-compiled llama-server executable
- `MODEL_DIR`: Where your GGUF models are stored
- `CACHE_DIR`: Where llama.cpp stores its cache files
- `SLOTS_DIR`: Directory for saving conversation slots
- `GPU_CARDS`: List of GPU cards with sysfs ID, display name, and Vulkan device ID


## 🖥️ Usage

### Starting the Web UI

```bash
python app.py
```

The web interface will be available at `http://localhost:5000` by default.

### Deploying a Model

1. Select a model from the dropdown menu
2. Configure the parameters (or use the defaults)

   **Model Parameters:**
   - **GPU Layers**: Number of layers to offload to GPU (default: 99)
   - **Context Size**: Token context window size (default: 16384)
   - **Port**: Server port (default: 4000)
   - **Host**: Server host (default: 0.0.0.0)

   **Advanced Settings:**
   - **Main GPU**: Primary GPU for computation (Vulkan device ID, matches llama-cli --list-devices output)
   - **Tensor Split**: Ratio for distributing model across GPUs in Vulkan device order (default: 1,0.4)
   - **Batch Size**: Processing batch size (default: 512)
   - **UBatch Size**: Micro-batch size (default: 128)
   - **Flash Attention**: Enable/disable flash attention optimization
   - **Parallel Sequences**: Number of parallel sequences (default: 1)
   - **Continuous Batching**: Enable continuous batching for better throughput

3. Click "Start Model"
4. The model will be available at the configured host:port (default: http://0.0.0.0:4000)

### Monitoring

- The **GPU Usage** section shows real-time AMD GPU statistics:
  - Temperature (°C)
  - GPU utilization (%)
  - Power consumption (W)
- The **Server Logs** section displays real-time output from the llama-server process
- Color-coded logs help identify errors, warnings, and token usage information

### Stopping a Model

Click the "Stop Model" button to terminate the server and clear the cache.

## 📁 Project Structure

```
llama-cpp-model-controller-vulkan/
├── app.py                  # Flask application
├── config.py               # Configuration file (paths, GPU settings)
├── templates/              # HTML templates
│   └── index.html          # Main UI template
├── models/                 # GGUF model files (not included in repo)
├── venv/                   # Python virtual environment
├── VULKAN_CONVERSION_GAMEPLAN.md  # Original conversion plan
├── VULKAN_TODO.md          # Detailed implementation checklist
└── CONVERSION_SUMMARY.md   # Summary of changes made
```

## ⚙️ Advanced Configuration

### Custom Port

To change the port the web UI runs on, modify the last line in `app.py`:

```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

### Adding Model Presets

You can create preset configurations for each model by modifying the HTML template.

## 🧪 Testing

The project includes test scripts to verify the GPU monitoring architecture:

```bash
# Navigate to the testscripts directory
cd testscripts

# Test 1: GPU monitor with caching architecture
python3 test_gpu_monitor.py

# Test 2: Full separated architecture (backend collector + monitor)
python3 test_separated_architecture.py
```

**What the tests verify:**
1. **Backend Collector** (`gpu_collector.py`): Pure data collection from sysfs
2. **GPU Monitor** (`gpu_monitor.py`): Caching and background service
3. **Integration**: Full pipeline from collection to caching to serving

**Architecture Overview:**
- `gpu_collector.py`: Backend - pure data collection, no caching
- `gpu_monitor.py`: Middleware - caching, background updates, thread safety
- `app.py`: Frontend - serves cached data via Flask API

This separation ensures:
- Frontend requests are fast (cached data)
- Backend errors don't break the UI (default values provided)
- Heavy operations are decoupled from serving

## 🔧 Troubleshooting

### Common Issues

1. **Model fails to load**
   - Ensure you have enough GPU VRAM (check llama-server logs)
   - Try reducing context size or using fewer GPU layers
   - Check model file permissions
   - Verify the `MODEL_DIR` path in `config.py` is correct and models exist there

2. **GPU not detected**
   - Verify Vulkan installation: `vulkaninfo | grep deviceName`
   - Check that llama.cpp was compiled with Vulkan support
   - Run `llama-cli --list-devices` to see available GPUs
   - Ensure AMD GPU drivers are properly installed

3. **GPU stats not showing**
   - Verify GPU card IDs in `config.py` match your system
   - Check card mapping: `ls -la /sys/class/drm/`
   - Ensure you have read permissions for `/sys/class/drm/card*/device/`
   - For AMD GPUs: card1 and card2 typically correspond to physical GPUs

4. **Out of memory errors**
   - Reduce context size (try 8192 or 4096)
   - Use a smaller quantized model (Q4 instead of Q8)
   - Adjust tensor-split ratio to favor the GPU with more VRAM
   - Reduce batch size and ubatch size

5. **Flash attention issues**
   - Flash attention may not work on all AMD GPU/driver combinations
   - Try disabling it in the UI if you encounter errors
   - Check llama-server logs for flash attention related warnings

6. **Tensor split not working as expected**
   - Ensure format is comma-separated (e.g., "1,0.4")
   - First value typically goes to main GPU
   - Adjust based on actual VRAM capacity of each GPU
   - Check llama-server logs for actual VRAM allocation

7. **Llama-server executable not found**
   - Check that `LLAMA_CPP_PATH` in `config.py` points to your Vulkan-compiled llama-server
   - Verify llama.cpp was compiled with `-DGGML_VULKAN=ON`
   - Verify execution permissions: `chmod +x [path-to-llama-server]`

8. **Path configuration issues**
   - The application logs the paths it's using on startup - check these logs
   - Ensure all directories in `config.py` exist and are accessible
   - Update `config.py` to match your environment

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

## 🙏 Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) for the incredible optimized LLM implementation
- All the model creators and fine-tuners who make their work available
