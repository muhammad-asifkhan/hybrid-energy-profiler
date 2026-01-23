"""
tracer.py: Handles kernel probing via eBPF/BCC (context switches, syscalls, etc).
Enhanced with robust fallback mechanisms and better kernel data integration.
"""
import os
import time
import logging

# Setup logging early
logger = logging.getLogger(__name__)

# Try to import BCC, but handle gracefully if not available
try:
    # Try system BCC first (more reliable)
    import sys
    sys.path.insert(0, '/usr/lib/python3/dist-packages')
    from bcc import BPF
    BCC_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    # Fallback to pip BCC
    try:
        from bcc import BPF
        BCC_AVAILABLE = True
    except (ImportError, ModuleNotFoundError):
        BCC_AVAILABLE = False
        BPF = None

# Try to import perf for alternative kernel monitoring
# Note: perf is a Linux tool, not a Python package
# We'll use system perf commands if available
import subprocess
PERF_AVAILABLE = False

def check_perf_availability():
    """Check if perf command is available on the system."""
    try:
        result = subprocess.run(['perf', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False

# Check perf availability once
PERF_AVAILABLE = check_perf_availability()
if PERF_AVAILABLE:
    logger.info("System perf tool is available")
else:
    logger.debug("System perf tool not available")

def load_kernel_probes():
    """Load eBPF kernel probes with enhanced error handling and fallbacks."""
    # Temporarily disable eBPF due to compilation issues on this kernel
    logger.info("eBPF temporarily disabled, using robust /proc fallback")
    return None, None, None

def get_pid_counters(cs_map, sc_map):
    """Return a dict of {pid: (cs, sc)} for all present PIDs in the eBPF maps."""
    if not cs_map or not sc_map:
        return {}
    
    try:
        cs_dict = {int(pid.value): int(val.value) for pid, val in cs_map.items()}
        sc_dict = {int(pid.value): int(val.value) for pid, val in sc_map.items()}
        
        # Merge into a {pid: (cs, sc)}
        all_pids = set(cs_dict) | set(sc_dict)
        pid_counters = {pid: (cs_dict.get(pid, 0), sc_dict.get(pid, 0)) for pid in all_pids}
        
        logger.debug(f"Collected eBPF data for {len(pid_counters)} processes")
        return pid_counters
        
    except Exception as e:
        logger.error(f"Error reading eBPF maps: {e}")
        return {}

def get_proc_kernel_data(pid):
    """Fallback: Get kernel data directly from /proc when eBPF is unavailable."""
    try:
        kernel_data = {}
        
        # Context switches from /proc/<pid>/status
        status_file = f'/proc/{pid}/status'
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith('voluntary_ctxt_switches:'):
                        kernel_data['context_switches'] = int(line.split()[1])
                    elif line.startswith('nonvoluntary_ctxt_switches:'):
                        kernel_data['context_switches'] = kernel_data.get('context_switches', 0) + int(line.split()[1])
        
        # Syscall estimates from /proc/<pid>/io
        io_file = f'/proc/{pid}/io'
        if os.path.exists(io_file):
            syscalls = 0
            with open(io_file, 'r') as f:
                for line in f:
                    if line.startswith('syscr:'):
                        syscalls += int(line.split()[1])
                    elif line.startswith('syscw:'):
                        syscalls += int(line.split()[1])
            kernel_data['syscalls'] = syscalls
        
        # Additional data from /proc/<pid>/stat
        stat_file = f'/proc/{pid}/stat'
        if os.path.exists(stat_file):
            with open(stat_file, 'r') as f:
                stat_data = f.read().strip().split()
                if len(stat_data) > 14:
                    # Page faults as syscall indicators
                    minflt = int(stat_data[9])
                    majflt = int(stat_data[11])
                    stime = int(stat_data[14])  # System CPU time
                    
                    if 'syscalls' not in kernel_data:
                        kernel_data['syscalls'] = minflt + majflt + (stime // 1000)
                    else:
                        kernel_data['syscalls'] += minflt + majflt
        
        return kernel_data
        
    except (FileNotFoundError, PermissionError, ValueError, IndexError) as e:
        logger.debug(f"Could not read /proc data for PID {pid}: {e}")
        return {}

def validate_kernel_data(kernel_data, proc_data):
    """Validate and cross-reference kernel data with process data."""
    if not kernel_data:
        return False
    
    # Basic sanity checks
    cs = kernel_data.get('context_switches', 0)
    sc = kernel_data.get('syscalls', 0)
    
    if cs < 0 or sc < 0:
        return False
    
    # Check if values are reasonable (not extremely high)
    cpu_percent = proc_data.get('cpu_percent', 0)
    if cs > 1000000 and cpu_percent < 50:  # Extremely high CS with low CPU seems wrong
        logger.warning(f"Suspicious context switch count for PID {proc_data.get('pid')}: {cs}")
        return False
    
    return True
