"""
Background GPU monitoring service with caching.
Uses backend collector for data collection, focuses on caching and serving.
"""

import threading
import time
import logging
from typing import List, Dict, Any
from gpu_collector import collect_gpu_stats, get_default_gpu_stats

logger = logging.getLogger(__name__)


class GPUMonitor:
    """Background GPU monitoring service with caching"""

    def __init__(self, update_interval: float = 2.0):
        """
        Initialize GPU monitor with specified update interval.

        Args:
            update_interval: Seconds between GPU stats updates (default: 2.0)
        """
        self.update_interval = update_interval
        self.cached_stats = []
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self._lock = threading.Lock()

        # Initialize with default values
        self._initialize_default_stats()

    def _initialize_default_stats(self):
        """Initialize cached stats with default values for all GPUs"""
        with self._lock:
            default_data = get_default_gpu_stats()
            self.cached_stats = []
            for gpu in default_data["gpus"]:
                gpu["last_update"] = 0
                gpu["error"] = None
                self.cached_stats.append(gpu)

    def _update_stats(self):
        """Update cached GPU stats using backend collector"""
        try:
            # Use backend collector to get fresh stats
            collected_data = collect_gpu_stats()

            # Add metadata fields for caching
            new_stats = []
            for gpu in collected_data["gpus"]:
                gpu["last_update"] = time.time()
                new_stats.append(gpu)

            with self._lock:
                self.cached_stats = new_stats

            if collected_data["errors"]:
                logger.debug(f"GPU collection had errors: {collected_data['errors']}")

        except Exception as e:
            logger.error(f"Error updating GPU stats: {e}")
            # Fall back to default stats
            default_data = get_default_gpu_stats()
            new_stats = []
            for gpu in default_data["gpus"]:
                gpu["last_update"] = time.time()
                gpu["error"] = str(e)
                new_stats.append(gpu)

            with self._lock:
                self.cached_stats = new_stats

    def _monitor_loop(self):
        """Background thread loop for updating GPU stats"""
        logger.info(f"GPU monitor started with {self.update_interval}s update interval")

        while not self._stop_event.is_set():
            try:
                self._update_stats()
            except Exception as e:
                logger.error(f"Error in GPU monitor loop: {e}")

            # Sleep until next update, but check for stop event frequently
            for _ in range(int(self.update_interval * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

        logger.info("GPU monitor stopped")

    def start(self):
        """Start the background GPU monitoring thread"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            logger.info("GPU monitor thread started")

    def stop(self):
        """Stop the background GPU monitoring thread"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None
            logger.info("GPU monitor thread stopped")

    def get_stats(self) -> List[Dict[str, Any]]:
        """
        Get current cached GPU stats.

        Returns:
            List of GPU stat dictionaries
        """
        with self._lock:
            # Return a copy to avoid thread safety issues
            return self.cached_stats.copy()

    def force_update(self):
        """Force an immediate update of GPU stats"""
        self._update_stats()


# Global instance for easy access
gpu_monitor = GPUMonitor()