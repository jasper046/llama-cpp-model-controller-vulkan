#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for configuration file
if [ ! -f "config.json" ]; then
    echo "Error: config.json not found."
    echo "Please run: ./gpu_autodetect_and_config.sh"
    echo "Then test with: ./test_config.sh"
    exit 1
fi

# Set ROCm environment variables for MI50
# For MI50 (gfx906): HSA_OVERRIDE_GFX_VERSION=9.0.6
# HIP_VISIBLE_DEVICES=1 to use only MI50 (device 1)
export HSA_OVERRIDE_GFX_VERSION=9.0.6
export HIP_VISIBLE_DEVICES=1
export ROCBLAS_USE_HIPBLASLT=1

echo "ROCm environment variables set:"
echo "  HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION"
echo "  HIP_VISIBLE_DEVICES=$HIP_VISIBLE_DEVICES"
echo "  ROCBLAS_USE_HIPBLASLT=$ROCBLAS_USE_HIPBLASLT"

VENV_DIR="venv"

# Check if the virtual environment directory exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        exit 1
    fi
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# Install/update requirements
echo "Installing requirements..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements."
    exit 1
fi

# Start the application
echo "Starting the application..."
python app.py
