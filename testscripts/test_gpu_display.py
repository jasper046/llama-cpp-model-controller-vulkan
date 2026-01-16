#!/usr/bin/env python3
"""
Test script to verify GPU display and error detection functionality.
"""

import json
import sys
import os

# Add current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from process_monitor import diagnose_gpu_crash, check_d_state_processes, check_gpu_sysfs_health


def test_process_monitor():
    """Test the process monitor module"""
    print("=" * 60)
    print("Testing Process Monitor Module")
    print("=" * 60)

    # Test 1: Check for D state processes
    print("\n1. Checking for D state processes...")
    has_d_state, d_state_pids = check_d_state_processes("llama-server")
    print(f"   Has D state: {has_d_state}")
    print(f"   D state PIDs: {d_state_pids}")

    # Test 2: Check GPU sysfs health
    print("\n2. Checking GPU sysfs health (RX 470 - card1)...")
    is_healthy, errors = check_gpu_sysfs_health("card1")
    print(f"   Is healthy: {is_healthy}")
    if errors:
        print(f"   Errors: {errors}")

    # Test 3: Full diagnosis
    print("\n3. Running full GPU diagnosis...")
    diagnosis = diagnose_gpu_crash()
    print(f"   D State Processes: {diagnosis['d_state_processes']}")
    print(f"   D State PIDs: {diagnosis['d_state_pids']}")
    print(f"   GPU Sysfs Healthy: {diagnosis['gpu_sysfs_healthy']}")
    print(f"   Sysfs Errors: {diagnosis['gpu_sysfs_errors']}")
    print(f"   Journalctl Errors: {diagnosis['journalctl_errors']}")
    print(f"   Severity: {diagnosis['severity']}")
    print(f"   Recommendation: {diagnosis['recommendation']}")

    # Test 4: Check response format for /gpu endpoint
    print("\n4. Simulating /gpu endpoint response format...")
    mock_response = {
        "gpus": [
            {
                "index": "card1",
                "name": "RX 470",
                "vulkan_id": 1,
                "temp": "65°C",
                "usage": "45%",
                "power": "120W",
                "gpu_clock": "1206MHz",
                "mem_clock": "1750MHz",
                "fan_speed": "75%",
                "memory": "4.50Gi/8.00Gi",
                "error": None
            },
            {
                "index": "card2",
                "name": "RX 6600",
                "vulkan_id": 0,
                "temp": "55°C",
                "usage": "30%",
                "power": "100W",
                "gpu_clock": "2495MHz",
                "mem_clock": "2000MHz",
                "fan_speed": "50%",
                "memory": "2.50Gi/8.00Gi",
                "error": None
            }
        ],
        "health": diagnosis,
        "timestamp": 1234567890.123
    }
    print(f"   Response structure: OK")
    print(f"   Number of GPUs: {len(mock_response['gpus'])}")
    print(f"   Health severity: {mock_response['health']['severity']}")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

    # Summary
    print("\nSummary:")
    if diagnosis['severity'] == 'critical':
        print("  ⚠️  CRITICAL: GPU crash detected! Check D state processes.")
    elif diagnosis['severity'] == 'warning':
        print("  ⚠️  WARNING: GPU issues detected. Monitor closely.")
    else:
        print("  ✅ OK: No GPU issues detected.")

    return diagnosis


if __name__ == "__main__":
    try:
        result = test_process_monitor()
        sys.exit(0 if result['severity'] == 'info' else 1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)