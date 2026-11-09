"""Release edition checks shared by packaging and signed-update validation."""
from pathlib import PurePosixPath
EDITIONS={'standard','full'}
CAPTURE_FILES={'main.py','detector.py','capture_privacy.py','window_telemetry_capture.py','displayinfo_reader.py','validated_displayinfo.py','screen_readers.py','textline_ocr.py','bedrock_textline.py','native_mining.py','telemetry_hud.py','blueprint_library_ui.py','probe_window_capture.py','SynthGameCapture.cpp','DxgiCapture.cpp','glyphs.bin','glyphs_mfd.bin','probe_displayinfo_pulse.py','test_displayinfo_keyboard.py'}
CAPTURE_PACKAGES={'windows_capture','mss','rapidocr_onnxruntime','onnxruntime','PIL','pyautogui','pyscreeze'}

def validate_edition(value):
    if value not in EDITIONS:raise ValueError('Unknown application edition')
    return value

def forbidden_standard_path(relative):
    path=PurePosixPath(str(relative).replace('\\','/'));parts=path.parts
    return ((path.name in CAPTURE_FILES and parts[0]!='runtime') or path.suffix.lower() in ('.onnx','.ort','.pt','.pth') and path.name!='python314._pth'
            or any(p in CAPTURE_PACKAGES or any(p.lower().startswith(name.lower()+'-') and p.endswith('.dist-info') for name in CAPTURE_PACKAGES) for p in parts)
            or 'mining_worker' in parts or any('mining_worker' in p.lower() for p in parts)
            or (parts and parts[0] in ('tools','tests','native','third_party') and ('ocr' in path.name.lower() or 'capture' in path.name.lower()) and path.name not in ('StandardCapture.cpp','ScreenCapture.cpp','ScreenCapture.h','SynthCapturePrivacy.h','SynthGameCapture.h','DxgiCapture.h')))

def check_update_edition(installed,manifest):
    current=validate_edition(installed.get('edition','full'));candidate=validate_edition(manifest.get('edition','full'))
    if current!=candidate:raise ValueError('Automatic updates cannot change the installed edition. Install the other edition explicitly.')
    return current
