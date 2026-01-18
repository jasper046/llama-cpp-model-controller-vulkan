"""
GPU service for monitoring AMD GPU statistics via sysfs
Uses background thread for data collection and caching
"""

import threading
import time
import logging
import subprocess
import re
import glob
import os
from typing import List, Dict, Any, Tuple, Optional
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
        self.update_interval = 2  # seconds
    
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
        """Read GPU statistics from sysfs"""
        base_path = f"/sys/class/drm/{card_id}/device"
        
        def read_sysfs(path, default="N/A"):
            try:
                with open(path, 'r') as f:
                    return f.read().strip()
            except:
                return default
        
        # Read temperature (in millidegrees Celsius)
        temp_raw = read_sysfs(f"{base_path}/hwmon/hwmon*/temp1_input", "0")
        temp = f"{int(temp_raw) // 1000}°C" if temp_raw != "N/A" else "N/A"
        
        # Read GPU utilization
        usage = read_sysfs(f"{base_path}/gpu_busy_percent", "0")
        usage = f"{usage}%" if usage != "N/A" else "0%"
        
        # Read power (in microwatts)
        power_raw = read_sysfs(f"{base_path}/hwmon/hwmon*/power1_average", "0")
        power = f"{int(power_raw) // 1000000}W" if power_raw != "N/A" else "N/A"
        
        # Read clocks (in kHz)
        gpu_clock_raw = read_sysfs(f"{base_path}/pp_dpm_sclk", "0")
        mem_clock_raw = read_sysfs(f"{base_path}/pp_dpm_mclk", "0")
        
        # Parse clock states (format: "0: 300Mhz *" or "1: 1000Mhz")
        gpu_clock = self._parse_clock_state(gpu_clock_raw)
        mem_clock = self._parse_clock_state(mem_clock_raw)
        
        # Read fan speed (RPM)
        fan_speed = read_sysfs(f"{base_path}/hwmon/hwmon*/fan1_input", "N/A")
        fan_speed = f"{fan_speed}RPM" if fan_speed != "N/A" else "N/A"
        
        # Read VRAM (simplified - AMD sysfs doesn't expose this easily)
        memory = "0.00Gi/0.00Gi"  # Placeholder
        
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
        """Parse clock state from pp_dpm format"""
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
    def diagnose_gpu_crash(self) -> Dict[str, Any]:
        """Comprehensive GPU crash diagnosis"""
        diagnosis = {
            'timestamp': time.time(),
            'd_state_processes': False,
            'd_state_pids': [],
            'gpu_sysfs_healthy': True,
            'gpu_sysfs_errors': [],
            'journalctl_errors': False,
            'journalctl_messages': [],
            'recommendation': 'No issues detected',
            'severity': 'info'  # info, warning, critical
        }

        # Check for D state processes
        has_d_state, d_pids = self._check_d_state_processes("llama-server")
        diagnosis['d_state_processes'] = has_d_state
        diagnosis['d_state_pids'] = d_pids

        # Check GPU sysfs health (focus on first GPU)
        if self.config.GPU_CARDS:
            card_id = self.config.GPU_CARDS[0][0]  # First GPU card ID
            is_healthy, errors = self._check_gpu_sysfs_health(card_id)
            diagnosis['gpu_sysfs_healthy'] = is_healthy
            diagnosis['gpu_sysfs_errors'] = errors

        # Check journalctl for GPU errors
        has_journal_errors, journal_messages = self._check_journalctl_gpu_errors("10 minutes ago")
        diagnosis['journalctl_errors'] = has_journal_errors
        diagnosis['journalctl_messages'] = journal_messages

        # Determine severity and recommendation
        if has_d_state:
            diagnosis['severity'] = 'critical'
            diagnosis['recommendation'] = (
                "CRITICAL: Processes in D (uninterruptible sleep) state detected. "
                "This indicates GPU memory crash. Processes cannot be killed. "
                "Recommended action: Hard system reset required."
            )
        elif not diagnosis['gpu_sysfs_healthy'] and has_journal_errors:
            diagnosis['severity'] = 'critical'
            diagnosis['recommendation'] = (
                "CRITICAL: GPU sysfs inaccessible and journalctl shows GPU errors. "
                "GPU may be crashed. Check GPU health and consider reset."
            )
        elif not diagnosis['gpu_sysfs_healthy']:
            diagnosis['severity'] = 'warning'
            diagnosis['recommendation'] = (
                "WARNING: GPU sysfs paths inaccessible. GPU may be unstable. "
                "Monitor closely and consider stopping model."
            )
        elif has_journal_errors:
            diagnosis['severity'] = 'warning'
            diagnosis['recommendation'] = (
                "WARNING: GPU-related errors in system logs. "
                "Monitor GPU stability and consider reducing overclock."
            )

        return diagnosis
    
    def _check_d_state_processes(self, process_name: str = "llama-server") -> Tuple[bool, List[str]]:
        """Check if any processes are in D (uninterruptible sleep) state."""
        processes = self._get_process_states(process_name)
        d_state_pids = []

        for proc in processes:
            if proc['is_d_state']:
                d_state_pids.append(proc['pid'])
                logger.warning(
                    f"Process {proc['pid']} ({proc['command']}) is in D state "
                    f"(uninterruptible sleep). State: {proc['state']}"
                )

        has_d_state = len(d_state_pids) > 0
        if has_d_state:
            logger.critical(
                f"Found {len(d_state_pids)} processes in D state: {d_state_pids}. "
                f"These cannot be killed and may indicate GPU memory crash."
            )

        return has_d_state, d_state_pids
    
    def _get_process_states(self, process_name: str = "llama-server") -> List[Dict[str, str]]:
        """Get process states for all processes matching the given name."""
        processes = []

        try:
            # Get process list with states
            result = subprocess.run(
                ['ps', '-eo', 'pid,stat,comm,args'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.error(f"ps command failed: {result.stderr}")
                return processes

            # Parse output
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue

                # Parse: PID STAT COMMAND ARGS
                parts = line.split(maxsplit=3)
                if len(parts) < 3:
                    continue

                pid, state, comm = parts[0], parts[1], parts[2]
                args = parts[3] if len(parts) > 3 else ""

                # Check if process name matches
                if process_name.lower() in comm.lower() or process_name.lower() in args.lower():
                    processes.append({
                        'pid': pid,
                        'state': state,
                        'command': comm,
                        'args': args,
                        'is_d_state': 'D' in state  # D = uninterruptible sleep
                    })

        except subprocess.TimeoutExpired:
            logger.error("ps command timed out")
        except Exception as e:
            logger.error(f"Error getting process states: {e}")

        return processes
    
    def _check_gpu_sysfs_health(self, card_id: str = "card1") -> Tuple[bool, List[str]]:
        """Check if GPU sysfs paths are accessible."""
        errors = []

        # Critical sysfs paths to check
        critical_paths = [
            f"/sys/class/drm/{card_id}/device/gpu_busy_percent",
            f"/sys/class/drm/{card_id}/device/pp_dpm_sclk",
            f"/sys/class/drm/{card_id}/device/pp_dpm_mclk",
            f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/temp1_input",
        ]

        for path_pattern in critical_paths:
            try:
                # Expand glob patterns
                if '*' in path_pattern:
                    matches = glob.glob(path_pattern)
                    if not matches:
                        errors.append(f"No matches for pattern: {path_pattern}")
                        continue
                    actual_path = matches[0]
                else:
                    actual_path = path_pattern

                # Check if path exists and is readable
                if not os.path.exists(actual_path):
                    errors.append(f"Path does not exist: {actual_path}")
                else:
                    # Try to read a small amount
                    with open(actual_path, 'r') as f:
                        f.read(1024)  # Try reading up to 1KB

            except PermissionError:
                errors.append(f"Permission denied: {actual_path}")
            except OSError as e:
                errors.append(f"OS error reading {actual_path}: {e}")
            except Exception as e:
                errors.append(f"Unexpected error with {path_pattern}: {e}")

        is_healthy = len(errors) == 0
        if not is_healthy:
            logger.warning(f"GPU sysfs health check failed for {card_id}: {errors}")

        return is_healthy, errors
    
    def _check_journalctl_gpu_errors(self, since: str = "5 minutes ago") -> Tuple[bool, List[str]]:
        """Check journalctl for GPU-related error messages."""
        error_messages = []

        try:
            # Common GPU error patterns
            patterns = [
                "amdgpu.*error",
                "amdgpu.*failed",
                "amdgpu.*timeout",
                "GPU.*reset",
                "memory.*allocation.*failed",
                "vram.*error",
                "D state",
                "uninterruptible",
            ]

            # Build journalctl command
            cmd = ['journalctl', '--since', since, '--priority=err', '--no-pager']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"journalctl command failed: {result.stderr}")
                return False, error_messages

            # Check for GPU-related errors
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line_lower = line.lower()
                if any(pattern in line_lower for pattern in patterns):
                    error_messages.append(line)
                    logger.warning(f"Found GPU-related error in logs: {line}")

        except subprocess.TimeoutExpired:
            logger.error("journalctl command timed out")
        except Exception as e:
            logger.error(f"Error checking journalctl: {e}")

        has_errors = len(error_messages) > 0
        return has_errors, error_messages
