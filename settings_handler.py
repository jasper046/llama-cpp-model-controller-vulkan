import os
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class SettingsHandler:
    """Handle persistent storage of user settings for the Llama Model Controller"""

    # Default settings (match app.py defaults)
    DEFAULT_SETTINGS = {
        # Model selection (store index, not value, as requested)
        "model_index": 0,

        # Model parameters
        "ngl": "999",  # All layers to GPU for maximum speed
        "ctx_size": "16384",
        "port": "4000",
        "host": "0.0.0.0",

        # Advanced settings
        "main_gpu": "0",
        "tensor_split": "1,0.4",
        "batch_size": "512",
        "ubatch_size": "128",
        "flash_attn": "on",
        "parallel": "1",
        "cont_batching": "true",
        "extra_args": "--jinja --chat-template chatml --gpu-sampling -ctk q8_0"
    }

    # Settings file path
    SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".llama_model_controller_settings.json")

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """Get all default settings"""
        return cls.DEFAULT_SETTINGS.copy()

    @classmethod
    def get_default(cls, key: str) -> Any:
        """Get default value for a specific setting"""
        return cls.DEFAULT_SETTINGS.get(key)

    @classmethod
    def load_settings(cls) -> Dict[str, Any]:
        """Load user settings from file, fall back to defaults if file doesn't exist"""
        try:
            if os.path.exists(cls.SETTINGS_FILE):
                with open(cls.SETTINGS_FILE, 'r') as f:
                    loaded_settings = json.load(f)

                # Ensure all expected keys exist (merge with defaults for missing keys)
                settings = cls.DEFAULT_SETTINGS.copy()
                settings.update(loaded_settings)
                logger.debug(f"Loaded settings from {cls.SETTINGS_FILE}")
                return settings
            else:
                logger.debug(f"Settings file {cls.SETTINGS_FILE} not found, using defaults")
                return cls.DEFAULT_SETTINGS.copy()

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return cls.DEFAULT_SETTINGS.copy()

    @classmethod
    def save_settings(cls, settings: Dict[str, Any]) -> bool:
        """Save user settings to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(cls.SETTINGS_FILE), exist_ok=True)

            with open(cls.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)

            logger.debug(f"Saved settings to {cls.SETTINGS_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    @classmethod
    def save_setting(cls, key: str, value: Any) -> bool:
        """Save a single setting"""
        settings = cls.load_settings()
        settings[key] = value
        return cls.save_settings(settings)

    @classmethod
    def reset_to_defaults(cls) -> bool:
        """Reset all settings to defaults and delete settings file"""
        try:
            if os.path.exists(cls.SETTINGS_FILE):
                os.remove(cls.SETTINGS_FILE)
                logger.debug(f"Removed settings file {cls.SETTINGS_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False

    @classmethod
    def get_form_defaults(cls, request_form) -> Dict[str, str]:
        """Get form values with user preferences as defaults, fallback to hardcoded defaults"""
        user_settings = cls.load_settings()
        form_defaults = {}

        # Map form field names to settings keys (some are the same)
        field_mapping = {
            'model': 'model_index',  # Special handling needed for model
            'ngl': 'ngl',
            'ctx_size': 'ctx_size',
            'port': 'port',
            'host': 'host',
            'main_gpu': 'main_gpu',
            'tensor_split': 'tensor_split',
            'batch_size': 'batch_size',
            'ubatch_size': 'ubatch_size',
            'flash_attn': 'flash_attn',
            'parallel': 'parallel',
            'cont_batching': 'cont_batching',
            'extra_args': 'extra_args'
        }

        for form_field, setting_key in field_mapping.items():
            if form_field == 'model':
                # Model is special - we store index, not value
                # The actual model value will be determined from the index when needed
                continue
            # Use user setting if exists and request doesn't have it, otherwise use request value
            form_value = request_form.get(form_field)
            if form_value is None or form_value == '':
                form_defaults[form_field] = str(user_settings.get(setting_key, cls.get_default(setting_key)))
            else:
                form_defaults[form_field] = form_value

        return form_defaults