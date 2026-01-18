#!/usr/bin/env python3
"""
Test VRAM reading from AMD sysfs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.config import Config
from src.services.gpu_service import GPUService

def test_vram_reading():
    """Test VRAM reading functionality"""
    print("Testing VRAM reading from AMD sysfs...")
    
    config = Config()
    gpu_service = GPUService(config)
    
    # Test reading stats for each GPU
    for card_id, display_name, vulkan_id in config.GPU_CARDS:
        print(f"\n{'='*60}")
        print(f"Testing {display_name} ({card_id}, Vulkan ID: {vulkan_id})...")
        print('='*60)
        
        try:
            stats = gpu_service._read_gpu_stats(card_id, display_name, vulkan_id)
            print(f"VRAM: {stats.memory}")
            print(f"Temperature: {stats.temp}")
            print(f"GPU Usage: {stats.usage}")
            print(f"Power: {stats.power}")
            print(f"GPU Clock: {stats.gpu_clock}")
            print(f"Memory Clock: {stats.mem_clock}")
            print(f"Fan Speed: {stats.fan_speed}")
            
            # Parse VRAM for percentage
            if 'Gi/' in stats.memory:
                try:
                    used_str, total_str = stats.memory.split('Gi/')
                    used = float(used_str.strip())
                    total = float(total_str.replace('Gi', '').strip())
                    if total > 0:
                        percentage = (used / total) * 100
                        print(f"VRAM Usage: {percentage:.1f}%")
                except:
                    print("Could not parse VRAM percentage")
                    
        except Exception as e:
            print(f"Error reading stats: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_vram_reading()
