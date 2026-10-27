"""
ftp_service.py (Windows Edition)
Lightweight embedded FTP server for receiving photos directly from
Sony cameras (Sony A7 IV, A7S III, A1, A9 II, etc.) via Wi-Fi or USB-C.
"""

import os
import sys
import time
import socket
import subprocess
import re
import threading

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import ThreadedFTPServer
    PYFTPDLIB_AVAILABLE = True
except ImportError:
    PYFTPDLIB_AVAILABLE = False


def get_local_ips():
    """Detects local IPv4 addresses (Wi-Fi, Ethernet, Hotspot, USB tether)."""
    ips = set()
    # 1. UDP probe to get default route IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    # 2. Hostname resolution
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ':' not in ip and not ip.startswith('127.'):
                ips.add(ip)
    except Exception:
        pass

    # 3. System command fallback
    try:
        if sys.platform == 'win32':
            out = subprocess.check_output(['ipconfig'], text=True)
            for m in re.finditer(r'IPv4 Address[.\s]+:\s*([\d.]+)', out):
                ips.add(m.group(1))
        else:
            out = subprocess.check_output(['ifconfig'], text=True)
            for m in re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out):
                ip = m.group(1)
                if not ip.startswith('127.'):
                    ips.add(ip)
    except Exception:
        pass

    valid = [ip for ip in sorted(list(ips)) if not ip.startswith('127.')]
    return valid or ['127.0.0.1']


class SonyFTPHandler(FTPHandler):
    """Custom FTP handler that notifies our app the moment a photo finishes uploading."""
    on_file_callback = None

    def on_file_received(self, file):
        super().on_file_received(file)
        if SonyFTPHandler.on_file_callback:
            try:
                SonyFTPHandler.on_file_callback(file)
            except Exception as e:
                print(f"[FTP] Callback error: {e}")


class PhotoBoothFTPServer:
    def __init__(self, watch_folder, port=2121, on_new_photo_callback=None):
        self.watch_folder = os.path.abspath(watch_folder)
        self.port = port
        self.on_new_photo_callback = on_new_photo_callback
        self.server = None
        self.thread = None
        self.running = False
        self.primary_ip = get_local_ips()[0]

    def start(self):
        if not PYFTPDLIB_AVAILABLE:
            print("[FTP] pyftpdlib is not installed. Run: pip install pyftpdlib")
            return False

        if self.running:
            return True

        os.makedirs(self.watch_folder, exist_ok=True)
        SonyFTPHandler.on_file_callback = self.on_new_photo_callback

        authorizer = DummyAuthorizer()
        perms = "elradfmwMT"
        authorizer.add_user("sony", "sony", self.watch_folder, perm=perms)
        authorizer.add_user("booth", "booth", self.watch_folder, perm=perms)
        authorizer.add_anonymous(self.watch_folder, perm=perms)

        handler = SonyFTPHandler
        handler.authorizer = authorizer
        handler.passive_ports = range(60000, 60050)
        handler.permit_foreign_addresses = True

        try:
            self.server = ThreadedFTPServer(("0.0.0.0", self.port), handler)
            self.running = True

            def run_server():
                try:
                    self.server.serve_forever()
                except Exception:
                    pass

            self.thread = threading.Thread(target=run_server, daemon=True)
            self.thread.start()
            print(f"[FTP] Server started on {self.primary_ip}:{self.port} -> {self.watch_folder}")
            return True
        except Exception as e:
            print(f"[FTP] Failed to start FTP server on port {self.port}: {e}")
            self.running = False
            return False

    def stop(self):
        self.running = False
        if self.server:
            try:
                self.server.close_all()
            except Exception:
                pass
            self.server = None
        print("[FTP] Server stopped.")

    def update_folder(self, new_folder):
        self.stop()
        self.watch_folder = os.path.abspath(new_folder)
        self.start()


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Pictures")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 2121

    print(f"Starting standalone PhotoBooth FTP Server on port {port}...")
    print(f"Detected IP(s): {', '.join(get_local_ips())}")
    print(f"Save Folder: {folder}")
    print("Credentials: User 'sony', Password 'sony' (or anonymous)")

    srv = PhotoBoothFTPServer(folder, port=port, on_new_photo_callback=lambda f: print(f"-> NEW PHOTO: {f}"))
    if srv.start():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            srv.stop()
