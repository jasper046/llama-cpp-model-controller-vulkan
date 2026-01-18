"""
Route definitions for the Flask application
Separated from business logic for clean architecture
"""

import time
import logging
from flask import jsonify, render_template, request
from src.utils.config import Config

logger = logging.getLogger(__name__)

def register_routes(app, model_service, gpu_service, log_service, settings_service):
    """Register all routes with the Flask application"""
    
    config = Config()
    
    @app.route("/")
    def index():
        """Main page with model selection and GPU configuration"""
        models = config.get_models()
        gpus = config.get_gpu_list()
        
        # Create tensor split label showing GPU mapping
        tensor_split_parts = []
        for gpu in gpus:
            tensor_split_parts.append(f"GPU{gpu['vulkan_id']}: {gpu['display_name']}")
        tensor_split_label = f"Tensor Split ({', '.join(tensor_split_parts)})"
        
        return render_template("index.html", 
                             models=models, 
                             gpus=gpus, 
                             tensor_split_label=tensor_split_label)
    
    @app.route("/gpu")
    def gpu_stats():
        """Return cached GPU stats from background monitor"""
        try:
            stats = gpu_service.get_stats()
            return jsonify({
                "gpus": stats,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.error(f"Error in /gpu endpoint: {e}")
            # Return default stats
            default_stats = []
            for card_id, card_name, vulkan_id in config.GPU_CARDS:
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
                    "memory": "0.00Gi/0.00Gi",
                    "error": str(e)
                })
            
            return jsonify({
                "gpus": default_stats,
                "timestamp": time.time()
            })
    
    @app.route("/logs")
    def get_logs():
        """Return logs that have been collected since the last request"""
        entries = log_service.get_logs()
        return jsonify({"entries": entries, "reset": False})
    
    @app.route("/start", methods=["POST"])
    def start_server():
        """Start a llama-server process with given parameters"""
        try:
            # Get model name
            model = request.form.get("model")
            if not model:
                return jsonify({"status": "No model selected!", "success": False})
            
            # Get parameters with user preferences as defaults
            form_defaults = settings_service.get_form_defaults(request.form)
            
            # Start the model
            result = model_service.start_model(model, form_defaults)
            
            if result["success"]:
                log_service.add_log(f"Model '{model}' started successfully")
            
            return jsonify(result)
            
        except Exception as e:
            logger.exception(f"Error starting model: {e}")
            return jsonify({"status": f"Error: {str(e)}", "success": False})
    
    @app.route("/stop", methods=["POST"])
    def stop_server():
        """Stop the running model process"""
        stopped = model_service.stop_model()
        
        if stopped:
            log_service.add_log("Model server stopped")
            return jsonify({"status": "Model server stopped!", "success": True})
        else:
            return jsonify({"status": "Error stopping model server", "success": False})
    
    @app.route("/status")
    def status():
        """Check if model is running"""
        return jsonify({"running": model_service.is_running()})
    
    @app.route("/save_settings", methods=["POST"])
    def save_settings():
        """Save user settings from frontend"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "No data provided", "success": False})
            
            success = settings_service.save_settings(data)
            
            if success:
                return jsonify({"status": "Settings saved successfully", "success": True})
            else:
                return jsonify({"status": "Failed to save settings", "success": False})
                
        except Exception as e:
            logger.exception(f"Error saving settings: {e}")
            return jsonify({"status": f"Error: {str(e)}", "success": False})
    
    @app.route("/reset_settings", methods=["POST"])
    def reset_settings():
        """Reset all settings to defaults"""
        success = settings_service.reset_settings()
        
        if success:
            return jsonify({"status": "Settings reset to defaults", "success": True})
        else:
            return jsonify({"status": "Failed to reset settings", "success": False})
    
    @app.route("/get_settings", methods=["GET"])
    def get_settings():
        """Get current user settings"""
        settings = settings_service.load_settings()
        return jsonify({"settings": settings, "success": True})
    
    @app.route("/diagnose_gpu", methods=["GET"])
    def diagnose_gpu():
        """Run GPU crash diagnosis"""
        try:
            diagnosis = gpu_service.diagnose_gpu_crash()
            return jsonify({
                "diagnosis": diagnosis,
                "success": True,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.exception(f"Error running GPU diagnosis: {e}")
            return jsonify({
                "status": f"Error: {str(e)}",
                "success": False,
                "timestamp": time.time()
            })
