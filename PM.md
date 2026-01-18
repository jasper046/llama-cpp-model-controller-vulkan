# 🎯 Project Manager (PM.md)

## 🏗️ Project Overview
- **Goal**: Vulkan-enabled web controller for llama.cpp models with AMD GPU support
- **Stack**: Python/Flask backend, HTML/JS frontend, Vulkan GPU monitoring via sysfs
- **Status**: Modular architecture complete with JSON configuration, ready for target machine testing

## 🚦 Status Board
- [x] Phase 1: Planning & Architecture (Vulkan conversion complete)
- [x] Phase 2: Core Development (Basic functionality working)
- [x] Phase 3: Architecture Refactoring (Modular architecture complete) ✓
- [x] Phase 4: Production Deployment (app.py modularized) ✓
- [x] Phase 5: Configuration System Improvements (JSON config added) ✓
- [ ] Phase 6: Target Machine Validation (Testing needed on remote machine)

## 📝 Active Task List
- [x] Refactor monolithic app.py into modular architecture ✓
- [x] Separate routes, services, and models into /src directory ✓
- [x] Update default tensor split to 0.54,0.13,0.33 ✓
- [x] Replace app.py with modular architecture ✓
- [x] Refactor gpu_service.py to meet <400 line limit (split into gpu_service.py and gpu_diagnosis_service.py) ✓
- [x] Create JSON configuration system for easy target machine adaptation ✓
- [x] Improve GPU monitoring with sysfs path discovery and fallbacks ✓
- [ ] Test on target machine (remote, not this laptop)
- [ ] Verify GPU monitoring works with actual AMD GPUs
- [ ] Validate llama-server process management
- [ ] Check all Flask routes and frontend integration

## ✅ Critical Issues RESOLVED
### 1. ✅ Configuration System IMPROVED
**Solution Implemented**:
- Created `config_template.json` with all configuration options
- Updated `Config` class to support JSON loading with fallback to defaults
- Added configuration validation and sysfs path discovery
- Documented GPU card mapping in README.md

### 2. ✅ GPU Monitoring IMPROVED
**Solutions Implemented**:
- Added sysfs path discovery with glob pattern support
- Implemented fallback reading methods for missing sysfs paths
- Added GPU-specific configuration via `SYSFS_PATHS` in config
- Enhanced error handling with default values

## 📓 Decision Log & Architecture Constraints
- *Decision*: Strict separation between frontend serving and backend processing
- *Decision*: Backend decides when to update data, not frontend
- *Decision*: Modular architecture with dependency injection
- *Decision*: Default tensor split changed to 0.54,0.13,0.33 for optimal GPU memory distribution
- *Constraint*: Files should be <400 lines each (achieved: app.py 68L, services ~100-200L each)
- *Constraint*: Use caching layers for instant serving of pre-computed data
- *Structure*: src/routes (Flask endpoints), src/services (business logic), src/utils (shared utilities)
- *Pattern*: Services are initialized once and injected into routes
- *Separation*: Configuration centralized in Config class, separate from business logic
- *Refactoring*: GPU service split into monitoring (gpu_service.py) and diagnosis (gpu_diagnosis_service.py)
- *Configuration*: JSON-based config system with template support for easy adaptation

## ⚠️ Risks & Blockers
- [x] app.py is monolithic (567 lines) and needs modularization ✓
- [ ] **CRITICAL**: Development on laptop, but app runs on different target machine with AMD GPUs
- [ ] Cannot test GPU monitoring, llama-server integration, or Vulkan functionality locally
- [ ] Need to test Flask integration on target machine
- [ ] No proper caching layer for GPU stats (GPUService has basic caching)
- [ ] Heavy operations may block UI responsiveness (background threads needed)
- [ ] Error handling could be more robust (fail-fast logic needed)
- [x] **RESOLVED**: Configuration system needs JSON-based templates for easy adaptation ✓
- [x] **RESOLVED**: GPU monitoring may fail on target machine due to sysfs path differences ✓

## 🎯 Next Actions - TARGET MACHINE TESTING
1. **Target Machine Setup (CRITICAL)**:
   - **IMPORTANT**: App runs on different machine than this laptop (AMD GPUs required)
   - Copy `config_template.json` to `config.json` on target machine
   - Update GPU card IDs, display names, and Vulkan IDs in `config.json`
   - Adjust sysfs paths if needed for specific AMD GPU model

2. **Test Commands for Target Machine**:
   ```bash
   # 1. Setup virtual environment
   python -m venv venv
   source venv/bin/activate
   pip install flask
   
   # 2. Validate modular architecture
   python test_modular_architecture.py
   
   # 3. Test configuration loading
   python -c "from src.utils.config import Config; c = Config(); print(f'GPU Cards: {c.GPU_CARDS}')"
   
   # 4. Run the application
   python app.py
   
   # 5. Test web interface
   # Open browser to http://localhost:5000
   ```

3. **Verification Checklist**:
   - [ ] Configuration loads correctly from config.json
   - [ ] GPU stats display correctly (temperature, usage, clocks)
   - [ ] Model loading and llama-server process management works
   - [ ] Tensor split configuration (0.54,0.13,0.33) applies correctly
   - [ ] All frontend controls function properly
   - [ ] Log streaming works in real-time
   - [ ] Settings persistence functions correctly
   - [ ] GPU diagnosis service works for crash detection

## 📁 Files Created/Modified
### New Modular Architecture:
- `app.py` (68L) - Main entry point with dependency injection
- `src/utils/config.py` - Centralized configuration management with JSON support
- `src/utils/logger.py` - Logging utilities and buffer
- `src/services/model_service.py` - Model process management
- `src/services/gpu_service.py` (203L) - GPU monitoring with improved sysfs handling
- `src/services/gpu_diagnosis_service.py` (236L) - GPU crash diagnosis
- `src/services/log_service.py` - Log management
- `src/services/settings_service.py` - User preferences
- `src/routes/__init__.py` - All Flask route definitions

### Configuration System:
- `config_template.json` - Comprehensive JSON configuration template
- `config.json` - User configuration (to be created on target machine)

### Documentation & Testing:
- `MODULAR_ARCHITECTURE.md` - Comprehensive architecture documentation
- `test_modular_architecture.py` - Validation script for target machine
- Updated `README.md` with JSON configuration instructions
- Updated `PM.md` with current status and decisions

### Configuration Updates:
- Updated default tensor split to `0.54,0.13,0.33` in:
  - `src/utils/config.py` (Config.DEFAULT_PARAMS)
  - `src/services/settings_service.py` (default_settings)

## 🔧 Technical Notes
- **File Size Reduction**: 567L → 68L (88% reduction in main file)
- **All files under 400 lines**: Meets line constraint (gpu_service: 203L, gpu_diagnosis: 236L)
- **GPU Service Split**: Monitoring separated from diagnosis for single responsibility
- **Dependency Injection**: Services initialized once, injected into routes
- **JSON Configuration**: Flexible config system for easy target machine adaptation
- **Sysfs Path Discovery**: Improved GPU monitoring with glob pattern support
- **Fallback Mechanisms**: Graceful degradation when sysfs paths are missing
- **Validation**: Python imports validated, Flask integration pending target machine test
- **Ready for Target**: Configuration system makes adaptation to different machines straightforward
