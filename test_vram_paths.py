#!/usr/bin/env python3
"""
Test script to find VRAM-related sysfs paths on AMD GPUs
"""

import os
import glob

def find_vram_paths(card_id="card1"):
    """Search for VRAM-related sysfs paths"""
    base_path = f"/sys/class/drm/{card_id}/device"
    
    print(f"Searching for VRAM paths under {base_path}...")
    
    # Look for memory-related files
    memory_patterns = [
        "mem_info",
        "vram",
        "memory",
        "gtt",
        "gpu_memory",
        "mem_",
        "_mem",
    ]
    
    found_paths = []
    
    # Walk the sysfs tree
    for root, dirs, files in os.walk(base_path):
        for file in files:
            file_lower = file.lower()
            if any(pattern in file_lower for pattern in memory_patterns):
                full_path = os.path.join(root, file)
                found_paths.append(full_path)
    
    # Also check for common AMD memory paths
    common_paths = [
        f"{base_path}/mem_info_vram_total",
        f"{base_path}/mem_info_vram_used",
        f"{base_path}/mem_info_gtt_total",
        f"{base_path}/mem_info_gtt_used",
        f"{base_path}/mem_busy_percent",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            found_paths.append(path)
    
    # Print results
    if found_paths:
        print(f"Found {len(found_paths)} memory-related paths:")
        for path in sorted(found_paths):
            try:
                with open(path, 'r') as f:
                    content = f.read().strip()
                    print(f"  {path}: {content}")
            except:
                print(f"  {path}: [unreadable]")
    else:
        print("No memory-related paths found")
        
    return found_paths

if __name__ == "__main__":
    # Test for all GPU cards
    for card_id in ["card1", "card2", "card3"]:
        card_path = f"/sys/class/drm/{card_id}"
        if os.path.exists(card_path):
            print(f"\n{'='*60}")
            print(f"Testing {card_id}...")
            print('='*60)
            find_vram_paths(card_id)
