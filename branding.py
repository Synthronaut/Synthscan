"""The window icon used by explicit auxiliary desktop tools."""
from pathlib import Path


def window_icon(root):
    icon=Path(__file__).resolve().parent/'assets/branding/SynthScan-Blue.ico'
    if icon.exists():
        try:root.iconbitmap(str(icon))
        except Exception:pass  # Non-Windows test environments may not support ICO.
