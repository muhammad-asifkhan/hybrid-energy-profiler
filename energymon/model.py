"""
model.py: Energy estimation model and process classification engine (hybrid, adaptive weights).
"""

def compute_energy_score(metric, kernel_data=None, adaptive=True):
    """
    Compute energy score using hybrid model: E = w1*C + w2*IO + w3*M + w4*CS + w5*SC
    With adaptive weight adjustment based on runtime ratios.
    
    Args:
        metric: dict with 'cpu_percent', 'memory_mb', 'io_read', 'io_write'
        kernel_data: dict with 'context_switches', 'syscalls' (optional)
        adaptive: bool, enable adaptive weight adjustment (default: True)
    
    Returns:
        energy_score: float
    """
    # Base weights (from proposal)
    w1 = 0.6  # CPU
    w2 = 0.3  # I/O
    w3 = 0.1  # Memory
    w4 = 0.2  # Context switches
    w5 = 0.1  # Syscalls
    
    # Extract metrics
    cpu = metric.get('cpu_percent', 0)
    mem = metric.get('memory_mb', 0)
    io_read = metric.get('io_read', 0)
    io_write = metric.get('io_write', 0)
    io_total = (io_read + io_write) / 1024 / 1024  # Convert to MB (not KB) for better scaling
    
    # Kernel metrics - prefer from metric dict (collected from /proc), fallback to kernel_data
    cs = metric.get('context_switches', 0) or (kernel_data.get('context_switches', 0) if kernel_data else 0)
    sc = metric.get('syscalls', 0) or (kernel_data.get('syscalls', 0) if kernel_data else 0)
    
    # Normalize kernel metrics to prevent them from dominating the energy score
    # These are cumulative counts, need strong normalization
    cs_normalized = cs / 1000000.0  # Normalize context switches to millions
    sc_normalized = sc / 10000000.0  # Normalize syscalls to ten-millions
    
    # Adaptive weight adjustment (from proposal section 5.2)
    if adaptive:
        # Calculate runtime ratios using normalized values
        total_ops = cpu + io_total + mem + cs_normalized + sc_normalized
        if total_ops > 0:
            cpu_ratio = cpu / total_ops
            io_ratio = io_total / total_ops
            cs_ratio = cs_normalized / (cs_normalized + 1)  # Normalize to avoid division by zero
            
            # Adjust weights based on ratios (from proposal)
            if cpu_ratio > 0.7:
                w1 *= 1.2  # Increase CPU weight for CPU-bound processes
            if io_ratio > 0.5:
                w2 *= 1.3  # Increase I/O weight for I/O-bound processes
            if cs_ratio > 0.3:
                w4 *= 1.2  # Increase context switch weight for context-heavy processes
    
    # Hybrid energy formula using normalized kernel metrics
    energy = (w1 * cpu) + (w2 * io_total) + (w3 * mem) + (w4 * cs_normalized) + (w5 * sc_normalized)
    
    return energy

