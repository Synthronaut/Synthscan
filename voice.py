"""
SynthScan - Star Citizen Ship Computer Neural Voice Engine
Features:
- Neural TTS powered by Microsoft Edge Neural Voices (Origin Jumpworks British Luxury Female AI by default)
- Custom Sci-Fi Cockpit DSP Filter (subtle holographic micro-chorus, presence EQ, and Origin harmonic chime)
- Instant WAV disk caching for zero-latency repeated radar callouts
- Graceful offline SAPI fallback (auto-selecting female voice)
"""

import os
import io
import wave
import hashlib
import asyncio
import ctypes
from ctypes import wintypes
import threading
import queue
import time
import subprocess
import winsound
import numpy as np
from scipy import signal

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_char * 260)
    ]

_sc_running_cache = False
_sc_running_last_check = 0.0

def is_star_citizen_running() -> bool:
    """
    Returns True ONLY if StarCitizen.exe is actually running.
    Prevents false triggers from the RSI Launcher, browser tabs, or desktop.
    Microsecond cached for 0.5s for zero CPU overhead.
    """
    global _sc_running_cache, _sc_running_last_check
    now = time.time()
    if (now - _sc_running_last_check) < 0.5:
        return _sc_running_cache
    _sc_running_last_check = now

    # 1. Quick check for CryENGINE window class (Star Citizen client engine)
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.FindWindowW("CryENGINE", None)
        if hwnd:
            _sc_running_cache = True
            return True
    except Exception:
        pass

    # 2. Check for StarCitizen.exe process (immune to RSI Launcher false positives)
    try:
        h_snap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if h_snap == -1:
            _sc_running_cache = False
            return False
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        found = False
        if ctypes.windll.kernel32.Process32First(h_snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.lower() == b"starcitizen.exe":
                    found = True
                    break
                if not ctypes.windll.kernel32.Process32Next(h_snap, ctypes.byref(entry)):
                    break
        ctypes.windll.kernel32.CloseHandle(h_snap)
        _sc_running_cache = found
        return found
    except Exception:
        _sc_running_cache = False
        return False

try:
    import edge_tts
    import miniaudio
    HAS_NEURAL_TTS = True
except ImportError:
    HAS_NEURAL_TTS = False

from installation import PROFILE,RELEASE
CACHE_DIR = str(PROFILE/'voice_cache') if RELEASE else os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Star Citizen Ship Manufacturer Voice Profiles
SHIP_VOICE_PROFILES = {
    "origin": {
        "label": "ORIGIN JUMPWORKS // LUXURY CONCIERGE (Sonia - UK Female)",
        "voice": "en-GB-SoniaNeural",
        "pitch_hz": 3,
        "base_rate_pct": 6,
        "chime_freqs": (1318.5, 1975.5),  # E6 -> B6 warm luxury crystal fifth
        "chorus_wet": 0.16,
        "highpass_hz": 110
    },
    "aegis": {
        "label": "AEGIS DYNAMICS // TACTICAL COMBAT AI (Libby - UK Female)",
        "voice": "en-GB-LibbyNeural",
        "pitch_hz": 0,
        "base_rate_pct": 10,
        "chime_freqs": (1760.0, 2217.5),  # A6 -> C#7 sharp tactical telemetry ping
        "chorus_wet": 0.22,
        "highpass_hz": 160
    },
    "anvil": {
        "label": "ANVIL AEROSPACE // UEE FLIGHT COMPUTER (Aria - US Female)",
        "voice": "en-US-AriaNeural",
        "pitch_hz": -2,
        "base_rate_pct": 8,
        "chime_freqs": (1046.5, 1568.0),  # C6 -> G6 military flight computer tone
        "chorus_wet": 0.18,
        "highpass_hz": 140
    },
    "crusader": {
        "label": "CRUSADER INDUSTRIES // TRANSPORT AI (Natasha - AU Female)",
        "voice": "en-AU-NatashaNeural",
        "pitch_hz": 2,
        "base_rate_pct": 5,
        "chime_freqs": (1174.7, 1760.0),  # D6 -> A6 gentle atmospheric chime
        "chorus_wet": 0.14,
        "highpass_hz": 110
    }
}


class VoiceEngine:
    def __init__(self, enabled=True, volume=100, rate=1, profile="origin", chime_enabled=True):
        self.enabled = bool(enabled)
        self.volume = max(0, min(100, int(volume)))
        self.rate = max(-5, min(5, int(rate)))
        self.profile = profile if profile in SHIP_VOICE_PROFILES else "origin"
        self.chime_enabled = bool(chime_enabled)

        self.queue = queue.Queue(maxsize=4)
        self.last_spoken = ""
        self.last_spoken_time = 0
        self.last_category_time = {}
        self.running = True

        self.worker = threading.Thread(target=self._run_queue, daemon=True)
        self.worker.start()

    def speak(self, text, cooldown=3.0, allow_when_game_closed=False, category=None):
        if not self.enabled or not text or self.volume <= 0:
            return
        if not allow_when_game_closed and not is_star_citizen_running():
            return
        now = time.time()
        if category:
            if (now - self.last_category_time.get(category, 0.0)) < cooldown:
                return
            self.last_category_time[category] = now
        elif text == self.last_spoken and (now - self.last_spoken_time) < cooldown:
            return

        self.last_spoken = text
        self.last_spoken_time = now

        try:
            self.queue.put_nowait((text, allow_when_game_closed))
        except queue.Full:
            pass

    def _get_cache_path(self, text):
        p_info = SHIP_VOICE_PROFILES.get(self.profile, SHIP_VOICE_PROFILES["origin"])
        key_str = f"v2|{self.profile}|{p_info['voice']}|r{self.rate}|c{int(self.chime_enabled)}|{text.strip().lower()}"
        digest = hashlib.md5(key_str.encode("utf-8")).hexdigest()[:16]
        return os.path.join(CACHE_DIR, f"{self.profile}_{digest}.wav")

    def _synthesize_chime(self, sample_rate, freqs):
        """
        Generates a sleek, luxury Star Citizen cockpit telemetry pre-chime.
        Two-note overlapping harmonic shimmer with exponential decay.
        """
        dur1 = 0.065
        dur2 = 0.140
        total_len = int(sample_rate * (dur1 + dur2 + 0.03))
        out = np.zeros(total_len, dtype=np.float32)

        f1, f2 = freqs
        # Note 1 (Gentle luxury whisper chime)
        t1 = np.linspace(0, dur1, int(sample_rate * dur1), endpoint=False)
        env1 = np.sin(np.pi * (t1 / dur1) ** 0.5) * np.exp(-t1 * 18.0)
        tone1 = (np.sin(2 * np.pi * f1 * t1) + 0.35 * np.sin(2 * np.pi * (f1 * 2) * t1)) * env1 * 0.11
        out[:len(tone1)] += tone1

        # Note 2 (overlapping slightly)
        start2 = int(sample_rate * 0.045)
        t2 = np.linspace(0, dur2, int(sample_rate * dur2), endpoint=False)
        env2 = (1.0 - np.exp(-t2 * 90.0)) * np.exp(-t2 * 16.0)
        tone2 = (np.sin(2 * np.pi * f2 * t2) + 0.4 * np.sin(2 * np.pi * (f2 * 1.5) * t2)) * env2 * 0.13
        end2 = min(total_len, start2 + len(tone2))
        out[start2:end2] += tone2[:end2 - start2]

        return out

    def _apply_ship_computer_dsp(self, samples_f32, sample_rate, profile_cfg):
        """
        Applies Star Citizen Origin/Ship AI DSP to raw float32 mono speech:
        1. High-pass filter to clean low rumble
        2. Presence peak boost around 3.2 kHz for crisp cockpit articulation
        3. Subtle holographic dual-delay micro-chorus (gives that unmistakable sci-fi AI sheen)
        4. Prepends luxury harmonic cockpit chime (if enabled)
        """
        nyq = sample_rate * 0.5

        # 1. High-pass filter
        hp_cutoff = min(0.4, max(0.01, profile_cfg.get("highpass_hz", 110) / nyq))
        b_hp, a_hp = signal.butter(2, hp_cutoff, btype="highpass")
        y = signal.lfilter(b_hp, a_hp, samples_f32)

        # 2. Crisp Air / Presence Shelf (boost 2.8kHz - 6.5kHz slightly)
        low_b = min(0.85, 2800.0 / nyq)
        high_b = min(0.95, 6500.0 / nyq)
        if low_b < high_b:
            b_bp, a_bp = signal.butter(2, [low_b, high_b], btype="bandpass")
            presence = signal.lfilter(b_bp, a_bp, y)
            y = y + 0.28 * presence

        # 3. Holographic Ship AI Micro-Chorus (11ms & 19ms subtle reflections)
        wet = profile_cfg.get("chorus_wet", 0.16)
        d1 = int(sample_rate * 0.011)
        d2 = int(sample_rate * 0.019)
        chorus = np.zeros_like(y)
        if len(y) > d2:
            chorus[d1:] += y[:-d1] * 0.65
            chorus[d2:] += y[:-d2] * 0.35
        y = (1.0 - wet * 0.5) * y + wet * chorus

        # Normalize speech peak to 0.70 (whisper headroom, lowered by 20%)
        peak = np.max(np.abs(y))
        if peak > 1e-4:
            y = (y / peak) * 0.70

        # 4. Prepend Ship Telemetry Chime if enabled
        if self.chime_enabled:
            chime = self._synthesize_chime(sample_rate, profile_cfg["chime_freqs"])
            y = np.concatenate([chime, y])

        return y

    async def _fetch_neural_mp3_bytes(self, text, voice_name, rate_str, pitch_str):
        communicate = edge_tts.Communicate(text, voice_name, rate=rate_str, pitch=pitch_str)
        mp3_buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_buf.write(chunk["data"])
        return mp3_buf.getvalue()

    def _ensure_cached_wav(self, text):
        cache_path = self._get_cache_path(text)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 200:
            return cache_path

        if not HAS_NEURAL_TTS:
            return None

        p_cfg = SHIP_VOICE_PROFILES.get(self.profile, SHIP_VOICE_PROFILES["origin"])
        voice_name = p_cfg["voice"]
        rate_pct = p_cfg["base_rate_pct"] + (self.rate * 6)
        rate_str = f"{rate_pct:+d}%"
        pitch_str = f"{p_cfg['pitch_hz']:+d}Hz"

        mp3_bytes = asyncio.run(self._fetch_neural_mp3_bytes(text, voice_name, rate_str, pitch_str))
        if not mp3_bytes:
            return None

        decoded = miniaudio.decode(mp3_bytes, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=24000)
        samples_i16 = np.frombuffer(decoded.samples, dtype=np.int16)
        samples_f32 = samples_i16.astype(np.float32) / 32768.0

        processed = self._apply_ship_computer_dsp(samples_f32, 24000, p_cfg)
        out_i16 = np.clip(processed * 32767.0, -32768, 32767).astype(np.int16)

        with wave.open(cache_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(out_i16.tobytes())

        return cache_path

    def _play_wav_scaled(self, wav_path):
        if self.volume <= 0:
            return

        # Scale amplitude in memory according to volume slider (scaled by 0.80 for soft whisper delivery)
        with wave.open(wav_path, "rb") as wf:
            params = wf.getparams()
            raw = wf.readframes(wf.getnframes())

        scale = (self.volume / 100.0) * 0.80
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) * scale
        scaled_i16 = np.clip(samples, -32768, 32767).astype(np.int16)

        mem_wav = io.BytesIO()
        with wave.open(mem_wav, "wb") as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(scaled_i16.tobytes())

        winsound.PlaySound(mem_wav.getvalue(), winsound.SND_MEMORY)

    def _fallback_sapi_female(self, text):
        clean_text = text.replace("'", "").replace('"', "")
        ps_script = f"""
        $v = New-Object -ComObject SAPI.SpVoice
        $female = $v.GetVoices() | Where-Object {{ $_.GetDescription() -match 'Zira|Hazel|Female' }} | Select-Object -First 1
        if ($female) {{ $v.Voice = $female }}
        $v.Volume = {self.volume}
        $v.Rate = {self.rate}
        $v.Speak('{clean_text}')
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000
        )

    def _run_queue(self):
        while self.running:
            try:
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if isinstance(item, tuple):
                text, allow_when_game_closed = item
            else:
                text, allow_when_game_closed = item, False

            if not self.enabled or self.volume <= 0:
                self.queue.task_done()
                continue

            if not allow_when_game_closed and not is_star_citizen_running():
                self.queue.task_done()
                continue

            try:
                wav_path = self._ensure_cached_wav(text)
                if wav_path and os.path.exists(wav_path):
                    self._play_wav_scaled(wav_path)
                else:
                    self._fallback_sapi_female(text)
            except Exception:
                try:
                    self._fallback_sapi_female(text)
                except Exception:
                    pass
            finally:
                self.queue.task_done()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except Exception:
                    break

    def set_volume(self, volume):
        self.volume = max(0, min(100, int(volume)))
        if self.volume <= 0:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def set_rate(self, rate):
        self.rate = max(-5, min(5, int(rate)))

    def set_profile(self, profile_key):
        if profile_key in SHIP_VOICE_PROFILES:
            self.profile = profile_key

    def set_chime(self, enabled):
        self.chime_enabled = bool(enabled)

