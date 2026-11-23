"""
Plants vs. Zombies Memory Engine
Handles process attachment, signature verification, and memory patching for auto-collecting sun/coins.
Compatible with GOTY 1.2.0.1073 and other releases via pattern scanning.
"""

import ctypes
from ctypes import wintypes
import time

PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

PAGE_EXECUTE_READWRITE = 0x40

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

class PvZMemoryEngine:
    def __init__(self):
        self.pid = None
        self.hProcess = None
        self.target_address = None
        self.original_byte = b"\x75" # jne
        self.patch_byte = b"\xEB"    # jmp
        self.is_patched = False
        
    def find_pvz_process(self):
        """Find PvZ process ID by checking common executable names."""
        import subprocess
        # Common image names for PvZ
        candidates = ["PlantsVsZombies.exe", "popcapgame1.exe", "Plants vs Zombies.exe"]
        for exe in candidates:
            try:
                cmd = f'tasklist /FI "IMAGENAME eq {exe}" /FO CSV /NH'
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
                for line in out.strip().splitlines():
                    parts = [p.strip(' "') for p in line.split('","')]
                    if len(parts) >= 2 and parts[0].lower() == exe.lower():
                        return int(parts[1]), parts[0]
            except Exception:
                pass
        return None, None

    def attach(self):
        """Attach to the running PvZ process and locate the auto-collect patch address."""
        self.detach()
        pid, exe_name = self.find_pvz_process()
        if not pid:
            return False, "Proses Plants vs. Zombies tidak ditemukan. Pastikan game sudah berjalan."

        self.pid = pid
        self.hProcess = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.hProcess:
            return False, f"Gagal membuka proses (PID: {self.pid}). Error code: {ctypes.GetLastError()}"

        # Locate target address
        # Check standard address for GOTY 1.2.0.1073: 0x004342F2
        test_addr = 0x004342F2
        buf = (ctypes.c_char * 2)()
        bytesRead = ctypes.c_size_t()
        
        if kernel32.ReadProcessMemory(self.hProcess, ctypes.c_void_p(test_addr), buf, 2, ctypes.byref(bytesRead)):
            b = bytes(buf)
            # Normal GOTY instruction at 0x4342EE is: 80 7B 50 00 [75 09] or [EB 09]
            if b in (b"\x75\x09", b"\xEB\x09"):
                self.target_address = test_addr
                self.is_patched = (b[0:1] == self.patch_byte)
                return True, f"Terhubung ke {exe_name} (PID: {self.pid}) pada 0x{self.target_address:X}!"

        # Fallback: AOB Scan for 80 7B 50 00 75
        found_addr = self._scan_pattern(b"\x80\x7b\x50\x00\x75")
        if found_addr:
            self.target_address = found_addr + 4
            self.is_patched = False
            return True, f"Terhubung ke {exe_name} via AOB Scan pada 0x{self.target_address:X}!"

        return False, "Proses ditemukan, namun tanda tangan kode auto-collect tidak cocok."

    def _scan_pattern(self, pattern):
        """Scan memory space of 0x00400000 - 0x00800000 for pattern."""
        size = 0x400000
        buff = (ctypes.c_char * size)()
        bytesRead = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self.hProcess, ctypes.c_void_p(0x00400000), buff, size, ctypes.byref(bytesRead)):
            data = bytes(buff[:bytesRead.value])
            idx = data.find(pattern)
            if idx != -1:
                return 0x00400000 + idx
        return None

    def enable(self):
        """Enable auto-collect by patching conditional jump to unconditional jump."""
        if not self.hProcess or not self.target_address:
            ok, msg = self.attach()
            if not ok:
                return False, msg

        old_protect = wintypes.DWORD()
        # Make page writable
        if not kernel32.VirtualProtectEx(self.hProcess, ctypes.c_void_p(self.target_address), 1, PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)):
            return False, f"VirtualProtectEx failed: {ctypes.GetLastError()}"

        bytesWritten = ctypes.c_size_t()
        buf = ctypes.c_char(self.patch_byte[0])
        write_ok = kernel32.WriteProcessMemory(self.hProcess, ctypes.c_void_p(self.target_address), ctypes.byref(buf), 1, ctypes.byref(bytesWritten))
        
        # Restore old protection
        kernel32.VirtualProtectEx(self.hProcess, ctypes.c_void_p(self.target_address), 1, old_protect.value, ctypes.byref(old_protect))

        if write_ok:
            self.is_patched = True
            return True, "Auto-Collect AKTIF (Mode Memori Instan)!"
        else:
            return False, f"WriteProcessMemory failed: {ctypes.GetLastError()}"

    def disable(self):
        """Disable auto-collect by restoring original byte."""
        if not self.hProcess or not self.target_address:
            return True, "Sudah nonaktif."

        old_protect = wintypes.DWORD()
        if not kernel32.VirtualProtectEx(self.hProcess, ctypes.c_void_p(self.target_address), 1, PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)):
            return False, f"VirtualProtectEx failed: {ctypes.GetLastError()}"

        bytesWritten = ctypes.c_size_t()
        buf = ctypes.c_char(self.original_byte[0])
        write_ok = kernel32.WriteProcessMemory(self.hProcess, ctypes.c_void_p(self.target_address), ctypes.byref(buf), 1, ctypes.byref(bytesWritten))

        kernel32.VirtualProtectEx(self.hProcess, ctypes.c_void_p(self.target_address), 1, old_protect.value, ctypes.byref(old_protect))

        if write_ok:
            self.is_patched = False
            return True, "Auto-Collect NONAKTIF (Koleksi Manual Normal)."
        else:
            return False, f"WriteProcessMemory failed: {ctypes.GetLastError()}"

    def is_game_running(self):
        """Check if attached game process is still alive."""
        if not self.hProcess:
            return False
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(self.hProcess, ctypes.byref(exit_code)):
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        return False

    def detach(self):
        """Safely restore original bytes and close handle."""
        if self.is_patched and self.hProcess and self.is_game_running():
            self.disable()
        if self.hProcess:
            kernel32.CloseHandle(self.hProcess)
            self.hProcess = None
        self.pid = None
        self.target_address = None
        self.is_patched = False
