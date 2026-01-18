"""
Log service for managing server logs
"""

import logging
from src.utils.logger import LogBuffer

logger = logging.getLogger(__name__)

class LogService:
    """Service for managing application logs"""
    
    def __init__(self):
        self.log_buffer = LogBuffer()
    
    def add_log(self, message: str):
        """Add a log message to the buffer"""
        self.log_buffer.add(message)
    
    def get_logs(self):
        """Get new logs from the buffer"""
        return self.log_buffer.get_new()
    
    def clear_logs(self):
        """Clear the log buffer"""
        self.log_buffer.clear()
