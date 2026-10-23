"""Exercise the packaged OCR stack with its own C++ runtime loaded first."""
import argparse
from pathlib import Path
import subprocess


def verify(payload):
    payload = Path(payload).resolve()
    script = r'''
import ctypes, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
handles = [ctypes.WinDLL(str(root / 'runtime' / name)) for name in
           ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll')]
for handle in handles:
    path = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetModuleFileNameW(ctypes.c_void_p(handle._handle), path, len(path))
    assert pathlib.Path(path.value).resolve().is_relative_to(root), path.value
import tkinter, cv2, grpc, onnxruntime, numpy, shapely, resvg_py
from textline_ocr import TextLineRecognizer
text, confidence = TextLineRecognizer().read(numpy.zeros((48, 160, 3), dtype=numpy.uint8))
assert isinstance(text, str) and 0 <= confidence <= 1
print('Bundled C++ runtime, UI dependencies, RPC and OCR inference passed')
'''
    subprocess.run([str(payload / 'runtime/python.exe'), '-I', '-B', '-c', script,
                    str(payload)], cwd=payload, check=True, timeout=90)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', required=True)
    verify(parser.parse_args().payload)
