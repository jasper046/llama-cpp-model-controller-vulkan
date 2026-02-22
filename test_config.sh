#!/usr/bin/env bash
# Configuration test script for llama.cpp Model Controller (ROCm Edition)
# Run this after gpu_autodetect_and_config.sh and before starting the app

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.json"
CONFIG_TEMPLATE="${SCRIPT_DIR}/config_template.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}



test_json_config() {
    log_info "Testing JSON configuration file..."

    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "config.json not found at $CONFIG_FILE"
        return 1
    fi

    if ! python3 -m json.tool "$CONFIG_FILE" > /dev/null 2>&1; then
        log_error "config.json contains invalid JSON"
        return 1
    fi

    log_info "✓ config.json exists and contains valid JSON"
    return 0
}

test_required_fields() {
    log_info "Testing required configuration fields..."

    local errors=0

    # Check gpu_configuration
    if ! python3 -c "
import json
import sys
with open('$CONFIG_FILE') as f:
    config = json.load(f)

# Check gpu_configuration section
if 'gpu_configuration' not in config:
    print('Missing gpu_configuration section')
    sys.exit(1)

gpu_config = config['gpu_configuration']

# Check gpu_cards
if 'gpu_cards' not in gpu_config:
    print('Missing gpu_cards in gpu_configuration')
    sys.exit(1)

if len(gpu_config['gpu_cards']) == 0:
    print('gpu_cards is empty')
    sys.exit(1)

# Check each GPU card
for i, gpu in enumerate(gpu_config['gpu_cards']):
    required = ['card_id', 'display_name', 'rocm_id']
    for field in required:
        if field not in gpu:
            print(f'GPU {i} missing field: {field}')
            sys.exit(1)

# Check model_configuration
if 'model_configuration' not in config:
    print('Missing model_configuration section')
    sys.exit(1)

model_config = config['model_configuration']
required_model_fields = ['llama_cpp_path', 'model_dir', 'cache_dir', 'slots_dir']
for field in required_model_fields:
    if field not in model_config:
        print(f'Missing model_configuration field: {field}')
        sys.exit(1)

print('All required fields present')
" 2>&1; then
        log_error "Configuration missing required fields"
        errors=$((errors + 1))
    else
        log_info "✓ All required configuration fields present"
    fi

    return $errors
}

test_llama_server() {
    log_info "Testing llama-server executable..."

    local llama_path=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
print(config['model_configuration']['llama_cpp_path'])
" 2>/dev/null)

    if [[ -z "$llama_path" ]]; then
        log_error "Could not extract llama_cpp_path from config"
        return 1
    fi

    # Expand ~ in path
    llama_path="${llama_path/#\~/$HOME}"

    if [[ ! -f "$llama_path" ]]; then
        log_error "llama-server not found at: $llama_path"
        log_warn "Expected path from config: $(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
print(config['model_configuration']['llama_cpp_path'])
")"
        return 1
    fi

    if [[ ! -x "$llama_path" ]]; then
        log_error "llama-server is not executable: $llama_path"
        return 1
    fi

    # Test basic ROCm device listing
    log_info "Testing ROCm device detection via llama-server..."
    if ! "$llama_path" --list-devices > /dev/null 2>&1; then
        log_warn "llama-server --list-devices failed (may not support ROCm)"
        log_warn "Output: $("$llama_path" --list-devices 2>&1 | head -20)"
    else
        log_info "✓ llama-server ROCm device listing works"
    fi

    log_info "✓ llama-server executable found and appears functional"
    return 0
}

