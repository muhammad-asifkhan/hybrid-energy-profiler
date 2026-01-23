"""
dashboard.py: Web-based dashboard for real-time energy profiling visualization.
"""
from flask import Flask, render_template_string, jsonify, request, send_file, send_from_directory, session, redirect, url_for
import os
from energymon.collector import collect_process_metrics
from energymon.model import compute_energy_score, classify_process, create_demo_processes
from energymon.tracer import load_kernel_probes, get_pid_counters, get_proc_kernel_data, validate_kernel_data
from energymon.exporter import export_to_csv, export_to_json, export_summary_report
from energymon.visualizer import generate_all_visualizations
from energymon.config import get_config
from energymon.logger import get_logger, log_metric_collection, log_error
from energymon.storage import get_storage
from energymon.auth import require_login, require_role, authenticate, login_user, logout_user, get_current_user, is_authenticated
from energymon.alerts import get_alert_manager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
import time

# Get configuration and logger
config = get_config()
logger = get_logger('energymon.dashboard')
storage = get_storage()  # Will be None if storage is disabled

app = Flask(__name__)
app.secret_key = config.get('security', 'secret_key', default=os.urandom(24).hex())
app.permanent_session_lifetime = timedelta(hours=24)

# Set Content Security Policy to allow inline scripts (required for dashboard functionality)
@app.after_request
def set_csp_header(response):
    """Set Content Security Policy header to allow inline scripts."""
    # Allow inline scripts and styles for the dashboard
    # 'unsafe-inline' is needed for inline event handlers (onclick, etc.)
    # Note: We don't use eval(), but some browsers may report false positives
    # If you see CSP errors, they're likely from browser extensions, not our code
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers['Content-Security-Policy'] = csp
    # Also set X-Content-Security-Policy for older browsers
    response.headers['X-Content-Security-Policy'] = csp
    return response

# Setup rate limiting
rate_limit = config.get('security', 'api_rate_limit', default=100)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{rate_limit} per minute", "200 per hour"],
    storage_uri="memory://"  # Use in-memory storage (can be upgraded to Redis)
)

