#!/bin/bash

# GPU Auto-Detection and Configuration Script
# for llama.cpp Model Controller (Vulkan Edition)
#
# This script detects AMD GPUs via Vulkan and sysfs,
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
GPUS=()
SELECTED_GPUS=()

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
# Extracts key identifiers like "RX 6600", "RX 470", etc.
gpu_models_match() {
    local model1="$1"
    local model2="$2"

    # Extract common identifiers: RX + number, R9 + number, etc.
    local id1=$(echo "$model1" | grep -oE "(RX|R9|R7|R5)[[:space:]]*[0-9]+" | tr -d ' ')
    local id2=$(echo "$model2" | grep -oE "(RX|R9|R7|R5)[[:space:]]*[0-9]+" | tr -d ' ')

    # If both have identifiers, compare them
    if [[ -n "$id1" ]] && [[ -n "$id2" ]]; then
        [[ "$id1" == "$id2" ]] && return 0 || return 1
    fi

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
    This script detects AMD GPUs via Vulkan and sysfs, then helps you configure
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
        log_error "Expected locations: /usr/local/bin/llama-cli, /usr/bin/llama-cli, or in PATH"
        exit 1
    fi
}

# Task 1.2-1.4: Detect Vulkan devices
detect_vulkan_devices() {
    log_info "Detecting Vulkan devices..."

    # Run llama-cli and capture output (allow non-zero exit codes)
    vulkan_output=$("$LLAMA_CLI" --list-devices 2>&1) || true

    if [[ -z "$vulkan_output" ]]; then
        log_error "Failed to run llama-cli --list-devices"
        log_error "Make sure Vulkan is properly installed and your GPUs are supported"
        exit 1
    fi
    
    log_verbose "Vulkan device list output:"
    log_verbose "$vulkan_output"
    
    # Parse Vulkan devices - use simpler approach to avoid issues
    local device_count=0
    
    # Save output to temp variable first
    local output="$vulkan_output"
    
    # Process using file to avoid here-string issues
    local temp_file=$(mktemp)
    echo "$output" > "$temp_file"
    
    while IFS= read -r line; do
        if [[ $line =~ ggml_vulkan:[[:space:]]+([0-9]+)[[:space:]]*=[[:space:]]*(.+)$ ]]; then
            local device_id="${BASH_REMATCH[1]}"
            local device_full_name="${BASH_REMATCH[2]}"
            local device_name=$(echo "$device_full_name" | sed 's/ (.*$//')
            
            if [[ $device_name =~ (AMD|Radeon|NVIDIA|GeForce|Intel|Arc) ]]; then
                log_verbose "Found GPU device: ID=$device_id, Name=$device_name"
                GPUS+=("$device_id:$device_name")
                ((device_count++)) || true
            fi
        fi
    done < "$temp_file"
    
    rm -f "$temp_file"
    
    # Fallback: try to parse "Available devices:" section if above failed
    if [[ ${#GPUS[@]} -eq 0 ]]; then
        log_verbose "Trying alternative parsing for Available devices section..."
        
        while IFS= read -r line; do
            # Parse lines like: "  Vulkan0: AMD Radeon RX 6600 (RADV NAVI23) (8176 MiB, 8128 MiB free)"
            if [[ $line =~ ^\ +Vulkan([0-9]+):\ (.+)$ ]]; then
                local device_id="${BASH_REMATCH[1]}"
                local device_full_name="${BASH_REMATCH[2]}"
                
                # Extract clean GPU name
                local device_name=$(echo "$device_full_name" | sed 's/ (.*//')
                
                # Check if it's a GPU device
                if [[ $device_name =~ (AMD|Radeon|NVIDIA|GeForce|Intel|Arc) ]]; then
                    log_verbose "Found GPU device (alt): ID=$device_id, Name=$device_name"
                    GPUS+=("$device_id:$device_name")
                    ((device_count++)) || true
                fi
            fi
        done < <(echo "$vulkan_output")
    fi
    
    if [[ ${#GPUS[@]} -eq 0 ]]; then
        log_error "No GPU devices found via Vulkan"
        log_error "Raw output from llama-cli --list-devices:"
        echo "$vulkan_output" >&2
        log_error "Please check your Vulkan installation and GPU drivers"
        exit 1
    fi
    
    log_success "Found ${#GPUS[@]} GPU device(s) via Vulkan"
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

    # Match cards to Vulkan devices using GPU model names
    local gpu_config=()

    for card_mapping in "${pcie_mapping[@]}"; do
        local card_id=$(echo "$card_mapping" | cut -d: -f1)
        local pcie_slot=$(echo "$card_mapping" | cut -d: -f2)
        local card_gpu_model=$(echo "$card_mapping" | cut -d: -f3-)

        # Try to find matching Vulkan device by GPU name
        local matched=false
        for vulkan_gpu_info in "${GPUS[@]}"; do
            local vulkan_id=$(echo "$vulkan_gpu_info" | cut -d: -f1)
            local vulkan_gpu_name=$(echo "$vulkan_gpu_info" | cut -d: -f2-)

            # Use smart matching function
            if gpu_models_match "$card_gpu_model" "$vulkan_gpu_name"; then
                gpu_config+=("$card_id:$pcie_slot:$vulkan_id:$vulkan_gpu_name")
                log_verbose "Matched $card_id ($card_gpu_model) to Vulkan ID $vulkan_id ($vulkan_gpu_name)"
                matched=true
                break
            fi
        done

        if [[ "$matched" == false ]]; then
            log_warn "Could not match $card_id ($card_gpu_model) to any Vulkan device, using fallback"
            # Fallback: use next available Vulkan ID
            local vulkan_index=${#gpu_config[@]}
            if [[ $vulkan_index -lt ${#GPUS[@]} ]]; then
                local fallback_gpu_info="${GPUS[$vulkan_index]}"
                local fallback_vulkan_id=$(echo "$fallback_gpu_info" | cut -d: -f1)
                local fallback_vulkan_name=$(echo "$fallback_gpu_info" | cut -d: -f2-)
                gpu_config+=("$card_id:$pcie_slot:$fallback_vulkan_id:$fallback_vulkan_name")
                log_verbose "Fallback: $card_id → Vulkan ID $fallback_vulkan_id ($fallback_vulkan_name)"
            else
                log_error "No more Vulkan devices available for $card_id"
                exit 1
            fi
        fi
    done

    GPUS=("${gpu_config[@]}")
    log_success "Mapped ${#GPUS[@]} GPUs to PCIe slots"

    # Sort GPUs by Vulkan ID so user sees them in Vulkan order
    IFS=$'\n' GPUS=($(sort -t: -k3 -n <<<"${GPUS[*]}"))
    unset IFS
    log_verbose "GPUs sorted by Vulkan ID for user interaction"
}

# Task 4: User Interaction
prompt_user_selection() {
    # In dry-run mode, use default selections
    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY-RUN: Using default GPU configuration"
        log_info "Would normally prompt for user input here..."
        
        # Auto-select all GPUs with default weights for dry-run
        local gpu_index=0
        for gpu_info in "${GPUS[@]}"; do
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
            
            SELECTED_GPUS+=("$gpu_info:$is_main:$tensor_weight")
            log_info "DRY-RUN: Would select $card_id ($gpu_name) - main=$is_main, weight=$tensor_weight"
            ((gpu_index++)) || true
        done
        return 0
    fi
    
    log_info "Detected GPUs:"
    echo
    
    local index=0
    for gpu_info in "${GPUS[@]}"; do
        local card_id=$(echo "$gpu_info" | cut -d: -f1)
        local pcie_slot=$(echo "$gpu_info" | cut -d: -f2)
        local vulkan_id=$(echo "$gpu_info" | cut -d: -f3)
        local gpu_name=$(echo "$gpu_info" | cut -d: -f4-)
        
        echo "$((index+1)). $card_id (PCIe $pcie_slot) -> Vulkan ID $vulkan_id - $gpu_name"
        ((index++)) || true
    done
    
    echo
    log_info "Please configure the GPUs to include:"
    
    local temp_selected_gpus=()
    local temp_tensor_weights=()

    for gpu_info in "${GPUS[@]}"; do
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

    # Now, populate SELECTED_GPUS in the format generate_config expects
    local i=0
    for gpu_info in "${temp_selected_gpus[@]}"; do
        local is_main="n"
        if [[ $i -eq $main_gpu_index ]]; then
            is_main="y"
        fi
        
        local tensor_weight="${temp_tensor_weights[$i]}"
        SELECTED_GPUS+=("$gpu_info:$is_main:$tensor_weight")
        ((i++)) || true
    done
    
    log_success "Selected ${#SELECTED_GPUS[@]} GPU(s) for configuration"
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
    
    # Sort selected GPUs by Vulkan ID (so tensor split makes sense)
    IFS=$'\n' SORTED_GPUS=($(sort -t: -k3 -n <<<"${SELECTED_GPUS[*]}"))
    unset IFS

    # Generate GPU configuration in Vulkan order
    local gpu_cards="["
    local tensor_parts=()
    local main_gpu_vulkan_id=""

    local gpu_index=0
    for selected_gpu in "${SORTED_GPUS[@]}"; do
        local card_id=$(echo "$selected_gpu" | cut -d: -f1)
        local pcie_slot=$(echo "$selected_gpu" | cut -d: -f2)
        local vulkan_id=$(echo "$selected_gpu" | cut -d: -f3)
        local gpu_name=$(echo "$selected_gpu" | cut -d: -f4)
        local is_main=$(echo "$selected_gpu" | cut -d: -f5)
        local tensor_weight=$(echo "$selected_gpu" | cut -d: -f6)
        
        # Add comma for all but first element
        if [[ $gpu_index -gt 0 ]]; then
            gpu_cards+=","
        fi
        
        # Generate GPU card entry
        gpu_cards+=$(cat << EOF
    {
      "card_id": "$card_id",
      "display_name": "$gpu_name",
      "vulkan_id": $vulkan_id,
      "sysfs_base": "/sys/class/drm/$card_id/device",
      "hwmon_pattern": "hwmon/hwmon*"
    }
EOF
)
        
        # Collect tensor weights
        tensor_parts+=("$tensor_weight")
        
        # Store main GPU Vulkan ID (use first one found)
        if [[ "$is_main" == "y" && -z "$main_gpu_vulkan_id" ]]; then
            main_gpu_vulkan_id="$vulkan_id"
        fi
        
        ((gpu_index++)) || true
    done
    
    gpu_cards+="]"
    
    # Generate tensor_split string
    local tensor_split=$(IFS=,; echo "${tensor_parts[*]}")
    
    # Validate tensor weights
    local total_weight=$(echo "${tensor_parts[*]}" | tr ' ' '+' | bc -l 2>/dev/null || echo "1.0")
    log_verbose "Total tensor weight: $total_weight"
    
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
config['default_parameters']['main_gpu'] = '$main_gpu_vulkan_id'

# Write updated config
with open('$temp_config', 'w') as f:
    json.dump(config, f, indent=2)

print("Configuration updated successfully")
EOF
    
    if [[ "$DRY_RUN" != true ]]; then
        mv "$temp_config" "$CONFIG_FILE"
        log_success "Configuration saved to $CONFIG_FILE"
        log_info "Tensor split: $tensor_split"
        log_info "Main GPU Vulkan ID: $main_gpu_vulkan_id"
    else
        echo
        log_info "DRY RUN - Configuration that would be saved:"
        cat "$temp_config"
        rm "$temp_config"
        echo
        log_info "Would save to: $CONFIG_FILE"
        log_info "Tensor split: $tensor_split"
        log_info "Main GPU Vulkan ID: $main_gpu_vulkan_id"
    fi
}

# Main function
main() {
    echo "GPU Auto-Detection and Configuration Script"
    echo "for llama.cpp Model Controller (Vulkan Edition)"
    echo "==============================================="
    echo
    
    parse_args "$@"
    
    log_verbose "Verbose mode enabled"
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Running in dry-run mode - no changes will be made"
    fi
    
    # Execute tasks
    check_llama_cli
    detect_vulkan_devices
    map_pcie_slots
    prompt_user_selection
    generate_config
    
    echo
    if [[ "$DRY_RUN" != true ]]; then
        log_success "GPU auto-configuration completed successfully!"
        log_info "You can now run the model controller with: python app.py"
    else
        log_success "Dry-run completed. Use without --dry-run to apply changes."
    fi
}

# Run main function with all arguments
main "$@"