import mss, numpy as np, time

sct = mss.mss()
mon = sct.monitors[1] # Primary monitor
t0 = time.time()
img = np.array(sct.grab(mon))[:, :, :3]
t1 = time.time()

print(f"Captured {mon['width']}x{mon['height']} in {(t1-t0)*1000:.1f}ms! Shape: {img.shape}")
