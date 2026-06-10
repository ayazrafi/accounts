import os
import json
import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QStyle
)
from PySide6.QtCore import Qt, QSize
from backend.network_manager import discover_server

SERVER_ADDRESS_FILE = "server_address.dat"

def get_saved_server_address():
    """Loads saved server address (ip, port) if exists."""
    if os.path.exists(SERVER_ADDRESS_FILE):
        try:
            with open(SERVER_ADDRESS_FILE, "r") as f:
                data = json.load(f)
                return data.get("ip"), data.get("port", 5050)
        except:
            pass
    return None, 5050

def save_server_address(ip, port=5050):
    """Saves server address locally."""
    try:
        with open(SERVER_ADDRESS_FILE, "w") as f:
            json.dump({"ip": ip, "port": port}, f)
    except:
        pass

class ServerConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Connection Settings")
        self.setFixedSize(450, 320)
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # Title
        title = QLabel("Connect to Server")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #3B82F6;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "This client installation must connect to the Bestie Accounts Server on your network. "
            "Please auto-discover or enter the Server's IP address manually."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748B; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # Status indicator
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #E5E7EB;")
        layout.addWidget(line)

        # Form layout manually using layouts
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # IP Input
        ip_layout = QHBoxLayout()
        ip_label = QLabel("Server IP:")
        ip_label.setFixedWidth(80)
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("e.g. 192.168.1.15")
        self.ip_edit.setStyleSheet("padding: 6px; font-size: 13px;")
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_edit)
        form_layout.addLayout(ip_layout)

        # Port Input
        port_layout = QHBoxLayout()
        port_label = QLabel("Server Port:")
        port_label.setFixedWidth(80)
        self.port_edit = QLineEdit("5050")
        self.port_edit.setStyleSheet("padding: 6px; font-size: 13px;")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_edit)
        form_layout.addLayout(port_layout)

        layout.addLayout(form_layout)

        # Buttons layout
        btn_layout = QHBoxLayout()
        
        # Discover Button
        self.discover_btn = QPushButton("Auto-Discover")
        self.discover_btn.setStyleSheet(
            "background: #10B981; color: white; padding: 8px 12px; font-weight: bold; border-radius: 5px;"
        )
        self.discover_btn.clicked.connect(self._on_discover)
        
        # Test & Save Button
        self.save_btn = QPushButton("Test & Connect")
        self.save_btn.setStyleSheet(
            "background: #3B82F6; color: white; padding: 8px 15px; font-weight: bold; border-radius: 5px;"
        )
        self.save_btn.clicked.connect(self._on_test_and_save)

        # Exit Button
        self.exit_btn = QPushButton("Exit")
        self.exit_btn.setStyleSheet(
            "background: #F1F5F9; color: #0F172A; padding: 8px 15px; font-weight: bold; border-radius: 5px; border: 1px solid #CBD5E1;"
        )
        self.exit_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.discover_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.exit_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def load_settings(self):
        ip, port = get_saved_server_address()
        if ip:
            self.ip_edit.setText(ip)
            self.port_edit.setText(str(port))
            # Test if it works
            if self._test_connection(ip, port):
                self.status_label.setText(f"Status: Connected to {ip}:{port}")
                self.status_label.setStyleSheet("color: #16A34A; font-weight: bold; font-size: 12px;")

    def _test_connection(self, ip, port):
        try:
            url = f"http://{ip}:{port}/api/health"
            response = requests.get(url, timeout=3)
            return response.status_code == 200 and response.json().get("status") == "ok"
        except:
            return False

    def _on_discover(self):
        self.discover_btn.setEnabled(False)
        self.discover_btn.setText("Scanning LAN...")
        # Process UI events so the button text updates
        self.discover_btn.repaint()
        
        ip, port = discover_server(timeout=2.0)
        
        self.discover_btn.setEnabled(True)
        self.discover_btn.setText("Auto-Discover")
        
        if ip:
            self.ip_edit.setText(ip)
            self.port_edit.setText(str(port))
            self.status_label.setText(f"Status: Discovered Server at {ip}:{port}")
            self.status_label.setStyleSheet("color: #16A34A; font-weight: bold; font-size: 12px;")
            QMessageBox.information(
                self, "Server Found", 
                f"Successfully discovered Bestie Accounts Server at IP: {ip} and Port: {port}."
            )
        else:
            QMessageBox.warning(
                self, "Discovery Failed", 
                "Could not find the server automatically. Please ensure the Server machine is running, "
                "connected to the same network, and that firewall settings are correctly set. "
                "Alternatively, enter the IP address manually."
            )

    def _on_test_and_save(self):
        ip = self.ip_edit.text().strip()
        port_str = self.port_edit.text().strip()
        
        if not ip:
            QMessageBox.warning(self, "Input Error", "Please enter the server IP address.")
            return
            
        try:
            port = int(port_str)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter a valid port number.")
            return

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Testing...")
        self.save_btn.repaint()

        connected = self._test_connection(ip, port)
        
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Test & Connect")

        if connected:
            save_server_address(ip, port)
            QMessageBox.information(self, "Connected", "Connection successful! Settings saved.")
            self.accept()
        else:
            QMessageBox.critical(
                self, "Connection Failed", 
                f"Could not reach Bestie Accounts Server at http://{ip}:{port}/api/health\n\n"
                "Please verify:\n"
                "1. The Server application is running on that machine.\n"
                "2. The IP address and Port are correct.\n"
                "3. Both machines are on the same network (LAN).\n"
                "4. Windows Firewall on the Server allows inbound connections."
            )
