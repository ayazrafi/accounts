import os
import json
import hashlib
import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
import subprocess
import uuid as _uuid

import threading

def _run_cmd_with_timeout(cmd, timeout=3):
    result = [None]
    def target():
        try:
            import sys
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )
            stdout, _ = proc.communicate()
            result[0] = stdout.decode().strip()
        except Exception:
            pass

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    return result[0]

def get_hwid():
    """Generates a unique hardware ID for the current machine."""
    try:
        # Use a single combined PowerShell command to query both UUID and ProcessorId
        # to reduce startup overhead by 2x and prevent timeout issues.
        cmd = (
            'powershell -NoProfile -Command '
            '"(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID; '
            '(Get-CimInstance -ClassName Win32_Processor).ProcessorId"'
        )
        out = _run_cmd_with_timeout(cmd, timeout=8)
        
        hw_uuid = ""
        cpu_id = ""
        if out:
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 1:
                hw_uuid = lines[0]
            if len(lines) >= 2:
                cpu_id = lines[1]

        if not hw_uuid or "Default" in hw_uuid or "None" in hw_uuid:
            hwid_raw = str(_uuid.getnode())
        else:
            hwid_raw = f"{hw_uuid}-{cpu_id}"

        return hashlib.sha256(hwid_raw.encode()).hexdigest().upper()
    except Exception:
        return hashlib.sha256(str(_uuid.getnode()).encode()).hexdigest().upper()

# Config
LICENSE_SERVER_URL = "https://webrtc.bestie11.com" 

# Store license in user's AppData directory to avoid permission errors under Program Files
_appdata_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BestieAccounts")
os.makedirs(_appdata_dir, exist_ok=True)
LICENSE_FILE = os.path.join(_appdata_dir, "license.dat")


def get_machine_id():
    return get_hwid()

class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Product Activation")
        self.setFixedSize(400, 250)
        self._hwid = get_machine_id()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Activate Your Software")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)

        desc = QLabel("Please enter your license key to activate the product on this machine.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        hwid_layout = QHBoxLayout()
        hwid_layout.addWidget(QLabel("Machine ID:"))
        self.hwid_edit = QLineEdit(self._hwid)
        self.hwid_edit.setReadOnly(True)
        self.hwid_edit.setStyleSheet("background: #f0f4f8; color: #546e7a; border: none; padding: 5px;")
        hwid_layout.addWidget(self.hwid_edit)
        layout.addLayout(hwid_layout)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_edit.setStyleSheet("padding: 8px; font-size: 14px; border: 1px solid #90caf9; border-radius: 4px;")
        layout.addWidget(self.key_edit)

        btn_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate Now")
        self.activate_btn.setStyleSheet("background: #1565C0; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        self.activate_btn.clicked.connect(self._on_activate)
        
        self.cancel_btn = QPushButton("Exit")
        self.cancel_btn.setStyleSheet("padding: 10px;")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.activate_btn)
        layout.addLayout(btn_layout)

    def _on_activate(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Required", "Please enter a license key.")
            return

        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Activating...")
        
        try:
            response = requests.post(f"{LICENSE_SERVER_URL}/activate", json={
                "key": key,
                "hwid": self._hwid
            }, timeout=10)
            
            data = response.json()
            if response.status_code == 200 and data.get("success"):
                lic_type = data.get("type", "client")
                # Save license locally
                with open(LICENSE_FILE, "w") as f:
                    json.dump({"key": key, "hwid": self._hwid, "type": lic_type}, f)
                
                QMessageBox.information(self, "Success", f"Software activated successfully as {lic_type.upper()}!")
                self.accept()
            else:
                QMessageBox.critical(self, "Activation Failed", data.get("error", "Unknown error occurred."))
                self.activate_btn.setEnabled(True)
                self.activate_btn.setText("Activate Now")
        except Exception as e:
            QMessageBox.critical(self, "Network Error", f"Could not connect to activation server.\n{e}")
            self.activate_btn.setEnabled(True)
            self.activate_btn.setText("Activate Now")

def check_license():
    """Returns 'server' or 'client' if license is valid, otherwise None."""
    hwid = get_machine_id()
    
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
            
            key = data.get("key")
            saved_hwid = data.get("hwid")
            saved_type = data.get("type", "server")
            
            if saved_hwid != hwid:
                # Calculate MAC-based fallback HWID to detect WMI query failures
                mac_hwid = hashlib.sha256(str(_uuid.getnode()).encode()).hexdigest().upper()
                if hwid == mac_hwid:
                    # WMI query timed out or failed on this run, but we have a saved license.
                    # Trust the local license to avoid locking the user out or deleting the file.
                    return saved_type

                # If hardware ID changed (and it's not a WMI fallback), verify with server.
                # Only delete license.dat if the server explicitly tells us it is invalid.
                try:
                    response = requests.post(f"{LICENSE_SERVER_URL}/verify", json={
                        "key": key,
                        "hwid": hwid
                    }, timeout=5)
                    if response.status_code == 200 and response.json().get("valid"):
                        lic_type = response.json().get("type", saved_type)
                        # Update local license with the new hwid
                        with open(LICENSE_FILE, "w") as f:
                            json.dump({"key": key, "hwid": hwid, "type": lic_type}, f)
                        return lic_type
                    else:
                        # Only delete the local license file if the server explicitly tells us
                        # the key itself is invalid, suspended, or expired.
                        data = response.json() if response.status_code != 500 else {}
                        err_msg = data.get("error", "").lower()
                        if "key" in err_msg or "suspended" in err_msg or "expired" in err_msg:
                            try:
                                os.remove(LICENSE_FILE)
                            except:
                                pass
                except Exception:
                    # Server is offline, trust the local file anyway
                    return saved_type
            else:
                # HWID matches, verify with server
                try:
                    response = requests.post(f"{LICENSE_SERVER_URL}/verify", json={
                        "key": key,
                        "hwid": hwid
                    }, timeout=5)
                    if response.status_code == 200 and response.json().get("valid"):
                        lic_type = response.json().get("type", saved_type)
                        # Update type in file if it changed
                        if lic_type != saved_type:
                            with open(LICENSE_FILE, "w") as f:
                                json.dump({"key": key, "hwid": hwid, "type": lic_type}, f)
                        return lic_type
                except:
                    # If offline, trust the local file (for now)
                    return saved_type
        except:
            pass

    # If we reach here, no valid license found
    dlg = ActivationDialog()
    if dlg.exec() == QDialog.DialogCode.Accepted:
        try:
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
            return data.get("type", "client")
        except:
            return "client"
    return None
