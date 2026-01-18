"""
Logging configuration and utilities
"""

import logging
from collections import deque
import queue

def setup_logging(name):
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)

class LogBuffer:
    """Thread-safe log buffer for storing server logs"""
    
    def __init__(self, max_size=1000):
        self.buffer = deque(maxlen=max_size)
        self.queue = queue.Queue()
    
    def add(self, log_entry):
        """Add a log entry to the buffer"""
        self.buffer.append(log_entry)
        self.queue.put(log_entry)
    
    def get_all(self):
        """Get all logs from the buffer"""
        return list(self.buffer)
    
    def get_new(self):
        """Get new logs from the queue"""
        entries = []
        try:
            while not self.queue.empty():
                entries.append({"text": self.queue.get_nowait()})
        except Exception as e:
            logging.getLogger(__name__).error(f"Error getting logs: {e}")
        return entries
    
    def clear(self):
        """Clear the log buffer"""
        self.buffer.clear()
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                pass
