import ctypes, subprocess, time
from ctypes import wintypes
import mss, mss.tools

user32 = ctypes.windll.user32

# 1. Kill any existing instances first
subprocess.run(['taskkill', '/F', '/IM', 'SynthScan.exe'], capture_output=True)
subprocess.run(['taskkill', '/F', '/IM', 'pythonw.exe'], capture_output=True)
time.sleep(1)

# 2. Launch on Default desktop
si = subprocess.STARTUPINFO()
si.lpDesktop = "WinSta0\\Default"
proc = subprocess.Popen(['python', 'native_control.py', '--launch'], startupinfo=si)
print('Launched native_control.py, pid:', proc.pid)
time.sleep(3)

# 3. Attach current thread to Default desktop
hdesk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
print('OpenDesktopW Default handle:', hdesk)
if hdesk:
    user32.SetThreadDesktop(hdesk)

# 4. Enumerate ALL windows on Default desktop
windows = []
def enum_cb(hwnd, lparam):
    pid = wintypes.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    buf_t = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf_t, 512)
    buf_c = ctypes.create_unicode_buffer(512)
    user32.GetClassNameW(hwnd, buf_c, 512)
    vis = bool(user32.IsWindowVisible(hwnd))
    en = bool(user32.IsWindowEnabled(hwnd))
    style = user32.GetWindowLongW(hwnd, -16)
    exstyle = user32.GetWindowLongW(hwnd, -20)
    windows.append({
        'hwnd': hwnd,
        'pid': pid.value,
        'tid': tid,
        'visible': vis,
        'enabled': en,
        'class': buf_c.value,
        'text': buf_t.value,
        'rect': (rect.left, rect.top, rect.right, rect.bottom),
        'style': style,
        'exstyle': exstyle
    })
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)

print(f'Total windows enumerated on Default desktop: {len(windows)}')
for w in windows:
    if w['visible'] and w['rect'][2] > w['rect'][0] and w['rect'][3] > w['rect'][1]:
        print(f"VISIBLE: HWND={w['hwnd']:#x} PID={w['pid']} Class={w['class']} Title='{w['text']}' Rect={w['rect']} Style={w['style']:#x} Enabled={w['enabled']}")

# Capture screenshots
with mss.mss() as sct:
    for i, mon in enumerate(sct.monitors):
        shot = sct.grab(mon)
        mss.tools.to_png(shot.rgb, shot.size, output=f'desktop_test_mon_{i}.png')
print('Screenshots saved to desktop_test_mon_*.png')
