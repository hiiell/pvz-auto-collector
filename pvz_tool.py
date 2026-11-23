"""
Plants vs. Zombies Auto Sun Collector Tool
Main GUI Application with Global Hotkey & Audio Feedback
"""

import sys
import os
import threading
import time
import winsound
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox

from memory_engine import PvZMemoryEngine
from vision_engine import PvZVisionEngine

user32 = ctypes.windll.user32

# Virtual Key codes mapping
VK_MAP = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
}

class PvZAutoCollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PvZ Auto Sun Collector v1.0")
        self.root.geometry("480x440")
        self.root.resizable(False, False)
        
        # Engines
        self.mem_engine = PvZMemoryEngine()
        self.vis_engine = PvZVisionEngine()
        
        # State
        self.is_active = False
        self.current_mode = tk.StringVar(value="memory")
        self.selected_hotkey = tk.StringVar(value="F4")
        self.hotkey_running = True
        
        # UI Setup
        self._setup_style()
        self._create_widgets()
        
        # Start background threads
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self.hotkey_thread.start()
        
        self.monitor_thread = threading.Thread(target=self._process_monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.log("Aplikasi siap. Silakan buka game Plants vs. Zombies.")
        self.check_game_connection()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        self.bg_color = "#1e1e24"
        self.card_bg = "#2b2b36"
        self.fg_color = "#ffffff"
        self.accent_green = "#2ecc71"
        self.accent_red = "#e74c3c"
        self.accent_gold = "#f1c40f"
        
        self.root.configure(bg=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        style.configure("Card.TLabel", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure("TRadiobutton", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))

    def _create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#16a085", height=50)
        header_frame.pack(fill=tk.X)
        header_lbl = tk.Label(header_frame, text="🌻 PLANTS VS. ZOMBIES AUTO-COLLECTOR", bg="#16a085", fg="#ffffff", font=("Segoe UI", 13, "bold"))
        header_lbl.pack(pady=10)

        # Main Container
        container = tk.Frame(self.root, bg=self.bg_color, padx=15, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Connection status bar
        conn_frame = tk.Frame(container, bg=self.card_bg, padx=10, pady=8)
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.conn_dot = tk.Label(conn_frame, text="●", fg=self.accent_red, bg=self.card_bg, font=("Segoe UI", 14, "bold"))
        self.conn_dot.pack(side=tk.LEFT, padx=(0, 5))
        
        self.conn_text = tk.Label(conn_frame, text="Mencari proses PlantsVsZombies.exe...", fg=self.fg_color, bg=self.card_bg, font=("Segoe UI", 10))
        self.conn_text.pack(side=tk.LEFT)

        # Mode Selection
        mode_box = tk.LabelFrame(container, text=" Mode Koleksi ", bg=self.card_bg, fg=self.accent_gold, font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        mode_box.pack(fill=tk.X, pady=(0, 10))
        
        r1 = tk.Radiobutton(mode_box, text="⚡ Mode Memori Instan (Rekomendasi - Cepat & Tanpa Gerak Mouse)",
                            variable=self.current_mode, value="memory", bg=self.card_bg, fg=self.fg_color,
                            selectcolor=self.bg_color, activebackground=self.card_bg, activeforeground=self.fg_color,
                            font=("Segoe UI", 9))
        r1.pack(anchor=tk.W, pady=2)
        
        r2 = tk.Radiobutton(mode_box, text="👁️ Mode Visual Auto-Clicker (OpenCV Screen Detection)",
                            variable=self.current_mode, value="vision", bg=self.card_bg, fg=self.fg_color,
                            selectcolor=self.bg_color, activebackground=self.card_bg, activeforeground=self.fg_color,
                            font=("Segoe UI", 9))
        r2.pack(anchor=tk.W, pady=2)

        # Shortcut Selection & Action
        ctrl_frame = tk.Frame(container, bg=self.card_bg, padx=10, pady=10)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))
        
        hk_lbl = tk.Label(ctrl_frame, text="Tombol Shortcut (Toggle):", bg=self.card_bg, fg=self.fg_color, font=("Segoe UI", 10))
        hk_lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        hk_dropdown = ttk.Combobox(ctrl_frame, textvariable=self.selected_hotkey, values=list(VK_MAP.keys()), width=6, state="readonly", font=("Segoe UI", 10, "bold"))
        hk_dropdown.pack(side=tk.LEFT)

        # Big Status Toggle Button
        self.btn_toggle = tk.Button(container, text="🔴 NONAKTIF (Tekan F4)", bg=self.accent_red, fg="#ffffff",
                                   font=("Segoe UI", 13, "bold"), relief="flat", cursor="hand2", pady=8,
                                   command=self.toggle_active)
        self.btn_toggle.pack(fill=tk.X, pady=(0, 10))

        # Log Window
        log_box = tk.LabelFrame(container, text=" Riwayat Aktivitas ", bg=self.card_bg, fg="#95a5a6", font=("Segoe UI", 9), padx=5, pady=5)
        log_box.pack(fill=tk.BOTH, expand=True)
        
        self.txt_log = tk.Text(log_box, height=5, bg="#121217", fg="#ecf0f1", font=("Consolas", 9), relief="flat", wrap="word")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        """Append a message to the activity log widget."""
        def _do():
            t = time.strftime("[%H:%M:%S] ")
            self.txt_log.insert(tk.END, t + message + "\n")
            self.txt_log.see(tk.END)
        self.root.after(0, _do)

    def check_game_connection(self):
        """Check if PvZ is active and update the indicator."""
        pid, exe = self.mem_engine.find_pvz_process()
        if pid:
            self.conn_dot.config(fg=self.accent_green)
            self.conn_text.config(text=f"Terdeteksi: {exe} (PID: {pid})")
            return True
        else:
            self.conn_dot.config(fg=self.accent_red)
            self.conn_text.config(text="Menunggu game Plants vs. Zombies dijalankan...")
            return False

    def toggle_active(self):
        """Toggle tool on/off with audio feedback."""
        if self.is_active:
            # Turn OFF
            self.is_active = False
            self.mem_engine.disable()
            self.vis_engine.stop()
            self._update_btn_ui()
            self.log("Auto-Collect dimatikan (OFF).")
            # Audio feedback: Low pitch beep
            threading.Thread(target=lambda: winsound.Beep(550, 130), daemon=True).start()
        else:
            # Turn ON
            mode = self.current_mode.get()
            if mode == "memory":
                ok, msg = self.mem_engine.enable()
                if ok:
                    self.is_active = True
                    self._update_btn_ui()
                    self.log(msg)
                    # Audio feedback: High pitch beep
                    threading.Thread(target=lambda: winsound.Beep(1150, 130), daemon=True).start()
                else:
                    self.log(f"Gagal mengaktifkan mode memori: {msg}")
                    threading.Thread(target=lambda: winsound.Beep(350, 200), daemon=True).start()
            else: # vision mode
                ok, msg = self.vis_engine.start()
                if ok:
                    self.is_active = True
                    self._update_btn_ui()
                    self.log(msg)
                    threading.Thread(target=lambda: winsound.Beep(1150, 130), daemon=True).start()
                else:
                    self.log(f"Gagal mengaktifkan mode visual: {msg}")
                    threading.Thread(target=lambda: winsound.Beep(350, 200), daemon=True).start()

    def _update_btn_ui(self):
        hk = self.selected_hotkey.get()
        if self.is_active:
            self.btn_toggle.config(text=f"🟢 AKTIF (Tekan {hk} untuk Matikan)", bg=self.accent_green)
        else:
            self.btn_toggle.config(text=f"🔴 NONAKTIF (Tekan {hk} untuk Nyalakan)", bg=self.accent_red)

    def _hotkey_listener_loop(self):
        """Poll GetAsyncKeyState for the selected hotkey."""
        last_state = False
        while self.hotkey_running:
            hk_name = self.selected_hotkey.get()
            vk = VK_MAP.get(hk_name, 0x73) # default F4
            
            # Check high-order bit
            state = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if state and not last_state:
                # Key pressed (rising edge)
                self.root.after(0, self.toggle_active)
                time.sleep(0.2) # debounce
            last_state = state
            time.sleep(0.04)

    def _process_monitor_loop(self):
        """Periodically check if game is still running."""
        while self.hotkey_running:
            time.sleep(2.0)
            is_running = self.check_game_connection()
            if not is_running and self.is_active:
                # Game was closed while active
                self.root.after(0, self.toggle_active)
                self.log("Game telah ditutup. Auto-collector dinonaktifkan.")

    def on_closing(self):
        """Clean shutdown and revert memory patches."""
        self.hotkey_running = False
        if self.is_active:
            self.mem_engine.disable()
            self.vis_engine.stop()
        self.mem_engine.detach()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PvZAutoCollectorApp(root)
    root.mainloop()
