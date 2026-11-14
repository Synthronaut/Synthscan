import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
desk = user32.OpenInputDesktop(0, False, 0x01ff)
user32.SetThreadDesktop(desk)

def inspect_window_tree(hwnd, indent=0):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    title = buf.value
    user32.GetClassNameW(hwnd, buf, 512)
    cls = buf.value
    vis = user32.IsWindowVisible(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    crect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    style = user32.GetWindowLongW(hwnd, -16)
    ex_style = user32.GetWindowLongW(hwnd, -20)
    print(f"{'  '*indent}HWND {hex(hwnd)} Vis:{vis} Rect:({rect.left},{rect.top},{rect.right-rect.left}x{rect.bottom-rect.top}) Client:({crect.right}x{crect.bottom}) Style:{hex(style)} Ex:{hex(ex_style)} Class:'{cls}' Title:'{title}'")

    child = user32.GetWindow(hwnd, 5) # GW_CHILD
    while child:
        inspect_window_tree(child, indent + 1)
        child = user32.GetWindow(child, 2) # GW_HWNDNEXT

print("=== MinerGUI (0xc90098) Tree ===")
inspect_window_tree(0xc90098)

print("\n=== SynthScanHome (0x1ad05e0) Tree ===")
inspect_window_tree(0x1ad05e0)