def create_demo_processes():
    """
    Create demo process data to ensure all classifications are represented.
    Designed to show dominant resource usage patterns.
    
    Returns:
        List of demo process metric dictionaries
    """
    demo_processes = [
        # CPU-bound process (dominant CPU usage)
        {
            'pid': 9991,
            'name': 'demo-cpu-bound',
            'cpu_percent': 75.0,      # High CPU
            'memory_mb': 50,          # Low memory
            'io_read': 2 * 1024 * 1024,   # 2MB I/O
            'io_write': 1 * 1024 * 1024,  # 1MB I/O
            'context_switches': 200,  # Low context switches
            'syscalls': 1000,
            'cmdline': 'python3 demo_cpu_intensive.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 2,
            'user_time': 1000,
            'system_time': 500,
            'memory_vms': 100,
            'memory_shared': 10,
            'nice': 0,
            'num_fds': 10,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # IO-bound process (dominant I/O usage)
        {
            'pid': 9992,
            'name': 'demo-io-bound',
            'cpu_percent': 8.0,       # Low CPU
            'memory_mb': 80,          # Moderate memory
            'io_read': 50 * 1024 * 1024,  # 50MB I/O (high)
            'io_write': 40 * 1024 * 1024,  # 40MB I/O (high)
            'context_switches': 300,  # Low context switches
            'syscalls': 5000,
            'cmdline': 'python3 demo_io_intensive.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 1,
            'user_time': 100,
            'system_time': 50,
            'memory_vms': 120,
            'memory_shared': 20,
            'nice': 0,
            'num_fds': 15,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # Memory-bound process (dominant memory usage)
        {
            'pid': 9993,
            'name': 'demo-memory-bound',
            'cpu_percent': 12.0,      # Low CPU
            'memory_mb': 800,         # High memory (800MB)
            'io_read': 3 * 1024 * 1024,   # 3MB I/O
            'io_write': 2 * 1024 * 1024,  # 2MB I/O
            'context_switches': 150,  # Low context switches
            'syscalls': 2000,
            'cmdline': 'python3 demo_memory_intensive.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 3,
            'user_time': 200,
            'system_time': 100,
            'memory_vms': 900,
            'memory_shared': 50,
            'nice': 0,
            'num_fds': 20,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # Context-heavy process (dominant context switches)
        {
            'pid': 9994,
            'name': 'demo-context-heavy',
            'cpu_percent': 15.0,      # Moderate CPU
            'memory_mb': 60,          # Low memory
            'io_read': 2 * 1024 * 1024,   # 2MB I/O
            'io_write': 1 * 1024 * 1024,  # 1MB I/O
            'context_switches': 8000,  # Very high context switches
            'syscalls': 10000,
            'cmdline': 'python3 demo_thread_heavy.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 25,        # Many threads
            'user_time': 150,
            'system_time': 75,
            'memory_vms': 80,
            'memory_shared': 15,
            'nice': 0,
            'num_fds': 30,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # Balanced process (truly balanced resource usage)
        {
            'pid': 9995,
            'name': 'demo-balanced',
            'cpu_percent': 30.0,      # Moderate CPU
            'memory_mb': 614,         # Moderate memory (30%)
            'io_read': 150 * 1024 * 1024,  # 150MB I/O (30%)
            'io_write': 150 * 1024 * 1024,  # 150MB I/O (30%)
            'context_switches': 1500,  # Moderate context switches (30%)
            'syscalls': 3000,
            'cmdline': 'python3 demo_balanced.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 4,
            'user_time': 300,
            'system_time': 150,
            'memory_vms': 700,
            'memory_shared': 25,
            'nice': 0,
            'num_fds': 12,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # CPU-IO-Mixed process (truly mixed CPU and I/O)
        {
            'pid': 9996,
            'name': 'demo-cpu-io-mixed',
            'cpu_percent': 80.0,      # High CPU
            'memory_mb': 200,         # Low memory (10%)
            'io_read': 160 * 1024 * 1024,  # 160MB I/O (80%)
            'io_write': 160 * 1024 * 1024,  # 160MB I/O (80%)
            'context_switches': 800,  # Low context switches (40%)
            'syscalls': 6000,
            'cmdline': 'python3 demo_cpu_io_heavy.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 3,
            'user_time': 800,
            'system_time': 400,
            'memory_vms': 250,
            'memory_shared': 20,
            'nice': 0,
            'num_fds': 18,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # Resource-Heavy process (truly heavy across all resources)
        {
            'pid': 9997,
            'name': 'demo-resource-heavy',
            'cpu_percent': 60.0,      # High CPU
            'memory_mb': 1024,        # High memory (50%)
            'io_read': 300 * 1024 * 1024,  # 300MB I/O (60%)
            'io_write': 300 * 1024 * 1024,  # 300MB I/O (60%)
            'context_switches': 3000,  # High context switches (60%)
            'syscalls': 12000,
            'cmdline': 'python3 demo_resource_heavy.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'running',
            'num_threads': 12,
            'user_time': 1200,
            'system_time': 600,
            'memory_vms': 1200,
            'memory_shared': 80,
            'nice': 0,
            'num_fds': 40,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        },
        # Idle process (very low everything)
        {
            'pid': 9998,
            'name': 'demo-idle',
            'cpu_percent': 0.5,       # Very low CPU
            'memory_mb': 10,          # Very low memory
            'io_read': 512 * 1024,    # 0.5MB I/O
            'io_write': 256 * 1024,   # 0.25MB I/O
            'context_switches': 20,   # Very low context switches
            'syscalls': 100,
            'cmdline': 'python3 demo_idle.py',
            'username': 'demo',
            'parent_pid': 1,
            'create_time': 1640000000,
            'status': 'sleeping',
            'num_threads': 1,
            'user_time': 10,
            'system_time': 5,
            'memory_vms': 15,
            'memory_shared': 2,
            'nice': 0,
            'num_fds': 3,
            'exe': '/usr/bin/python3',
            'cwd': '/home/demo',
        }
    ]
    
    return demo_processes

def classify_process(metric, kernel_data=None):
    """
    Classify process based on its dominant resource usage pattern.
    Analyzes which resource the process uses most heavily relative to its own usage profile.
    
    Returns:
        classification: str ('CPU-bound', 'IO-bound', 'Memory-bound', 'Context-heavy', 'Balanced')
    """
    cpu = metric.get('cpu_percent', 0)
    mem = metric.get('memory_mb', 0)
    io_read = metric.get('io_read', 0)
    io_write = metric.get('io_write', 0)
    io_total = io_read + io_write
    cs = metric.get('context_switches', 0) or (kernel_data.get('context_switches', 0) if kernel_data else 0)
    
    # Normalize all metrics to comparable scale (0-100)
    # CPU is already in percentage (0-100)
    cpu_score = min(cpu, 100)
    
    # Memory: normalize with 1GB as 100% (more sensitive)
    mem_score = min((mem / 1024) * 100, 100)  # 1GB = 100%
    
    # I/O: normalize with 200MB as 100% (less dominant)
    io_mb = io_total / (1024 * 1024)
    io_score = min((io_mb / 200) * 100, 100)  # 200MB = 100%
    
    # Context switches: normalize with 2,000 as 100% (more sensitive)
    cs_score = min((cs / 2000) * 100, 100)  # 2,000 = 100%
    
    # Calculate total resource usage to understand process intensity
    total_usage = cpu_score + mem_score + io_score + cs_score
    
    # If process is using very little resources overall, classify as Idle/Low
    if total_usage < 5:  # Less than 5% total normalized usage
        return 'Idle'
    
    # Find dominant resource
    resources = {
        'CPU-bound': cpu_score,
        'Memory-bound': mem_score, 
        'IO-bound': io_score,
        'Context-heavy': cs_score
    }
    
    # Get the dominant resource
    dominant_resource = max(resources, key=resources.get)
    dominant_score = resources[dominant_resource]
    
    # Calculate dominance ratio (how much more dominant vs others)
    other_scores = [v for k, v in resources.items() if k != dominant_resource]
    avg_other_score = sum(other_scores) / len(other_scores) if other_scores else 0
    dominance_ratio = dominant_score / (avg_other_score + 0.1)  # Avoid division by zero
    
    # Enhanced classification logic
    if dominance_ratio > 2.5:  # Very dominant resource
        return dominant_resource
    elif dominance_ratio > 1.5:  # Check for mixed patterns first
        # CPU-IO Mixed: Both CPU and I/O are high (>35%) and relatively balanced
        if cpu_score > 35 and io_score > 35 and abs(cpu_score - io_score) < 20:
            return 'CPU-IO-Mixed'
        # Memory-Context Mixed: Both Memory and Context Switches are high (>25%)
        elif mem_score > 25 and cs_score > 25 and abs(mem_score - cs_score) < 30:
            return 'Memory-Context-Mixed'
        # Resource-Heavy: All resources are high (>25% average)
        elif total_usage > 100:  # Average >25% across all 4 resources
            return 'Resource-Heavy'
        # Otherwise, use dominant resource
        else:
            return dominant_resource
    else:
        # Resources are relatively balanced - check for specific patterns
        # CPU-IO Mixed: Both CPU and I/O are high (>30%) and dominant
        if cpu_score > 30 and io_score > 30 and max(cpu_score, io_score) > min(mem_score, cs_score) * 2:
            return 'CPU-IO-Mixed'
        # Memory-Context Mixed: Both Memory and Context Switches are high (>20%)
        elif mem_score > 20 and cs_score > 20 and max(mem_score, cs_score) > min(cpu_score, io_score) * 2:
            return 'Memory-Context-Mixed'
        # Resource-Heavy: All resources are high (>20% average)
        elif total_usage > 80:  # Average >20% across all 4 resources
            return 'Resource-Heavy'
        # Balanced: Resources are relatively even
        else:
            return 'Balanced'
