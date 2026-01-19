#!/usr/bin/env python3
"""
Main entry point for the Llama.cpp Model Controller (Vulkan Edition)
Modular architecture with strict separation of concerns.
"""

import os
import atexit
import logging
from flask import Flask

# Import modular components
from src.routes import register_routes
from src.services.model_service import ModelService
from src.services.gpu_service import GPUService
from src.services.gpu_diagnosis_service import GPUDiagnosisService
from src.services.log_service import LogService
from src.services.settings_service import SettingsService
from src.utils.config import Config
from src.utils.logger import setup_logging

# Set up logging
logger = setup_logging(__name__)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Initialize configuration
    config = Config()
    
    # Initialize services with dependency injection
    model_service = ModelService(config)
    gpu_service = GPUService(config)
    gpu_diagnosis_service = GPUDiagnosisService(config)
    log_service = LogService()
    settings_service = SettingsService()
    
    # Clean up any orphaned llama-server processes from previous runs
    orphaned_count = model_service.cleanup_orphaned_processes()
    if orphaned_count > 0:
        logger.info(f"Cleaned up {orphaned_count} orphaned llama-server process(es) on startup")
    
    # Register routes with services
    register_routes(app, model_service, gpu_service, gpu_diagnosis_service, log_service, settings_service)
    
    # Setup cleanup
    def cleanup():
        logger.info("Cleaning up before exit...")
        model_service.cleanup()
        gpu_service.cleanup()
    
    atexit.register(cleanup)
    
    return app, model_service, gpu_service

def main():
    """Main application entry point"""
    logger.info("Starting Llama Model Controller server (Vulkan Edition)...")
    
    # Create app and services
    app, model_service, gpu_service = create_app()
    
    # Verify configuration
    config = Config()
    config.verify()
    
    # Start background services
    gpu_service.start_monitor()
    
    # Run the application
    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == "__main__":
    main()
