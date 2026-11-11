"""Rapid session recovery for Star Citizen.

Cleanly terminates StarCitizen.exe and any hung EasyAntiCheat processes,
brings RSI Launcher into focus for authenticated relaunch,
and facilitates rejoining the same shard via Game.log frontend detection.
"""
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import subprocess
import threading
import time

LOG = logging.getLogger(__name__)

# Target process names to cleanly sweep
TARGET_PROCESSES = [
    "starcitizen.exe",
    "easyanticheat_eos.exe",
    "easyanticheat.exe",
    "easyanticheat_eos_setup.exe",
    "starcitizen_launcher.exe"
]

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def read_game_memory(pids=None):
    """Read committed memory and working set in GB directly via Windows kernel.
    
    Zero injection, zero screen reading, executes in ~0.002 ms.
    """
    if not pids:
        from app_lifecycle import game_process_ids
        pids = game_process_ids()
    if not pids:
        return None

    k32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi

    for pid in pids:
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            try:
                pmc = PROCESS_MEMORY_COUNTERS_EX()
                pmc.cb = ctypes.sizeof(pmc)
                if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                    return {
                        'commit_gb': pmc.PrivateUsage / (1024**3),
                        'working_set_gb': pmc.WorkingSetSize / (1024**3)
                    }
            finally:
                k32.CloseHandle(h)
    return None

def terminate_sc_and_eac():
    """Cleanly and decisively terminate Star Citizen and lingering EAC instances.

    Requests graceful shutdown first via WM_CLOSE so Star Citizen can save its
    in-memory Vulkan pipeline/shader cache and exit cleanly with code 0.
    This prevents RSI Launcher from displaying 'Star Citizen has stopped running unexpectedly'
    and prevents lost shader caches. Falls back to forceful termination if hung.
    """
    LOG.info("Initiating graceful Star Citizen shutdown...")
    from app_lifecycle import game_process_ids
    user32 = ctypes.windll.user32

    # Step 1: Request graceful shutdown via WM_CLOSE to game window
    sc_hwnd = user32.FindWindowW("CryENGINE", None) or user32.FindWindowW(None, "Star Citizen ")
    if sc_hwnd:
        LOG.info(f"Posting WM_CLOSE to Star Citizen window {sc_hwnd:#x}")
        user32.PostMessageW(sc_hwnd, 0x0010, 0, 0)  # WM_CLOSE

    # Also send graceful taskkill (without /F) which broadcasts WM_CLOSE to process windows
    subprocess.run(["taskkill", "/IM", "starcitizen.exe"], capture_output=True, text=True)

    # Allow up to 3.5 seconds for clean exit and shader cache flush
    for _ in range(18):
        if not game_process_ids():
            LOG.info("Star Citizen exited gracefully.")
            break
        time.sleep(0.2)

    # Step 2: If still running (hung/frozen), terminate forcefully
    pids = game_process_ids()
    if pids:
        LOG.warning("Star Citizen did not exit within grace period, terminating forcefully...")
        subprocess.run(["taskkill", "/F", "/T", "/IM", "starcitizen.exe"], capture_output=True, text=True)

    # Sweep lingering EAC helper processes
    for proc_name in ["easyanticheat_eos.exe", "easyanticheat.exe", "easyanticheat_eos_setup.exe", "starcitizen_launcher.exe"]:
        subprocess.run(["taskkill", "/F", "/T", "/IM", proc_name], capture_output=True, text=True)

    # Allow Windows up to 2 seconds to release kernel handles
    for _ in range(10):
        if not game_process_ids():
            break
        time.sleep(0.2)

