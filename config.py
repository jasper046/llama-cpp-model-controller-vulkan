import os
import json

HOME_DIR = os.path.expanduser("~")

# Try to load from config.json first, fall back to defaults
CONFIG_JSON_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Default values (will be overridden by config.json if it exists)
LLAMA_CPP_PATH = "/home/cotg/llmstuff/llama.cpp/build-rocm/bin/llama-server"
MODEL_DIR = os.path.join(HOME_DIR, "models")
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
SLOTS_DIR = "/tmp/llama_slots"

# Default GPU cards (will be overridden by config.json)
# MI50-only configuration
GPU_CARDS = [
    # Format: (sysfs_card_id, display_name, rocm_device_id)
    ("card2", "AMD Radeon Graphics (MI50)", 1),    # card2 = MI50 = ROCm device 1
]

# Environment variables for ROCm
# For MI50-only: HSA_OVERRIDE_GFX_VERSION=9.0.6, HIP_VISIBLE_DEVICES=1
ROCM_ENV_VARS = {
    "HSA_OVERRIDE_GFX_VERSION": "9.0.6",
    "HIP_VISIBLE_DEVICES": "1",
    "ROCBLAS_USE_HIPBLASLT": "1"
}

# Load from config.json if it exists
if os.path.exists(CONFIG_JSON_PATH):
    try:
        with open(CONFIG_JSON_PATH, 'r') as f:
            config_data = json.load(f)
        
        # Update llama_cpp_path from config.json
        if 'model_configuration' in config_data and 'llama_cpp_path' in config_data['model_configuration']:
            LLAMA_CPP_PATH = config_data['model_configuration']['llama_cpp_path']
        
        # Update GPU cards from config.json
        if 'gpu_configuration' in config_data and 'gpu_cards' in config_data['gpu_configuration']:
            GPU_CARDS = []
            for gpu in config_data['gpu_configuration']['gpu_cards']:
                GPU_CARDS.append((
                    gpu['card_id'],
                    gpu['display_name'],
                    gpu['rocm_id']
                ))
        
        print(f"Loaded configuration from {CONFIG_JSON_PATH}")
        print(f"GPU cards: {GPU_CARDS}")
        print(f"llama_cpp_path: {LLAMA_CPP_PATH}")
        
        # Set ROCm environment variables based on GPU configuration
        # If we have MI50 only, use 9.0.6 and device 1
        if len(GPU_CARDS) == 1 and GPU_CARDS[0][2] == 1:  # Single GPU, ROCm ID 1 (MI50)
            ROCM_ENV_VARS = {
                "HSA_OVERRIDE_GFX_VERSION": "9.0.6",
                "HIP_VISIBLE_DEVICES": "1",
                "ROCBLAS_USE_HIPBLASLT": "1"
            }
        # TODO: Add logic for other GPU configurations
        
    except Exception as e:
        print(f"Error loading config.json: {e}")
        print("Using default configuration")
