# Llama.cpp Model Controller (Vulkan Edition) 🦙

A web UI for managing and interacting with `llama.cpp` models, with a focus on supporting AMD GPUs via Vulkan. This interface allows for easy loading/unloading of models, dynamic adjustment of parameters, and real-time monitoring of GPU performance.

This fork has been converted from the original CUDA-only implementation to support AMD GPUs, enabling multi-GPU and mixed-GPU configurations on the Vulkan backend.

## Features
- **Vulkan Backend**: Full support for `llama.cpp`'s Vulkan features, including multi-GPU tensor splitting.
- **Web UI**: An intuitive interface for deploying models, adjusting parameters, and monitoring performance.
- **Automated GPU Configuration**: Includes a script to detect and configure your AMD GPUs automatically.
- **Real-time Monitoring**: Live stats for GPU temperature, utilization, and power draw.
- **Dynamic Parameters**: Adjust `ngl`, context size, batching, and other `llama.cpp` parameters on the fly.

## Getting Started

Follow these steps to get the application up and running.

### 1. Prerequisites
- **Python 3.8+**
- **Vulkan SDK & Drivers**: Ensure your AMD drivers and the Vulkan SDK are properly installed and functional. You can verify your setup with `vulkaninfo`.
- **llama.cpp**: A version of `llama.cpp` compiled with Vulkan support (`-DGGML_VULKAN=ON`) must be installed on your system. The `llama-cli` executable should be in your `PATH` or at `/usr/local/bin/llama-cli`.

### 2. GPU Configuration
The repository includes a script to automatically detect your GPUs and create the necessary `config.json` file. This is the recommended first step.

```bash
# Make the script executable
chmod +x ./gpu_autodetect_and_config.sh

# Run the interactive configuration
./gpu_autodetect_and_config.sh
```
The script will guide you through selecting GPUs, assigning tensor weights, and choosing a primary GPU.

### 3. Start the Application
A startup script is provided to handle the Python virtual environment, install dependencies, and launch the web UI.

```bash
# Run the startup script
./start.sh
```
The script will automatically:
1. Create a Python virtual environment (`venv`) if it doesn't exist.
2. Activate the virtual environment.
3. Install all required dependencies from `requirements.txt`.
4. Start the Flask web server.

Once started, the web UI will be accessible at **`http://localhost:5000`**.

## Manual Configuration
If the auto-detection script fails, or if you prefer a manual setup, you can create the `config.json` file by hand.

1.  **Copy the template:**
    ```bash
    cp config_template.json config.json
    ```
2.  **Edit `config.json`:**
    You will need to manually fill out the `gpu_configuration` and `model_configuration` sections. Refer to the `config_template.json` for structure and comments.

## Troubleshooting

### GPU Not Detected or Mismatched
If the `gpu_autodetect_and_config.sh` script fails, it is often due to a driver-level issue where `llama-cli` reports incorrect device names.

1.  **Verify Vulkan Devices**:
    ```bash
    vulkaninfo | grep "deviceName"
    ```
    This command shows the "true" device names as seen by Vulkan.

2.  **Verify `llama-cli` Devices**:
    ```bash
    llama-cli --list-devices
    ```
    Compare this output with `vulkaninfo`. If `llama-cli` is misreporting a GPU (e.g., showing an "Instinct MI50" as an "RX 6600"), this indicates an issue with `llama-cli` or its interaction with the driver, which the configuration script cannot work around.

### Other Common Issues
- **Model Fails to Load**: Ensure you have enough VRAM and that the model paths in `config.json` are correct.
- **GPU Stats Not Showing**: Verify that your `card_id` in `config.json` matches the directories in `/sys/class/drm/` and that you have the necessary read permissions.
- **`start.sh` Fails**: Make sure `python3` is installed and in your `PATH`.

## License
This project is licensed under the [MIT License](LICENSE).

## Acknowledgments
- [Dan-Duran](https://github.com/Dan-Duran/llama-cpp-model-controller) for the original project.
- The [llama.cpp](https://github.com/ggerganov/llama.cpp) team for their incredible work on LLM inference.