# Dashboard HTML template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Hybrid Energy Profiler</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='grad' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23667eea;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%23764ba2;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' fill='url(%23grad)' rx='20'/%3E%3Cpath d='M50 20 L35 50 L50 50 L50 80 L65 50 L50 50 Z' fill='white' stroke='%23fff' stroke-width='3'/%3E%3C/svg%3E">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%);
            color: #2c3e50;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
        }
        h1 {
            color: #1e3c72;
            margin-bottom: 10px;
            text-align: center;
            font-weight: 700;
            font-size: 2.5em;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-bar {
            display: flex;
            justify-content: space-around;
            margin: 25px 0;
            padding: 20px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }
        .status-item {
            text-align: center;
        }
        .status-item strong {
            display: block;
            font-size: 28px;
            color: #1e3c72;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .status-item span {
            color: #6c757d;
            font-size: 14px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .kernel-status {
            padding: 15px;
            border-radius: 12px;
            margin: 15px 0;
            text-align: center;
            font-weight: 500;
        }
        .kernel-available {
            background: linear-gradient(135deg, #d1f2eb 0%, #b8e6d8 100%);
            color: #0f5132;
            border: 1px solid #b8e6d8;
            box-shadow: 0 2px 8px rgba(11, 214, 155, 0.15);
        }
        .kernel-unavailable {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            color: #664d03;
            border: 1px solid #ffeaa7;
            box-shadow: 0 2px 8px rgba(255, 193, 7, 0.15);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            border-radius: 12px;
            overflow: hidden;
        }
        th {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }
        td {
            padding: 14px 12px;
            border-bottom: 1px solid #f1f3f4;
            font-size: 14px;
        }
        tr:hover {
            background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
        }
        .energy-high { 
            color: #e74c3c; 
            font-weight: 700; 
            background: linear-gradient(135deg, #ffeaa7 0%, #fdcb6e 100%);
            padding: 4px 8px;
            border-radius: 6px;
            display: inline-block;
        }
        .energy-medium { 
            color: #f39c12; 
            font-weight: 600; 
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            padding: 4px 8px;
            border-radius: 6px;
            display: inline-block;
        }
        .energy-low { 
            color: #27ae60; 
            font-weight: 500;
            background: linear-gradient(135deg, #d1f2eb 0%, #b8e6d8 100%);
            padding: 4px 8px;
            border-radius: 6px;
            display: inline-block;
        }
        .class-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .class-cpu { 
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%); 
            color: white; 
            box-shadow: 0 3px 8px rgba(255, 107, 107, 0.3);
        }
        .class-io { 
            background: linear-gradient(135deg, #4ecdc4 0%, #44a39d 100%); 
            color: white; 
            box-shadow: 0 3px 8px rgba(78, 205, 196, 0.3);
        }
        .class-memory { 
            background: linear-gradient(135deg, #45b7d1 0%, #3498db 100%); 
            color: white; 
            box-shadow: 0 3px 8px rgba(69, 183, 209, 0.3);
        }
        .class-mixed { 
            background: linear-gradient(135deg, #95a5a6 0%, #7f8c8d 100%); 
            color: white; 
            box-shadow: 0 3px 8px rgba(149, 165, 166, 0.3);
        }
        .class-contextheavy { 
            background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); 
            color: white; 
            box-shadow: 0 3px 8px rgba(155, 89, 182, 0.3);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 25px rgba(30, 60, 114, 0.3);
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(30, 60, 114, 0.4);
        }
        .stat-card h3 {
            font-size: 14px;
            margin-bottom: 15px;
            opacity: 0.9;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .value {
            font-size: 36px;
            font-weight: 700;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .filter-panel {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px;
            border-radius: 15px;
            margin: 25px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            border: 1px solid rgba(255,255,255,0.5);
        }
        .filter-form {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 15px;
            align-items: end;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
        }
        .filter-group label {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .filter-group input {
            padding: 12px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            background: white;
        }
        .filter-group input:focus {
            outline: none;
            border-color: #1e3c72;
            box-shadow: 0 0 0 3px rgba(30, 60, 114, 0.1);
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .btn-primary {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #2a5298 0%, #1e3c72 100%);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(30, 60, 114, 0.3);
        }
        .btn-secondary {
            background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
            color: white;
        }
        .btn-secondary:hover {
            background: linear-gradient(135deg, #5a6268 0%, #6c757d 100%);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(108, 117, 125, 0.3);
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #667eea;
        }
        #processTableBody tr.empty-row td {
            text-align: center;
            padding: 30px;
            color: #999;
        }
        /* Sortable columns */
        th.sortable {
            cursor: pointer;
            user-select: none;
            position: relative;
        }
        th.sortable:hover {
            background: #5568d3;
        }
        th.sortable::after {
            content: ' ↕';
            opacity: 0.5;
            font-size: 12px;
        }
        th.sortable.asc::after {
            content: ' ↑';
            opacity: 1;
        }
        th.sortable.desc::after {
            content: ' ↓';
            opacity: 1;
        }
        /* Energy hog highlighting */
        tr.energy-hog-top5 {
            background: #ffebee !important;
            border-left: 4px solid #dc3545;
        }
        tr.energy-hog-top5:hover {
            background: #ffcdd2 !important;
        }
        tr.energy-hog-top10 {
            background: #fff3e0 !important;
            border-left: 4px solid #ff9800;
        }
        tr.energy-hog-top10:hover {
            background: #ffe0b2 !important;
        }
        /* Expandable details */
        .expand-icon {
            cursor: pointer;
            display: inline-block;
            width: 20px;
            text-align: center;
            font-weight: bold;
            color: #667eea;
        }
        .process-details {
            display: none;
            background: #f8f9fa;
            padding: 15px;
            border-top: 2px solid #667eea;
        }
        .process-details.show {
            display: table-row;
        }
        .process-details td {
            padding: 15px;
        }
        .detail-row {
            display: grid;
            grid-template-columns: 150px 1fr;
            gap: 10px;
            margin: 8px 0;
        }
        .detail-label {
            font-weight: 600;
            color: #666;
        }
        /* Tooltips */
        .tooltip-trigger {
            position: relative;
            cursor: help;
            border-bottom: 1px dotted #667eea;
        }
        .tooltip {
            visibility: hidden;
            background-color: #333;
            color: #fff;
            text-align: left;
            border-radius: 6px;
            padding: 8px 12px;
            position: absolute;
            z-index: 1000;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            white-space: nowrap;
            font-size: 12px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .tooltip-trigger:hover .tooltip {
            visibility: visible;
            opacity: 1;
        }
        /* Class filter buttons */
        .class-filters {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 15px 0;
        }
        .class-filter-btn {
            padding: 6px 12px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .class-filter-btn:hover {
            background: #f0f0ff;
        }
        .class-filter-btn.active {
            background: #667eea;
            color: white;
        }
        /* Top by selector */
        .top-by-selector {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 15px 0;
        }
        .top-by-selector select {
            padding: 8px 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            cursor: pointer;
        }
        /* Insights panel */
        .insights-panel {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        /* Alerts panel */
        .alerts-panel {
            background: linear-gradient(135deg, #ffeaa7 0%, #fdcb6e 100%);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #e74c3c;
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.2);
        }
        .alert-item {
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-10px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        .insight-item {
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }
        .insight-item strong {
            color: #667eea;
        }
        /* Sparkline container */
        .sparkline {
            display: inline-block;
            width: 100px;
            height: 20px;
            margin-left: 10px;
        }
        /* What-if panel */
        .what-if-panel {
            background: #fff3cd;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #ffc107;
        }
        .recommendation {
            background: #d1ecf1;
            padding: 12px;
            border-radius: 5px;
            margin: 8px 0;
            border-left: 3px solid #17a2b8;
        }
        .recommendation strong {
            color: #0c5460;
        }
        /* Actions Panel */
        .actions-panel {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        .actions-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .action-group {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #ddd;
        }
        .action-group h4 {
            margin: 0 0 10px 0;
            color: #667eea;
            font-size: 14px;
        }
        .action-buttons {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .btn-export {
            background: #28a745;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-export:hover {
            background: #218838;
        }
        .btn-graph {
            background: #17a2b8;
            color: white;
        }
        .btn-graph:hover {
            background: #138496;
        }
        .btn-download {
            background: #6c757d;
            color: white;
            font-size: 12px;
            padding: 6px 12px;
        }
        .btn-download:hover {
            background: #5a6268;
        }
        .monitoring-controls {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: 10px;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 24px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 24px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #667eea;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .refresh-control {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .refresh-control input {
            width: 60px;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 10px;
        }
        .status-success {
            background: #d4edda;
            color: #155724;
        }
        .status-info {
            background: #d1ecf1;
            color: #0c5460;
        }
        .download-links {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }
        .download-link {
            display: block;
            color: #667eea;
            text-decoration: none;
            margin: 5px 0;
            font-size: 12px;
        }
        .download-link:hover {
            text-decoration: underline;
        }
        
        /* CPU Activity Indicators */
        .cpu-indicator {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-weight: 500;
        }
        .cpu-activity-icon {
            font-size: 14px;
        }
        .cpu-idle {
            color: #6c757d;
            font-style: italic;
        }
        .cpu-minimal {
            color: #856404;
            font-size: 12px;
        }
        .cpu-low {
            color: #004085;
        }
        .cpu-active {
            color: #155724;
            font-weight: 600;
        }
        .cpu-source {
            font-size: 10px;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Hybrid Energy Profiler</h1>
        
        <div class="kernel-status {{ kernel_status_class }}">
            <strong>Kernel Tracing Status:</strong> <span id="kernelStatus">{{ kernel_status_msg }}</span>
            <div style="margin-top: 8px; font-size: 12px; opacity: 0.9;">
                <strong>Note:</strong> This mode uses /proc filesystem to collect kernel-level context switch data directly from the kernel. 
                Full eBPF tracing (optional) provides real-time syscall counts, but /proc-based collection provides the core hybrid model functionality.
            </div>
        </div>
        
        <div class="filter-panel">
            <h3 style="margin-bottom: 15px; color: #667eea;">🔍 Filter Processes</h3>
            <div class="filter-form">
                <div class="filter-group">
                    <label for="filterName">Process Name (contains):</label>
                    <input type="text" id="filterName" placeholder="e.g., python, chrome" />
                </div>
                <div class="filter-group">
                    <label for="filterCpu">Min CPU %:</label>
                    <input type="number" id="filterCpu" step="0.1" min="0" placeholder="0.0" />
                </div>
                <div class="filter-group">
                    <label for="filterMemory">Min Memory (MB):</label>
                    <input type="number" id="filterMemory" step="1" min="0" placeholder="0" />
                </div>
                <div class="filter-buttons">
                    <button class="btn btn-primary" onclick="applyFilters()">Apply Filters</button>
                    <button class="btn btn-secondary" onclick="clearFilters()">Clear</button>
                </div>
            </div>
        </div>
        
        <div class="status-bar">
            <div class="status-item">
                <strong>{{ total_processes }}</strong>
                <span>Total Processes</span>
            </div>
            <div class="status-item">
                <strong>{{ high_energy }}</strong>
                <span>High Energy (>100 mJ/s)</span>
            </div>
            <div class="status-item">
                <strong>{{ avg_energy }} mJ/s</strong>
                <span>Avg Energy Score</span>
            </div>
            <div class="status-item">
                <strong>{{ last_update }}</strong>
                <span>Last Update</span>
            </div>
        </div>
        
        <div style="text-align: center; margin: 20px 0;">
            <button id="demoToggle" class="class-filter-btn" onclick="toggleDemo()">
                🎭 Enable Demo Mode
            </button>
            <small style="display: block; margin-top: 5px; color: #666;">
                Demo mode adds sample processes to show all classification types
            </small>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>CPU-Bound Processes</h3>
                <div class="value">{{ cpu_bound_count }}</div>
            </div>
            <div class="stat-card">
                <h3>IO-Bound Processes</h3>
                <div class="value">{{ io_bound_count }}</div>
            </div>
            <div class="stat-card">
                <h3>Memory-Bound Processes</h3>
                <div class="value">{{ memory_bound_count }}</div>
            </div>
            <div class="stat-card">
                <h3>Context-Heavy Processes</h3>
                <div class="value">{{ context_heavy_count }}</div>
            </div>
            <div class="stat-card">
                <h3>Mixed Processes</h3>
                <div class="value">{{ mixed_count }}</div>
            </div>
        </div>
        
        <div class="insights-panel" id="insightsPanel">
            <h3 style="margin-bottom: 15px; color: #667eea;">💡 Energy Insights</h3>
            <div id="insightsContent">
                <div class="insight-item">
                    <strong>Biggest Energy Consumer:</strong> <span id="biggestConsumer">Loading...</span>
                </div>
                <div class="insight-item">
                    <strong>Energy Trend:</strong> <span id="energyTrend">Loading...</span>
                </div>
                <div id="recommendationsContainer"></div>
            </div>
        </div>
        
        <div class="what-if-panel" id="whatIfPanel" style="display: none;">
            <h3 style="margin-bottom: 15px; color: #ff9800;">🔮 What-If Analysis</h3>
            <div id="whatIfContent">
                <p>Select processes to see energy savings if stopped:</p>
                <div id="whatIfResults"></div>
                <button class="btn btn-secondary" onclick="closeWhatIf()" style="margin-top: 10px;">Close</button>
            </div>
        </div>
        <button class="btn btn-primary" onclick="showWhatIf()" style="margin: 15px 0;">🔮 What-If: Stop Energy Hogs</button>
        
        <div class="actions-panel">
            <h3 style="margin-bottom: 15px; color: #667eea;">⚙️ Actions & Controls</h3>
            <div class="actions-grid">
                <div class="action-group">
                    <h4>📥 Export Data</h4>
                    <div class="action-buttons">
                        <button class="btn btn-export" onclick="exportData('csv')">📄 Export to CSV</button>
                        <button class="btn btn-export" onclick="exportData('json')">📋 Export to JSON</button>
                        <button class="btn btn-export" onclick="exportData('txt')">📝 Export Report</button>
                    </div>
                    <div class="download-links" id="exportLinks"></div>
                </div>
                
                <div class="action-group">
                    <h4>📊 Generate Graphs</h4>
                    <div class="action-buttons">
                        <button class="btn btn-export btn-graph" onclick="generateGraphs()">📈 Generate All Graphs</button>
                    </div>
                    <div class="download-links" id="graphLinks"></div>
                </div>
                
                <div class="action-group">
                    <h4>🔄 Monitoring Controls</h4>
                    <div class="monitoring-controls">
                        <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                            <span>Auto-refresh:</span>
                            <label class="switch" for="autoRefreshToggle">
                                <input type="checkbox" id="autoRefreshToggle" checked onchange="toggleAutoRefresh()">
                                <span class="slider"></span>
                            </label>
                            <span id="refreshStatus" class="status-badge status-success">ON</span>
                        </label>
                    </div>
                    <div class="refresh-control" style="margin-top: 10px;">
                        <label for="refreshInterval">Refresh Interval (seconds):</label>
                        <input type="number" id="refreshInterval" value="5" min="1" max="60" onchange="updateRefreshInterval()">
                    </div>
                </div>
            </div>
        </div>
        
        <h2 style="margin-top: 30px; color: #667eea;">Process Table</h2>
        <div class="top-by-selector">
            <label for="topBySelector"><strong>Show Top:</strong></label>
            <select id="topBySelector" onchange="applyTopBy()">
                <option value="energy">Top by Energy Score</option>
                <option value="cpu">Top by CPU %</option>
                <option value="memory">Top by Memory</option>
                <option value="io">Top by I/O</option>
            </select>
            <label for="topCountSelector" style="margin-left: 20px;"><strong>Count:</strong></label>
            <select id="topCountSelector" onchange="applyTopBy()">
                <option value="10">Top 10</option>
                <option value="20">Top 20</option>
                <option value="30" selected>Top 30</option>
                <option value="50">Top 50</option>
                <option value="all">All</option>
            </select>
        </div>
        
        <div class="class-filters">
            <strong>Filter by Class:</strong>
            <button class="class-filter-btn" onclick="toggleClassFilter('all')" id="filter-all">All</button>
            <button class="class-filter-btn" onclick="toggleClassFilter('CPU-bound')" id="filter-cpu">CPU-bound</button>
            <button class="class-filter-btn" onclick="toggleClassFilter('IO-bound')" id="filter-io">IO-bound</button>
            <button class="class-filter-btn" onclick="toggleClassFilter('Memory-bound')" id="filter-memory">Memory-bound</button>
            <button class="class-filter-btn" onclick="toggleClassFilter('Context-heavy')" id="filter-context">Context-heavy</button>
            <button class="class-filter-btn" onclick="toggleClassFilter('Mixed')" id="filter-mixed">Mixed</button>
        </div>
        <div id="loadingIndicator" class="loading" style="display: none;">🔄 Loading...</div>
        <table>
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('expand')" title="Expand Details">+</th>
                    <th class="sortable" onclick="sortTable('pid')">PID</th>
                    <th class="sortable" onclick="sortTable('name')">Process Name</th>
                    <th class="sortable" onclick="sortTable('cpu')" title="CPU Usage Percentage">CPU % <span class="tooltip-trigger">ℹ️<span class="tooltip">CPU usage percentage. Higher values indicate more CPU-intensive processes.</span></span></th>
                    <th class="sortable" onclick="sortTable('memory')" title="Memory Usage">Memory (MB) <span class="tooltip-trigger">ℹ️<span class="tooltip">Resident Set Size (RSS) in megabytes. Shows how much physical memory the process is using.</span></span></th>
                    <th class="sortable" onclick="sortTable('io')" title="I/O Activity">IO (KB) <span class="tooltip-trigger">ℹ️<span class="tooltip">Total I/O bytes (read + write) in kilobytes. High I/O indicates disk or network activity.</span></span></th>
                    <th class="sortable" onclick="sortTable('energy')" title="Energy Score">Energy Score (mJ/s) <span class="tooltip-trigger">ℹ️<span class="tooltip">Estimated energy consumption rate in millijoules per second. Formula: w1×CPU + w2×IO + w3×Memory + w4×ContextSwitches + w5×Syscalls. Higher scores indicate higher energy consumption.</span></span></th>
                    <th class="sortable" onclick="sortTable('classification')" title="Process Classification">Classification <span class="tooltip-trigger">ℹ️<span class="tooltip">Process type based on resource usage: CPU-bound (high CPU, low I/O), IO-bound (high I/O), Memory-bound (large memory), Context-heavy (frequent task switching), or Mixed (balanced).</span></span></th>
                </tr>
            </thead>
            <tbody id="processTableBody">
                {% for proc in top_processes %}
                <tr>
                    <td><span class="expand-icon" onclick="toggleDetails({{ proc.pid }})">+</span></td>
                    <td>{{ proc.pid }}</td>
                    <td><strong>{{ proc.name }}</strong></td>
                    <td>{{ "%.1f"|format(proc.cpu_percent) }}%</td>
                    <td>{{ "%.1f"|format(proc.memory_mb) }}</td>
                    <td>{{ "%.1f"|format((proc.io_read + proc.io_write) / 1024) }}</td>
                    <td class="energy-{{ 'high' if proc.energy_score > 100 else 'medium' if proc.energy_score > 50 else 'low' }}">
                        {{ "%.2f"|format(proc.energy_score) }}
                    </td>
                    <td>
                        {% set class_name = 'mixed' %}
                        {% if proc.classification %}
                            {% if 'CPU' in proc.classification and 'IO' not in proc.classification %}
                                {% set class_name = 'cpu' %}
                            {% elif 'IO' in proc.classification or 'I/O' in proc.classification %}
                                {% set class_name = 'io' %}
                            {% elif 'Memory' in proc.classification %}
                                {% set class_name = 'memory' %}
                            {% elif 'Context' in proc.classification %}
                                {% set class_name = 'contextheavy' %}
                            {% endif %}
                        {% endif %}
                        <span class="class-badge class-{{ class_name }}">
                            {{ proc.classification or 'Mixed' }}
                        </span>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <p style="text-align: center; margin-top: 20px; color: #666;">
            <span id="lastUpdate">Auto-refreshing every 5 seconds | Last updated: {{ last_update }}</span>
        </p>
    </div>
    
    <script>
        // Define toggleDetails immediately so it's available for initial template rendering
        function toggleDetails(pid) {
            const detailsRow = document.getElementById(`details-${pid}`);
            const icon = event.target;
            if (detailsRow) {
                if (detailsRow.classList.contains('show')) {
                    detailsRow.classList.remove('show');
                    icon.textContent = '+';
                } else {
                    detailsRow.classList.add('show');
                    icon.textContent = '−';
                }
            }
        }
        // Make it globally available immediately
        window.toggleDetails = toggleDetails;
        
        let currentFilters = {};
        let refreshInterval;
        let currentData = [];
        let sortColumn = 'energy';
        let sortDirection = 'desc';
        let classFilter = 'all';
        let topBy = 'energy';
        let topCount = 30;
        let processHistory = {}; // For sparklines
        let demoMode = false; // Demo mode state
        
        function toggleDemo() {
            demoMode = !demoMode;
            const btn = document.getElementById('demoToggle');
            if (demoMode) {
                btn.textContent = '🎭 Disable Demo Mode';
                btn.classList.add('active');
                console.log('🎭 Demo mode ENABLED');
            } else {
                btn.textContent = '🎭 Enable Demo Mode';
                btn.classList.remove('active');
                console.log('🎭 Demo mode DISABLED');
            }
            // Refresh dashboard with new demo setting
            updateDashboard();
        }
        
        function updateDashboard() {
            const demoParam = demoMode ? '?demo=true' : '';
            fetch('/api/data' + demoParam)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to fetch data: ' + response.statusText);
                    }
                    return response.json();
                })
                .then(data => {
                    // Ensure we have processes data
                    if (!data.processes || !Array.isArray(data.processes)) {
                        console.error('Invalid data format:', data);
                        currentData = [];
                    } else {
                        currentData = data.processes;
                        console.log(`✅ Loaded ${currentData.length} processes`);
                    }
                    
                    // Update status bars
                    const statusItems = document.querySelectorAll('.status-item strong');
                    if (statusItems.length >= 4) {
                        statusItems[0].textContent = data.total_processes || 0;
                        statusItems[1].textContent = data.high_energy || 0;
                        statusItems[2].textContent = (data.avg_energy || 0) + ' mJ/s';
                        statusItems[3].textContent = data.last_update || 'N/A';
                    }
                    
                    // Update kernel status
                    const kernelStatus = document.getElementById('kernelStatus');
                    if (kernelStatus) {
                        if (data.kernel_available) {
                            kernelStatus.textContent = '✅ ACTIVE - Collecting kernel events via eBPF (context switches, syscalls)';
                            document.querySelector('.kernel-status').className = 'kernel-status kernel-available';
                        } else {
                            kernelStatus.textContent = '✅ HYBRID MODE - Collecting kernel data via /proc (context switches from /proc/<pid>/status) + CPU, Memory, I/O';
                            document.querySelector('.kernel-status').className = 'kernel-status kernel-available';
                        }
                    }
                    
                    // Update classification cards
                    if (data.classifications) {
                        const statCards = document.querySelectorAll('.stat-card .value');
                        if (statCards.length >= 5) {
                            statCards[0].textContent = data.classifications.cpu_bound || 0;
                            statCards[1].textContent = data.classifications.io_bound || 0;
                            statCards[2].textContent = data.classifications.memory_bound || 0;
                            statCards[3].textContent = data.classifications.context_heavy || 0;
                            statCards[4].textContent = data.classifications.mixed || 0;
                        }
                    }
                    
                    // Update insights
                    updateInsights(data);
                    
                    // Update last update time
                    const lastUpdate = document.getElementById('lastUpdate');
                    if (lastUpdate) {
                        lastUpdate.textContent = `Auto-refreshing every 5 seconds | Last updated: ${data.last_update || 'N/A'}`;
                    }
                    
                    // Update process history for sparklines (keep last 20 data points)
                    currentData.forEach(proc => {
                        if (!processHistory[proc.pid]) {
                            processHistory[proc.pid] = {energy: [], cpu: []};
                        }
                        processHistory[proc.pid].energy.push(proc.energy_score);
                        processHistory[proc.pid].cpu.push(proc.cpu_percent);
                        if (processHistory[proc.pid].energy.length > 20) {
                            processHistory[proc.pid].energy.shift();
                            processHistory[proc.pid].cpu.shift();
                        }
                    });
                    
                    // Render table with filters and sorting (this will handle all rendering)
                    renderTable();
                })
                .catch(error => {
                    console.error('❌ Error fetching dashboard data:', error);
                    const tbody = document.getElementById('processTableBody');
                    if (tbody) {
                        tbody.innerHTML = '<tr class="empty-row"><td colspan="8">❌ Error loading data. Please refresh the page.</td></tr>';
                    }
                });
        }
        
        function renderTable() {
            // Get current filter values from DOM
            const topBySelector = document.getElementById('topBySelector');
            const topCountSelector = document.getElementById('topCountSelector');
            if (topBySelector) topBy = topBySelector.value;
            if (topCountSelector) topCount = topCountSelector.value;
            
            // Make sure we have data
            if (!currentData || currentData.length === 0) {
                const tbody = document.getElementById('processTableBody');
                if (tbody) {
                    tbody.innerHTML = '<tr class="empty-row"><td colspan="8">⏳ Loading processes...</td></tr>';
                }
                return;
            }
            
            let processes = [...currentData];
            
            // Apply class filter
            if (classFilter !== 'all') {
                processes = processes.filter(p => p.classification === classFilter);
            }
            
            // Apply top-by sorting
            processes.sort((a, b) => {
                let valA, valB;
                if (topBy === 'energy') { valA = a.energy_score; valB = b.energy_score; }
                else if (topBy === 'cpu') { valA = a.cpu_percent; valB = b.cpu_percent; }
                else if (topBy === 'memory') { valA = a.memory_mb; valB = b.memory_mb; }
                else if (topBy === 'io') { valA = (a.io_read + a.io_write) / 1024; valB = (b.io_read + b.io_write) / 1024; }
                else { valA = a.energy_score; valB = b.energy_score; }
                return sortDirection === 'desc' ? valB - valA : valA - valB;
            });
            
            // Apply top count limit
            if (topCount !== 'all') {
                const count = parseInt(topCount);
                if (!isNaN(count) && count > 0) {
                    processes = processes.slice(0, count);
                }
            }
            
            // Update table
            const tbody = document.getElementById('processTableBody');
            tbody.innerHTML = '';
            
            if (processes.length === 0) {
                tbody.innerHTML = '<tr class="empty-row"><td colspan="8">⚠️ No processes found matching the current filters. Try adjusting your filter criteria.</td></tr>';
            } else {
                processes.forEach((proc, index) => {
                    // Determine energy hog class
                    let hogClass = '';
                    if (index < 5) hogClass = 'energy-hog-top5';
                    else if (index < 15) hogClass = 'energy-hog-top10';
                    
                    const row = document.createElement('tr');
                    row.className = hogClass;
                    row.setAttribute('data-pid', proc.pid);
                    
                    const energyClass = proc.energy_score > 100 ? 'high' : (proc.energy_score > 50 ? 'medium' : 'low');
                    
                    // Normalize classification for CSS class
                    let classBadge = 'mixed'; // default
                    const classification = proc.classification || 'Mixed';
                    if (classification.includes('CPU')) {
                        classBadge = 'cpu';
                    } else if (classification.includes('IO') || classification.includes('I/O')) {
                        classBadge = 'io';
                    } else if (classification.includes('Memory')) {
                        classBadge = 'memory';
                    } else if (classification.includes('Context')) {
                        classBadge = 'contextheavy';
                    } else if (classification.includes('Mixed') || classification.includes('Balanced') || classification.includes('Resource')) {
                        classBadge = 'mixed';
                    }
                    
                    // Generate sparkline SVG
                    const sparkline = generateSparkline(proc.pid, 'energy');
                    
                    row.innerHTML = `
                        <td><span class="expand-icon" onclick="toggleDetails(${proc.pid})">+</span></td>
                        <td>${proc.pid}</td>
                        <td><strong>${proc.name || 'Unknown'}</strong></td>
                        <td>${formatCpuDisplay(proc)}</td>
                        <td>${proc.memory_mb.toFixed(1)}</td>
                        <td>${((proc.io_read + proc.io_write) / 1024).toFixed(1)}</td>
                        <td class="energy-${energyClass}">
                            ${proc.energy_score.toFixed(2)}
                        </td>
                        <td>
                            <span class="class-badge class-${classBadge}">
                                ${classification}
                            </span>
                        </td>
                    `;
                    tbody.appendChild(row);
                    
                    // Add details row directly after the main row
                    const detailsRow = document.createElement('tr');
                    detailsRow.className = 'process-details';
                    detailsRow.id = `details-${proc.pid}`;
                    detailsRow.innerHTML = `
                        <td colspan="8">
                            ${generateDetailedView(proc)}
                        </td>
                    `;
                    tbody.appendChild(detailsRow);
                });
            }
            
            // Update sort indicators
            document.querySelectorAll('th.sortable').forEach(th => {
                th.classList.remove('asc', 'desc');
            });
            const sortTh = Array.from(document.querySelectorAll('th.sortable')).find(th => {
                const colMap = {'pid': 1, 'name': 2, 'cpu': 3, 'memory': 4, 'io': 5, 'energy': 6, 'classification': 7};
                return th.getAttribute('onclick') && th.getAttribute('onclick').includes(sortColumn);
            });
            if (sortTh) {
                sortTh.classList.add(sortDirection);
            }
        }
        
        function formatCpuDisplay(proc) {
            const cpu = proc.cpu_percent;
            const source = proc.cpu_source || 'unknown';
            const status = proc.activity_status || 'unknown';
            
            let displayHtml = '';
            let cssClass = '';
            let icon = '';
            
            // Determine display based on activity status
            if (status === 'error') {
                icon = '❌';
                cssClass = 'cpu-idle';
                displayHtml = `<span class="cpu-indicator ${cssClass}">${icon} Error</span>`;
            } else if (cpu === 0 || status === 'idle') {
                icon = '💤';
                cssClass = 'cpu-idle';
                displayHtml = `<span class="cpu-indicator ${cssClass}">${icon} Idle</span>`;
            } else if (status === 'minimal') {
                icon = '🟡';
                cssClass = 'cpu-minimal';
                displayHtml = `<span class="cpu-indicator ${cssClass}">${icon} ${cpu.toFixed(1)}%</span>`;
            } else if (status === 'low') {
                icon = '🟢';
                cssClass = 'cpu-low';
                displayHtml = `<span class="cpu-indicator ${cssClass}">${icon} ${cpu.toFixed(1)}%</span>`;
            } else {
                icon = '🔥';
                cssClass = 'cpu-active';
                displayHtml = `<span class="cpu-indicator ${cssClass}">${icon} ${cpu.toFixed(1)}%</span>`;
            }
            
            // Add source indicator for debugging
            const sourceClass = 'cpu-source';
            const sourceText = source === 'interval' ? 'RT' : 
                              source === 'cumulative' ? 'AVG' : 
                              source === 'activity_based' ? 'ACT' : 'ERR';
            
            return `${displayHtml} <span class="${sourceClass}">${sourceText}</span>`;
        }
        
        function generateDetailedView(proc) {
            return `
                <div class="detail-row">
                    <span class="detail-label">PID:</span>
                    <span>${proc.pid}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Command Line:</span>
                    <span>${proc.cmdline || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">User:</span>
                    <span>${proc.username || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Parent PID:</span>
                    <span>${proc.parent_pid || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span>${proc.status || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Threads:</span>
                    <span>${proc.num_threads || 1}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">User Time:</span>
                    <span>${(proc.user_time || 0).toFixed(2)}s</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">System Time:</span>
                    <span>${(proc.system_time || 0).toFixed(2)}s</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">CPU Usage:</span>
                    <span>${formatCpuDisplay(proc)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">CPU Source:</span>
                    <span>${proc.cpu_source || 'unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Activity Status:</span>
                    <span>${proc.activity_status || 'unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Memory:</span>
                    <span>${(proc.memory_vms || 0).toFixed(1)} MB</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Shared Memory:</span>
                    <span>${(proc.memory_shared || 0).toFixed(1)} MB</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Nice Priority:</span>
                    <span>${proc.nice || 0}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">File Descriptors:</span>
                    <span>${proc.num_fds || 0}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Context Switches:</span>
                    <span>${proc.context_switches || 0}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Syscalls:</span>
                    <span>${proc.syscalls || 0}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Data Source:</span>
                    <span>${proc.data_source || 'unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Executable:</span>
                    <span>${proc.exe || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Working Directory:</span>
                    <span>${proc.cwd || 'N/A'}</span>
                </div>
            `;
        }
        
        function sortTable(column) {
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'desc';
            }
            renderTable();
        }
        
        function toggleClassFilter(className) {
            classFilter = className;
            document.querySelectorAll('.class-filter-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(`filter-${className.toLowerCase().replace('-', '')}`).classList.add('active');
            renderTable();
        }
        
        // toggleDetails is already defined at the top of the script (line ~994)
        // No need to redefine it here
        
        function applyTopBy() {
            const topBySelector = document.getElementById('topBySelector');
            const topCountSelector = document.getElementById('topCountSelector');
            if (topBySelector) topBy = topBySelector.value;
            if (topCountSelector) topCount = topCountSelector.value;
            renderTable();
        }
        
        function generateSparkline(pid, type) {
            const history = processHistory[pid];
            if (!history || !history[type] || history[type].length < 2) {
                return '';
            }
            
            const data = history[type];
            const max = Math.max(...data);
            const min = Math.min(...data);
            const range = max - min || 1;
            const width = 100;
            const height = 20;
            const points = data.map((val, i) => {
                const x = (i / (data.length - 1)) * width;
                const y = height - ((val - min) / range) * height;
                return `${x},${y}`;
            }).join(' ');
            
            return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
                <polyline points="${points}" fill="none" stroke="#667eea" stroke-width="2"/>
            </svg>`;
        }
        
        function updateInsights(data) {
            const processes = data.processes || [];
            if (processes.length === 0) {
                document.getElementById('biggestConsumer').textContent = 'No processes';
                return;
            }
            
            const top = processes[0];
            document.getElementById('biggestConsumer').textContent = 
                `${top.name} (PID: ${top.pid}) - Energy Score: ${top.energy_score.toFixed(2)}`;
            
            // Calculate energy trend
            if (processHistory[top.pid] && processHistory[top.pid].energy.length > 1) {
                const history = processHistory[top.pid].energy;
                const recent = history.slice(-5);
                const older = history.slice(-10, -5);
                const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
                const olderAvg = older.length > 0 ? older.reduce((a, b) => a + b, 0) / older.length : recentAvg;
                const trend = recentAvg > olderAvg ? 'Increasing' : recentAvg < olderAvg ? 'Decreasing' : 'Stable';
                document.getElementById('energyTrend').textContent = trend;
            } else {
                document.getElementById('energyTrend').textContent = 'Collecting data...';
            }
            
            // Generate recommendations
            const recommendations = [];
            const highEnergy = processes.filter(p => p.energy_score > 100);
            if (highEnergy.length > 0) {
                const topIO = processes.reduce((max, p) => {
                    const ioTotal = (p.io_read + p.io_write) / 1024;
                    const maxIO = (max.io_read + max.io_write) / 1024;
                    return ioTotal > maxIO ? p : max;
                }, processes[0]);
                const topIOTotal = (topIO.io_read + topIO.io_write) / 1024;
                if (topIOTotal > 1000) {
                    recommendations.push({
                        type: 'io',
                        message: `${topIO.name} is your highest I/O process (${(topIOTotal/1024).toFixed(1)} MB) and accounts for ${((topIO.energy_score/data.avg_energy)*100).toFixed(1)}% of system energy. Consider closing some files or reducing disk activity.`
                    });
                }
                
                if (highEnergy.length >= 3) {
                    const totalEnergy = highEnergy.reduce((sum, p) => sum + p.energy_score, 0);
                    recommendations.push({
                        type: 'general',
                        message: `You have ${highEnergy.length} high-energy processes consuming ${totalEnergy.toFixed(1)} total energy. Consider stopping non-essential processes to save energy.`
                    });
                }
            }
            
            const recommendationsContainer = document.getElementById('recommendationsContainer');
            recommendationsContainer.innerHTML = '';
            if (recommendations.length > 0) {
                recommendations.forEach(rec => {
                    const div = document.createElement('div');
                    div.className = 'recommendation';
                    div.innerHTML = `<strong>💡 Recommendation:</strong> ${rec.message}`;
                    recommendationsContainer.appendChild(div);
                });
            }
        }
        
        function showWhatIf() {
            const top5 = currentData.slice(0, 5);
            const totalEnergy = top5.reduce((sum, p) => sum + p.energy_score, 0);
            const avgEnergy = currentData.reduce((sum, p) => sum + p.energy_score, 0) / currentData.length;
            const savings = (totalEnergy / (totalEnergy + (currentData.length - 5) * avgEnergy)) * 100;
            
            const resultsDiv = document.getElementById('whatIfResults');
            resultsDiv.innerHTML = `
                <div class="insight-item">
                    <strong>If you stop the top 5 energy hogs:</strong>
                    <ul style="margin-top: 10px; padding-left: 20px;">
                        ${top5.map(p => `<li>${p.name} (PID: ${p.pid}) - Energy: ${p.energy_score.toFixed(2)}</li>`).join('')}
                    </ul>
                    <p style="margin-top: 10px;"><strong>Estimated Energy Savings:</strong> ${totalEnergy.toFixed(2)} energy units (~${savings.toFixed(1)}% reduction)</p>
                    <p style="color: #666; font-size: 12px; margin-top: 5px;">Note: This is an estimate. Actual savings depend on system load and process dependencies.</p>
                </div>
            `;
            document.getElementById('whatIfPanel').style.display = 'block';
        }
        
        function closeWhatIf() {
            document.getElementById('whatIfPanel').style.display = 'none';
        }
        
        function exportData(format) {
            const params = new URLSearchParams();
            if (currentFilters.name) params.append('name', currentFilters.name);
            if (currentFilters.min_cpu) params.append('min_cpu', currentFilters.min_cpu);
            if (currentFilters.min_memory) params.append('min_memory', currentFilters.min_memory);
            params.append('format', format);
            
            const linksDiv = document.getElementById('exportLinks');
            linksDiv.innerHTML = '<span style="color: #667eea;">⏳ Exporting...</span>';
            
            fetch(`/api/export?${params.toString()}`)
                .then(response => {
                    if (response.ok) {
                        return response.blob();
                    }
                    throw new Error('Export failed: ' + response.statusText);
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                    const filename = `energy_profile_${timestamp}.${format}`;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    
                    // Show success message
                    linksDiv.innerHTML = `<span style="color: #28a745;">✅ ${format.toUpperCase()} exported successfully!</span><br>`;
                    const link = document.createElement('a');
                    link.className = 'download-link';
                    link.href = `/api/export?${params.toString()}`;
                    link.textContent = `📥 Download ${filename} again`;
                    link.download = filename;
                    linksDiv.appendChild(link);
                })
                .catch(error => {
                    linksDiv.innerHTML = `<span style="color: #dc3545;">❌ Export failed: ${error.message}</span>`;
                });
        }
        
        function generateGraphs() {
            const params = new URLSearchParams();
            if (currentFilters.name) params.append('name', currentFilters.name);
            if (currentFilters.min_cpu) params.append('min_cpu', currentFilters.min_cpu);
            if (currentFilters.min_memory) params.append('min_memory', currentFilters.min_memory);
            
            const graphLinksDiv = document.getElementById('graphLinks');
            graphLinksDiv.innerHTML = '<span style="color: #667eea;">⏳ Generating graphs...</span>';
            
            fetch(`/api/generate-graphs?${params.toString()}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        graphLinksDiv.innerHTML = '<strong style="color: #28a745;">✅ Graphs generated successfully!</strong><br>';
                        data.files.forEach(file => {
                            const link = document.createElement('a');
                            link.className = 'download-link';
                            link.href = `/api/download/${file}`;
                            link.textContent = `📊 Download ${file}`;
                            link.download = file;
                            graphLinksDiv.appendChild(link);
                            graphLinksDiv.appendChild(document.createElement('br'));
                        });
                    } else {
                        graphLinksDiv.innerHTML = `<span style="color: #dc3545;">❌ Error: ${data.error}</span>`;
                    }
                })
                .catch(error => {
                    graphLinksDiv.innerHTML = `<span style="color: #dc3545;">❌ Error: ${error.message}</span>`;
                });
        }
        
        function toggleAutoRefresh() {
            const toggle = document.getElementById('autoRefreshToggle');
            const status = document.getElementById('refreshStatus');
            
            if (toggle.checked) {
                const interval = parseInt(document.getElementById('refreshInterval').value) * 1000;
                refreshInterval = setInterval(updateDashboard, interval);
                status.textContent = 'ON';
                status.className = 'status-badge status-success';
            } else {
                if (refreshInterval) {
                    clearInterval(refreshInterval);
                    refreshInterval = null;
                }
                status.textContent = 'OFF';
                status.className = 'status-badge status-info';
            }
        }
        
        function updateRefreshInterval() {
            const interval = parseInt(document.getElementById('refreshInterval').value) * 1000;
            if (refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = setInterval(updateDashboard, interval);
            }
        }
        
        function applyFilters() {
            currentFilters = {
                name: document.getElementById('filterName').value.trim() || null,
                min_cpu: document.getElementById('filterCpu').value || null,
                min_memory: document.getElementById('filterMemory').value || null
            };
            updateDashboard();
        }
        
        function clearFilters() {
            document.getElementById('filterName').value = '';
            document.getElementById('filterCpu').value = '';
            document.getElementById('filterMemory').value = '';
            currentFilters = {};
            updateDashboard();
        }
        
        // Initialize class filter
        document.getElementById('filter-all').classList.add('active');
        
        // Initialize topCount from DOM
        const topCountSelector = document.getElementById('topCountSelector');
        if (topCountSelector) {
            topCount = topCountSelector.value;
        }
        
        // Make ALL functions globally accessible for onclick handlers
        // This must be done AFTER all functions are defined
        window.applyTopBy = applyTopBy;
        // toggleDetails is already registered at the top of the script, but register again to be safe
        if (typeof window.toggleDetails === 'undefined') {
            window.toggleDetails = toggleDetails;
        }
        window.toggleClassFilter = toggleClassFilter;
        window.sortTable = sortTable;
        window.toggleDemo = toggleDemo;
        window.applyFilters = applyFilters;
        window.clearFilters = clearFilters;
        window.exportData = exportData;
        window.generateGraphs = generateGraphs;
        window.showWhatIf = showWhatIf;
        window.closeWhatIf = closeWhatIf;
        window.toggleAutoRefresh = toggleAutoRefresh;
        window.updateRefreshInterval = updateRefreshInterval;
        window.renderTable = renderTable;
        window.updateDashboard = updateDashboard;
        
        // Auto-refresh every 5 seconds (initialized by toggle)
        refreshInterval = setInterval(updateDashboard, 5000);
        
        // Initial load
        console.log('Initializing dashboard...');
        updateDashboard();
    </script>
</body>
</html>
"""

def get_dashboard_data(filter_name=None, min_cpu=0.0, min_memory=0.0, include_demo=False):
    """Collect data and prepare for dashboard display with robust kernel integration."""
    import time
    start_time = time.time()
    
    # Try to load kernel probes
    b, cs_map, sc_map = load_kernel_probes()
    kernel_available = b is not None
    
    kernel_data = {}
    if kernel_available:
        try:
            pid_counters = get_pid_counters(cs_map, sc_map)
            kernel_data = {pid: {'context_switches': cs, 'syscalls': sc} 
                          for pid, (cs, sc) in pid_counters.items()}
            logger.info(f"eBPF monitoring: {len(kernel_data)} processes tracked")
            print(f"  📊 eBPF monitoring: {len(kernel_data)} processes tracked")
        except Exception as e:
            log_error(logger, e, context={'function': 'get_dashboard_data', 'stage': 'ebpf'})
            print(f"  ⚠️  eBPF data collection failed: {e}")
            kernel_available = False
    else:
        logger.debug("Using /proc-based kernel monitoring")
        print("  📋 Using /proc-based kernel monitoring")
    
    # Collect process metrics (this already includes /proc kernel data)
    try:
        metrics = collect_process_metrics(min_cpu=min_cpu, min_memory=min_memory, filter_name=filter_name)
        logger.debug(f"Collected {len(metrics)} process metrics")
    except Exception as e:
        log_error(logger, e, context={'function': 'get_dashboard_data', 'stage': 'collection'})
        raise
    
    # Add demo processes if requested and if no real processes match certain classifications
    if include_demo:
        demo_processes = create_demo_processes()
        
        # Check which classifications are missing from real processes
        existing_classifications = set()
        for m in metrics:
            try:
                classification = classify_process(m)
                existing_classifications.add(classification)
            except:
                continue
        
        # Add demo processes for missing classifications
        for demo_proc in demo_processes:
            demo_classification = classify_process(demo_proc)
            if demo_classification not in existing_classifications:
                # Add this demo process to show the missing classification
                metrics.append(demo_proc)
                logger.debug(f"Added demo process: {demo_proc['name']} ({demo_classification})")
                print(f"  🎭 Added demo process: {demo_proc['name']} ({demo_classification})")
    
    # Enhanced kernel data integration
    processes_with_energy = []
    for m in metrics:
        pid = m['pid']
        
        # Priority 1: Use eBPF data if available
        if kernel_available and pid in kernel_data:
            kdata = kernel_data[pid]
            if validate_kernel_data(kdata, m):
                # Use eBPF data (more accurate)
                m['context_switches'] = kdata['context_switches']
                m['syscalls'] = kdata['syscalls']
                m['data_source'] = 'eBPF'
            else:
                # Fallback to /proc data if eBPF seems invalid
                proc_kdata = get_proc_kernel_data(pid)
                if proc_kdata:
                    m.update(proc_kdata)
                    m['data_source'] = '/proc'
                else:
                    m['data_source'] = 'estimated'
        else:
            # Priority 2: Use /proc data directly (collector already got this)
            m['data_source'] = '/proc'
            
            # Priority 3: Additional fallback if /proc data is missing
            if m.get('context_switches', 0) == 0 or m.get('syscalls', 0) == 0:
                proc_kdata = get_proc_kernel_data(pid)
                if proc_kdata:
                    # Merge with existing data
                    m['context_switches'] = max(m.get('context_switches', 0), proc_kdata.get('context_switches', 0))
                    m['syscalls'] = max(m.get('syscalls', 0), proc_kdata.get('syscalls', 0))
                    m['data_source'] = '/proc+'
        
        # Calculate energy score with the best available kernel data
        energy = compute_energy_score(m, adaptive=True)
        classification = classify_process(m)
        
        # Add metadata
        m['energy_score'] = energy
        m['classification'] = classification
        
        processes_with_energy.append(m)
    
    # Sort by energy score (highest first)
    processes_with_energy.sort(key=lambda x: x.get('energy_score', 0), reverse=True)
    
    # Calculate statistics
    total_processes = len(processes_with_energy)
    high_energy_count = sum(1 for p in processes_with_energy if p.get('energy_score', 0) > 100)
    avg_energy = sum(p.get('energy_score', 0) for p in processes_with_energy) / max(total_processes, 1)
    
    # Classification counts
    classifications = {
        'cpu_bound': 0,
        'io_bound': 0,
        'memory_bound': 0,
        'context_heavy': 0,
        'mixed': 0
    }
    for p in processes_with_energy:
        cls = p.get('classification', 'Mixed')
        if cls == 'CPU-bound':
            classifications['cpu_bound'] += 1
        elif cls == 'IO-bound':
            classifications['io_bound'] += 1
        elif cls == 'Memory-bound':
            classifications['memory_bound'] += 1
        elif cls == 'Context-heavy':
            classifications['context_heavy'] += 1
        else:
            classifications['mixed'] += 1
    
    # Data source summary
    sources = {}
    for p in processes_with_energy:
        source = p.get('data_source', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    
    duration = time.time() - start_time
    log_metric_collection(logger, len(processes_with_energy), duration)
    logger.debug(f"Data sources: {dict(sources)}")
    print(f"  📈 Data sources: {dict(sources)}")
    
    # Save snapshot to database if storage is enabled
    if storage:
        try:
            saved_count = storage.save_snapshot(processes_with_energy)
            logger.debug(f"Saved {saved_count} processes to database")
        except Exception as e:
            log_error(logger, e, context={'function': 'get_dashboard_data', 'stage': 'storage'})
            # Don't fail the request if storage fails
    
    # Check alerts
    alert_manager = get_alert_manager()
    alerts = alert_manager.check_alerts(processes_with_energy)
    
    return {
        'processes': processes_with_energy,
        'kernel_available': kernel_available,
        'total_processes': total_processes,
        'high_energy': high_energy_count,
        'avg_energy': round(avg_energy, 2),
        'last_update': time.strftime('%H:%M:%S'),
        'kernel_status': 'eBPF Active' if kernel_available else '/proc Fallback',
        'data_sources': sources,
        'classifications': classifications,
        'alerts': alerts  # Add alerts to response
    }

@app.route('/health')
def health_check():
    """
    Health check endpoint for load balancers and monitoring systems.
    
    Returns:
        JSON with health status and component checks
    """
    import time
    health_status = {
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'service': 'Hybrid Energy Profiler',
        'version': '1.0.0',
        'components': {}
    }
    
    # Check process collection
    try:
        test_metrics = collect_process_metrics(min_cpu=0, min_memory=0)
        health_status['components']['collector'] = {
            'status': 'healthy',
            'process_count': len(test_metrics)
        }
        logger.debug("Health check: Collector OK")
    except Exception as e:
        health_status['components']['collector'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'
        log_error(logger, e, context={'function': 'health_check', 'component': 'collector'})
    
    # Check kernel integration
    try:
        b, cs_map, sc_map = load_kernel_probes()
        kernel_available = b is not None
        health_status['components']['kernel_integration'] = {
            'status': 'healthy' if kernel_available else 'degraded',
            'ebpf_available': kernel_available,
            'mode': 'eBPF' if kernel_available else '/proc fallback'
        }
    except Exception as e:
        health_status['components']['kernel_integration'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'degraded'
        log_error(logger, e, context={'function': 'health_check', 'component': 'kernel_integration'})
    
    # Check storage (if enabled)
    storage_enabled = config.get('storage', 'enabled', default=True)
    if storage_enabled:
        try:
            db_path = config.get('storage', 'db_path', default='data/metrics.db')
            import os
            db_exists = os.path.exists(db_path)
            health_status['components']['storage'] = {
                'status': 'healthy' if db_exists else 'degraded',
                'db_path': db_path,
                'db_exists': db_exists
            }
        except Exception as e:
            health_status['components']['storage'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
    
    # Determine overall status code
    status_code = 200
    if health_status['status'] == 'degraded':
        status_code = 503
    elif any(comp.get('status') == 'unhealthy' for comp in health_status['components'].values()):
        health_status['status'] = 'unhealthy'
        status_code = 503
    
    logger.info(f"Health check: {health_status['status']}")
    return jsonify(health_status), status_code

# Login page
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - Hybrid Energy Profiler</title>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 400px;
        }
        h1 {
            color: #1e3c72;
            text-align: center;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #666;
            font-weight: 500;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 14px;
            box-sizing: border-box;
        }
        input:focus {
            outline: none;
            border-color: #1e3c72;
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 10px;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .error {
            color: #e74c3c;
            margin-top: 10px;
            text-align: center;
        }
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 12px;
            color: #1976d2;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>⚡ Hybrid Energy Profiler</h1>
        <div class="info">
            <strong>Default Credentials:</strong><br>
            Admin: admin / admin123<br>
            Viewer: viewer / viewer123<br>
            <small>(Change these in production!)</small>
        </div>
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn">Login</button>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    require_auth = config.get('security', 'require_auth', default=False)
    
    # Skip auth if not required
    if not require_auth:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if authenticate(username, password):
            login_user(username)
            next_page = request.args.get('next') or '/'
            return redirect(next_page)
        else:
            return render_template_string(LOGIN_HTML, error='Invalid username or password')
    
    # If already logged in, redirect to dashboard
    if is_authenticated():
        return redirect('/')
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    """Logout handler."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@require_login
def dashboard():
    """Main dashboard page."""
    data = get_dashboard_data()
    
    # Get current user info
    user = get_current_user()
    
    # Prepare template variables
    template_vars = {
        'user': user,  # Add user info for template
        'kernel_status_class': 'kernel-available' if data['kernel_available'] else 'kernel-unavailable',
        'kernel_status_msg': '✅ ACTIVE - Collecting kernel events via eBPF (context switches, syscalls)' if data['kernel_available'] 
                           else '✅ HYBRID MODE - Collecting kernel data via /proc (context switches from /proc/<pid>/status) + CPU, Memory, I/O',
        'total_processes': data['total_processes'],
        'high_energy': data['high_energy'],
        'avg_energy': data['avg_energy'],
        'kernel_status': data['kernel_status'],
        'data_sources': data['data_sources'],
        'last_update': data['last_update'],
        'top_processes': data['processes'][:30],  # Top 30
        'cpu_bound_count': data['classifications']['cpu_bound'],
        'io_bound_count': data['classifications']['io_bound'],
        'memory_bound_count': data['classifications']['memory_bound'],
        'context_heavy_count': data['classifications']['context_heavy'],
        'mixed_count': data['classifications']['mixed']
    }
    
    return render_template_string(DASHBOARD_HTML, **template_vars)

@app.route('/api/data')
@require_login
@limiter.limit("10 per minute")  # More restrictive for data endpoint
def api_data():
    """API endpoint for JSON data with filtering support."""
    # Get filter parameters from request
    filter_name = request.args.get('name', None)
    min_cpu = request.args.get('min_cpu', 0.0)
    min_memory = request.args.get('min_memory', 0.0)
    include_demo = request.args.get('demo', 'false').lower() == 'true'
    
    data = get_dashboard_data(filter_name=filter_name, min_cpu=min_cpu, min_memory=min_memory, include_demo=include_demo)
    # Convert to JSON-serializable format
    return jsonify({
        'kernel_available': data['kernel_available'],
        'total_processes': data['total_processes'],
        'high_energy': data['high_energy'],
        'avg_energy': data['avg_energy'],
        'kernel_status': data['kernel_status'],
        'data_sources': data['data_sources'],
        'last_update': data['last_update'],
        'classifications': data['classifications'],
        'processes': [
            {
                'pid': p['pid'],
                'name': p['name'],
                'cpu_percent': p['cpu_percent'],
                'cpu_source': p.get('cpu_source', 'unknown'),  # New: CPU measurement source
                'activity_status': p.get('activity_status', 'unknown'),  # New: Activity status
                'memory_mb': p['memory_mb'],
                'io_read': p['io_read'],
                'io_write': p['io_write'],
                'context_switches': p['context_switches'],
                'syscalls': p['syscalls'],
                'energy_score': p['energy_score'],
                'classification': p['classification'],
                'data_source': p.get('data_source', 'unknown'),
                'cmdline': p.get('cmdline', p['name']),
                'username': p.get('username', 'N/A'),
                'parent_pid': p.get('parent_pid', 0),
                'create_time': p.get('create_time', 0),
                'status': p.get('status', 'unknown'),
                'num_threads': p.get('num_threads', 1),
                'user_time': p.get('user_time', 0),
                'system_time': p.get('system_time', 0),
                'memory_vms': p.get('memory_vms', 0),
                'memory_shared': p.get('memory_shared', 0),
                'nice': p.get('nice', 0),
                'num_fds': p.get('num_fds', 0),
                'exe': p.get('exe', 'N/A'),
                'cwd': p.get('cwd', 'N/A')
            }
            for p in data['processes']
        ]
    })

@app.route('/api/export')
@require_login
@limiter.limit("5 per minute")  # Export is resource-intensive
def api_export():
    """API endpoint for exporting data in various formats."""
    # Get filter parameters
    filter_name = request.args.get('name', None)
    min_cpu = request.args.get('min_cpu', 0.0)
    min_memory = request.args.get('min_memory', 0.0)
    format_type = request.args.get('format', 'csv').lower()
    
    # Get data
    try:
        data = get_dashboard_data(filter_name=filter_name, min_cpu=min_cpu, min_memory=min_memory)
        processes = data['processes']
        
        if not processes or len(processes) == 0:
            return jsonify({'error': 'No processes found matching the filter criteria'}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to collect data: {str(e)}'}), 500
    
    # Export based on format
    try:
        if format_type == 'csv':
            filepath = export_to_csv(processes)
            # Convert to absolute path for Flask
            filepath = os.path.abspath(filepath)
            filename = os.path.basename(filepath)
            if not os.path.exists(filepath):
                return jsonify({'error': f'File not found: {filepath}'}), 404
            return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/csv')
        elif format_type == 'json':
            filepath = export_to_json(processes)
            filepath = os.path.abspath(filepath)
            filename = os.path.basename(filepath)
            if not os.path.exists(filepath):
                return jsonify({'error': f'File not found: {filepath}'}), 404
            return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/json')
        elif format_type == 'txt':
            filepath = export_summary_report(processes)
            filepath = os.path.abspath(filepath)
            filename = os.path.basename(filepath)
            if not os.path.exists(filepath):
                return jsonify({'error': f'File not found: {filepath}'}), 404
            return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/plain')
        else:
            return jsonify({'error': 'Invalid format. Use csv, json, or txt'}), 400
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        log_error(logger, e, context={'function': 'api_export', 'format': format_type})
        print(f"Export error: {error_msg}")
        print(f"Traceback: {error_trace}")
        return jsonify({'error': error_msg, 'traceback': error_trace}), 500

@app.route('/api/generate-graphs')
@require_login
@limiter.limit("3 per minute")  # Graph generation is CPU-intensive
def api_generate_graphs():
    """API endpoint for generating visualization graphs."""
    # Get filter parameters
    filter_name = request.args.get('name', None)
    min_cpu = request.args.get('min_cpu', 0.0)
    min_memory = request.args.get('min_memory', 0.0)
    
    # Get data
    data = get_dashboard_data(filter_name=filter_name, min_cpu=min_cpu, min_memory=min_memory)
    processes = data['processes']
    
    try:
        # Generate graphs in configured directory
        output_dir = config.get('output', 'graphs_dir', default='output/graphs')
        os.makedirs(output_dir, exist_ok=True)
        generate_all_visualizations(processes, output_dir=output_dir)
        
        # Return list of generated files
        graph_files = [
            'cpu_vs_energy.png',
            'io_vs_energy.png',
            'classification.png',
            'energy_heatmap.png'
        ]
        
        return jsonify({
            'success': True,
            'files': graph_files,
            'message': 'Graphs generated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/history')
def api_history():
    """API endpoint for retrieving historical data."""
    if not storage:
        return jsonify({'error': 'Storage is disabled'}), 503
    
    # Get query parameters
    pid = request.args.get('pid', type=int)
    name = request.args.get('name', type=str)
    hours = request.args.get('hours', default=24, type=int)
    limit = request.args.get('limit', default=1000, type=int)
    
    try:
        history = storage.get_history(pid=pid, name=name, hours=hours, limit=limit)
        return jsonify({
            'success': True,
            'count': len(history),
            'data': history
        })
    except Exception as e:
        log_error(logger, e, context={'function': 'api_history'})
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/trends/<name>')
def api_trends(name):
    """API endpoint for process energy trends."""
    if not storage:
        return jsonify({'error': 'Storage is disabled'}), 503
    
    hours = request.args.get('hours', default=24, type=int)
    
    try:
        trends = storage.get_trends(name, hours=hours)
        return jsonify({
            'success': True,
            'process_name': name,
            'hours': hours,
            'data': trends
        })
    except Exception as e:
        log_error(logger, e, context={'function': 'api_trends', 'name': name})
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/stats')
def api_storage_stats():
    """API endpoint for storage statistics."""
    if not storage:
        return jsonify({'error': 'Storage is disabled'}), 503
    
    try:
        stats = storage.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        log_error(logger, e, context={'function': 'api_storage_stats'})
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
@require_login
def api_alerts():
    """API endpoint for recent alerts."""
    limit = request.args.get('limit', default=10, type=int)
    alert_manager = get_alert_manager()
    
    return jsonify({
        'success': True,
        'alerts': alert_manager.get_recent_alerts(limit=limit),
        'rule_stats': alert_manager.get_rule_stats()
    })

@app.route('/api/alerts/rules')
@require_login
@require_role('admin')
def api_alert_rules():
    """API endpoint for managing alert rules (admin only)."""
    alert_manager = get_alert_manager()
    
    if request.method == 'POST':
        # Add new rule (future implementation)
        return jsonify({'error': 'Not implemented yet'}), 501
    
    return jsonify({
        'success': True,
        'rules': alert_manager.get_rule_stats()
    })

@app.route('/api/download/<filename>')
def api_download(filename):
    """API endpoint for downloading generated files."""
    # Security: only allow downloading from output directories
    if filename.endswith('.png'):
        directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'graphs')
    elif filename.endswith(('.csv', '.json', '.txt')):
        directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'exports')
    else:
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Check if file exists
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'File not found: {filename}'}), 404
        
        # Use send_file instead of send_from_directory for better control
        return send_file(filepath, as_attachment=True, download_name=filename)
        
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def run_dashboard(host=None, port=None, debug=None):
    """Run the dashboard server."""
    # Use config values if not provided
    if host is None:
        host = config.get('dashboard', 'host', default='0.0.0.0')
    if port is None:
        port = config.get('dashboard', 'port', default=5000)
    if debug is None:
        debug = config.get('dashboard', 'debug', default=False)
    
    print(f"\n{'='*60}")
    print("🚀 Starting Hybrid Energy Profiler Dashboard")
    print(f"{'='*60}")
    print(f"📊 Hybrid Energy Profiler: http://localhost:{port}")
    print(f"📡 API Endpoint: http://localhost:{port}/api/data")
    print(f"⚙️  Configuration: {config.config_path}")
    print(f"{'='*60}\n")
    print("Press Ctrl+C to stop the dashboard\n")
    
    app.run(host=host, port=port, debug=debug)

