# 🎯 Project Manager (PM.md)

## 🏗️ Project Overview
- **Goal**: Vulkan-enabled web controller for llama.cpp models with AMD GPU support
- **Stack**: Python/Flask backend, HTML/JS frontend, Vulkan GPU monitoring via sysfs
- **Status**: Modular architecture complete, ready for target machine testing

## 🚦 Status Board
- [x] Phase 1: Planning & Architecture (Vulkan conversion complete)
- [x] Phase 2: Core Development (Basic functionality working)
- [x] Phase 3: Architecture Refactoring (Modular architecture complete) ✓
- [x] Phase 4: Production Deployment (app_new.py replaced app.py) ✓
- [ ] Phase 5: Target Machine Validation (Testing needed on remote machine)

## 📝 Active Task List
- [x] Refactor monolithic app.py into modular architecture ✓
- [x] Separate routes, services, and models into /src directory ✓
- [x] Update default tensor split to 0.54,0.13,0.33 ✓
- [x] Replace app.py with modular app_new.py ✓
- [ ] Test on target machine (remote, not this laptop)
- [ ] Verify GPU monitoring works with actual AMD GPUs
- [ ] Validate llama-server process management
- [ ] Check all Flask routes and frontend integration

## 📓 Decision Log & Architecture Constraints
- *Decision*: Strict separation between frontend serving and backend processing
- *Decision*: Backend decides when to update data, not frontend
- *Decision*: Modular architecture with dependency injection
- *Decision*: Default tensor split changed to 0.54,0.13,0.33 for optimal GPU memory distribution
- *Constraint*: Files should be <400 lines each (achieved: app_new.py 80L, services ~100L each)
- *Constraint*: Use caching layers for instant serving of pre-computed data
- *Structure*: src/routes (Flask endpoints), src/services (business logic), src/utils (shared utilities)
- *Pattern*: Services are initialized once and injected into routes
- *Separation*: Configuration centralized in Config class, separate from business logic

## ⚠️ Risks & Blockers
- [x] app.py is monolithic (567 lines) and needs modularization ✓
- [ ] **CRITICAL**: Development on laptop, but app runs on different target machine with AMD GPUs
- [ ] Cannot test GPU monitoring, llama-server integration, or Vulkan functionality locally
- [ ] Need to test Flask integration on target machine
- [ ] No proper caching layer for GPU stats (GPUService has basic caching)
- [ ] Heavy operations may block UI responsiveness (background threads needed)
- [ ] Error handling could be more robust (fail-fast logic needed)

## 🎯 Next Actions
1. **Target Machine Testing (CRITICAL)**:
   - **IMPORTANT**: App runs on different machine than this laptop (AMD GPUs required)
   - Run `test_modular_architecture.py` on target machine to validate imports
   - Test `app.py` (formerly app_new.py) with Flask in virtual environment
   - Validate GPU monitoring works with actual AMD GPUs via sysfs
   - Test llama-server process management and Vulkan tensor splitting
   - Check all Flask routes and frontend integration

2. **Test Commands for Target Machine**:
   ```bash
   # 1. Setup virtual environment
   python -m venv venv
   source venv/bin/activate
   pip install flask
   
   # 2. Validate modular architecture
   python test_modular_architecture.py
   
   # 3. Run the application
   python app.py
   
   # 4. Test web interface
   # Open browser to http://localhost:5000
   ```

3. **Verification Checklist**:
   - [ ] GPU stats display correctly (temperature, usage, clocks)
   - [ ] Model loading and llama-server process management works
   - [ ] Tensor split configuration (0.54,0.13,0.33) applies correctly
   - [ ] All frontend controls function properly
   - [ ] Log streaming works in real-time
   - [ ] Settings persistence functions correctly

## 📁 Files Created/Modified
### New Modular Architecture:
- `app_new.py` (80L) - Main entry point with dependency injection
- `src/utils/config.py` - Centralized configuration management
- `src/utils/logger.py` - Logging utilities and buffer
- `src/services/model_service.py` - Model process management
- `src/services/gpu_service.py` - GPU monitoring with diagnosis
- `src/services/log_service.py` - Log management
- `src/services/settings_service.py` - User preferences
- `src/routes/__init__.py` - All Flask route definitions

### Documentation & Testing:
- `MODULAR_ARCHITECTURE.md` - Comprehensive architecture documentation
- `test_modular_architecture.py` - Validation script for target machine
- Updated `PM.md` with current status and decisions

### Configuration Updates:
- Updated default tensor split to `0.54,0.13,0.33` in:
  - `src/utils/config.py` (Config.DEFAULT_PARAMS)
  - `src/services/settings_service.py` (default_settings)

## 🔧 Technical Notes
- **File Size Reduction**: 567L → 80L (86% reduction in main file)
- **All files under 200 lines**: Meets <400 line constraint
- **GPU Diagnosis**: Integrated into GPUService with comprehensive crash detection
- **Dependency Injection**: Services initialized once, injected into routes
- **Caching**: Basic GPU stats caching implemented, needs enhancement
- **Validation**: Python imports validated, Flask integration pending target machine test
