from PIL import ImageGrab
import numpy as np, time

t0 = time.time()
im = ImageGrab.grab()
img = np.array(im)[:, :, :3]
t1 = time.time()

print(f"PIL ImageGrab captured {im.size} in {(t1-t0)*1000:.1f}ms! Shape: {img.shape}")