test_sysfs_access() {
    log_info "Testing sysfs GPU access..."

    local errors=0

    # Get GPU cards from config
    local gpu_cards_json=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
import json as json_module
print(json_module.dumps(config['gpu_configuration']['gpu_cards']))
" 2>/dev/null)

    if [[ -z "$gpu_cards_json" ]]; then
        log_error "Could not extract GPU cards from config"
        return 1
    fi

    # Parse each GPU card
    local card_count=$(echo "$gpu_cards_json" | python3 -c "import json, sys; data=json.load(sys.stdin); print(len(data))")

    log_info "Found $card_count GPU card(s) in configuration"

    for i in $(seq 0 $((card_count - 1))); do
        local card_id=$(echo "$gpu_cards_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data[$i]['card_id'])
" 2>/dev/null)

        local display_name=$(echo "$gpu_cards_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data[$i]['display_name'])
" 2>/dev/null)

        local rocm_id=$(echo "$gpu_cards_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data[$i]['rocm_id'])
" 2>/dev/null)

        log_info "Testing GPU $i: $display_name (card: $card_id, ROCm ID: $rocm_id)"

        # Check sysfs directory exists
        local sysfs_path="/sys/class/drm/$card_id"
        if [[ ! -d "$sysfs_path" ]]; then
            log_error "  ❌ Sysfs directory not found: $sysfs_path"
            errors=$((errors + 1))
        else
            log_info "  ✓ Sysfs directory exists: $sysfs_path"
        fi

        # Check device directory exists
        local device_path="/sys/class/drm/$card_id/device"
        if [[ ! -d "$device_path" ]]; then
            log_warn "  ⚠ Device directory not found: $device_path (may be normal for some cards)"
        else
            log_info "  ✓ Device directory exists: $device_path"

            # Try to read some basic info
            if [[ -f "$device_path/vendor" ]]; then
                local vendor=$(cat "$device_path/vendor" 2>/dev/null || echo "unknown")
                log_info "  ✓ Vendor: $(printf '0x%04x' $((vendor)))"
            fi
        fi
    done

    if [[ $errors -eq 0 ]]; then
        log_info "✓ Sysfs access tests passed"
    else
        log_error "Sysfs access tests failed with $errors error(s)"
    fi

    return $errors
}

test_python_dependencies() {
    log_info "Testing Python dependencies..."

    # Check if virtual environment exists
    if [[ -d "venv" ]]; then
        log_info "Found virtual environment, checking Flask in venv..."
        if ! venv/bin/python -c "import flask" > /dev/null 2>&1; then
            log_error "Flask not installed in virtual environment. Run: source venv/bin/activate && pip install flask"
            return 1
        fi
        log_info "✓ Flask is installed in virtual environment"
    else
        # Check system Python
        if ! python3 -c "import flask" > /dev/null 2>&1; then
            log_error "Flask not installed. Run: pip install flask"
            return 1
        fi
        log_info "✓ Flask is installed in system Python"
    fi

    return 0
}

test_model_directory() {
    log_info "Testing model directory..."

    local model_dir=$(python3 -c "
import json, os
with open('$CONFIG_FILE') as f:
    config = json.load(f)
print(os.path.expanduser(config['model_configuration']['model_dir']))
" 2>/dev/null)

    if [[ -z "$model_dir" ]]; then
        log_error "Could not extract model_dir from config"
        return 1
    fi

    if [[ ! -d "$model_dir" ]]; then
        log_warn "Model directory does not exist: $model_dir"
        log_warn "Creating directory..."
        mkdir -p "$model_dir" 2>/dev/null || {
            log_error "Failed to create model directory"
            return 1
        }
        log_info "Created model directory: $model_dir"
    else
        log_info "✓ Model directory exists: $model_dir"

        # Check for GGUF files
        local gguf_count=$(find "$model_dir" -name "*.gguf" -type f 2>/dev/null | wc -l)
        if [[ $gguf_count -eq 0 ]]; then
            log_warn "No GGUF model files found in $model_dir"
            log_warn "Place your .gguf model files in this directory"
        else
            log_info "✓ Found $gguf_count GGUF model file(s)"
            find "$model_dir" -name "*.gguf" -type f 2>/dev/null | head -5 | while read -r model; do
                log_info "  - $(basename "$model")"
            done
        fi
    fi

    return 0
}

main() {
    echo "==============================================="
    echo "Configuration Test for llama.cpp Model Controller"
    echo "ROCm Edition"
    echo "==============================================="
    echo

    local total_errors=0
    local total_tests=0

    # Run tests
    for test_func in test_json_config test_required_fields test_llama_server test_sysfs_access test_python_dependencies test_model_directory; do
        ((total_tests++))
        log_info ""
        log_info "Running: $test_func"
        echo "-----------------------------------------------"
        if $test_func; then
            log_info "✓ $test_func passed"
        else
            log_error "✗ $test_func failed"
            total_errors=$((total_errors + 1))
        fi
    done

    echo
    echo "==============================================="
    if [[ $total_errors -eq 0 ]]; then
        log_info "ALL TESTS PASSED ($total_tests/$total_tests)"
        log_info ""
        log_info "Configuration appears valid. You can now start the app:"
        log_info "  ./start.sh  # or: python app.py"
        log_info ""
        log_info "The web interface will be available at: http://localhost:5000"
    else
        log_error "TESTS FAILED: $total_errors of $total_tests tests failed"
        log_error ""
        log_error "Please fix the issues above before starting the app."
        log_error "Common solutions:"
        log_error "1. Run ./gpu_autodetect_and_config.sh to generate config"
        log_error "2. Install missing dependencies: pip install flask"
        log_error "3. Check llama-server path in config.json"
        log_error "4. Ensure GPU sysfs paths are correct"
        exit 1
    fi
}

# Run main function
main "$@"