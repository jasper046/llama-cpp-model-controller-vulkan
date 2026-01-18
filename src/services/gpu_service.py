"""
GPU service for monitoring AMD GPU statistics via sysfs
Uses background thread for data collection and caching
"""

import threading
import time
import logging
import glob
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class GPUStats:
    """GPU statistics data class"""
    card_id: str
    name: str
    vulkan_id: int
    temp: str
    usage: str
    power: str
    gpu_clock: str
    mem_clock: str
    fan_speed: str
    memory: str
    error: str = ""
    last_update: datetime = None

class GPUService:
    """Service for GPU monitoring with caching"""
    
    def __init__(self, config):
        self.config = config
        self.stats_cache: Dict[str, GPUStats] = {}
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        self.update_interval = config.UPDATE_INTERVAL
    
    def start_monitor(self):
        """Start the background GPU monitor thread"""
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            logger.warning("GPU monitor already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("GPU monitor started")
    
    def stop_monitor(self):
        """Stop the GPU monitor thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            logger.info("GPU monitor stopped")
    
    def get_stats(self) -> List[Dict[str, Any]]:
        """Get cached GPU statistics"""
        stats_list = []
        for gpu in self.stats_cache.values():
            stats_dict = {
                "index": gpu.card_id,
                "name": gpu.name,
                "vulkan_id": gpu.vulkan_id,
                "temp": gpu.temp,
                "usage": gpu.usage,
                "power": gpu.power,
                "gpu_clock": gpu.gpu_clock,
                "mem_clock": gpu.mem_clock,
                "fan_speed": gpu.fan_speed,
                "memory": gpu.memory,
            }
            if gpu.error:
                stats_dict["error"] = gpu.error
            stats_list.append(stats_dict)
        
        return stats_list
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_monitor()
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                self._update_stats()
            except Exception as e:
                logger.error(f"Error in GPU monitor loop: {e}")
            
            time.sleep(self.update_interval)
    
    def _update_stats(self):
        """Update GPU statistics from sysfs"""
        for card_id, display_name, vulkan_id in self.config.GPU_CARDS:
            try:
                stats = self._read_gpu_stats(card_id, display_name, vulkan_id)
                self.stats_cache[card_id] = stats
            except Exception as e:
                logger.error(f"Error reading stats for {card_id}: {e}")
                # Create error entry
                self.stats_cache[card_id] = GPUStats(
                    card_id=card_id,
                    name=display_name,
                    vulkan_id=vulkan_id,
                    temp="N/A",
                    usage="0%",
                    power="N/A",
                    gpu_clock="N/A",
                    mem_clock="N/A",
                    fan_speed="N/A",
                    memory="0.00Gi/0.00Gi",
                    error=str(e),
                    last_update=datetime.now()
                )
    
    def _read_gpu_stats(self, card_id: str, display_name: str, vulkan_id: int) -> GPUStats:
        """Read GPU statistics from sysfs with improved path handling"""
        def read_sysfs_metric(metric: str, default="N/A") -> str:
            """Read a sysfs metric with path resolution"""
            path_pattern = self.config.get_sysfs_path(card_id, metric)
            if not path_pattern:
                return default
            
            try:
                # Handle glob patterns
                if '*' in path_pattern:
                    matches = glob.glob(path_pattern)
                    if not matches:
                        return default
                    actual_path = matches[0]
                else:
                    actual_path = path_pattern
                
                with open(actual_path, 'r') as f:
                    return f.read().strip()
            except FileNotFoundError:
                logger.debug(f"Path not found: {path_pattern}")
                return default
            except PermissionError:
                logger.warning(f"Permission denied: {path_pattern}")
                return default
            except Exception as e:
                logger.debug(f"Error reading {path_pattern}: {e}")
                return default
        
        # Read temperature (in millidegrees Celsius)
        temp_raw = read_sysfs_metric("temperature", "0")
        temp = f"{int(temp_raw) // 1000}°C" if temp_raw != "N/A" else "N/A"
        
        # Read GPU utilization
        usage = read_sysfs_metric("gpu_busy_percent", "0")
        usage = f"{usage}%" if usage != "N/A" else "0%"
        
        # Read power (in microwatts)
        power_raw = read_sysfs_metric("power", "0")
        power = f"{int(power_raw) // 1000000}W" if power_raw != "N/A" else "N/A"
        
        # Read clocks
        gpu_clock_raw = read_sysfs_metric("gpu_clock", "N/A")
        mem_clock_raw = read_sysfs_metric("mem_clock", "N/A")
        
        # Parse clock states (format: "0: 300Mhz *" or "1: 1000Mhz")
        gpu_clock = self._parse_clock_state(gpu_clock_raw)
        mem_clock = self._parse_clock_state(mem_clock_raw)
        
        # Read fan speed (RPM)
        fan_speed = read_sysfs_metric("fan_speed", "N/A")
        fan_speed = f"{fan_speed}RPM" if fan_speed != "N/A" else "N/A"
        
        # Read VRAM from AMD sysfs
        vram_total_raw = read_sysfs_metric("vram_total", "0")
        vram_used_raw = read_sysfs_metric("vram_used", "0")
        
        # Convert bytes to GiB (1 GiB = 1073741824 bytes)
        if vram_total_raw != "N/A" and vram_used_raw != "N/A":
            try:
                vram_total = int(vram_total_raw)
                vram_used = int(vram_used_raw)
                vram_total_gib = vram_total / 1073741824
                vram_used_gib = vram_used / 1073741824
                memory = f"{vram_used_gib:.2f}Gi/{vram_total_gib:.2f}Gi"
            except (ValueError, ZeroDivisionError):
                memory = "0.00Gi/0.00Gi"
        else:
            memory = "0.00Gi/0.00Gi"
        
        return GPUStats(
            card_id=card_id,
            name=display_name,
            vulkan_id=vulkan_id,
            temp=temp,
            usage=usage,
            power=power,
            gpu_clock=gpu_clock,
            mem_clock=mem_clock,
            fan_speed=fan_speed,
            memory=memory,
            last_update=datetime.now()
        )
    
    def _parse_clock_state(self, clock_data: str) -> str:
        """Parse clock state from pp_dpm format with improved handling"""
        if clock_data == "N/A":
            return "N/A"
        
        lines = clock_data.strip().split('\n')
        for line in lines:
            if '*' in line:  # Current state marked with *
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[1].strip().split()[0]  # Get frequency part
        
        # If no current state found, return first or N/A
        if lines:
            parts = lines[0].split(':')
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
        
        return "N/A"
