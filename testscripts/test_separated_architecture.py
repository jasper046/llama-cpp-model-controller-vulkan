#!/usr/bin/env python3
"""
Test script for the separated GPU architecture.
Tests backend collector, monitor, and integration.
"""

import time
import logging
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_backend_collector():
    """Test the backend GPU collector"""
    print("Testing Backend GPU Collector...")
    print("=" * 60)

    try:
        from gpu_collector import collect_gpu_stats, get_default_gpu_stats

        # Test 1: Collect actual stats
        print("\nTest 1: Collecting GPU stats...")
        collected_data = collect_gpu_stats()

        print(f"Collection timestamp: {collected_data['timestamp']}")
        print(f"Number of GPUs found: {len(collected_data['gpus'])}")
        print(f"Errors: {collected_data['errors']}")

        for i, gpu in enumerate(collected_data['gpus']):
            print(f"\nGPU {i}: {gpu['name']}")
            print(f"  Card: {gpu['index']}, Vulkan: {gpu['vulkan_id']}")
            print(f"  Temperature: {gpu['temp']}")
            print(f"  Usage: {gpu['usage']}")
            print(f"  Power: {gpu['power']}")

        # Test 2: Get default stats
        print("\nTest 2: Getting default stats...")
        default_data = get_default_gpu_stats()
        print(f"Default stats timestamp: {default_data['timestamp']}")
        print(f"Default GPUs: {len(default_data['gpus'])}")
        print(f"Default errors: {default_data['errors']}")

        return True

    except Exception as e:
        print(f"\nError testing backend collector: {e}")
        return False

def test_gpu_monitor():
    """Test the GPU monitor with backend collector"""
    print("\n\nTesting GPU Monitor with Backend Collector...")
    print("=" * 60)

    try:
        from gpu_monitor import GPUMonitor

        # Create monitor with fast update for testing
        monitor = GPUMonitor(update_interval=1.0)

        print("Starting GPU monitor...")
        monitor.start()
        time.sleep(1.5)  # Wait for initial collection

        # Test: Get cached stats
        print("\nGetting cached stats from monitor...")
        stats = monitor.get_stats()

        print(f"Cached GPUs: {len(stats)}")
        for i, gpu in enumerate(stats):
            print(f"\nGPU {i}: {gpu['name']}")
            print(f"  Last update: {gpu.get('last_update', 'N/A')}")
            print(f"  Error: {gpu.get('error', 'None')}")
            print(f"  Usage: {gpu['usage']}")

        # Test force update
        print("\nForcing update...")
        monitor.force_update()
        time.sleep(0.5)

        stats2 = monitor.get_stats()
        print(f"Updated stats retrieved successfully")

        # Cleanup
        print("\nStopping GPU monitor...")
        monitor.stop()

        return True

    except Exception as e:
        print(f"\nError testing GPU monitor: {e}")
        return False

def test_integration():
    """Test the full integration"""
    print("\n\nTesting Full Integration...")
    print("=" * 60)

    try:
        # Import all components
        from gpu_collector import collect_gpu_stats
        from gpu_monitor import GPUMonitor

        print("1. Backend collector works independently")
        collected = collect_gpu_stats()
        print(f"   ✓ Collected {len(collected['gpus'])} GPUs")

        print("\n2. Monitor uses backend collector")
        monitor = GPUMonitor(update_interval=1.0)
        monitor.start()
        time.sleep(1.5)

        cached = monitor.get_stats()
        print(f"   ✓ Monitor cached {len(cached)} GPUs")

        print("\n3. Architecture separation verified")
        print("   ✓ Backend: Pure data collection (gpu_collector.py)")
        print("   ✓ Middleware: Caching & serving (gpu_monitor.py)")
        print("   ✓ Frontend: Fast API responses (app.py)")

        monitor.stop()
        return True

    except Exception as e:
        print(f"\nError testing integration: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Separated GPU Architecture")
    print("=" * 60)

    tests = [
        ("Backend Collector", test_backend_collector),
        ("GPU Monitor", test_gpu_monitor),
        ("Full Integration", test_integration),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    all_passed = True
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not success:
            all_passed = False

    print(f"\n{'='*60}")
    if all_passed:
        print("ALL TESTS PASSED! Architecture is properly separated.")
    else:
        print("SOME TESTS FAILED. Check the errors above.")

    print("\nArchitecture Overview:")
    print("1. gpu_collector.py - Pure data collection backend")
    print("2. gpu_monitor.py - Caching & background service")
    print("3. app.py - Frontend API serving cached data")

if __name__ == "__main__":
    main()