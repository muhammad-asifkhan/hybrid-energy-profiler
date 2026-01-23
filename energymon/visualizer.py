"""
visualizer.py: Visualization engine for CLI tables and graphs (matplotlib/seaborn).
"""
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from collections import defaultdict
from energymon.config import get_config

config = get_config()

def show_cli_table(processes_with_energy, show_empty_message=True):
    """Display enhanced CLI table with energy scores and classifications."""
    print("\n" + "="*100)
    print(f"{'PID':>7}  {'Name':<20}  {'CPU%':>8}  {'MEM(MB)':>10}  {'IO(KB)':>12}  {'Energy':>10}  {'Class':<15}")
    print("="*100)
    
    if not processes_with_energy:
        if show_empty_message:
            print("  ⚠️  No processes found matching the current filters.")
            print("  💡 Try:")
            print("     • Removing filters: python3 main.py")
            print("     • Lowering CPU threshold: --min-cpu 0.1")
            print("     • Removing name filter: --filter ''")
        print("="*100)
        return
    
    # Sort by energy score
    sorted_processes = sorted(processes_with_energy, key=lambda x: x.get('energy_score', 0), reverse=True)
    
    for p in sorted_processes[:30]:  # Show top 30
        pid = p.get('pid', 0)
        name = p.get('name', 'N/A')[:18]
        cpu = p.get('cpu_percent', 0)
        mem = p.get('memory_mb', 0)
        io = (p.get('io_read', 0) + p.get('io_write', 0)) / 1024
        energy = p.get('energy_score', 0)
        classification = p.get('classification', 'Unknown')
        
        print(f"{pid:7d}  {name:<20}  {cpu:>7.1f}%  {mem:>9.1f}  {io:>11.1f}  {energy:>9.2f}  {classification:<15}")
    
    if len(sorted_processes) > 30:
        print(f"\n  ... and {len(sorted_processes) - 30} more processes (showing top 30)")
    
    print("="*100)

def plot_cpu_vs_energy(processes_with_energy, save_path=None):
    """Graph 1: CPU Time vs Energy Score (line graph)."""
    df = pd.DataFrame(processes_with_energy)
    df = df.sort_values('cpu_percent')
    
    plt.figure(figsize=(10, 6))
    plt.plot(df['cpu_percent'], df['energy_score'], marker='o', linewidth=2, markersize=4)
    plt.xlabel('CPU Usage (%)', fontsize=12)
    plt.ylabel('Energy Score', fontsize=12)
    plt.title('CPU Time vs Energy Score', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"  Saved: {save_path}")
    else:
        plt.show()

def plot_io_vs_energy(processes_with_energy, save_path=None):
    """Graph 2: I/O Bytes vs Energy Score (scatter plot)."""
    df = pd.DataFrame(processes_with_energy)
    df['io_total_kb'] = (df['io_read'] + df['io_write']) / 1024
    
    plt.figure(figsize=(10, 6))
    plt.scatter(df['io_total_kb'], df['energy_score'], alpha=0.6, s=50)
    plt.xlabel('I/O Total (KB)', fontsize=12)
    plt.ylabel('Energy Score', fontsize=12)
    plt.title('I/O Bytes vs Energy Score', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"  Saved: {save_path}")
    else:
        plt.show()

def plot_classification(processes_with_energy, save_path=None):
    """Graph 3: Process Classification (bar plot)."""
    classifications = defaultdict(int)
    for p in processes_with_energy:
        cls = p.get('classification', 'Unknown')
        classifications[cls] += 1
    
    plt.figure(figsize=(10, 6))
    classes = list(classifications.keys())
    counts = list(classifications.values())
    
    bars = plt.bar(classes, counts, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'])
    plt.xlabel('Process Classification', fontsize=12)
    plt.ylabel('Number of Processes', fontsize=12)
    plt.title('Process Classification Distribution', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='y')
    
    # Add count labels on bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"  Saved: {save_path}")
    else:
        plt.show()

def plot_energy_heatmap(processes_with_energy, save_path=None):
    """Graph 4: Energy Heatmap (top processes by energy)."""
    df = pd.DataFrame(processes_with_energy)
    df = df.sort_values('energy_score', ascending=False).head(20)  # Top 20
    
    # Create heatmap data
    heatmap_data = df[['cpu_percent', 'memory_mb', 'energy_score']].T
    heatmap_data.columns = [f"PID {pid}" for pid in df['pid']]
    
    plt.figure(figsize=(14, 6))
    sns.heatmap(heatmap_data, annot=True, fmt='.1f', cmap='YlOrRd', cbar_kws={'label': 'Intensity'})
    plt.xlabel('Processes (Top 20 by Energy)', fontsize=12)
    plt.ylabel('Metrics', fontsize=12)
    plt.title('Energy Heatmap: Top Processes', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"  Saved: {save_path}")
    else:
        plt.show()

def generate_all_visualizations(processes_with_energy, output_dir=None):
    """Generate all graphs and save them."""
    import os
    if output_dir is None:
        output_dir = config.get('output', 'graphs_dir', default='output/graphs')
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n[visualizer] Generating graphs...")
    
    plot_cpu_vs_energy(processes_with_energy, f"{output_dir}/cpu_vs_energy.png")
    plot_io_vs_energy(processes_with_energy, f"{output_dir}/io_vs_energy.png")
    plot_classification(processes_with_energy, f"{output_dir}/classification.png")
    plot_energy_heatmap(processes_with_energy, f"{output_dir}/energy_heatmap.png")
    
    print(f"\n[visualizer] All graphs saved to {output_dir}/")
    print("[visualizer] All graphs generated successfully!")
