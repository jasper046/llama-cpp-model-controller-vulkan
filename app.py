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

def get_gpu_stats():
    """Get AMD GPU stats from sysfs"""
    gpus = []

    for card_id, card_name in GPU_CARDS:
        try:
            temp_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/temp1_input"
            temp_files = glob.glob(temp_path)
            temp = "N/A"
            if temp_files:
                with open(temp_files[0]) as f:
                    temp = f"{int(f.read().strip()) // 1000}°C"

            power_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/power1_average"
            power_files = glob.glob(power_path)
            power = "N/A"
            if power_files:
                with open(power_files[0]) as f:
                    power = f"{int(f.read().strip()) // 1000000}W"

            busy_path = f"/sys/class/drm/{card_id}/device/gpu_busy_percent"
            usage = "N/A"
            if os.path.exists(busy_path):
                with open(busy_path) as f:
                    usage = f"{f.read().strip()}%"

            gpus.append({
                "index": card_id,
                "name": card_name,
                "temp": temp,
                "usage": usage,
                "power": power,
                "memory": "See server logs"
            })
        except Exception as e:
            logger.error(f"Error reading {card_id}: {e}")
            gpus.append({
                "index": card_id,
                "name": card_name,
                "error": str(e)
            })

    return gpus

def log_reader(process):
    """Read logs from the process stdout and stderr and add them to the buffer"""
    global log_buffer, last_log_id
    
    def read_stream(stream, prefix):
        for line in iter(stream.readline, b''):
            try:
                line_str = line.decode('utf-8').rstrip()
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"[{timestamp}] {prefix}: {line_str}"
                log_buffer.append(log_entry)
                log_queue.put(log_entry)
                logger.debug(f"Log: {log_entry}")
            except Exception as e:
                logger.error(f"Error processing log line: {e}")
    
    # Start threads to read stdout and stderr
    threading.Thread(target=read_stream, args=(process.stdout, "OUT"), daemon=True).start()
    threading.Thread(target=read_stream, args=(process.stderr, "ERR"), daemon=True).start()

@app.route("/")
def index():
    models = get_models()
    return render_template("index.html", models=models)

@app.route("/gpu")
def gpu_stats():
    return jsonify(get_gpu_stats())

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
    if model_process:
        return jsonify({"status": "Model is already running!", "success": False})

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

        # Get Vulkan parameters with defaults from working config
        port = request.form.get("port", "4000")
        host = request.form.get("host", "0.0.0.0")
        ngl = request.form.get("ngl", "99")
        ctx_size = request.form.get("ctx_size", "16384")
        batch_size = request.form.get("batch_size", "512")
        ubatch_size = request.form.get("ubatch_size", "128")
        main_gpu = request.form.get("main_gpu", "0")
        tensor_split = request.form.get("tensor_split", "1,0.4")
        flash_attn = request.form.get("flash_attn", "on")
        parallel = request.form.get("parallel", "1")
        cont_batching = request.form.get("cont_batching", "true")

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
{"--cont-batching" if cont_batching == "true" else ""}"""
        
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

        return jsonify({"status": f"Model '{model}' started on {host}:{port}", "success": True})

    except Exception as e:
        logger.exception(f"Error starting model: {e}")
        return jsonify({"status": f"Error: {str(e)}", "success": False})

@app.route("/stop", methods=["POST"])
def stop_server():
    global model_process

    logger.debug("Stopping model server...")
    if model_process:
        os.killpg(os.getpgid(model_process.pid), signal.SIGTERM)
        model_process = None
        logger.debug("Model process terminated")

    # Clear Llama-Server Cache
    try:
        subprocess.run(["rm", "-rf", CACHE_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug("Llama cache cleared")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({"status": f"Error clearing cache: {str(e)}", "success": False})

    # Double-check: Kill any remaining `llama-server` processes
    subprocess.run(["pkill", "-f", "llama-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.debug("Killed any remaining llama-server processes")

    return jsonify({"status": "Model server fully stopped and cache cleared!", "success": True})

@app.route("/status")
def status():
    return jsonify({"running": model_process is not None})

# Ensure the model process is killed when Flask exits
def cleanup():
    global model_process
    logger.info("Cleaning up before exit...")

    if model_process:
        os.killpg(os.getpgid(model_process.pid), signal.SIGTERM)
        logger.info("Model process terminated")

    # Clear Llama-Server Cache on Exit
    subprocess.run(["rm", "-rf", CACHE_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info("Llama cache cleared")

    # Kill any remaining `llama-server` processes
    subprocess.run(["pkill", "-f", "llama-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info("Killed any remaining llama-server processes")

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
    
    # Check if llama-server exists
    if not os.path.exists(LLAMA_CPP_PATH):
        logger.error(f"llama-server executable not found at {LLAMA_CPP_PATH}")
        logger.error("Please compile llama.cpp or update the LLAMA_CPP_PATH variable")
    
    app.run(host="0.0.0.0", port=5000, debug=True)