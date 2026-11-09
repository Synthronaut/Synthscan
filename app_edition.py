"""Installed capability boundary. No environment override or preference toggle."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def edition(root=ROOT):
    path=Path(root)/'release.json'
    if not path.exists():return 'full' # Development and legacy full builds.
    data=json.loads(path.read_text(encoding='utf-8'))
    value=data.get('edition','full')
    if value not in ('standard','full'):raise ValueError('Invalid application edition')
    return value

def screen_reading():return edition()=='full'

def require_screen_reading():
    if not screen_reading():raise PermissionError('Screen reading is not installed in SynthScan Standard. Install Full explicitly to add it.')
