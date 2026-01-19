"""
Model service for managing llama-server processes
Handles starting, stopping, and monitoring model processes
"""

import os
import subprocess
import signal
import threading
import time
import logging
import psutil
from typing import Optional, List

logger = logging.getLogger(__name__)

class ModelService:
    """Service for managing llama-server processes"""
    
    def __init__(self, config):
        self.config = config
        self.model_process: Optional[subprocess.Popen] = None
        self.log_reader_threads = []
    
    def start_model(self, model_name: str, params: dict) -> dict:
        """Start a llama-server process with given parameters"""
        # Stop any currently running model
        if self.model_process is not None:
            logger.info("Model already running, stopping it first...")
            self.stop_model()
        
        try:
            # Build command
            command = self._build_command(model_name, params)
            logger.debug(f"Executing command: {command}")
            
            # Start process
            env = os.environ.copy()
            self.model_process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                env=env,
                bufsize=1,
                universal_newlines=False
            )
            
            # Wait to check for immediate failures
            time.sleep(1)
            
            if self.model_process.poll() is not None:
                exit_code = self.model_process.poll()
                error_msg = f"Process exited immediately with code {exit_code}"
                logger.error(error_msg)
                self.model_process = None
                return {"success": False, "status": f"Error: {error_msg}"}
            
            return {"success": True, "status": f"Model '{model_name}' started"}
            
        except Exception as e:
            logger.exception(f"Error starting model: {e}")
            return {"success": False, "status": f"Error: {str(e)}"}
    
    def stop_model(self) -> bool:
        """Stop the running model process"""
        if self.model_process is None:
            logger.info("No model process to stop")
            return True
        
        process_gid = None
        try:
            # Get the process group ID (PGID)
            try:
                process_gid = os.getpgid(self.model_process.pid)
            except ProcessLookupError:
                logger.warning(f"Process {self.model_process.pid} no longer exists")
                self.model_process = None
                return True
            
            # Try graceful termination - kill entire process group
            logger.info(f"Sending SIGTERM to process group {process_gid} (PID {self.model_process.pid})")
            try:
                os.killpg(process_gid, signal.SIGTERM)
            except ProcessLookupError:
                logger.warning("Process group no longer exists")
                self.model_process = None
                return True
            
            # Wait with timeout
            try:
                self.model_process.wait(timeout=10)
                logger.info("Model process stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                logger.warning("Model process didn't stop gracefully, sending SIGKILL to process group...")
                try:
                    os.killpg(process_gid, signal.SIGKILL)
                except ProcessLookupError:
                    logger.warning("Process group no longer exists")
                    self.model_process = None
                    return True
                
                try:
                    self.model_process.wait(timeout=5)
                    logger.info("Model process killed with SIGKILL")
                    return True
                except subprocess.TimeoutExpired:
                    logger.error("Model process won't die!")
                    return False
        finally:
            self.model_process = None
    
    def is_running(self) -> bool:
        """Check if model process is running"""
        return self.model_process is not None and self.model_process.poll() is None
    
    def cleanup(self):
        """Cleanup resources"""
        if self.model_process is not None:
            self.stop_model()
        
        # Also clean up any orphaned llama-server processes
        self.cleanup_orphaned_processes()
    
    def _build_command(self, model_name: str, params: dict) -> str:
        """Build the llama-server command string"""
        # Merge with defaults
        merged_params = {**self.config.DEFAULT_PARAMS, **params}
        
        # Build command parts
        cmd_parts = [
            self.config.LLAMA_CPP_PATH,
            f"-m {self.config.MODEL_DIR}/{model_name}",
            f"--ctx-size {merged_params['ctx_size']}",
            f"--n-gpu-layers {merged_params['ngl']}",
            f"--main-gpu {merged_params['main_gpu']}",
            f"--tensor-split {merged_params['tensor_split']}",
            f"--flash-attn {merged_params['flash_attn']}",
            f"--batch-size {merged_params['batch_size']}",
            f"--ubatch-size {merged_params['ubatch_size']}",
            f"--port {merged_params['port']}",
            f"--host {merged_params['host']}",
            f"--parallel {merged_params['parallel']}",
            f"--slot-save-path {self.config.SLOTS_DIR}",
        ]
        
        # Add conditional parameters
        if merged_params.get('cont_batching') == 'true':
            cmd_parts.append("--cont-batching")
        
        # Add extra args if provided
        if merged_params.get('extra_args'):
            cmd_parts.append(merged_params['extra_args'])
        
        return " \\\n".join(cmd_parts)
    
    def cleanup_orphaned_processes(self) -> int:
        """
        Find and kill any orphaned llama-server processes.
        Returns the number of processes killed.
        """
        try:
            killed_count = 0
            
            # Find all llama-server processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if this is a llama-server process
                    if proc.info['name'] == 'llama-server' or 'llama-server' in proc.info['cmdline']:
                        # Check if this process is orphaned (parent is not our current process)
                        # or if it's a child process that should have been killed
                        logger.info(f"Found orphaned llama-server process: PID {proc.info['pid']}")
                        
                        # Kill the entire process group
                        try:
                            pgid = os.getpgid(proc.info['pid'])
                            os.killpg(pgid, signal.SIGKILL)
                            logger.info(f"Killed process group {pgid} for PID {proc.info['pid']}")
                            killed_count += 1
                        except ProcessLookupError:
                            # Process already died, try killing the PID directly
                            try:
                                proc.kill()
                                logger.info(f"Killed process {proc.info['pid']}")
                                killed_count += 1
                            except psutil.NoSuchProcess:
                                pass
                        except psutil.NoSuchProcess:
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if killed_count > 0:
                logger.info(f"Cleaned up {killed_count} orphaned llama-server process(es)")
            else:
                logger.debug("No orphaned llama-server processes found")
            
            return killed_count
            
        except ImportError:
            logger.warning("psutil not available, skipping orphaned process cleanup")
            return 0
        except Exception as e:
            logger.error(f"Error cleaning up orphaned processes: {e}")
            return 0
