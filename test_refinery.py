import cv2, numpy as np
from refinery_db import parse_refinery_image, add_haul_record, compute_total_value

# Generate a synthetic refinery terminal screen
h, w = 400, 700
img = np.zeros((h, w, 3), dtype=np.uint8)
img[:] = (20, 25, 30) # Dark sci-fi gray

# Terminal header
cv2.putText(img, "REFINERY WORK ORDER DETAILS // CRU-L1", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2)
cv2.line(img, (30, 70), (670, 70), (0, 229, 255), 1)

# Rows
rows = [
    ("Quantainium", "32.00 SCU", 120),
    ("Bexalite", "14.50 SCU", 180),
    ("Gold", "8.20 SCU", 240),
    ("Laranite", "20.00 SCU", 300)
]

for name, qty, y in rows:
    cv2.putText(img, name, (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, qty, (450, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 230, 118), 2)

test_path = r"C:\Users\Dev\Documents\SynthScan\test_refinery_receipt.png"
cv2.imwrite(test_path, img)

print("Saved synthetic receipt, running parse_refinery_image...")
parsed = parse_refinery_image(test_path)
print("Parsed Ores:", parsed)

inv = add_haul_record(parsed, source="test_receipt")
total_scu, total_auec = compute_total_value(inv["totals"])
print(f"Total Refined: {total_scu} SCU | Est. Market Value: {total_auec:,} aUEC")
