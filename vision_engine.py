"""
Plants vs. Zombies Vision Engine
Detects sun on the game screen using computer vision (MSS + OpenCV)
and simulates mouse clicks to collect them.
"""

import threading
import time
import ctypes
from ctypes import wintypes
import numpy as np
import cv2
import mss

user32 = ctypes.windll.user32

# Mouse events
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

class PvZVisionEngine:
    def __init__(self):
        self.running = False
        self.thread = None
        self.hwnd = None
        
    def find_pvz_window(self):
        """Find the Plants vs. Zombies window handle by title or process ID."""
        import subprocess
        target_pid = None
        for exe in ["PlantsVsZombies.exe", "popcapgame1.exe"]:
            try:
                cmd = f'tasklist /FI "IMAGENAME eq {exe}" /FO CSV /NH'
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
                for line in out.strip().splitlines():
                    parts = [p.strip(' "') for p in line.split('","')]
                    if len(parts) >= 2 and parts[0].lower() == exe.lower():
                        target_pid = int(parts[1])
                        break
            except Exception:
                pass
            if target_pid:
                break

        found_hwnds = []
        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                # Check PID match
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if target_pid and pid.value == target_pid:
                    found_hwnds.append(hwnd)
                    return True
                
                # Check title match
                buff = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buff, 512)
                title = buff.value.lower()
                if "plants vs" in title or "plants vs." in title or "plantsvszombies" in title:
                    found_hwnds.append(hwnd)
            return True
            
        cb_func = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(enum_cb)
        user32.EnumWindows(cb_func, 0)
        
        if found_hwnds:
            return found_hwnds[0]
            
        # Try direct FindWindow
        h = user32.FindWindowW(None, "Plants vs. Zombies")
        if h:
            return h
        return None

    def get_window_client_rect(self, hwnd):
        """Get the client area rectangle in screen coordinates."""
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        
        if width <= 0 or height <= 0:
            return None
            
        return {
            "top": pt.y,
            "left": pt.x,
            "width": width,
            "height": height
        }

    def click_at(self, screen_x, screen_y):
        """Simulate a left click at the given screen coordinates and restore cursor."""
        # Save current cursor position
        orig_pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(orig_pt))
        
        # Move and click
        user32.SetCursorPos(screen_x, screen_y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        # Restore cursor
        user32.SetCursorPos(orig_pt.x, orig_pt.y)

    def start(self):
        """Start the vision loop in a background thread."""
        if self.running:
            return True, "Vision Engine sudah berjalan."
            
        self.hwnd = self.find_pvz_window()
        if not self.hwnd:
            return False, "Jendela Plants vs. Zombies tidak ditemukan atau terminimalkan."
            
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True, "Auto-Collect AKTIF (Mode Visual Auto-Clicker)!"

    def stop(self):
        """Stop the vision loop."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None
        return True, "Auto-Collect NONAKTIF (Mode Visual Dihentikan)."

    def _run_loop(self):
        """Background thread detecting suns and clicking."""
        # Yellow sun HSV range in PvZ
        # PvZ sun is bright golden yellow with orange/white core
        lower_yellow = np.array([18, 120, 200], dtype=np.uint8)
        upper_yellow = np.array([35, 255, 255], dtype=np.uint8)

        with mss.mss() as sct:
            while self.running:
                if not user32.IsWindow(self.hwnd):
                    self.hwnd = self.find_pvz_window()
                    if not self.hwnd:
                        time.sleep(1.0)
                        continue

                bbox = self.get_window_client_rect(self.hwnd)
                if not bbox or bbox["width"] < 100 or bbox["height"] < 100:
                    time.sleep(0.2)
                    continue

                try:
                    img = np.array(sct.grab(bbox))
                    hsv = cv2.cvtColor(img, cv2.COLOR_BGRA2HSV)
                    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
                    
                    # Morphological cleanup
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

                    # Find contours
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    suns_found = []
                    for c in contours:
                        area = cv2.contourArea(c)
                        # Sun radius in PvZ GOTY (800x600) is approx 25-45px, area ~ 400 - 3000
                        if 300 < area < 4000:
                            perimeter = cv2.arcLength(c, True)
                            if perimeter > 0:
                                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                                if circularity > 0.45:
                                    # Get center
                                    M = cv2.moments(c)
                                    if M["m00"] != 0:
                                        cx = int(M["m10"] / M["m00"])
                                        cy = int(M["m01"] / M["m00"])
                                        # Filter out UI top-left sun counter (roughly x < 120 and y < 90)
                                        if cx > 100 or cy > 90:
                                            suns_found.append((cx, cy))

                    for (cx, cy) in suns_found:
                        if not self.running:
                            break
                        abs_x = bbox["left"] + cx
                        abs_y = bbox["top"] + cy
                        self.click_at(abs_x, abs_y)
                        time.sleep(0.04)

                except Exception:
                    pass

                time.sleep(0.12)
