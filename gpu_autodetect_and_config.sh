#!/bin/bash

# GPU Auto-Detection and Configuration Script
# for llama.cpp Model Controller (ROCm Edition)
#
# This script detects AMD GPUs via ROCm and sysfs,
# then creates/updates config.json with user preferences
#
# COMPATIBILITY REQUIREMENTS:
# - Designed for Ubuntu Server and headless environments
# - Terminal-only interaction (no TUI libraries like whiptail/dialog)
# - Works via SSH sessions
# - Uses plain bash I/O (read -p, echo) and ANSI color codes
# - No graphical interfaces required

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.json"
CONFIG_TEMPLATE="${SCRIPT_DIR}/config_template.json"
BACKUP_FILE="${SCRIPT_DIR}/config.json.backup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
VERBOSE=false
DRY_RUN=false
LLAMA_CLI=""
ROCM_GPUS=()
SELECTED_ROCM_GPUS=()

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

# Function to check if two GPU model names refer to the same GPU
# Extracts key identifiers like "RX 6600", "RX 470", "MI50", etc.
gpu_models_match() {
    local model1="$1"
    local model2="$2"

    # Extract common identifiers: RX + number, R9 + number, MI + number, etc.
    local id1=$(echo "$model1" | grep -oE "(RX|R9|R7|R5|MI|WX|PRO)[[:space:]]*[0-9]+" | tr -d ' ')
    local id2=$(echo "$model2" | grep -oE "(RX|R9|R7|R5|MI|WX|PRO)[[:space:]]*[0-9]+" | tr -d ' ')

    # If both have identifiers, compare them
    if [[ -n "$id1" ]] && [[ -n "$id2" ]]; then
        [[ "$id1" == "$id2" ]] && return 0 || return 1
    fi

    # Extract codenames (e.g., VEGA20, NAVI23) if present in parentheses
    local codename1=$(echo "$model1" | grep -oP '\((RADV |VEGA|NAVI|GF|TU|AD)[0-9A-Z]+\)' | sed -E 's/^\((RADV |)//;s/\)$//')
    local codename2=$(echo "$model2" | grep -oP '\((RADV |VEGA|NAVI|GF|TU|AD)[0-9A-Z]+\)' | sed -E 's/^\((RADV |)//;s/\)$//')

    # If both have codenames, compare them
    if [[ -n "$codename1" ]] && [[ -n "$codename2" ]]; then
        if [[ "$codename1" == "$codename2" ]]; then
            return 0
        fi
    fi

    # Check for "Instinct" series (MI50, MI100, etc.)
    if [[ "$model1" == *"Instinct"* ]] && [[ "$model2" == *"Instinct"* ]]; then
        # Extract MI number from both
        local mi1=$(echo "$model1" | grep -oE "MI[0-9]+")
        local mi2=$(echo "$model2" | grep -oE "MI[0-9]+")
        if [[ -n "$mi1" ]] && [[ -n "$mi2" ]] && [[ "$mi1" == "$mi2" ]]; then
            return 0
        fi
    fi
    
    # Handle case where ROCm reports generic names like "AMD Radeon Graphics" for MI50
    # Check if one is "AMD Radeon Graphics" and the other contains "MI50" or "VEGA20"
    if [[ "$model1" == *"Radeon Graphics"* ]] && [[ "$model2" == *"MI50"* ]] || [[ "$model2" == *"VEGA20"* ]]; then
        return 0
    fi
    if [[ "$model2" == *"Radeon Graphics"* ]] && [[ "$model1" == *"MI50"* ]] || [[ "$model1" == *"VEGA20"* ]]; then
        return 0
    fi
    
    # Handle case where both have same architecture but different names
    # (e.g., both show as gfx900 due to HSA_OVERRIDE_GFX_VERSION=9.0.0)
    # If we can't match by name but both are AMD GPUs detected in the same system,
    # we should match them based on PCIe slot order or other heuristics
    # This is handled in the map_pcie_slots function

    # Fallback: check for partial match (one is substring of other)
    if [[ "$model1" == *"$model2"* ]] || [[ "$model2" == *"$model1"* ]]; then
        return 0
    fi

    # No match
    return 1
}

