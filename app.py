import os
import subprocess
import signal
import atexit
import logging
import threading
import time
import re
import queue
import glob
from collections import deque
from flask import Flask, render_template, request, jsonify
from config import HOME_DIR, LLAMA_CPP_PATH, MODEL_DIR, CACHE_DIR, SLOTS_DIR, GPU_CARDS
from settings_handler import SettingsHandler
from gpu_monitor import gpu_monitor

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
model_process = None

# Buffer to store server logs
log_buffer = deque(maxlen=1000)  # Store up to 1000 log lines
log_queue = queue.Queue()
last_log_id = 0

def get_models():
    """Retrieve all available models from the models directory"""
    if not os.path.exists(MODEL_DIR):
        logger.warning(f"Model directory {MODEL_DIR} does not exist")
        return []
    return [f for f in os.listdir(MODEL_DIR) if f.endswith(".gguf")]


def log_reader(process):
    """Read logs from the process stdout and stderr and add them to the buffer"""
    global log_buffer, last_log_id

    def read_stream(stream, prefix):
        for line in iter(stream.readline, b''):
            try:
                line_str = line.decode('utf-8').rstrip()
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"[{timestamp}] {line_str}"
                log_buffer.append(log_entry)
                log_queue.put(log_entry)
                logger.debug(f"Log: {log_entry}")
            except Exception as e:
                logger.error(f"Error processing log line: {e}")

    # Start threads to read stdout and stderr
    threading.Thread(target=read_stream, args=(process.stdout, "OUT"), daemon=True).start()
    threading.Thread(target=read_stream, args=(process.stderr, "ERR"), daemon=True).start()

