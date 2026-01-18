#!/usr/bin/env python3
"""
Test script to verify modular architecture imports and structure.
Run this on the target machine to validate the new architecture.
"""

import sys
import os

def test_imports():
    """Test all module imports"""
    print("Testing modular architecture imports...")
    
    tests = [
        ("src.utils.config", "Config"),
        ("src.utils.logger", "setup_logging", "LogBuffer"),
        ("src.services.model_service", "ModelService"),
        ("src.services.gpu_service", "GPUService"),
        ("src.services.log_service", "LogService"),
        ("src.services.settings_service", "SettingsService"),
        ("src.routes", "register_routes"),
    ]
    
    all_passed = True
    for module_name, *imports in tests:
        try:
            module = __import__(module_name, fromlist=imports)
            for item in imports:
                if hasattr(module, item):
                    print(f"  ✓ {module_name}.{item}")
                else:
                    print(f"  ✗ {module_name}.{item} (not found)")
                    all_passed = False
        except ImportError as e:
            print(f"  ✗ {module_name} (ImportError: {e})")
            all_passed = False
        except Exception as e:
            print(f"  ✗ {module_name} (Error: {e})")
            all_passed = False
    
    return all_passed

def test_service_instantiation():
    """Test service instantiation and dependencies"""
    print("\nTesting service instantiation...")
    
    try:
        from src.utils.config import Config
        from src.services.model_service import ModelService
        from src.services.gpu_service import GPUService
        from src.services.log_service import LogService
        from src.services.settings_service import SettingsService
        
        config = Config()
        print(f"  ✓ Config created (MODEL_DIR: {config.MODEL_DIR})")
        
        model_service = ModelService(config)
        print("  ✓ ModelService instantiated")
        
        gpu_service = GPUService(config)
        print("  ✓ GPUService instantiated")
        
        log_service = LogService()
        print("  ✓ LogService instantiated")
        
        settings_service = SettingsService()
        print("  ✓ SettingsService instantiated")
        
        # Test GPUService methods
        if hasattr(gpu_service, 'diagnose_gpu_crash'):
            print("  ✓ GPUService.diagnose_gpu_crash method exists")
        else:
            print("  ✗ GPUService.diagnose_gpu_crash method missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Service instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_validation():
    """Test configuration validation"""
    print("\nTesting configuration validation...")
    
    try:
        from src.utils.config import Config
        config = Config()
        
        # Test get_models method
        models = config.get_models()
        print(f"  ✓ Config.get_models() returned {len(models)} models")
        
        # Test get_gpu_list method
        gpus = config.get_gpu_list()
        print(f"  ✓ Config.get_gpu_list() returned {len(gpus)} GPUs")
        
        # Test verify method
        is_valid = config.verify()
        print(f"  ✓ Config.verify() returned {is_valid}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Llama.cpp Model Controller - Modular Architecture Test")
    print("=" * 60)
    
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Run tests
    import_ok = test_imports()
    service_ok = test_service_instantiation()
    config_ok = test_config_validation()
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print(f"  Imports: {'PASS' if import_ok else 'FAIL'}")
    print(f"  Services: {'PASS' if service_ok else 'FAIL'}")
    print(f"  Config: {'PASS' if config_ok else 'FAIL'}")
    
    all_ok = import_ok and service_ok and config_ok
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_ok else '❌ SOME TESTS FAILED'}")
    
    if all_ok:
        print("\nNext steps:")
        print("1. Ensure Flask is installed in the virtual environment")
        print("2. Run: python app_new.py")
        print("3. Test web interface at http://localhost:5000")
        print("4. Compare functionality with original app.py")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
