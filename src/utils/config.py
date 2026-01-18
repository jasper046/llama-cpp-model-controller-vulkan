"""
Configuration management for the Llama.cpp Model Controller
Centralized configuration with validation.
"""

import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management"""
    
    def __init__(self):
        self.HOME_DIR = os.path.expanduser("~")
        self.LLAMA_CPP_PATH = "/usr/local/bin/llama-server"
        self.MODEL_DIR = os.path.join(self.HOME_DIR, "models")
        self.CACHE_DIR = os.path.join(self.HOME_DIR, ".cache/llama")
        self.SLOTS_DIR = "/tmp/llama_slots"
        
        # GPU configuration - should be updated based on system
        self.GPU_CARDS = [
            ("card1", "RX 470", 1),
            ("card2", "RX 6600", 0)
        ]
        
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
        for card_id, _, _ in self.GPU_CARDS:
            card_path = f"/sys/class/drm/{card_id}"
            if not os.path.exists(card_path):
                logger.warning(f"GPU card {card_id} not found at {card_path}")
        
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
