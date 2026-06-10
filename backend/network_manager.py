"""
Network Configuration & UDP Auto-Discovery Manager
Handles Windows Firewall configuration, port binding, and IP discovery over LAN.
"""
import socket
import threading
import json
import os
import subprocess
import time

DISCOVERY_PORT = 5555
DISCOVERY_MSG = "DISCOVER_BESTIE_SERVER"
RESPONSE_PREFIX = "BESTIE_SERVER_RESPONSE:"

def get_local_ip():
    """Gets the primary local IP address of this machine on the LAN."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a public dummy address (does not actually send packets)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def setup_firewall(flask_port=5050):
    """
    Sets up Windows Firewall rules for the Flask server and UDP Discovery port.
    Attempts to run netsh. If permissions are missing, it fails gracefully.
    """
    import sys
    if sys.platform != 'win32':
        return
        
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    # Rules to add
    rules = [
        ("Bestie Accounts Server TCP", flask_port, "TCP"),
        ("Bestie Accounts Discovery UDP", DISCOVERY_PORT, "UDP")
    ]
    
    print("[Firewall] Configuring firewall rules...")
    for name, port, proto in rules:
        # Check if rule exists
        check_cmd = f'netsh advfirewall firewall show rule name="{name}"'
        try:
            res = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, startupinfo=startupinfo)
            if name in res.stdout:
                print(f"[Firewall] Rule '{name}' already exists.")
                continue
        except Exception as e:
            print(f"[Firewall] Error checking rule '{name}': {e}")
            
        # Add rule
        add_cmd = f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow protocol={proto} localport={port}'
        try:
            res = subprocess.run(add_cmd, shell=True, capture_output=True, text=True, startupinfo=startupinfo)
            if res.returncode == 0:
                print(f"[Firewall] Successfully added rule: {name} ({proto} port {port})")
            else:
                print(f"[Firewall] Failed to add rule '{name}' (requires administrator privileges).")
        except Exception as e:
            print(f"[Firewall] Exception adding rule '{name}': {e}")

class DiscoveryServer:
    """UDP Broadcast listener that runs on the Server machine to let Clients find it."""
    def __init__(self, flask_port=5050):
        self.flask_port = flask_port
        self.running = False
        self.socket = None
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow reusing address
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind(('', DISCOVERY_PORT))
        except Exception as e:
            print(f"[DiscoveryServer] Failed to bind to port {DISCOVERY_PORT}: {e}")
            return

        print(f"[DiscoveryServer] Listening for client discovery requests on port {DISCOVERY_PORT}...")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                message = data.decode('utf-8', errors='ignore').strip()
                if message == DISCOVERY_MSG:
                    # Respond with server IP and Flask port
                    server_ip = get_local_ip()
                    response = f"{RESPONSE_PREFIX}{server_ip}:{self.flask_port}"
                    self.socket.sendto(response.encode('utf-8'), addr)
                    print(f"[DiscoveryServer] Responded to client {addr} with {response}")
            except Exception as e:
                if not self.running:
                    break
                time.sleep(0.5)

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()

def discover_server(timeout=1.5):
    """
    Sends a UDP broadcast to find the server IP and port on the LAN.
    Returns (ip, port) if found, else (None, None).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    
    server_address = ('255.255.255.255', DISCOVERY_PORT)
    try:
        print(f"[DiscoveryClient] Broadcasting discovery request to port {DISCOVERY_PORT}...")
        sock.sendto(DISCOVERY_MSG.encode('utf-8'), server_address)
        
        # Wait for reply
        data, server = sock.recvfrom(1024)
        response = data.decode('utf-8', errors='ignore').strip()
        if response.startswith(RESPONSE_PREFIX):
            parts = response[len(RESPONSE_PREFIX):].split(':')
            if len(parts) == 2:
                ip, port = parts[0], int(parts[1])
                print(f"[DiscoveryClient] Found server at {ip}:{port}")
                return ip, port
    except socket.timeout:
        print("[DiscoveryClient] Discovery timed out (no server responded).")
    except Exception as e:
        print(f"[DiscoveryClient] Discovery error: {e}")
    finally:
        sock.close()
    return None, None