def focus_rsi_launcher():
    """Restore and bring RSI Launcher to the foreground for authenticated relaunch,
    and dismiss any unexpected crash dialog.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
    if hdesk:
        user32.SetThreadDesktop(hdesk)

    found = []
    def cb(hwnd, lp):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value == 'RSI Launcher':
            found.append(hwnd)
        return 1

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    if hdesk:
        user32.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)

    target_hwnd = found[0] if found else None

    if not target_hwnd:
        # If minimized/hidden or not found on desktop enum, run RSI Launcher to trigger second-instance
        rsi_launcher = Path(r"C:\Program Files\Roberts Space Industries\RSI Launcher\RSI Launcher.exe")
        if rsi_launcher.is_file():
            LOG.info("Focusing RSI Launcher via executable...")
            subprocess.Popen([str(rsi_launcher)], cwd=str(rsi_launcher.parent))
            time.sleep(1.0)
            if hdesk:
                user32.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)
            target_hwnd = found[0] if found else None

    if target_hwnd:
        my_tid = kernel32.GetCurrentThreadId()
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
        target_tid = user32.GetWindowThreadProcessId(target_hwnd, None)

        if fg_tid and fg_tid != my_tid:
            user32.AttachThreadInput(my_tid, fg_tid, True)
        if target_tid and target_tid != my_tid:
            user32.AttachThreadInput(my_tid, target_tid, True)

        try:
            user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(target_hwnd)
            user32.SetForegroundWindow(target_hwnd)
        finally:
            if fg_tid and fg_tid != my_tid:
                user32.AttachThreadInput(my_tid, fg_tid, False)
            if target_tid and target_tid != my_tid:
                user32.AttachThreadInput(my_tid, target_tid, False)

        # Wait briefly for window focus to take effect
        time.sleep(0.3)

        # DISMISS ERROR MODAL:
        # If 'Star Citizen has stopped running unexpectedly' modal is active,
        # Escape dismisses the modal (calling Cancel / onOpenChange(false))
        # without triggering the Verify button.
        LOG.info("Dismissing any crash error modal in RSI Launcher...")
        user32.keybd_event(0x1B, 0, 0, 0)  # VK_ESCAPE down
        time.sleep(0.05)
        user32.keybd_event(0x1B, 0, 2, 0)  # VK_ESCAPE up
        time.sleep(0.2)
        user32.keybd_event(0x1B, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(0x1B, 0, 2, 0)

    return bool(target_hwnd)

def relaunch_game(game_dir=None):
    """Brings RSI Launcher to the foreground so the authenticated game token flow is preserved."""
    return focus_rsi_launcher()

def auto_rejoin_watcher(game_log_path=None, stop_event=None, callback=None):
    """Monitors Game.log for frontend readiness, focuses window, and triggers rejoin."""
    from installation import game_directory
    if not game_log_path:
        game_log_path = Path(game_directory(required=False)) / "Game.log"

    LOG.info("Auto-rejoin watcher waiting for game process...")
    
    # Wait for new game process to appear (user clicking LAUNCH GAME in RSI Launcher)
    game_pid = None
    for _ in range(240):  # Wait up to 120s for process
        if stop_event and stop_event.is_set():
            return
        from app_lifecycle import game_process_ids
        pids = game_process_ids()
        if pids:
            game_pid = next(iter(pids))
            break
        time.sleep(0.5)

    if not game_pid:
        LOG.warning("Game process did not appear within timeout.")
        return

    if callback:
        callback("LOADING GAME...")

    # Watch Game.log until Frontend is loaded
    frontend_ready = False
    for _ in range(360):  # Wait up to 180s for frontend
        if stop_event and stop_event.is_set():
            return
        if game_log_path.is_file():
            try:
                with open(game_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(max(0, os.path.getsize(game_log_path) - 10000))
                    content = f.read()
                    if 'RequestFrontEnd' in content or 'SC_Frontend' in content:
                        frontend_ready = True
                        break
            except Exception:
                pass
        time.sleep(0.5)

    if frontend_ready:
        if callback:
            callback("REJOINING...")
        LOG.info("Main menu detected. Bringing Star Citizen to focus...")
        time.sleep(2.0)  # Brief grace period for UI animation
        user32 = ctypes.windll.user32
        
        # Find window by class/title
        hwnd = user32.FindWindowW("CryENGINE", None) or user32.FindWindowW(None, "Star Citizen")
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            # Send Spacebar (VK_SPACE = 0x20) to trigger primary card (Recovery/Enter PU)
            user32.keybd_event(0x20, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x20, 0, 2, 0)
            LOG.info("Auto-rejoin trigger key delivered.")

def execute_recovery_async(callback=None):
    """Run full recovery sequence in a background worker."""
    def worker():
        try:
            if callback:
                callback("CLOSING GAME...")
            terminate_sc_and_eac()
            time.sleep(0.5)
            if callback:
                callback("RESTORING LAUNCHER...")
            focus_rsi_launcher()
            if callback:
                callback("CLICK LAUNCH IN RSI")
            auto_rejoin_watcher(callback=callback)
            if callback:
                callback(None)  # Reset to idle
        except Exception as e:
            LOG.error(f"Recovery failed: {e}")
            if callback:
                callback(None)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
