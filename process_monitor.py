"""
Process monitoring utilities for detecting unkillable (D state) processes.
"""

import subprocess
import logging
import re
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def get_process_states(process_name: str = "llama-server") -> List[Dict[str, str]]:
    """
    Get process states for all processes matching the given name.

    Args:
        process_name: Process name to search for

    Returns:
        List of dicts with keys: pid, state, command
    """
    processes = []

    try:
        # Get process list with states
        result = subprocess.run(
            ['ps', '-eo', 'pid,stat,comm,args'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            logger.error(f"ps command failed: {result.stderr}")
            return processes

        # Parse output
        for line in result.stdout.strip().split('\n')[1:]:  # Skip header
            if not line.strip():
                continue

            # Parse: PID STAT COMMAND ARGS
            parts = line.split(maxsplit=3)
            if len(parts) < 3:
                continue

            pid, state, comm = parts[0], parts[1], parts[2]
            args = parts[3] if len(parts) > 3 else ""

            # Check if process name matches
            if process_name.lower() in comm.lower() or process_name.lower() in args.lower():
                processes.append({
                    'pid': pid,
                    'state': state,
                    'command': comm,
                    'args': args,
                    'is_d_state': 'D' in state  # D = uninterruptible sleep
                })

    except subprocess.TimeoutExpired:
        logger.error("ps command timed out")
    except Exception as e:
        logger.error(f"Error getting process states: {e}")

    return processes


def check_d_state_processes(process_name: str = "llama-server") -> Tuple[bool, List[str]]:
    """
    Check if any processes are in D (uninterruptible sleep) state.

    Args:
        process_name: Process name to check

    Returns:
        Tuple of (has_d_state, list_of_pids)
    """
    processes = get_process_states(process_name)
    d_state_pids = []

    for proc in processes:
        if proc['is_d_state']:
            d_state_pids.append(proc['pid'])
            logger.warning(
                f"Process {proc['pid']} ({proc['command']}) is in D state "
                f"(uninterruptible sleep). State: {proc['state']}"
            )

    has_d_state = len(d_state_pids) > 0
    if has_d_state:
        logger.critical(
            f"Found {len(d_state_pids)} processes in D state: {d_state_pids}. "
            f"These cannot be killed and may indicate GPU memory crash."
        )

    return has_d_state, d_state_pids


def check_gpu_sysfs_health(card_id: str = "card1") -> Tuple[bool, List[str]]:
    """
    Check if GPU sysfs paths are accessible.

    Args:
        card_id: GPU card ID (e.g., "card1" for RX 470)

    Returns:
        Tuple of (is_healthy, list_of_errors)
    """
    errors = []

    # Critical sysfs paths to check
    critical_paths = [
        f"/sys/class/drm/{card_id}/device/gpu_busy_percent",
        f"/sys/class/drm/{card_id}/device/pp_dpm_sclk",
        f"/sys/class/drm/{card_id}/device/pp_dpm_mclk",
        f"/sys/class/drm/{card_id}/device/hwmon/hwmon*/temp1_input",
    ]

    import glob
    import os

    for path_pattern in critical_paths:
        try:
            # Expand glob patterns
            if '*' in path_pattern:
                matches = glob.glob(path_pattern)
                if not matches:
                    errors.append(f"No matches for pattern: {path_pattern}")
                    continue
                actual_path = matches[0]
            else:
                actual_path = path_pattern

            # Check if path exists and is readable
            if not os.path.exists(actual_path):
                errors.append(f"Path does not exist: {actual_path}")
            else:
                # Try to read a small amount
                with open(actual_path, 'r') as f:
                    f.read(1024)  # Try reading up to 1KB

        except PermissionError:
            errors.append(f"Permission denied: {actual_path}")
        except OSError as e:
            errors.append(f"OS error reading {actual_path}: {e}")
        except Exception as e:
            errors.append(f"Unexpected error with {path_pattern}: {e}")

    is_healthy = len(errors) == 0
    if not is_healthy:
        logger.warning(f"GPU sysfs health check failed for {card_id}: {errors}")

    return is_healthy, errors


def check_journalctl_gpu_errors(since: str = "5 minutes ago") -> Tuple[bool, List[str]]:
    """
    Check journalctl for GPU-related error messages.

    Args:
        since: Time range to check (e.g., "5 minutes ago", "1 hour ago")

    Returns:
        Tuple of (has_errors, list_of_error_messages)
    """
    error_messages = []

    try:
        # Common GPU error patterns
        patterns = [
            "amdgpu.*error",
            "amdgpu.*failed",
            "amdgpu.*timeout",
            "GPU.*reset",
            "memory.*allocation.*failed",
            "vram.*error",
            "D state",
            "uninterruptible",
        ]

        # Build journalctl command
        cmd = ['journalctl', '--since', since, '--priority=err', '--no-pager']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            logger.error(f"journalctl command failed: {result.stderr}")
            return False, error_messages

        # Check for GPU-related errors
        lines = result.stdout.strip().split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(pattern in line_lower for pattern in patterns):
                error_messages.append(line)
                logger.warning(f"Found GPU-related error in logs: {line}")

    except subprocess.TimeoutExpired:
        logger.error("journalctl command timed out")
    except Exception as e:
        logger.error(f"Error checking journalctl: {e}")

    has_errors = len(error_messages) > 0
    return has_errors, error_messages


def diagnose_gpu_crash() -> Dict[str, any]:
    """
    Comprehensive GPU crash diagnosis.

    Returns:
        Dictionary with diagnosis results
    """
    diagnosis = {
        'timestamp': __import__('time').time(),
        'd_state_processes': False,
        'd_state_pids': [],
        'gpu_sysfs_healthy': True,
        'gpu_sysfs_errors': [],
        'journalctl_errors': False,
        'journalctl_messages': [],
        'recommendation': 'No issues detected',
        'severity': 'info'  # info, warning, critical
    }

    # Check for D state processes
    has_d_state, d_pids = check_d_state_processes("llama-server")
    diagnosis['d_state_processes'] = has_d_state
    diagnosis['d_state_pids'] = d_pids

    # Check GPU sysfs health (focus on RX 470 - card1)
    is_healthy, errors = check_gpu_sysfs_health("card1")
    diagnosis['gpu_sysfs_healthy'] = is_healthy
    diagnosis['gpu_sysfs_errors'] = errors

    # Check journalctl for GPU errors
    has_journal_errors, journal_messages = check_journalctl_gpu_errors("10 minutes ago")
    diagnosis['journalctl_errors'] = has_journal_errors
    diagnosis['journalctl_messages'] = journal_messages

    # Determine severity and recommendation
    if has_d_state:
        diagnosis['severity'] = 'critical'
        diagnosis['recommendation'] = (
            "CRITICAL: Processes in D (uninterruptible sleep) state detected. "
            "This indicates GPU memory crash. Processes cannot be killed. "
            "Recommended action: Hard system reset required."
        )
    elif not is_healthy and has_journal_errors:
        diagnosis['severity'] = 'critical'
        diagnosis['recommendation'] = (
            "CRITICAL: GPU sysfs inaccessible and journalctl shows GPU errors. "
            "GPU may be crashed. Check GPU health and consider reset."
        )
    elif not is_healthy:
        diagnosis['severity'] = 'warning'
        diagnosis['recommendation'] = (
            "WARNING: GPU sysfs paths inaccessible. GPU may be unstable. "
            "Monitor closely and consider stopping model."
        )
    elif has_journal_errors:
        diagnosis['severity'] = 'warning'
        diagnosis['recommendation'] = (
            "WARNING: GPU-related errors in system logs. "
            "Monitor GPU stability and consider reducing overclock."
        )

    return diagnosis


if __name__ == "__main__":
    # Test the diagnosis
    import json
    result = diagnose_gpu_crash()
    print(json.dumps(result, indent=2))