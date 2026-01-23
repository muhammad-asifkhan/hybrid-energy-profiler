"""
exporter.py: Export energy profiling data to various formats (CSV, JSON).
"""
import csv
import json
import os
from datetime import datetime
from energymon.config import get_config

config = get_config()

def export_to_csv(processes_with_energy, filename=None):
    """
    Export process energy data to CSV file.
    
    Args:
        processes_with_energy: List of process dictionaries with energy data
        filename: Output filename (default: energy_profile_YYYYMMDD_HHMMSS.csv)
    
    Returns:
        str: Path to exported file
    """
    # Create output/exports directory if it doesn't exist
    output_dir = config.get('output', 'exports_dir', default='output/exports')
    os.makedirs(output_dir, exist_ok=True)
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'energy_profile_{timestamp}.csv'
    
    # Ensure .csv extension
    if not filename.endswith('.csv'):
        filename += '.csv'
    
    # Full path
    filepath = os.path.join(output_dir, filename)
    
    # Sort by energy score
    sorted_processes = sorted(processes_with_energy, key=lambda x: x.get('energy_score', 0), reverse=True)
    
    # Write CSV
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['pid', 'name', 'cpu_percent', 'memory_mb', 'io_read_kb', 'io_write_kb', 
                         'io_total_kb', 'energy_score', 'classification', 'context_switches', 'syscalls']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for p in sorted_processes:
                # Get context switches and syscalls from metric dict (collected from /proc)
                cs = p.get('context_switches', 0)
                sc = p.get('syscalls', 0)
                
                writer.writerow({
                    'pid': p.get('pid', 0),
                    'name': p.get('name', 'N/A'),
                    'cpu_percent': round(p.get('cpu_percent', 0), 2),
                    'memory_mb': round(p.get('memory_mb', 0), 2),
                    'io_read_kb': round((p.get('io_read', 0) / 1024), 2),
                    'io_write_kb': round((p.get('io_write', 0) / 1024), 2),
                    'io_total_kb': round((p.get('io_read', 0) + p.get('io_write', 0)) / 1024, 2),
                    'energy_score': round(p.get('energy_score', 0), 2),
                    'classification': p.get('classification', 'Unknown'),
                    'context_switches': cs,
                    'syscalls': sc
                })
    except IOError as e:
        raise IOError(f"Failed to write CSV file: {e}")
    
    return filepath

def export_to_json(processes_with_energy, filename=None, include_metadata=True):
    """
    Export process energy data to JSON file.
    
    Args:
        processes_with_energy: List of process dictionaries with energy data
        filename: Output filename (default: energy_profile_YYYYMMDD_HHMMSS.json)
        include_metadata: Include export timestamp and summary statistics
    
    Returns:
        str: Path to exported file
    """
    # Create output/exports directory if it doesn't exist
    output_dir = config.get('output', 'exports_dir', default='output/exports')
    os.makedirs(output_dir, exist_ok=True)
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'energy_profile_{timestamp}.json'
    
    # Ensure .json extension
    if not filename.endswith('.json'):
        filename += '.json'
    
    # Full path
    filepath = os.path.join(output_dir, filename)
    
    # Sort by energy score
    sorted_processes = sorted(processes_with_energy, key=lambda x: x.get('energy_score', 0), reverse=True)
    
    # Prepare export data
    export_data = {
        'processes': sorted_processes
    }
    
    if include_metadata:
        # Calculate summary statistics
        total = len(sorted_processes)
        total_energy = sum(p.get('energy_score', 0) for p in sorted_processes)
        avg_energy = total_energy / total if total > 0 else 0
        high_energy = len([p for p in sorted_processes if p.get('energy_score', 0) > 100])
        
        # Classification counts
        classifications = {}
        for p in sorted_processes:
            cls = p.get('classification', 'Unknown')
            classifications[cls] = classifications.get(cls, 0) + 1
        
        export_data['metadata'] = {
            'export_timestamp': datetime.now().isoformat(),
            'total_processes': total,
            'total_energy_score': round(total_energy, 2),
            'average_energy_score': round(avg_energy, 2),
            'high_energy_processes': high_energy,
            'classifications': classifications
        }
    
    # Write JSON
    try:
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2)
    except IOError as e:
        raise IOError(f"Failed to write JSON file: {e}")
    
    return filepath

def export_summary_report(processes_with_energy, filename=None):
    """
    Export a human-readable summary report.
    
    Args:
        processes_with_energy: List of process dictionaries with energy data
        filename: Output filename (default: energy_report_YYYYMMDD_HHMMSS.txt)
    
    Returns:
        str: Path to exported file
    """
    # Create output/exports directory if it doesn't exist
    output_dir = config.get('output', 'exports_dir', default='output/exports')
    os.makedirs(output_dir, exist_ok=True)
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'energy_report_{timestamp}.txt'
    
    # Ensure .txt extension
    if not filename.endswith('.txt'):
        filename += '.txt'
    
    # Full path
    filepath = os.path.join(output_dir, filename)
    
    # Sort by energy score
    sorted_processes = sorted(processes_with_energy, key=lambda x: x.get('energy_score', 0), reverse=True)
    
    # Calculate statistics
    total = len(sorted_processes)
    total_energy = sum(p.get('energy_score', 0) for p in sorted_processes)
    avg_energy = total_energy / total if total > 0 else 0
    high_energy = len([p for p in sorted_processes if p.get('energy_score', 0) > 100])
    
    # Classification counts
    classifications = {}
    for p in sorted_processes:
        cls = p.get('classification', 'Unknown')
        classifications[cls] = classifications.get(cls, 0) + 1
    
    # Write report
    try:
        with open(filepath, 'w', encoding='utf-8') as reportfile:
            reportfile.write("="*80 + "\n")
            reportfile.write("ENERGY PROFILING REPORT\n")
            reportfile.write("="*80 + "\n\n")
            reportfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            reportfile.write("SUMMARY STATISTICS\n")
            reportfile.write("-"*80 + "\n")
            reportfile.write(f"Total Processes Analyzed: {total}\n")
            reportfile.write(f"Total Energy Score: {total_energy:.2f}\n")
            reportfile.write(f"Average Energy Score: {avg_energy:.2f}\n")
            reportfile.write(f"High Energy Processes (>100): {high_energy}\n\n")
            
            reportfile.write("PROCESS CLASSIFICATION\n")
            reportfile.write("-"*80 + "\n")
            for cls, count in sorted(classifications.items(), key=lambda x: x[1], reverse=True):
                reportfile.write(f"  {cls}: {count}\n")
            reportfile.write("\n")
            
            reportfile.write("TOP 20 ENERGY CONSUMERS\n")
            reportfile.write("-"*80 + "\n")
            reportfile.write(f"{'PID':>7}  {'Name':<25}  {'CPU%':>8}  {'MEM(MB)':>10}  {'Energy':>10}  {'Class':<15}\n")
            reportfile.write("-"*80 + "\n")
            
            for p in sorted_processes[:20]:
                pid = p.get('pid', 0)
                name = p.get('name', 'N/A')[:23]
                cpu = p.get('cpu_percent', 0)
                mem = p.get('memory_mb', 0)
                energy = p.get('energy_score', 0)
                cls = p.get('classification', 'Unknown')
                reportfile.write(f"{pid:7d}  {name:<25}  {cpu:>7.1f}%  {mem:>9.1f}  {energy:>9.2f}  {cls:<15}\n")
            
            reportfile.write("\n" + "="*80 + "\n")
    except IOError as e:
        raise IOError(f"Failed to write report file: {e}")
    
    return filepath

