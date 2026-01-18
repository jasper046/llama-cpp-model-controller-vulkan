"""
Configuration management for the Llama.cpp Model Controller
Centralized configuration with JSON support and validation.
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management with JSON support"""
    
    def __init__(self, config_path: str = None):
        self.HOME_DIR = os.path.expanduser("~")
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        self.config_data = {}
        
        # Default configuration
        self.LLAMA_CPP_PATH = "/usr/local/bin/llama-server"
        self.MODEL_DIR = os.path.join(self.HOME_DIR, "models")
        self.CACHE_DIR = os.path.join(self.HOME_DIR, ".cache/llama")
        self.SLOTS_DIR = "/tmp/llama_slots"
        
        # GPU configuration - will be loaded from JSON or use defaults
        self.GPU_CARDS = [
            ("card1", "RX 500", 1),    # card1 = RX 550 = Vulkan device 1
            ("card2", "RX 470", 2),    # card2 = RX 470 = Vulkan device 2
            ("card3", "RX 6600", 0)    # card3 = RX 6600 = Vulkan device 0
        ]
        
        # Sysfs paths for GPU monitoring
        self.SYSFS_PATHS = {
            "gpu_busy_percent": "gpu_busy_percent",
            "temperature": "hwmon/hwmon*/temp1_input",
            "power": "hwmon/hwmon*/power1_average",
            "gpu_clock": "pp_dpm_sclk",
            "mem_clock": "pp_dpm_mclk",
            "fan_speed": "hwmon/hwmon*/fan1_input",
            "vram_total": "mem_info_vram_total",
            "vram_used": "mem_info_vram_used"
        }
        
        # Default model parameters
        self.DEFAULT_PARAMS = {
            "port": "4000",
            "host": "0.0.0.0",
            "ngl": "999",
            "ctx_size": "16384",
            "batch_size": "512",
            "ubatch_size": "128",
            "main_gpu": "0",
            "tensor_split": "0.54,0.13,0.33",
            "flash_attn": "on",
            "parallel": "1",
            "cont_batching": "true",
            "extra_args": "--jinja --chat-template chatml"
        }
        
        # Monitoring settings
        self.UPDATE_INTERVAL = 2
        self.CACHE_TTL = 5
        self.DIAGNOSIS_INTERVAL = 60
        
        # Load configuration from JSON if available
        self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config_data = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
                self._apply_config()
            except Exception as e:
                logger.error(f"Failed to load configuration from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"Configuration file {self.config_path} not found. Using defaults.")
            logger.info(f"Create {self.config_path} from config_template.json for custom configuration")
    
    def _apply_config(self):
        """Apply loaded configuration data"""
        # Apply GPU configuration
        if "gpu_configuration" in self.config_data:
            gpu_config = self.config_data["gpu_configuration"]
            
            # Update GPU cards
            if "gpu_cards" in gpu_config:
                self.GPU_CARDS = []
                for gpu in gpu_config["gpu_cards"]:
                    self.GPU_CARDS.append((
                        gpu.get("card_id", ""),
                        gpu.get("display_name", ""),
                        gpu.get("vulkan_id", 0)
                    ))
            
            # Update sysfs paths
            if "sysfs_paths" in gpu_config:
                self.SYSFS_PATHS.update(gpu_config["sysfs_paths"])
        
        # Apply model configuration
        if "model_configuration" in self.config_data:
            model_config = self.config_data["model_configuration"]
            
            if "llama_cpp_path" in model_config:
                self.LLAMA_CPP_PATH = model_config["llama_cpp_path"]
            
            if "model_dir" in model_config:
                self.MODEL_DIR = os.path.expanduser(model_config["model_dir"])
            
            if "cache_dir" in model_config:
                self.CACHE_DIR = os.path.expanduser(model_config["cache_dir"])
            
            if "slots_dir" in model_config:
                self.SLOTS_DIR = model_config["slots_dir"]
        
        # Apply default parameters
        if "default_parameters" in self.config_data:
            self.DEFAULT_PARAMS.update(self.config_data["default_parameters"])
        
        # Apply monitoring settings
        if "monitoring" in self.config_data:
            monitoring = self.config_data["monitoring"]
            
            if "update_interval" in monitoring:
                self.UPDATE_INTERVAL = monitoring["update_interval"]
            
            if "cache_ttl" in monitoring:
                self.CACHE_TTL = monitoring["cache_ttl"]
            
            if "diagnosis_interval" in monitoring:
                self.DIAGNOSIS_INTERVAL = monitoring["diagnosis_interval"]
    
    def verify(self):
        """Verify all required paths and configurations"""
        logger.info("Verifying configuration...")
        
        # Check model directory
        if not os.path.exists(self.MODEL_DIR):
            logger.warning(f"Model directory {self.MODEL_DIR} does not exist. Creating it...")
            try:
                os.makedirs(self.MODEL_DIR, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create model directory: {e}")
        
        # Check slots directory
        if not os.path.exists(self.SLOTS_DIR):
            logger.warning(f"Slots directory {self.SLOTS_DIR} does not exist. Creating it...")
            try:
                os.makedirs(self.SLOTS_DIR, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create slots directory: {e}")
        
        # Check llama-server executable
        if not os.path.exists(self.LLAMA_CPP_PATH):
            logger.error(f"llama-server executable not found at {self.LLAMA_CPP_PATH}")
            logger.error("Please compile llama.cpp or update the LLAMA_CPP_PATH variable")
            return False
        
        # Verify GPU cards exist in sysfs
        for card_id, display_name, vulkan_id in self.GPU_CARDS:
            card_path = f"/sys/class/drm/{card_id}"
            if not os.path.exists(card_path):
                logger.warning(f"GPU card {card_id} ({display_name}) not found at {card_path}")
        
        logger.info("Configuration verified successfully")
        return True
    
    def get_models(self):
        """Retrieve all available models from the models directory"""
        if not os.path.exists(self.MODEL_DIR):
            logger.warning(f"Model directory {self.MODEL_DIR} does not exist")
            return []
        
        return [f for f in os.listdir(self.MODEL_DIR) if f.endswith(".gguf")]
    
    def get_gpu_list(self):
        """Prepare GPU list sorted by Vulkan ID"""
        gpus = []
        for card_id, display_name, vulkan_id in sorted(self.GPU_CARDS, key=lambda x: x[2]):
            gpus.append({
                "vulkan_id": vulkan_id,
                "display_name": display_name,
                "card_id": card_id
            })
        return gpus
    
    def get_sysfs_path(self, card_id: str, metric: str) -> str:
        """Get sysfs path for a specific GPU metric"""
        base_path = f"/sys/class/drm/{card_id}/device"
        path_pattern = self.SYSFS_PATHS.get(metric, "")
        
        if not path_pattern:
            return ""
        
        return os.path.join(base_path, path_pattern)
    
    def save_template(self, template_path: str = "config_template.json"):
        """Save current configuration as a template"""
        template = {
            "gpu_configuration": {
                "gpu_cards": [
                    {
                        "card_id": card_id,
                        "display_name": display_name,
                        "vulkan_id": vulkan_id
                    }
                    for card_id, display_name, vulkan_id in self.GPU_CARDS
                ],
                "sysfs_paths": self.SYSFS_PATHS
            },
            "model_configuration": {
                "llama_cpp_path": self.LLAMA_CPP_PATH,
                "model_dir": self.MODEL_DIR.replace(self.HOME_DIR, "~"),
                "cache_dir": self.CACHE_DIR.replace(self.HOME_DIR, "~"),
                "slots_dir": self.SLOTS_DIR
            },
            "default_parameters": self.DEFAULT_PARAMS,
            "monitoring": {
                "update_interval": self.UPDATE_INTERVAL,
                "cache_ttl": self.CACHE_TTL,
                "diagnosis_interval": self.DIAGNOSIS_INTERVAL
            }
        }
        
        try:
            with open(template_path, 'w') as f:
                json.dump(template, f, indent=2)
            logger.info(f"Configuration template saved to {template_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration template: {e}")
            return False
