import sys
from radar_db import parse_signature

test_sigs = [1700, 3400, 5100, 6800, 8500, 2000, 4000, 6000, 8000, 10000, 620, 930, 1240, 1860, 6600, 7700]
for s in test_sigs:
    res = parse_signature(s)
    if res:
        print(f"RS {s:5d} -> {res['title']:<25} | TTS: \"{res['speech']}\"")
    else:
        print(f"RS {s:5d} -> Unknown")
