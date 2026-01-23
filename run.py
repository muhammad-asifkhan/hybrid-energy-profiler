#!/usr/bin/env python3
"""
Quick runner script - Launches the Hybrid Energy Profiler Dashboard directly.
"""
from energymon.dashboard import run_dashboard
from energymon.config import get_config
import os
import subprocess
import webbrowser
import threading
import time

# Get configuration
config = get_config()

def open_browser(port=None, delay=2):
    """Open browser after a short delay to let server start."""
    if port is None:
        port = config.get('dashboard', 'port', default=5000)
    
    time.sleep(delay)
    url = f'http://127.0.0.1:{port}'

    # Prefer opening in the user's *system* browser. In Cursor/VS Code terminals,
    # clicking links can open an IDE webview which may fail (service worker errors).
    try:
        if os.name == "posix":
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    except Exception:
        pass

    # Fallback (may use environment/browser integration)
    try:
        webbrowser.open(url, new=2)
    except Exception:
        # Last resort: do nothing; user can copy/paste the URL.
        return

if __name__ == "__main__":
    port = config.get('dashboard', 'port', default=5000)
    print("🚀 Launching Hybrid Energy Profiler Dashboard...")
    print("📊 Hybrid Energy Profiler will open automatically in your browser")
    print(f"   If it doesn't, copy/paste: http://127.0.0.1:{port}\n")
    
    # Start browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,), daemon=True)
    browser_thread.start()
    
    # Launch dashboard (will use config values)
    run_dashboard()