def stop_model_if_running():
    """Stop any running llama-server processes with proper cleanup"""
    global model_process
    killed_any = False

    # 1. Stop the main model process if we have it
    if model_process and model_process.poll() is None:
        logger.info("Stopping model process (PID: %s)...", model_process.pid)

        # Try SIGTERM first (graceful)
        model_process.terminate()

        # Wait with timeout
        try:
            model_process.wait(timeout=10)
            logger.info("Model process stopped gracefully")
            killed_any = True
        except subprocess.TimeoutExpired:
            logger.warning("Model process didn't stop gracefully, sending SIGKILL...")
            model_process.kill()  # SIGKILL

            try:
                model_process.wait(timeout=5)
                logger.info("Model process killed with SIGKILL")
                killed_any = True
            except subprocess.TimeoutExpired:
                logger.error("Model process won't die! PID: %s", model_process.pid)
                # Process might be in D state

    # 2. Kill ALL llama-server processes (cleanup any orphans)
    logger.info("Cleaning up all llama-server processes...")

    # First try pkill -f (matches command line)
    try:
        subprocess.run(["pkill", "-f", "llama-server"],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        time.sleep(2)
    except:
        pass

    # Check if any remain
    result = subprocess.run(["pgrep", "-f", "llama-server"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:  # Processes still exist
        pids = result.stdout.strip().split()
        logger.warning(f"llama-server processes still running: {pids}")

        # Try SIGKILL on each
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                logger.info(f"Sent SIGKILL to PID {pid}")
            except:
                pass

        time.sleep(2)

        # Final check
        result = subprocess.run(["pgrep", "-f", "llama-server"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            pids = result.stdout.decode().strip().split()
            logger.error(f"llama-server processes STILL running: {pids}")
            logger.error("Processes may be in D state (unkillable)")
        else:
            logger.info("All llama-server processes cleaned up")
            killed_any = True
    else:
        logger.info("No llama-server processes running")
        killed_any = True

    # Clear Llama-Server Cache
    try:
        subprocess.run(["rm", "-rf", CACHE_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug("Llama cache cleared")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        # Continue anyway - model is already stopped

    # Reset model_process
    model_process = None

    return killed_any

@app.route("/")
def index():
    models = get_models()
    # Prepare GPU list sorted by Vulkan ID (0, 1, ...)
    gpus = []
    for card_id, display_name, vulkan_id in sorted(GPU_CARDS, key=lambda x: x[2]):
        gpus.append({
            "vulkan_id": vulkan_id,
            "display_name": display_name,
            "card_id": card_id
        })

    # Create tensor split label showing GPU mapping
    tensor_split_parts = []
    for gpu in gpus:
        tensor_split_parts.append(f"GPU{gpu['vulkan_id']}: {gpu['display_name']}")
    tensor_split_label = f"Tensor Split ({', '.join(tensor_split_parts)})"

    return render_template("index.html", models=models, gpus=gpus, tensor_split_label=tensor_split_label)

@app.route("/gpu")
def gpu_stats():
    """Return cached GPU stats from background monitor"""
    try:
        stats = gpu_monitor.get_stats()
        # Remove internal fields before sending to frontend
        clean_stats = []
        for gpu in stats:
            clean_gpu = {k: v for k, v in gpu.items() if k not in ["last_update", "error"]}
            clean_stats.append(clean_gpu)
        return jsonify(clean_stats)
    except Exception as e:
        logger.error(f"Error in /gpu endpoint: {e}")
        # Return default stats if cache fails
        default_stats = []
        for card_id, card_name, vulkan_id in GPU_CARDS:
            default_stats.append({
                "index": card_id,
                "name": card_name,
                "vulkan_id": vulkan_id,
                "temp": "N/A",
                "usage": "0%",
                "power": "N/A",
                "gpu_clock": "N/A",
                "mem_clock": "N/A",
                "fan_speed": "N/A",
                "memory": "0.00Gi/0.00Gi"
            })
        return jsonify(default_stats)

@app.route("/logs")
def get_logs():
    """Return logs that have been collected since the last request"""
    entries = []
    try:
        # Get all available logs from the queue
        while not log_queue.empty():
            entries.append({"text": log_queue.get_nowait()})
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
    
    return jsonify({"entries": entries, "reset": False})

@app.route("/start", methods=["POST"])
def start_server():
    global model_process
    # Stop any currently running model before starting a new one
    was_running = model_process is not None
    if was_running:
        logger.info("Model already running, stopping it first...")
        stop_model_if_running()

    try:
        # Debug all form data
        logger.debug("Form data received:")
        for key, value in request.form.items():
            logger.debug(f"  {key}: {value}")
        
        # Get model name
        model = request.form.get("model")
        if not model:
            logger.error("No model selected!")
            return jsonify({"status": "No model selected!", "success": False})

        # Get Vulkan parameters with user preferences as defaults
        form_defaults = SettingsHandler.get_form_defaults(request.form)

        port = form_defaults.get("port", "4000")
        host = form_defaults.get("host", "0.0.0.0")
        ngl = form_defaults.get("ngl", "99")
        ctx_size = form_defaults.get("ctx_size", "16384")
        batch_size = form_defaults.get("batch_size", "512")
        ubatch_size = form_defaults.get("ubatch_size", "128")
        main_gpu = form_defaults.get("main_gpu", "0")
        tensor_split = form_defaults.get("tensor_split", "1,0.4")
        flash_attn = form_defaults.get("flash_attn", "on")
        parallel = form_defaults.get("parallel", "1")
        cont_batching = form_defaults.get("cont_batching", "true")
        extra_args = form_defaults.get("extra_args", "")

        # Log the actual values being used
        logger.debug(f"Using model: {model}")
        logger.debug(f"Port: {port}")
        logger.debug(f"Host: {host}")
        logger.debug(f"GPU Layers (ngl): {ngl}")
        logger.debug(f"Context size: {ctx_size}")
        logger.debug(f"Batch size: {batch_size}")
        logger.debug(f"UBatch size: {ubatch_size}")
        logger.debug(f"Main GPU: {main_gpu}")
        logger.debug(f"Tensor split: {tensor_split}")
        logger.debug(f"Flash attention: {flash_attn}")
        logger.debug(f"Parallel: {parallel}")
        logger.debug(f"Continuous batching: {cont_batching}")
        logger.debug(f"Extra args: {extra_args}")

        env = os.environ.copy()

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
{"--cont-batching" if cont_batching == "true" else ""} \
{extra_args if extra_args else ""}"""
        
        # Log the final command being executed
        logger.debug(f"Executing command: {command}")

        # Clear the log buffers before starting a new process
        log_buffer.clear()
        while not log_queue.empty():
            log_queue.get()

        # Add a special status message to the logs
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        start_msg = f"[{timestamp}] STARTING MODEL: {model} on {host}:{port}"
        log_buffer.append(start_msg)
        log_queue.put(start_msg)
        logger.debug(start_msg)

        # Start the process with pipes for stdout and stderr
        model_process = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            preexec_fn=os.setsid, 
            env=env,
            bufsize=1,  # Line buffered
            universal_newlines=False  # Binary mode
        )
        
        # Start the log reader threads
        log_reader(model_process)
        
        # Wait a short time to check for immediate failures
        time.sleep(1)
        
        # Check if process is still running
        if model_process.poll() is not None:
            # Process has already exited
            exit_code = model_process.poll()
            error_msg = f"Process exited immediately with code {exit_code}"
            logger.error(error_msg)
            
            # Add the error message to the logs
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_msg = f"[{timestamp}] CRITICAL ERROR: {error_msg}"
            log_buffer.append(log_msg)
            log_queue.put(log_msg)
            
            model_process = None
            return jsonify({"status": f"Error: {error_msg}", "success": False})

        if was_running:
            return jsonify({"status": f"Stopped previous model and started '{model}' on {host}:{port}", "success": True})
        else:
            return jsonify({"status": f"Model '{model}' started on {host}:{port}", "success": True})

    except Exception as e:
        logger.exception(f"Error starting model: {e}")
        return jsonify({"status": f"Error: {str(e)}", "success": False})

@app.route("/stop", methods=["POST"])
def stop_server():
    logger.debug("Stopping model server...")
    stopped = stop_model_if_running()

    if stopped:
        return jsonify({"status": "Model server fully stopped and cache cleared!", "success": True})
    else:
        # Check if there was an error or no model was running
        if model_process:
            # Model was running but error occurred during stop
            return jsonify({"status": "Error stopping model server", "success": False})
        else:
            # No model was running
            return jsonify({"status": "No model was running", "success": True})

@app.route("/status")
def status():
    return jsonify({"running": model_process is not None})

@app.route("/save_settings", methods=["POST"])
def save_settings():
    """Save user settings from frontend"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "No data provided", "success": False})

        # Save each setting
        for key, value in data.items():
            if key == "model_index":
                # Store model index as integer
                SettingsHandler.save_setting("model_index", int(value))
            elif key in ["ngl", "ctx_size", "port", "host", "main_gpu", "tensor_split",
                        "batch_size", "ubatch_size", "flash_attn", "parallel", "cont_batching", "extra_args"]:
                SettingsHandler.save_setting(key, value)

        return jsonify({"status": "Settings saved successfully", "success": True})
    except Exception as e:
        logger.exception(f"Error saving settings: {e}")
        return jsonify({"status": f"Error: {str(e)}", "success": False})

@app.route("/reset_settings", methods=["POST"])
def reset_settings():
    """Reset all settings to defaults"""
    try:
        success = SettingsHandler.reset_to_defaults()
        if success:
            return jsonify({"status": "Settings reset to defaults", "success": True})
        else:
            return jsonify({"status": "Failed to reset settings", "success": False})
    except Exception as e:
        logger.exception(f"Error resetting settings: {e}")
        return jsonify({"status": f"Error: {str(e)}", "success": False})

@app.route("/get_settings", methods=["GET"])
def get_settings():
    """Get current user settings"""
    try:
        settings = SettingsHandler.load_settings()
        return jsonify({"settings": settings, "success": True})
    except Exception as e:
        logger.exception(f"Error getting settings: {e}")
        return jsonify({"status": f"Error: {str(e)}", "success": False})

# Ensure the model process is killed when Flask exits
def cleanup():
    logger.info("Cleaning up before exit...")
    stop_model_if_running()
    # Stop GPU monitor if it's running
    try:
        gpu_monitor.stop()
    except Exception as e:
        logger.error(f"Error stopping GPU monitor: {e}")

atexit.register(cleanup)

if __name__ == "__main__":
    logger.info("Starting Llama Model Controller server...")
    logger.info(f"Using model directory: {MODEL_DIR}")
    logger.info(f"Using llama.cpp server path: {LLAMA_CPP_PATH}")
    
    # Check if model directory exists
    if not os.path.exists(MODEL_DIR):
        logger.warning(f"Model directory {MODEL_DIR} does not exist. Creating it...")
        try:
            os.makedirs(MODEL_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create model directory: {e}")

    # Check if slots directory exists
    if not os.path.exists(SLOTS_DIR):
        logger.warning(f"Slots directory {SLOTS_DIR} does not exist. Creating it...")
        try:
            os.makedirs(SLOTS_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create slots directory: {e}")

    # Check if llama-server exists
    if not os.path.exists(LLAMA_CPP_PATH):
        logger.error(f"llama-server executable not found at {LLAMA_CPP_PATH}")
        logger.error("Please compile llama.cpp or update the LLAMA_CPP_PATH variable")

    # Start GPU monitor in background
    logger.info("Starting GPU monitor...")
    gpu_monitor.start()

    # Register cleanup for GPU monitor
    atexit.register(gpu_monitor.stop)

    app.run(host="0.0.0.0", port=5000, debug=True)