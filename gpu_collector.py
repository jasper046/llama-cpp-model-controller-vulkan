"""
Backend GPU stats collection logic.
Pure data collection without caching or threading concerns.
"""

import os
import glob
import re
from typing import Dict, Any
from config import GPU_CARDS


def collect_gpu_stats() -> Dict[str, Any]:
    """
    Collect GPU stats from sysfs.
    Returns a dictionary with raw stats and metadata.

    Returns:
        Dict with keys:
        - 'gpus': List of GPU stat dictionaries
        - 'timestamp': Collection timestamp
        - 'errors': List of any errors encountered
    """
    import time

    gpus = []
    errors = []
    timestamp = time.time()

    for card_id, card_name, vulkan_id in GPU_CARDS:
        try:
            gpu_stat = _read_single_gpu(card_id, card_name, vulkan_id)
            gpus.append(gpu_stat)

            if gpu_stat.get("error"):
                errors.append(f"{card_id}: {gpu_stat['error']}")

        except Exception as e:
            errors.append(f"{card_id}: {str(e)}")
            # Add default stats for this GPU
            gpus.append({
                "index": card_id,
                "name": card_name,
                "vulkan_id": vulkan_id,
                "temp": "N/A",
                "usage": "0%",
                "power": "N/A",
                "gpu_clock": "N/A",
                "mem_clock": "N/A",
                "fan_speed": "N/A",
                "memory": "0.00Gi/0.00Gi",
                "error": str(e)
            })

    return {
        "gpus": gpus,
        "timestamp": timestamp,
        "errors": errors
    }


def _read_single_gpu(card_id: str, card_name: str, vulkan_id: int) -> Dict[str, Any]:
    """
    Read stats for a single GPU card.

    Returns:
        Dictionary with GPU stats
    """
    gpu_data = {
        "index": card_id,
        "name": card_name,
        "vulkan_id": vulkan_id,
        "temp": "N/A",
        "usage": "0%",
        "power": "N/A",
        "gpu_clock": "N/A",
        "mem_clock": "N/A",
        "fan_speed": "N/A",
        "memory": "0.00Gi/0.00Gi",
        "error": None
    }

    # Temperature
    temp_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/temp1_input"
    temp_files = glob.glob(temp_path)
    if temp_files:
        try:
            with open(temp_files[0]) as f:
                temp_c = int(f.read().strip()) // 1000
                gpu_data["temp"] = f"{temp_c}°C"
        except (ValueError, OSError):
            pass

    # Power usage
    power_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/power1_average"
    power_files = glob.glob(power_path)
    if power_files:
        try:
            with open(power_files[0]) as f:
                power_w = int(f.read().strip()) // 1000000
                gpu_data["power"] = f"{power_w}W"
        except (ValueError, OSError):
            pass

    # GPU usage percentage
    busy_path = f"/sys/class/drm/{card_id}/device/gpu_busy_percent"
    if os.path.exists(busy_path):
        try:
            with open(busy_path) as f:
                usage = f.read().strip()
                gpu_data["usage"] = f"{usage}%"
        except (ValueError, OSError):
            pass

    # GPU clock (MHz) - parse pp_dpm_sclk for active clock (marked with *)
    sclk_path = f"/sys/class/drm/{card_id}/device/pp_dpm_sclk"
    if os.path.exists(sclk_path):
        try:
            with open(sclk_path) as f:
                for line in f:
                    if '*' in line:
                        match = re.search(r'(\d+)\s*Mhz', line, re.IGNORECASE)
                        if match:
                            gpu_data["gpu_clock"] = f"{match.group(1)}MHz"
                        break
        except (ValueError, OSError):
            pass

    # Memory clock (MHz) - parse pp_dpm_mclk for active clock
    mclk_path = f"/sys/class/drm/{card_id}/device/pp_dpm_mclk"
    if os.path.exists(mclk_path):
        try:
            with open(mclk_path) as f:
                for line in f:
                    if '*' in line:
                        match = re.search(r'(\d+)\s*Mhz', line, re.IGNORECASE)
                        if match:
                            gpu_data["mem_clock"] = f"{match.group(1)}MHz"
                        break
        except (ValueError, OSError):
            pass

    # Fan speed (%) - calculate from fan1_input / fan1_max
    fan_input_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/fan1_input"
    fan_max_path = f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/fan1_max"
    fan_input_files = glob.glob(fan_input_path)
    fan_max_files = glob.glob(fan_max_path)

    if fan_input_files and fan_max_files:
        try:
            with open(fan_input_files[0]) as f:
                fan_input = int(f.read().strip())
            with open(fan_max_files[0]) as f:
                fan_max = int(f.read().strip())
            if fan_max > 0:
                fan_percent = int((fan_input / fan_max) * 100)
                gpu_data["fan_speed"] = f"{fan_percent}%"
        except (ValueError, ZeroDivisionError, OSError):
            pass

    # Memory usage
    vram_used_path = f"/sys/class/drm/{card_id}/device/mem_info_vram_used"
    vram_total_path = f"/sys/class/drm/{card_id}/device/mem_info_vram_total"
    if os.path.exists(vram_used_path) and os.path.exists(vram_total_path):
        try:
            with open(vram_used_path) as f:
                vram_used = int(f.read().strip())
            with open(vram_total_path) as f:
                vram_total = int(f.read().strip())
            if vram_total > 0:
                # Convert bytes to GiB
                vram_used_gib = vram_used / (1024**3)
                vram_total_gib = vram_total / (1024**3)
                gpu_data["memory"] = f"{vram_used_gib:.2f}Gi/{vram_total_gib:.2f}Gi"
        except (ValueError, ZeroDivisionError):
            pass

    return gpu_data


def get_default_gpu_stats() -> Dict[str, Any]:
    """
    Get default GPU stats (used when collection fails).

    Returns:
        Dictionary with default GPU stats
    """
    import time

    gpus = []
    for card_id, card_name, vulkan_id in GPU_CARDS:
        gpus.append({
            "index": card_id,
            "name": card_name,
            "vulkan_id": vulkan_id,
            "temp": "N/A",
            "usage": "0%",
            "power": "N/A",
            "gpu_clock": "N/A",
            "mem_clock": "N/A",
            "fan_speed": "N/A",
            "memory": "0.00Gi/0.00Gi"
        })

    return {
        "gpus": gpus,
        "timestamp": time.time(),
        "errors": ["Using default stats - collection failed"]
    }