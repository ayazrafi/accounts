"""
MongoDB Auto-Start Manager
Checks if MongoDB is running on the configured port.
If not, finds mongod.exe and starts it automatically.
"""
import os
import sys
import socket
import subprocess
import time
import glob
import winreg
from dotenv import load_dotenv

load_dotenv()

MONGO_PORT = int(os.getenv("MONGO_URI", "mongodb://localhost:27021/").split(":")[-1].rstrip("/"))

if getattr(sys, 'frozen', False):
    # Packaged production environment - use safe local AppData folder
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BestieAccounts", "db")
else:
    DATA_DIR = os.getenv("MONGO_DBPATH", r"C:\data\db")


def is_port_open(host: str = "127.0.0.1", port: int = None) -> bool:
    if port is None:
        port = MONGO_PORT
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _find_mongod() -> str | None:
    """Try to locate mongod.exe on this machine."""
    # 0. Packaged environment search (Option B or Onefile)
    if getattr(sys, 'frozen', False):
        # A. Check internal PyInstaller temp dir (sys._MEIPASS)
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled = os.path.join(meipass, "bin", "mongod.exe")
            if os.path.isfile(bundled):
                return bundled
        
        # B. Check local 'bin' directory next to the executable
        exe_dir = os.path.dirname(sys.executable)
        local_bin = os.path.join(exe_dir, "bin", "mongod.exe")
        if os.path.isfile(local_bin):
            return local_bin

    # 1. Already on PATH
    import shutil
    found = shutil.which("mongod")
    if found:
        return found

    # 2. Windows Registry — MongoDB installer writes here
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MongoDB\Server"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\MongoDB\Server"),
    ]
    for hive, key_path in reg_paths:
        try:
            key = winreg.OpenKey(hive, key_path)
            install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
            mongod = os.path.join(install_dir, "bin", "mongod.exe")
            if os.path.isfile(mongod):
                return mongod
        except Exception:
            pass

    # 3. Common installation directories (wildcard version folders)
    search_globs = [
        r"C:\Program Files\MongoDB\Server\*\bin\mongod.exe",
        r"C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe",
        r"C:\mongodb\bin\mongod.exe",
    ]
    for pattern in search_globs:
        matches = sorted(glob.glob(pattern), reverse=True)  # latest version first
        if matches:
            return matches[0]

    return None


def _ensure_dbpath(path: str):
    os.makedirs(path, exist_ok=True)


def start_mongodb(port: int = None, dbpath: str = None) -> subprocess.Popen | None:
    """Start mongod on the given port. Returns the Popen object or None on failure."""
    if port is None:
        port = MONGO_PORT
    if dbpath is None:
        dbpath = DATA_DIR

    mongod = _find_mongod()
    if not mongod:
        return None

    _ensure_dbpath(dbpath)

    log_dir = os.path.join(os.path.dirname(dbpath), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "mongod.log")

    cmd = [
        mongod,
        "--port", str(port),
        "--dbpath", dbpath,
        "--logpath", log_file,
        "--logappend",
    ]

    proc = subprocess.Popen(
        cmd,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def wait_for_mongo(port: int = None, timeout: int = 20) -> bool:
    if port is None:
        port = MONGO_PORT
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_open(port=port):
            return True
        time.sleep(0.4)
    return False


def ensure_mongodb_running(port: int = None, status_callback=None) -> bool:
    """
    Main entry: check MongoDB, start if needed.
    status_callback(msg: str) is called with progress messages.
    Returns True if MongoDB is ready.
    """
    if port is None:
        port = MONGO_PORT

    def _log(msg):
        if status_callback:
            status_callback(msg)

    if is_port_open(port=port):
        _log(f"MongoDB already running on port {port}")
        return True

    _log(f"MongoDB not found on port {port}. Locating mongod.exe...")
    mongod_path = _find_mongod()
    if not mongod_path:
        _log("ERROR: mongod.exe not found. Please install MongoDB.")
        return False

    _log(f"Found: {mongod_path}")
    _log(f"Starting MongoDB on port {port} (dbpath: {DATA_DIR})...")
    proc = start_mongodb(port=port)
    if proc is None:
        _log("ERROR: Failed to launch mongod process.")
        return False

    _log("Waiting for MongoDB to be ready...")
    if wait_for_mongo(port=port, timeout=25):
        _log(f"MongoDB is ready on port {port}!")
        return True
    else:
        _log("ERROR: MongoDB did not start in time.")
        proc.terminate()
        return False
