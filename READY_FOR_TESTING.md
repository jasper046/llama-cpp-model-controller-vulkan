# Ready for Testing - Vulkan Conversion Complete ✅

## What Was Done

All code conversion from CUDA to Vulkan has been completed successfully. The application is ready for testing on your target hardware (RX 480 + RX 6600).

### Files Created
1. **config.py** - Centralized configuration
2. **CONVERSION_SUMMARY.md** - Detailed summary of all changes
3. **VULKAN_TODO.md** - Implementation checklist (Phases 0-9 complete)
4. **READY_FOR_TESTING.md** - This file

### Files Modified
1. **app.py** - Complete backend conversion to Vulkan
2. **templates/index.html** - Complete frontend UI updates
3. **README.md** - Updated documentation with Vulkan information

## Quick Start on Target Machine

1. **Install dependencies:**
   ```bash
   cd /path/to/llama-cpp-model-controller-vulkan
   python -m venv venv
   source venv/bin/activate
   pip install flask
   ```

2. **Verify configuration in `config.py`:**
   ```python
   LLAMA_CPP_PATH = os.path.join(HOME_DIR, "/usr/local/bin/llama-server")
   MODEL_DIR = os.path.join(HOME_DIR, "models")
   GPU_CARDS = [
       ("card1", "RX 480"),
       ("card2", "RX 6600")
   ]
   ```

3. **Verify GPU card mapping:**
   ```bash
   ls -la /sys/class/drm/
   ```
   If your AMD GPUs are on different card IDs, update `GPU_CARDS` in config.py.

4. **Start the application:**
   ```bash
   python app.py
   ```

5. **Access the web UI:**
   Open browser to `http://localhost:5000`

## Testing Checklist

### Phase 1: Basic Functionality
- [ ] Flask app starts without errors
- [ ] Web UI loads at http://localhost:5000
- [ ] Models directory shows available GGUF models
- [ ] Configuration paths are correct (check startup logs)

### Phase 2: GPU Monitoring
- [ ] GPU stats section shows both RX 480 and RX 6600
- [ ] Temperature readings appear and update
- [ ] Power readings appear and update
- [ ] GPU usage percentage appears and updates
- [ ] No permission errors in console/logs

### Phase 3: Model Loading
- [ ] Select a model from dropdown
- [ ] Start model with default parameters
- [ ] Check server logs stream correctly in UI
- [ ] Verify in logs that both GPUs are being used
- [ ] Model responds to requests at http://localhost:4000

### Phase 4: Parameter Testing
- [ ] Try different tensor-split values (e.g., "1,0", "0.5,0.5", "1,0.4")
- [ ] Switch main GPU between 0 and 1
- [ ] Toggle flash attention on/off
- [ ] Change batch sizes (256, 512, 1024)
- [ ] Toggle continuous batching
- [ ] Change context size (4096, 8192, 16384)

### Phase 5: Process Management
- [ ] Stop model button terminates llama-server
- [ ] Cache is cleared after stopping
- [ ] No orphaned llama-server processes (`ps aux | grep llama`)
- [ ] Can start a different model after stopping

## Expected Behavior

### GPU Monitoring
You should see something like:
```
RX 480 (card1)
Temp: 65°C | Usage: 45%
Power: 120W

RX 6600 (card2)
Temp: 58°C | Usage: 38%
Power: 85W
```

### Model Loading Logs
Look for these patterns in server logs:
- `ggml_vulkan: Found 2 Vulkan devices`
- VRAM allocation for each GPU
- Model loading progress
- Token generation metrics

## Common Issues & Solutions

### Issue: GPU stats show "N/A"
**Solution:** Check card IDs with `ls -la /sys/class/drm/` and update `GPU_CARDS` in config.py

### Issue: Only one GPU being used
**Solution:**
- Verify tensor-split is not "1,0" (which uses only GPU 0)
- Check llama-server logs for actual GPU allocation
- Ensure both GPUs have enough VRAM for the model

### Issue: Flash attention errors
**Solution:** Disable flash attention in UI and restart model

### Issue: Out of memory
**Solution:**
- Reduce context size to 8192 or 4096
- Adjust tensor-split to favor GPU with more VRAM
- Use smaller model quantization (Q4 instead of Q8)

### Issue: Model not starting
**Solution:**
- Check llama-server logs in UI for error messages
- Verify LLAMA_CPP_PATH is correct
- Ensure llama.cpp was compiled with Vulkan support: `ldd ~//usr/local/bin/llama-server | grep vulkan`

## Performance Comparison

After testing, compare with your working `start_model.sh` command:

**Working CLI command:**
```bash
~//usr/local/bin/llama-server \
  -m ~/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf \
  --ctx-size 16384 \
  --n-gpu-layers 99 \
  --main-gpu 0 \
  --tensor-split 1,0.4 \
  --flash-attn on \
  --batch-size 512 \
  --ubatch-size 128 \
  --port 4000 \
  --host 0.0.0.0 \
  --parallel 1 \
  --slot-save-path /tmp/llama_slots \
  --cont-batching
```

**Web UI equivalent:** Use the default settings, they match the above command exactly.

## Next Steps After Testing

1. **If testing succeeds:**
   - Mark Phase 8 complete in VULKAN_TODO.md
   - Consider implementing Phase 10 optional enhancements
   - Report any performance differences vs CLI

2. **If issues are found:**
   - Document specific error messages
   - Check relevant sections in CONVERSION_SUMMARY.md
   - Review troubleshooting section in README.md
   - Open issue with details for debugging

## Support Files

- **VULKAN_CONVERSION_GAMEPLAN.md** - Original detailed conversion plan
- **VULKAN_TODO.md** - Bite-sized implementation checklist
- **CONVERSION_SUMMARY.md** - Summary of all changes made
- **README.md** - User documentation with Vulkan-specific info

## Success Criteria

The conversion is successful when:
1. ✅ Models start from web UI with same parameters as CLI
2. ✅ GPU monitoring shows accurate stats for both AMD GPUs
3. ✅ All Vulkan parameters are configurable via UI
4. ✅ Server logs stream to browser in real-time
5. ✅ Can switch between models without issues
6. ✅ Performance matches direct CLI usage

Good luck with testing! 🚀