# Function to look up GPU model from PCI device ID
get_gpu_model_from_pci_id() {
    local vendor_device_id="$1"
    local device_id=$(echo "$vendor_device_id" | cut -d: -f2 | tr '[:lower:]' '[:upper:]')

    case "$device_id" in
        # AMD Instinct
        66A0) echo "AMD Radeon Instinct MI50 (VEGA20)" ;;
        66A1) echo "AMD Radeon Instinct MI50 (VEGA20)" ;;

        # AMD Navi (RDNA 2)
        73DF) echo "AMD Radeon RX 7900 XTX" ;;
        73E4) echo "AMD Radeon RX 7900 XT" ;;
        73FF) echo "AMD Radeon RX 6600/6600 XT/6600M" ;;
        73BF) echo "AMD Radeon RX 6800/6800 XT/6900 XT" ;;
        73EF) echo "AMD Radeon RX 6800 XT" ;;
        7360) echo "AMD Radeon RX 6750 XT" ;;
        7362) echo "AMD Radeon RX 6700 XT" ;;
        731F) echo "AMD Radeon RX 5700 XT" ;;
        7310) echo "AMD Radeon RX 5700" ;;

        # AMD Navi (RDNA 1)
        734F) echo "AMD Radeon RX 5500 XT 5500M" ;;
        7340) echo "AMD Radeon RX 5500" ;;
        7341) echo "AMD Radeon RX 5300" ;;

        # AMD Polaris
        67DF) echo "AMD Radeon RX 470/480/570/580" ;;
        67FF) echo "AMD Radeon RX 470/570" ;;
        67EF) echo "AMD Radeon RX 480/580" ;;
        683F) echo "AMD Radeon RX 590" ;;

        # AMD Lexa
        699F) echo "AMD Radeon 540/550X/RX 550" ;;
        6987) echo "AMD Radeon RX 550" ;;
        6985) echo "AMD Radeon RX 540X/550X" ;;

        # AMD Tonga
        6939) echo "AMD Radeon R9 380X" ;;
        6950) echo "AMD Radeon R9 285" ;;

        # AMD Hawaii
        67B0) echo "AMD Radeon R9 290X" ;;
        67A1) echo "AMD Radeon R9 290" ;;

        # AMD Baffin
        699E) echo "AMD Radeon RX 560D" ;;
        699D) echo "AMD Radeon RX 560" ;;

        # AMD Ellesmere
        67DF) echo "AMD Radeon RX 470/480/570/580" ;;
        67D7) echo "AMD Radeon RX 460" ;;

        # NVIDIA (example - can be expanded)
        1B80) echo "NVIDIA GeForce GTX 1080" ;;
        1E04) echo "NVIDIA GeForce RTX 2080" ;;
        2204) echo "NVIDIA GeForce RTX 3080" ;;

        # Intel (example - can be expanded)
        9A49) echo "Intel Iris Xe Graphics" ;;
        4680) echo "Intel Arc A770M" ;;

        *) echo "Unknown GPU (ID: $device_id)" ;;
    esac
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

GPU Auto-Detection and Configuration Script for llama.cpp Model Controller

OPTIONS:
    -v, --verbose    Enable verbose logging
    -d, --dry-run     Show what would be changed without making changes
    -h, --help        Show this help message

DESCRIPTION:
    This script detects AMD GPUs via ROCm and sysfs, then helps you configure
    them for use with llama.cpp model controller. It will create or update
    config.json with your GPU selections and tensor split preferences.

EXAMPLES:
    $0                           # Normal operation
    $0 --verbose                 # Show detailed information
    $0 --dry-run                 # Preview changes without applying

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Task 1.1: Check if llama-cli is available
check_llama_cli() {
    log_info "Checking for llama-cli..."
    
    # First check for ROCm-built llama-cli in common build locations
    local rocm_build_paths=(
        "/home/cotg/llmstuff/llama.cpp/build-rocm/bin/llama-cli"
        "/home/cotg/llmstuff/llama.cpp/build/bin/llama-cli"
        "/home/cotg/llmstuff/llama.cpp/build-rocm-simple/bin/llama-cli"
    )
    
    for build_path in "${rocm_build_paths[@]}"; do
        if [[ -f "$build_path" ]]; then
            LLAMA_CLI="$build_path"
            log_success "Found ROCm-built llama-cli at $build_path"
            return 0
        fi
    done
    
    # Then check standard locations
    if command -v llama-cli &> /dev/null; then
        LLAMA_CLI="llama-cli"
        log_success "Found llama-cli in PATH"
        return 0
    elif [[ -f "/usr/local/bin/llama-cli" ]]; then
        LLAMA_CLI="/usr/local/bin/llama-cli"
        log_success "Found llama-cli at /usr/local/bin/llama-cli"
        return 0
    elif [[ -f "/usr/bin/llama-cli" ]]; then
        LLAMA_CLI="/usr/bin/llama-cli"
        log_success "Found llama-cli at /usr/bin/llama-cli"
        return 0
    else
        log_error "llama-cli not found. Please install llama.cpp or add llama-cli to PATH."
        log_error "Expected locations:"
        log_error "  - ROCm build: /home/cotg/llmstuff/llama.cpp/build-rocm/bin/llama-cli"
        log_error "  - System: /usr/local/bin/llama-cli, /usr/bin/llama-cli, or in PATH"
        log_error "  - Or rebuild with: cd ~/llmstuff/llama.cpp && mkdir -p build-rocm && cd build-rocm"
        log_error "    HIPCXX=\"\$(hipconfig -l)/clang\" HIP_PATH=\"\$(hipconfig -R)\" cmake .. \\"
        log_error "      -DGGML_HIP=ON -DAMDGPU_TARGETS=\"gfx906;gfx1030\" \\"
        log_error "      -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=ON"
        log_error "    cmake --build . --config Release -j \$(nproc)"
        exit 1
    fi
}

