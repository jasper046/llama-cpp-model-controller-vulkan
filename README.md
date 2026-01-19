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

1.  **Clone and Install:**
    ```bash
    git clone https://github.com/Dan-Duran/llama-cpp-model-controller.git
    cd llama-cpp-model-controller
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configure GPUs:**
    Run the interactive script to detect your GPUs and create the `config.json` file.
    ```bash
    chmod +x ./gpu_autodetect_and_config.sh
    ./gpu_autodetect_and_config.sh
    ```

3.  **Start the Controller:**
    ```bash
    python app.py
    ```
    Access the web UI at `http://localhost:5000`.

## ⚙️ Configuration

The application is configured via `config.json`. The recommended way to create and configure this file is by using the auto-detection script.

### Recommended Method: GPU Auto-Detection Script

For users on Linux, a helper script is provided to automate the detection of Vulkan devices and system paths. This is the easiest and most reliable way to configure your GPUs.

1.  **Make the script executable:**
    ```bash
    chmod +x ./gpu_autodetect_and_config.sh
    ```

2.  **Run the script:**
    ```bash
    ./gpu_autodetect_and_config.sh
    ```

The script will interactively guide you through:
- Detecting all available GPUs recognized by Vulkan.
- Letting you choose which GPUs to use.
- Asking you to assign tensor weights for splitting models across multiple GPUs.
- Prompting you to select a primary GPU for the model.
- Automatically generating a `config.json` file with the correct GPU settings and default parameters.

After running the script, your `config.json` will be ready to use.

### Manual GPU Configuration (Alternative)

If the script does not work for your system, or if you prefer a manual setup, you can create the `config.json` file by hand.

1.  **Copy the template:**
    ```bash
    cp config_template.json config.json
    ```
2.  **Edit `config.json`:**
    You will need to manually fill out the `gpu_configuration` and `model_configuration` sections.

#### Finding GPU Information

-   **List PCI devices** to see your GPUs: `lspci | grep -i vga`
-   **Get Vulkan device ID**: Use `vulkaninfo | grep deviceName` or `llama-cli --list-devices`. The script uses `llama-cli`.
-   **Find sysfs path**: It's typically `/sys/class/drm/card0`, `/sys/class/drm/card1`, etc. The `cardX` number usually corresponds to the GPU's order on the PCIe bus.
-   **Find hwmon path**: Look inside the `sysfs` path for an `hwmon` directory, like `hwmon/hwmon5`.

#### `config.json` Structure

Here are the key sections to customize in `config.json`:

-   `gpu_configuration`: Defines the GPUs available to the controller.
    -   `gpu_cards`: A list of your GPUs. Each GPU needs a `card_id` (from `sysfs`), a `display_name`, and its `vulkan_id`.
-   `model_configuration`: Sets paths for the `llama-server` executable and model files.
-   `default_parameters`:
    -   `main_gpu`: The `vulkan_id` of the primary GPU.
    -   `tensor_split`: Comma-separated values for distributing model layers across GPUs, ordered by `vulkan_id`.

**Example `gpu_configuration`:**
```json
"gpu_configuration": {
  "gpu_cards": [
    {
      "card_id": "card1",
      "display_name": "RX 470",
      "vulkan_id": 1,
      "sysfs_base": "/sys/class/drm/card1/device",
      "hwmon_pattern": "hwmon/hwmon*"
    },
    {
      "card_id": "card2",
      "display_name": "RX 6600",
      "vulkan_id": 0,
      "sysfs_base": "/sys/class/drm/card2/device",
      "hwmon_pattern": "hwmon/hwmon*"
    }
  ]
}
```

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
