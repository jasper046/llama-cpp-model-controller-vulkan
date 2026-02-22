# Llama.cpp Model Controller (ROCm Edition) 🦙

A web UI for managing and interacting with `llama.cpp` models, with a focus on supporting AMD GPUs via ROCm. This interface allows for easy loading/unloading of models, dynamic adjustment of parameters, and real-time monitoring of GPU performance.

This fork has been converted from the original CUDA-only implementation to support AMD GPUs, enabling multi-GPU and mixed-GPU configurations on the ROCm backend.

## Features
- **ROCm Backend**: Full support for `llama.cpp`'s ROCm features, including multi-GPU tensor splitting.
- **Web UI**: An intuitive interface for deploying models, adjusting parameters, and monitoring performance.
- **Automated GPU Configuration**: Includes a script to detect and configure your AMD GPUs automatically.
- **Real-time Monitoring**: Live stats for GPU temperature, utilization, and power draw.
- **Dynamic Parameters**: Adjust `ngl`, context size, batching, and other `llama.cpp` parameters on the fly.

## Getting Started

Follow these steps to get the application up and running.

### 1. Prerequisites
- **Python 3.8+**
- **ROCm SDK & Drivers**: Ensure your AMD drivers and the ROCm SDK are properly installed and functional. You can verify your setup with `rocminfo`.
- **llama.cpp**: A version of `llama.cpp` compiled with ROCm support (`-DGGML_HIP=ON`) must be installed on your system. The `llama-cli` executable should be in your `PATH` or at `/usr/local/bin/llama-cli`.
  
  **For mixed GPU systems (e.g., MI50 + RX 6600)**: You need to build llama.cpp with specific GPU targets:
  ```bash
  cd ~/llmstuff/llama.cpp
  mkdir -p build-rocm && cd build-rocm
  HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
    cmake .. -DGGML_HIP=ON -DAMDGPU_TARGETS="gfx906;gfx1030" \
    -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=ON
  cmake --build . --config Release -j $(nproc)
  ```

### 2. GPU Configuration
The repository includes a script to automatically detect your GPUs and create the necessary `config.json` file. This is the recommended first step.

```bash
# Make the script executable
chmod +x ./gpu_autodetect_and_config.sh

# For mixed GPU systems (e.g., MI50 + RX 6600), set environment variables:
export HSA_OVERRIDE_GFX_VERSION=9.0.0  # Needed for mixed Vega + RDNA2 systems
export ROCBLAS_USE_HIPBLASLT=1         # Enable hipBLASLt for better performance
export HIP_VISIBLE_DEVICES=0,1         # Make both GPUs visible

# Run the interactive configuration
./gpu_autodetect_and_config.sh
```
The script will guide you through selecting GPUs, assigning tensor weights, and choosing a primary GPU.

### 3. Test Configuration
After configuring your GPUs, test the configuration before starting the application:

```bash
# Test the configuration
./test_config.sh
```
The test script will verify:
1. Configuration file validity and required fields
2. llama-server executable availability and ROCm support
3. Sysfs GPU access permissions
4. Python dependencies (Flask)
5. Model directory setup

If any tests fail, the script will provide guidance on how to fix the issues.

### 4. Start the Application
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

### Configuration Testing
For any issues with the application, first run the configuration test script:
```bash
./test_config.sh
```
This will identify common problems like missing configuration files, incorrect paths, permission issues, or missing dependencies.

### Building llama.cpp with ROCm Support for Mixed GPU Systems
If you have a mixed GPU system (e.g., MI50 Vega 20 + RX 6600 Navi 23), you need to build llama.cpp with ROCm support:

```bash
# Navigate to llama.cpp directory
cd ~/llmstuff/llama.cpp

# Create build directory
mkdir -p build-rocm && cd build-rocm

# Configure with ROCm support for both GPUs
# gfx906 = MI50 (Vega 20)
# gfx1030 = RX 6600 (Navi 23) - using gfx1030 as compatible target
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
cmake .. \
  -DGGML_HIP=ON \
  -DAMDGPU_TARGETS="gfx906;gfx1030" \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_CURL=ON

# Build
cmake --build . --config Release -j $(nproc)

# Test ROCm detection (requires environment variables for mixed GPU systems)
export HSA_OVERRIDE_GFX_VERSION=9.0.0  # Needed for mixed Vega + RDNA2 systems
export ROCBLAS_USE_HIPBLASLT=1         # Enable hipBLASLt for better performance
export HIP_VISIBLE_DEVICES=0,1         # Make both GPUs visible

# Test GPU detection
./bin/llama-cli --list-devices
```

**Expected Output**:
```
ggml_cuda_init: found 2 ROCm devices:
  Device 0: AMD Radeon RX 6600, gfx900:xnack- (0x900), VMM: no, Wave Size: 32
  Device 1: AMD Radeon Graphics, gfx900:xnack- (0x900), VMM: no, Wave Size: 64
Available devices:
  ROCm0: AMD Radeon RX 6600 (8176 MiB, 8152 MiB free)
  ROCm1: AMD Radeon Graphics (32752 MiB, 32732 MiB free)
```

**Note**: 
1. Both GPUs show as `gfx900` due to `HSA_OVERRIDE_GFX_VERSION=9.0.0` which forces GFX9 (Vega) compatibility mode for mixed GPU systems.
2. The MI50 may be reported as "AMD Radeon Graphics" instead of "AMD Radeon Instinct MI50".
3. The GPU auto-configuration script may have difficulty matching PCIe card names with ROCm device names in mixed GPU systems. If this happens, you may need to manually edit `config.json` or use the existing configuration if one was created previously.

### GPU Not Detected or Mismatched
If the `gpu_autodetect_and_config.sh` script fails, it is often due to a driver-level issue where `llama-cli` reports incorrect device names.

1.  **Verify ROCm Devices**:
    ```bash
    # For mixed GPU systems, use HSA_OVERRIDE_GFX_VERSION
    HSA_OVERRIDE_GFX_VERSION=9.0.0 rocminfo
    ```
    This command shows the "true" device names as seen by ROCm.

2.  **Verify `llama-cli` Devices**:
    ```bash
    # For mixed GPU systems, use environment variables
    HSA_OVERRIDE_GFX_VERSION=9.0.0 ROCBLAS_USE_HIPBLASLT=1 llama-cli --list-devices
    ```
    Compare this output with `rocminfo`. If `llama-cli` is misreporting a GPU (e.g., showing an "Instinct MI50" as an "RX 6600"), this indicates an issue with `llama-cli` or its interaction with the driver, which the configuration script cannot work around.

### Other Common Issues
- **Model Fails to Load**: Ensure you have enough VRAM and that the model paths in `config.json` are correct.
- **GPU Stats Not Showing**: Verify that your `card_id` in `config.json` matches the directories in `/sys/class/drm/` and that you have the necessary read permissions.
- **`start.sh` Fails**: Make sure `python3` is installed and in your `PATH`.

## License
This project is licensed under the [MIT License](LICENSE).

## Acknowledgments
- [Dan-Duran](https://github.com/Dan-Duran/llama-cpp-model-controller) for the original project.
- The [llama.cpp](https://github.com/ggerganov/llama.cpp) team for their incredible work on LLM inference.