# Task 1.2-1.4: Detect ROCm devices
detect_rocm_devices() {
    log_info "Detecting ROCm devices..."

    # Set ROCm environment variables for device detection
    # HSA_OVERRIDE_GFX_VERSION=9.0.0 is needed for MI50 (Vega 20) and mixed GPU systems
    # ROCBLAS_USE_HIPBLASLT=1 enables hipBLASLt for better performance
    local rocm_output=""
    
    # For mixed GPU systems (MI50 Vega 20 + RX 6600 Navi 23), we need HSA_OVERRIDE_GFX_VERSION=9.0.0
    # This forces GFX9 (Vega) compatibility mode for all GPUs
    log_verbose "Using ROCm environment: HSA_OVERRIDE_GFX_VERSION=9.0.0 ROCBLAS_USE_HIPBLASLT=1"
    rocm_output=$(HSA_OVERRIDE_GFX_VERSION=9.0.0 ROCBLAS_USE_HIPBLASLT=1 "$LLAMA_CLI" --list-devices 2>&1) || true
    
    # Check if we got any GPU devices in the output
    if [[ -n "$rocm_output" ]] && echo "$rocm_output" | grep -q -E "(AMD|Radeon|NVIDIA|GeForce|Intel|Arc)"; then
        log_verbose "Successfully detected GPUs with HSA_OVERRIDE_GFX_VERSION=9.0.0"
        log_verbose "ROCm device list output:"
        log_verbose "$rocm_output"
    else
        log_error "Failed to detect GPUs via ROCm with HSA_OVERRIDE_GFX_VERSION=9.0.0"
        log_error "Trying alternative HSA_OVERRIDE_GFX_VERSION values..."
        
        # Try alternative values
        local hsa_versions=("8.0.0" "10.0.0" "9.0.6" "")
        for hsa_version in "${hsa_versions[@]}"; do
            if [[ -n "$hsa_version" ]]; then
                log_verbose "Trying HSA_OVERRIDE_GFX_VERSION=$hsa_version"
                rocm_output=$(HSA_OVERRIDE_GFX_VERSION="$hsa_version" ROCBLAS_USE_HIPBLASLT=1 "$LLAMA_CLI" --list-devices 2>&1) || true
            else
                log_verbose "Trying without HSA_OVERRIDE_GFX_VERSION"
                rocm_output=$(ROCBLAS_USE_HIPBLASLT=1 "$LLAMA_CLI" --list-devices 2>&1) || true
            fi
            
            if [[ -n "$rocm_output" ]] && echo "$rocm_output" | grep -q -E "(AMD|Radeon|NVIDIA|GeForce|Intel|Arc)"; then
                log_verbose "Successfully detected GPUs with HSA_OVERRIDE_GFX_VERSION=${hsa_version:-not set}"
                break
            fi
        done
        
        if [[ -z "$rocm_output" ]] || ! echo "$rocm_output" | grep -q -E "(AMD|Radeon|NVIDIA|GeForce|Intel|Arc)"; then
            log_error "Failed to detect GPUs via ROCm"
            log_error "Make sure ROCm is properly installed and your GPUs are supported"
            log_verbose "Last attempt output:"
            log_verbose "$rocm_output"
            # Don't exit yet - continue to diagnostics
        else
            log_verbose "ROCm device list output:"
            log_verbose "$rocm_output"
        fi
    fi
    
    # Parse ROCm devices - use simpler approach to avoid issues
    local device_count=0
    
    # Save output to temp variable first
    local output="$rocm_output"
    
    # Process using file to avoid here-string issues
    local temp_file=$(mktemp)
    echo "$output" > "$temp_file"
    
    while IFS= read -r line; do
        # Parse ggml_cuda_init: lines (ROCm backend)
        if [[ $line =~ ggml_cuda_init:[[:space:]]+found[[:space:]]+([0-9]+)[[:space:]]+ROCm[[:space:]]+devices: ]]; then
            continue  # Skip header line
        fi
        
        # Parse device lines like: "  Device 0: AMD Radeon RX 6600, gfx900:xnack- (0x900), VMM: no, Wave Size: 32"
        if [[ $line =~ ^[[:space:]]+Device[[:space:]]+([0-9]+):[[:space:]]+(.+),[[:space:]]+gfx ]]; then
            local device_id="${BASH_REMATCH[1]}"
            local device_full_name="${BASH_REMATCH[2]}"
            
            # Clean up the device name - remove leading/trailing spaces
            local device_name=$(echo "$device_full_name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            
            if [[ $device_name =~ (AMD|Radeon|NVIDIA|GeForce|Intel|Arc) ]]; then
                log_verbose "Found GPU device (ggml_cuda_init): ID=$device_id, Name='$device_name'"
                ROCM_GPUS+=("$device_id:$device_name")
                ((device_count++)) || true
            fi
        fi
    done < "$temp_file"
    
    rm -f "$temp_file"
    
    # Fallback: try to parse "Available devices:" section if above failed
    if [[ ${#ROCM_GPUS[@]} -eq 0 ]]; then
        log_verbose "Trying alternative parsing for Available devices section..."
        
        while IFS= read -r line; do
            # Parse lines like: "  ROCm0: AMD Radeon RX 6600 (8176 MiB, 8152 MiB free)"
            if [[ $line =~ ^[[:space:]]+ROCm([0-9]+):[[:space:]]+(.+)$ ]]; then
                local device_id="${BASH_REMATCH[1]}"
                local device_full_name="${BASH_REMATCH[2]}"
                
                # Extract clean GPU name (remove memory info in parentheses)
                local device_name=$(echo "$device_full_name" | sed 's/ ([^)]*)[^)]*$//')
                device_name=$(echo "$device_name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                
                # Check if it's a GPU device
                if [[ $device_name =~ (AMD|Radeon|NVIDIA|GeForce|Intel|Arc) ]]; then
                    log_verbose "Found GPU device (ROCm): ID=$device_id, Name='$device_name'"
                    ROCM_GPUS+=("$device_id:$device_name")
                    ((device_count++)) || true
                fi
            fi
        done < <(echo "$rocm_output")
    fi

    # Third attempt: Generic parsing for any GPU vendor names
    if [[ ${#ROCM_GPUS[@]} -eq 0 ]]; then
        log_verbose "Trying generic GPU parsing..."

        while IFS= read -r line; do
            # Look for GPU vendor names anywhere in line
            if [[ $line =~ (AMD|Radeon|NVIDIA|GeForce|Intel|Arc) ]]; then
                # Try to extract device ID - look for number at beginning of line or before colon
                local device_id=""
                local device_name=""

                # Pattern 1: "  ROCm0: AMD Radeon ..." or "  HIP0: AMD Radeon ..."
                if [[ $line =~ ^[[:space:]]*(ROCm|HIP|Device|GPU)([0-9]+)[[:space:]]*:[[:space:]]*(.+) ]]; then
                    device_id="${BASH_REMATCH[2]}"
                    device_name="${BASH_REMATCH[3]}"
                # Pattern 2: "  0: AMD Radeon ..."
                elif [[ $line =~ ^[[:space:]]*([0-9]+)[[:space:]]*:[[:space:]]*(.+) ]]; then
                    device_id="${BASH_REMATCH[1]}"
                    device_name="${BASH_REMATCH[2]}"
                # Pattern 3: Any line with GPU vendor name
                else
                    # Use line number as pseudo ID
                    device_id="${#ROCM_GPUS[@]}"
                    device_name="$line"
                fi

                # Clean up device name - remove memory info in parentheses
                device_name=$(echo "$device_name" | sed 's/ ([^)]*)[^)]*$//' | sed 's/ *$//')

                log_verbose "Found GPU device (generic): ID=$device_id, Name=$device_name"
                ROCM_GPUS+=("$device_id:$device_name")
            fi
        done < <(echo "$rocm_output")
    fi

    if [[ ${#ROCM_GPUS[@]} -eq 0 ]]; then
        log_error "No GPU devices found via ROCm"
        log_error "Raw output from llama-cli --list-devices:"
        echo "$rocm_output" >&2

        # Run additional diagnostics
        log_info "Running additional diagnostics..."

        # Check for rocminfo
        if command -v rocminfo &> /dev/null; then
            log_info "Checking ROCm devices via rocminfo..."
            rocminfo_output=$(rocminfo 2>&1 | head -50)
            if [[ $? -eq 0 ]]; then
                log_verbose "rocminfo output (first 50 lines):"
                log_verbose "$rocminfo_output"
                if echo "$rocminfo_output" | grep -q "Agent"; then
                    log_info "rocminfo found ROCm agents"
                else
                    log_warn "rocminfo did not find any ROCm agents"
                fi
            fi
        else
            log_warn "rocminfo not found. Install ROCm for better diagnostics."
        fi

        # Check sysfs for GPU devices
        log_info "Checking sysfs for GPU devices..."
        local sysfs_gpus=($(ls -d /sys/class/drm/card[0-9]* 2>/dev/null | grep -v "card[0-9]*-" | sort -V))
        if [[ ${#sysfs_gpus[@]} -gt 0 ]]; then
            log_info "Found ${#sysfs_gpus[@]} GPU(s) in sysfs:"
            for gpu_path in "${sysfs_gpus[@]}"; do
                local card_name=$(basename "$gpu_path")
                local vendor_path="$gpu_path/device/vendor"
                local device_path="$gpu_path/device/device"
                local vendor_id="unknown"
                local device_id="unknown"

                if [[ -f "$vendor_path" ]]; then
                    vendor_id=$(cat "$vendor_path" 2>/dev/null | head -1 || echo "unknown")
                fi
                if [[ -f "$device_path" ]]; then
                    device_id=$(cat "$device_path" 2>/dev/null | head -1 || echo "unknown")
                fi

                log_info "  - $card_name: Vendor: $(printf '0x%04x' $((vendor_id)) 2>/dev/null || echo $vendor_id), Device: $(printf '0x%04x' $((device_id)) 2>/dev/null || echo $device_id)"
            done
        else
            log_warn "No GPU devices found in /sys/class/drm/"
        fi

        # Check user groups for GPU access
        log_info "Checking user permissions..."
        if groups | grep -q "render" || groups | grep -q "video"; then
            log_info "User is in render/video group(s)"
        else
            log_warn "User is NOT in 'render' or 'video' groups. GPU access may be limited."
            log_warn "Add your user to these groups: sudo usermod -aG render,video $USER"
        fi

        # MI50 + RX 6600 mixed system guidance
        log_info "MI50 (Vega 20) + RX 6600 (Navi 23) mixed system notes:"
        log_info "1. MI50 requires ROCm 5.x or later, RX 6600 requires ROCm 5.4+"
        log_info "2. HSA_OVERRIDE_GFX_VERSION=9.0.0 is needed for mixed GPU systems"
        log_info "3. MI50 is gfx906 (Vega 20), RX 6600 is gfx1032 (Navi 23)"
        log_info "4. Check dmesg for GPU initialization errors"
        log_info "5. Ensure llama.cpp is built with ROCm support: -DGGML_HIP=ON -DAMDGPU_TARGETS=\"gfx906;gfx1030\""

        log_error ""
        log_error "Possible solutions for mixed GPU system:"
        log_error "1. Ensure ROCm 6.2+ is properly installed: https://rocm.docs.amd.com"
        log_error "2. Use HSA_OVERRIDE_GFX_VERSION=9.0.0 for mixed Vega + RDNA2 systems"
        log_error "3. Rebuild llama.cpp with: -DGGML_HIP=ON -DAMDGPU_TARGETS=\"gfx906;gfx1030\""
        log_error "4. Check ROCm detects GPUs: HSA_OVERRIDE_GFX_VERSION=9.0.0 rocminfo"
        log_error "5. Run 'dmesg | grep -i amd' to check for GPU errors"
        log_error "6. For MI50 issues, try: HSA_OVERRIDE_GFX_VERSION=9.0.6"
        log_error "7. For RX 6600 issues, try: HSA_OVERRIDE_GFX_VERSION=10.3.2"

        exit 1
    fi
    
    log_success "Found ${#ROCM_GPUS[@]} GPU device(s) via ROCm"
}

# Task 2: PCIe Slot Mapping (with PCI ID-based matching)
map_pcie_slots() {
    log_info "Mapping GPUs to PCIe slots..."

    # Get all card directories (filter out display outputs like card0-DP-1)
    local card_dirs=($(ls -d /sys/class/drm/card[0-9]* 2>/dev/null | grep -v "card[0-9]*-" | sort -V))

    if [[ ${#card_dirs[@]} -eq 0 ]]; then
        log_error "No GPU card directories found in /sys/class/drm/"
        log_error "Make sure your GPU drivers are properly installed"
        exit 1
    fi

    log_verbose "Found card directories: ${card_dirs[*]}"

    # Create PCIe slot mapping with PCI ID lookup
    local pcie_mapping=()

    for card_dir in "${card_dirs[@]}"; do
        local card_name=$(basename "$card_dir")

        # Get PCIe slot from uevent (most reliable)
        local pcie_slot=$(grep "PCI_SLOT_NAME=" "$card_dir/device/uevent" 2>/dev/null | cut -d= -f2)

        if [[ -n "$pcie_slot" ]]; then
            # Extract PCI ID from uevent
            local pci_id=$(grep "PCI_ID=" "$card_dir/device/uevent" 2>/dev/null | cut -d= -f2)

            if [[ -n "$pci_id" ]]; then
                local gpu_model=$(get_gpu_model_from_pci_id "$pci_id")
                pcie_mapping+=("$card_name:$pcie_slot:$gpu_model")
                log_verbose "Mapped $card_name to PCIe slot $pcie_slot (PCI ID: $pci_id, Model: $gpu_model)"
            else
                log_warn "Could not extract PCI ID for $card_name"
                pcie_mapping+=("$card_name:$pcie_slot:unknown")
            fi
        else
            log_warn "Could not extract PCIe slot for $card_name"
            pcie_mapping+=("$card_name:unknown:unknown")
        fi
    done

    # Match cards to ROCm devices using GPU model names
    local gpu_config=()

    for card_mapping in "${pcie_mapping[@]}"; do
        local card_id=$(echo "$card_mapping" | cut -d: -f1)
        local pcie_slot=$(echo "$card_mapping" | cut -d: -f2)
        local card_gpu_model=$(echo "$card_mapping" | cut -d: -f3-)

        # Try to find matching ROCm device by GPU name
        local matched=false
        for rocm_gpu_info in "${ROCM_GPUS[@]}"; do
            local rocm_id=$(echo "$rocm_gpu_info" | cut -d: -f1)
            local rocm_gpu_name=$(echo "$rocm_gpu_info" | cut -d: -f2-)

            # Use smart matching function
            if gpu_models_match "$card_gpu_model" "$rocm_gpu_name"; then
                gpu_config+=("$card_id:$pcie_slot:$rocm_id:$rocm_gpu_name")
                log_verbose "Matched $card_id ($card_gpu_model) to ROCm ID $rocm_id ($rocm_gpu_name)"
                matched=true
                break
            fi
        done

        if [[ "$matched" == false ]]; then
            log_error "Could not match $card_id ($card_gpu_model) to any ROCm device."
            log_error "This usually indicates a problem with ROCm drivers reporting incorrect GPU names."
            exit 1
        fi
    done

    ROCM_GPUS=("${gpu_config[@]}")
    log_success "Mapped ${#ROCM_GPUS[@]} GPUs to PCIe slots"

    # Sort GPUs by ROCm ID so user sees them in ROCm order
    IFS=$'\n' ROCM_GPUS=($(sort -t: -k3 -n <<<"${ROCM_GPUS[*]}"))
    unset IFS
    log_verbose "GPUs sorted by ROCm ID for user interaction"
}

# Task 4: User Interaction
prompt_user_selection() {
    # In dry-run mode, use default selections
    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY-RUN: Using default GPU configuration"
        log_info "Would normally prompt for user input here..."
        
        # Auto-select all GPUs with default weights for dry-run
        local gpu_index=0
        for gpu_info in "${ROCM_GPUS[@]}"; do
            local card_id=$(echo "$gpu_info" | cut -d: -f1)
            local gpu_name=$(echo "$gpu_info" | cut -d: -f4-)
            
            # Default weights: first GPU is main, others are secondary
            local is_main="n"
            local tensor_weight="0.33"  # Default weight
            
            if [[ $gpu_index -eq 0 ]]; then
                is_main="y"
                tensor_weight="0.54"
            elif [[ $gpu_index -eq 1 ]]; then
                tensor_weight="0.13"
            fi
            
            SELECTED_ROCM_GPUS+=("$gpu_info|$is_main|$tensor_weight")
            log_info "DRY-RUN: Would select $card_id ($gpu_name) - main=$is_main, weight=$tensor_weight"
            ((gpu_index++)) || true
        done
        return 0
    fi
    
    log_info "Detected GPUs:"
    echo
    
    local index=0
    for gpu_info in "${ROCM_GPUS[@]}"; do
        local card_id=$(echo "$gpu_info" | cut -d: -f1)
        local pcie_slot=$(echo "$gpu_info" | cut -d: -f2)
        local rocm_id=$(echo "$gpu_info" | cut -d: -f3)
        local gpu_name=$(echo "$gpu_info" | cut -d: -f4-)
        
        echo "$((index+1)). $card_id (PCIe $pcie_slot) -> ROCm ID $rocm_id - $gpu_name"
        ((index++)) || true
    done
    
    echo
    log_info "Please configure the GPUs to include:"
    
    local temp_selected_gpus=()
    local temp_tensor_weights=()

    for gpu_info in "${ROCM_GPUS[@]}"; do
        local card_id=$(echo "$gpu_info" | cut -d: -f1)
        local gpu_name=$(echo "$gpu_info" | cut -d: -f4-)
        
        echo
        # Ask if GPU should be included
        local include_gpu=""
        while [[ "$include_gpu" != "y" && "$include_gpu" != "n" ]]; do
            read -p "Include $card_id ($gpu_name)? (y/n): " include_gpu
            include_gpu=$(echo "$include_gpu" | tr '[:upper:]' '[:lower:]')
            
            if [[ "$include_gpu" != "y" && "$include_gpu" != "n" ]]; then
                echo "Please enter 'y' or 'n'"
            fi
        done
        
        if [[ "$include_gpu" == "y" ]]; then
            # Ask for tensor weight
            local tensor_weight=""
            while true; do
                read -p "Tensor weight for $card_id (e.g., 0.54): " tensor_weight
                if [[ "$tensor_weight" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                    break
                else
                    echo "Please enter a positive number (e.g., 0.54, 1.0)"
                fi
            done
            
            temp_selected_gpus+=("$gpu_info")
            temp_tensor_weights+=("$tensor_weight")
            log_verbose "Added $card_id with weight $tensor_weight"
        fi
    done
    
    if [[ ${#temp_selected_gpus[@]} -eq 0 ]]; then
        log_error "No GPUs selected. At least one GPU must be selected."
        exit 1
    fi
    
    local main_gpu_index=0
    if [[ ${#temp_selected_gpus[@]} -gt 1 ]]; then
        echo
        log_info "Please select the main GPU from the list:"
        local i=0
        for gpu_info in "${temp_selected_gpus[@]}"; do
            local card_id=$(echo "$gpu_info" | cut -d: -f1)
            local gpu_name=$(echo "$gpu_info" | cut -d: -f4-)
            echo "$((i+1)). $card_id - $gpu_name"
            ((i++)) || true
        done
        
        local user_choice=""
        while true; do
            read -p "Enter the number of the main GPU (1-${#temp_selected_gpus[@]}): " user_choice
            if [[ "$user_choice" =~ ^[0-9]+$ ]] && [ "$user_choice" -ge 1 ] && [ "$user_choice" -le ${#temp_selected_gpus[@]} ]; then
                main_gpu_index=$((user_choice-1))
                break
            else
                echo "Invalid selection. Please enter a number between 1 and ${#temp_selected_gpus[@]}."
            fi
        done
    fi

    # Now, populate SELECTED_ROCM_GPUS in the format generate_config expects
    # Use | as delimiter since GPU names may contain colons
    local i=0
    for gpu_info in "${temp_selected_gpus[@]}"; do
        local is_main="n"
        if [[ $i -eq $main_gpu_index ]]; then
            is_main="y"
        fi
        
        local tensor_weight="${temp_tensor_weights[$i]}"
        SELECTED_ROCM_GPUS+=("$gpu_info|$is_main|$tensor_weight")
        ((i++)) || true
    done
    
    log_success "Selected ${#SELECTED_ROCM_GPUS[@]} GPU(s) for configuration"
}

# Task 5-6: Configuration Generation and Validation
generate_config() {
    log_info "Generating configuration..."
    
    # Check if config file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        if [[ ! -f "$CONFIG_TEMPLATE" ]]; then
            log_error "Neither config.json nor config_template.json found!"
            log_error "Cannot create new configuration."
            exit 1
        fi
        
        log_info "Creating config.json from template..."
        cp "$CONFIG_TEMPLATE" "$CONFIG_FILE"
    else
        # Create backup
        if [[ "$DRY_RUN" != true ]]; then
            cp "$CONFIG_FILE" "$BACKUP_FILE"
            log_info "Created backup of existing config.json"
        fi
    fi
    
    # Sort selected GPUs by ROCm ID (so tensor split makes sense)
    IFS=$'\n' SORTED_ROCM_GPUS=($(sort -t: -k3 -n <<<"${SELECTED_ROCM_GPUS[*]}"))
    unset IFS

    # Generate GPU configuration in ROCm order
    local gpu_cards="["
    local tensor_parts=()
    local main_gpu_rocm_id=""

    local gpu_index=0
    for selected_gpu in "${SORTED_ROCM_GPUS[@]}"; do
        local card_id=$(echo "$selected_gpu" | cut -d'|' -f1 | cut -d: -f1)
        local pcie_slot=$(echo "$selected_gpu" | cut -d'|' -f1 | cut -d: -f2)
        local rocm_id=$(echo "$selected_gpu" | cut -d'|' -f1 | cut -d: -f3)
        local gpu_name=$(echo "$selected_gpu" | cut -d'|' -f1 | cut -d: -f4-)
        local is_main=$(echo "$selected_gpu" | cut -d'|' -f2)
        local tensor_weight=$(echo "$selected_gpu" | cut -d'|' -f3)
        
        # Add comma for all but first element
        if [[ $gpu_index -gt 0 ]]; then
            gpu_cards+=","
        fi
        
        # Generate GPU card entry
        gpu_cards+=$(cat << EOF
    {
      "card_id": "$card_id",
      "display_name": "$gpu_name",
      "rocm_id": $rocm_id,
      "sysfs_base": "/sys/class/drm/$card_id/device",
      "hwmon_pattern": "hwmon/hwmon*"
    }
EOF
)
        
        # Collect tensor weights
        tensor_parts+=("$tensor_weight")
        
        # Store main GPU ROCm ID (use first one found)
        if [[ "$is_main" == "y" && -z "$main_gpu_rocm_id" ]]; then
            main_gpu_rocm_id="$rocm_id"
        fi
        
        ((gpu_index++)) || true
    done
    
    gpu_cards+="]"
    
    # Generate tensor_split string
    local tensor_split=$(IFS=,; echo "${tensor_parts[*]}")
    
    # Debug: show tensor parts
    log_verbose "Tensor parts: ${tensor_parts[*]}"
    log_verbose "Tensor split: $tensor_split"
    
    # Validate tensor weights
    local total_weight=0
    for weight in "${tensor_parts[@]}"; do
        if [[ -n "$weight" ]] && [[ "$weight" =~ ^[0-9]*\.?[0-9]+$ ]]; then
            total_weight=$(echo "$total_weight + $weight" | bc -l 2>/dev/null || echo "$total_weight")
        else
            log_warn "Invalid tensor weight: '$weight'"
        fi
    done
    
    log_verbose "Total tensor weight: $total_weight"
    
    # Warn if total weight is not close to 1.0
    if [[ "$DRY_RUN" != true ]]; then
        local weight_diff=$(echo "scale=2; $total_weight - 1.0" | bc -l 2>/dev/null || echo "0")
        local abs_diff=$(echo "scale=2; sqrt($weight_diff^2)" | bc -l 2>/dev/null || echo "0")
        if (( $(echo "$abs_diff > 0.5" | bc -l 2>/dev/null) )); then
            log_warn "Total tensor weight ($total_weight) is significantly different from 1.0"
            log_warn "For optimal performance, tensor weights should sum to approximately 1.0"
            log_warn "Example: For 2 GPUs, use weights like 0.7 and 0.3 (sums to 1.0)"
        fi
    fi
    
    # Create updated config JSON (using python for proper JSON handling)
    local temp_config=$(mktemp)
    
    python3 << EOF
import json
import sys

# Load existing config
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)

# Update GPU configuration
config['gpu_configuration']['gpu_cards'] = json.loads('''$gpu_cards''')
config['default_parameters']['tensor_split'] = '$tensor_split'
config['default_parameters']['main_gpu'] = '$main_gpu_rocm_id'

# Write updated config
with open('$temp_config', 'w') as f:
    json.dump(config, f, indent=2)

print("Configuration updated successfully")
EOF
    
    if [[ "$DRY_RUN" != true ]]; then
        mv "$temp_config" "$CONFIG_FILE"
        log_success "Configuration saved to $CONFIG_FILE"
        log_info "Tensor split: $tensor_split"
        log_info "Main GPU ROCm ID: $main_gpu_rocm_id"
    else
        echo
        log_info "DRY RUN - Configuration that would be saved:"
        cat "$temp_config"
        rm "$temp_config"
        echo
        log_info "Would save to: $CONFIG_FILE"
        log_info "Tensor split: $tensor_split"
        log_info "Main GPU ROCm ID: $main_gpu_rocm_id"
    fi
}

# Main function
main() {
    echo "GPU Auto-Detection and Configuration Script"
    echo "for llama.cpp Model Controller (ROCm Edition)"
    echo "==============================================="
    echo
    
    parse_args "$@"
    
    log_verbose "Verbose mode enabled"
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Running in dry-run mode - no changes will be made"
    fi
    
    # Execute tasks
    check_llama_cli
    detect_rocm_devices
    map_pcie_slots
    prompt_user_selection
    generate_config
    
    echo
    if [[ "$DRY_RUN" != true ]]; then
        log_success "GPU auto-configuration completed successfully!"
        log_info "Next, test your configuration: ./test_config.sh"
        log_info "Then start the model controller: ./start.sh"
    else
        log_success "Dry-run completed. Use without --dry-run to apply changes."
    fi
}

# Run main function with all arguments
main "$@"