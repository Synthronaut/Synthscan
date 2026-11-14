import ctypes
import numpy as np

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

w = user32.GetSystemMetrics(0)
h = user32.GetSystemMetrics(1)
print(f"Primary screen dimensions: {w}x{h}")

hdc_screen = user32.GetDC(0)
hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
gdi32.SelectObject(hdc_mem, hbm)

res = gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020) # SRCCOPY
print("BitBlt result (1 = success):", res)

gdi32.DeleteObject(hbm)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(0, hdc_screen)
