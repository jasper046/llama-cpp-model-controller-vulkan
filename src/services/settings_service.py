"""
Settings service for managing user preferences
"""

import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SettingsService:
    """Service for managing user settings"""
    
    def __init__(self):
        self.settings_file = os.path.expanduser("~/.llama_controller_settings.json")
        self.default_settings = {
            "model_index": 0,
            "ngl": "999",
            "ctx_size": "16384",
            "port": "4000",
            "host": "0.0.0.0",
            "main_gpu": "0",
            "tensor_split": "0.54,0.13,0.33",
            "batch_size": "512",
            "ubatch_size": "128",
            "flash_attn": "on",
            "parallel": "1",
            "cont_batching": "true",
            "extra_args": "--jinja --chat-template chatml"
        }
    
    def load_settings(self) -> Dict[str, Any]:
        """Load user settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**self.default_settings, **loaded}
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
        
        return self.default_settings.copy()
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save user settings to file"""
        try:
            # Only save settings that are different from defaults
            to_save = {}
            for key, value in settings.items():
                if key in self.default_settings and value != self.default_settings[key]:
                    to_save[key] = value
            
            with open(self.settings_file, 'w') as f:
                json.dump(to_save, f, indent=2)
            
            logger.info("Settings saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def reset_settings(self) -> bool:
        """Reset settings to defaults"""
        try:
            if os.path.exists(self.settings_file):
                os.remove(self.settings_file)
            logger.info("Settings reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False
    
    def get_form_defaults(self, form_data: Dict[str, str]) -> Dict[str, str]:
        """Get parameter defaults with user preferences as priority"""
        user_settings = self.load_settings()
        defaults = {}
        
        # Map form field names to setting names
        field_mapping = {
            "ngl": "ngl",
            "ctx_size": "ctx_size",
            "port": "port",
            "host": "host",
            "main_gpu": "main_gpu",
            "tensor_split": "tensor_split",
            "batch_size": "batch_size",
            "ubatch_size": "ubatch_size",
            "flash_attn": "flash_attn",
            "parallel": "parallel",
            "cont_batching": "cont_batching",
            "extra_args": "extra_args"
        }
        
        for form_field, setting_name in field_mapping.items():
            # Priority: form data > user settings > defaults
            if form_field in form_data and form_data[form_field]:
                defaults[setting_name] = form_data[form_field]
            elif setting_name in user_settings:
                defaults[setting_name] = user_settings[setting_name]
            else:
                defaults[setting_name] = self.default_settings[setting_name]
        
        return defaults
