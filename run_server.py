import os
import sys
import threading
import time
import urllib.request
import webbrowser
import subprocess

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.environ["PYTHONPATH"] = ROOT_DIR

storage_dir = os.path.join(ROOT_DIR, "storage")
os.makedirs(storage_dir, exist_ok=True)
log_path = os.path.join(storage_dir, "server.log")

# Ensure valid stdout/stderr streams even under pythonw.exe
if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = open(log_path, "a", encoding="utf-8", buffering=1)

HEALTH_URL = "http://127.0.0.1:8000/api/v1/system/health"
APP_URL = "http://127.0.0.1:8000"


def is_running() -> bool:
    """Checks whether Content Factory is already active on port 8000."""
    try:
        req = urllib.request.urlopen(HEALTH_URL, timeout=1.0)
        return req.getcode() == 200
    except Exception:
        return False


def cleanup_stale_port_8000():
    """If port 8000 is occupied by a dead/unresponsive zombie process, release it."""
    try:
        cmd = 'Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess'
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
        pids = set(res.stdout.strip().split())
        for pid_str in pids:
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid > 0 and pid != os.getpid():
                    if not is_running():
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    except Exception:
        pass


def open_browser_when_ready(open_browser: bool):
    """Waits for the server to bind and respond, then launches user browser."""
    if not open_browser:
        return
    for _ in range(60):
        time.sleep(0.3)
        if is_running():
            try:
                webbrowser.open(APP_URL)
            except Exception:
                pass
            return


def main():
    open_browser = "--no-browser" not in sys.argv

    # If already running, simply focus/open browser and exit
    if is_running():
        if open_browser:
            webbrowser.open(APP_URL)
        sys.exit(0)

    # Ensure port 8000 is clean of non-responsive zombie processes
    cleanup_stale_port_8000()

    # Launch daemon thread that opens browser as soon as server responds
    thread = threading.Thread(target=open_browser_when_ready, args=(open_browser,), daemon=True)
    thread.start()

    # Run Uvicorn directly in this process (runs completely in background if called via pythonw)
    try:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        import traceback
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[FATAL ERROR IN RUN_SERVER]: {e}\n")
            traceback.print_exc(file=f)


if __name__ == "__main__":
    main()
