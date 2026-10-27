"""
watcher.py
Monitors a folder for newly captured photos from Sony Imaging Edge.
Ensures file writing is finished before alerting the UI.
"""

import os
import time
import threading

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}


class FolderWatcher:
    def __init__(self, folder_path, on_new_photo_callback, poll_interval=0.5):
        self.folder_path = os.path.abspath(folder_path)
        self.callback = on_new_photo_callback
        self.poll_interval = poll_interval
        self._seen_files = set()
        self._running = False
        self._thread = None

        if os.path.isdir(self.folder_path):
            # Seed seen files with existing files
            self._seen_files = self._get_current_image_files()

    def _get_current_image_files(self):
        if not os.path.isdir(self.folder_path):
            return set()
        found = set()
        try:
            for root, _, files in os.walk(self.folder_path):
                for fname in files:
                    _, ext = os.path.splitext(fname)
                    if ext.lower() in SUPPORTED_EXTENSIONS and not fname.startswith("."):
                        found.add(os.path.join(root, fname))
        except Exception:
            pass
        return found

    def get_recent_photos(self, limit=20):
        """Returns the most recent photos sorted by modification time."""
        files = list(self._get_current_image_files())
        try:
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        except Exception:
            pass
        return files[:limit]

    def _wait_for_file_settled(self, file_path, max_wait=5.0):
        """
        Ensures camera tethering has finished writing the image to disk.
        Waits until file size stops growing.
        """
        start_time = time.time()
        last_size = -1
        while time.time() - start_time < max_wait:
            try:
                if not os.path.exists(file_path):
                    return False
                current_size = os.path.getsize(file_path)
                if current_size > 0 and current_size == last_size:
                    # Size is stable
                    return True
                last_size = current_size
            except Exception:
                pass
            time.sleep(0.3)
        return True

    def _watch_loop(self):
        while self._running:
            if os.path.isdir(self.folder_path):
                current_files = self._get_current_image_files()
                new_files = current_files - self._seen_files
                if new_files:
                    # Sort new files by mtime so we process in capture order
                    sorted_new = sorted(new_files, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
                    for f in sorted_new:
                        if not self._running:
                            break
                        if self._wait_for_file_settled(f):
                            self._seen_files.add(f)
                            if self.callback:
                                self.callback(f)
            time.sleep(self.poll_interval)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def update_folder(self, new_folder):
        self.stop()
        self.folder_path = os.path.abspath(new_folder)
        self._seen_files = self._get_current_image_files()
        self.start()

