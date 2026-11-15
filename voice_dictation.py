"""Voice dictation service for SynthScan live chat push-to-talk.

Captures microphone audio via miniaudio and transcribes in real-time
using Windows native System.Speech.Recognition (DictationGrammar).
Zero cloud dependencies, offline, low latency.
"""
import io
import os
import sys
import tempfile
import threading
import time
import wave
from typing import Optional

# Standard Windows GAC path for System.Speech.dll
SYSTEM_SPEECH_DLL = r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL\System.Speech\v4.0_4.0.0.0__31bf3856ad364e35\System.Speech.dll"


class VoiceDictationService:
    _instance: Optional["VoiceDictationService"] = None

    @classmethod
    def get_instance(cls) -> "VoiceDictationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._lock = threading.Lock()
        self._engine = None
        self._capture_device = None
        self._frames = []
        self._is_recording = False
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import clr
            if os.path.exists(SYSTEM_SPEECH_DLL):
                clr.AddReference(SYSTEM_SPEECH_DLL)
            else:
                clr.AddReference("System.Speech")
            from System.Speech.Recognition import SpeechRecognitionEngine, DictationGrammar
            engine = SpeechRecognitionEngine()
            engine.LoadGrammar(DictationGrammar())
            self._engine = engine
        except Exception as exc:
            self._engine = None
            print(f"[voice_dictation] System.Speech engine unavailable: {exc}")

    @property
    def is_available(self) -> bool:
        return self._engine is not None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self) -> bool:
        with self._lock:
            if self._is_recording:
                return True
            try:
                import miniaudio
                self._frames = []

                def record_gen():
                    while True:
                        data = yield
                        self._frames.append(data)

                gen = record_gen()
                next(gen)

                self._capture_device = miniaudio.CaptureDevice(nchannels=1, sample_rate=16000)
                self._capture_device.start(gen)
                self._is_recording = True
                return True
            except Exception as exc:
                self._is_recording = False
                print(f"[voice_dictation] Microphone capture start failed: {exc}")
                return False

    def stop_recording_and_recognize(self, timeout_sec: float = 4.0) -> str:
        with self._lock:
            if not self._is_recording:
                return ""
            self._is_recording = False
            device = self._capture_device
            self._capture_device = None

            if device:
                try:
                    device.stop()
                    device.close()
                except Exception:
                    pass

            raw_pcm = b"".join(self._frames)
            self._frames = []

        if len(raw_pcm) < 3200:  # < 0.1s
            return ""

        if not self._engine:
            return ""

        tmp_wav = os.path.join(tempfile.gettempdir(), f"ss_dictation_{int(time.time()*1000)}.wav")
        try:
            with wave.open(tmp_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(raw_pcm)

            with self._lock:
                from System import TimeSpan
                self._engine.SetInputToWaveFile(tmp_wav)
                res = self._engine.Recognize(TimeSpan.FromSeconds(timeout_sec))
                text = str(res.Text).strip() if res and hasattr(res, "Text") else ""
                return text
        except Exception as exc:
            print(f"[voice_dictation] Recognition error: {exc}")
            return ""
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass
