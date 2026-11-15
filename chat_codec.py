"""Star Citizen chat codec and live translation helper.

Handles:
- Decoding community `[zh] @CODE` localization-key chat strings (7,020 keys
  compatible with StarCitizenToolBox's `chinese_(simplified).txt` input method)
  without requiring the user to overwrite their English `global.ini`.
- Encoding Chinese text (or translated English -> Chinese text) into `[zh] @CODE`
  format so English players can reply to `[zh]` speakers in-game.
- Repairing raw UTF-8-as-Latin-1 mojibake when present.
- Caching live translations (non-English -> English and English -> Chinese).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import threading
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple


_ZH_PREFIX_RE = re.compile(r"^\s*\[zh\]\s*", re.IGNORECASE)
_ZH_CODE_TOKEN_RE = re.compile(r"(\s*)@([0-9A-Z]{1,4})")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af\u0400-\u04ff]")
_NON_ASCII_LETTER_RE = re.compile(r"[^\x00-\x7f]")

_CODEC_LOCK = threading.Lock()
_CODE_TO_CHAR: Dict[str, str] = {}
_CHAR_TO_CODE: Dict[str, str] = {}
_CODEC_LOADED = False


def _dictionary_path() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve().parent
    candidates = [
        here / "data" / "zh_chat_codes.json",
        pathlib.Path.cwd() / "data" / "zh_chat_codes.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _ensure_codec_loaded() -> None:
    global _CODEC_LOADED
    if _CODEC_LOADED:
        return
    with _CODEC_LOCK:
        if _CODEC_LOADED:
            return
        path = _dictionary_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for code, ch in data.items():
                    code_u = str(code).strip().upper()
                    ch_s = str(ch)
                    if code_u and ch_s:
                        _CODE_TO_CHAR[code_u] = ch_s
                        _CHAR_TO_CODE.setdefault(ch_s, code_u)
        except Exception:
            pass
        _CODEC_LOADED = True


def try_repair_mojibake(text: str) -> Tuple[str, bool]:
    """Repair UTF-8 bytes misinterpreted as Latin-1/CP1252 when applicable."""
    if not text or not any(0x80 <= ord(ch) <= 0xFF for ch in text):
        return text, False
    if _CJK_RE.search(text):
        return text, False
    try:
        raw_bytes = text.encode("latin-1")
        repaired = raw_bytes.decode("utf-8")
        if repaired != text and (_CJK_RE.search(repaired) or len(repaired) < len(text)):
            return repaired, True
    except Exception:
        pass
    return text, False


def decode_sc_chat(content: str) -> Dict[str, object]:
    """Decode Star Citizen chat content, including `[zh] @...` encoded messages."""
    _ensure_codec_loaded()
    raw = str(content or "")
    if not raw.strip():
        return {
            "raw": raw,
            "decoded": raw,
            "was_zh_encoded": False,
            "was_mojibake": False,
            "needs_translation": False,
            "lang_hint": "en",
        }

    has_zh_prefix = bool(_ZH_PREFIX_RE.match(raw))
    body = _ZH_PREFIX_RE.sub("", raw, count=1) if has_zh_prefix else raw

    # Count how many valid @CODE tokens exist in the message
    code_matches = list(_ZH_CODE_TOKEN_RE.finditer(body))
    valid_codes = sum(1 for m in code_matches if m.group(2) in _CODE_TO_CHAR)

    if has_zh_prefix or (valid_codes >= 2 and valid_codes >= len(code_matches) * 0.6):
        out_parts: list[str] = []
        last_end = 0
        prev_was_code = False
        for m in code_matches:
            start, end = m.span()
            leading_ws, code = m.group(1), m.group(2)
            between = body[last_end:start]
            if between:
                # If StarCitizenToolBox inserted a separator space after @CODE before ASCII, strip single separator space
                if prev_was_code and between.startswith(" ") and len(between) > 1 and between[1:].strip():
                    between = between[1:]
                out_parts.append(between)
                prev_was_code = False
            ch = _CODE_TO_CHAR.get(code)
            if ch is not None:
                out_parts.append(ch)
                prev_was_code = True
            else:
                out_parts.append(leading_ws + "@" + code)
                prev_was_code = False
            last_end = end
        tail = body[last_end:]
        if tail:
            if prev_was_code and tail.startswith(" ") and len(tail) > 1 and tail[1:].strip():
                tail = tail[1:]
            out_parts.append(tail)
        decoded = "".join(out_parts).strip()
        return {
            "raw": raw,
            "decoded": decoded or raw,
            "was_zh_encoded": True,
            "was_mojibake": False,
            "needs_translation": True,
            "lang_hint": "zh-CN",
        }

    repaired, was_mojibake = try_repair_mojibake(raw)
    has_cjk = bool(_CJK_RE.search(repaired))
    has_non_ascii = bool(_NON_ASCII_LETTER_RE.search(repaired))
    return {
        "raw": raw,
        "decoded": repaired,
        "was_zh_encoded": False,
        "was_mojibake": was_mojibake,
        "needs_translation": has_cjk or was_mojibake or has_non_ascii,
        "lang_hint": "zh-CN" if has_cjk else ("auto" if has_non_ascii else "en"),
    }


def encode_sc_zh_chat(text: str) -> str:
    """Encode Chinese text into StarCitizenToolBox-compatible `[zh] @CODE` format."""
    _ensure_codec_loaded()
    clean = str(text or "").strip()
    if not clean:
        return ""
    if _ZH_PREFIX_RE.match(clean):
        return clean

    sb: list[str] = ["[zh] "]
    last_was_code = False
    last_was_ascii = False

    for ch in clean:
        code = _CHAR_TO_CODE.get(ch)
        if code is not None:
            if last_was_ascii:
                sb.append(" ")
            sb.append("@")
            sb.append(code)
            last_was_code = True
            last_was_ascii = False
        else:
            if last_was_code and ch != " ":
                sb.append(" ")
            sb.append(ch)
            last_was_code = False
            last_was_ascii = ch != " "
    return "".join(sb).strip()


class ChatTranslator:
    """Lightweight translation client with in-memory + optional file cache."""

    def __init__(self, cache_path: Optional[pathlib.Path] = None) -> None:
        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[str, str]] = {}
        self._cache_path = cache_path
        if cache_path and cache_path.exists():
            try:
                raw = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if isinstance(v, list) and len(v) == 2:
                            self._cache[str(k)] = (str(v[0]), str(v[1]))
            except Exception:
                pass

    def _save_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            items = list(self._cache.items())[-1000:]
            payload = {k: [v[0], v[1]] for k, v in items}
            self._cache_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def translate(self, text: str, target_lang: str = "en", source_lang: str = "auto") -> Tuple[str, str]:
        """Translate `text` to `target_lang`, returning `(translated_text, detected_source_lang)`."""
        clean = str(text or "").strip()
        if not clean:
            return "", source_lang

        cache_key = f"{source_lang}:{target_lang}:{clean}"
        with self._lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if os.environ.get("SYNTHSCAN_DISABLE_CHAT_TRANSLATE") == "1":
            return clean, source_lang

        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={urllib.parse.quote(source_lang)}"
            f"&tl={urllib.parse.quote(target_lang)}&dt=t&q={urllib.parse.quote(clean)}"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = data[0] if isinstance(data, list) and data else []
            translated = "".join(str(p[0]) for p in parts if isinstance(p, list) and p and p[0]).strip()
            detected = str(data[2]) if isinstance(data, list) and len(data) > 2 and data[2] else source_lang
            if not translated:
                translated = clean
            result = (translated, detected)
            with self._lock:
                self._cache[cache_key] = result
                self._save_cache()
            return result
        except Exception:
            return clean, source_lang

    def translate_and_encode_zh(self, text: str) -> Dict[str, str]:
        """Translate English (or arbitrary text) into Simplified Chinese and encode as `[zh] @...`."""
        clean = str(text or "").strip()
        if not clean:
            return {"original": "", "zh_text": "", "encoded": ""}
        if _ZH_PREFIX_RE.match(clean):
            decoded_info = decode_sc_chat(clean)
            return {
                "original": clean,
                "zh_text": str(decoded_info.get("decoded") or clean),
                "encoded": clean,
            }
        # If already Chinese characters, encode directly without translating
        if _CJK_RE.search(clean):
            zh_text = clean
        else:
            zh_text, _ = self.translate(clean, target_lang="zh-CN", source_lang="auto")
        encoded = encode_sc_zh_chat(zh_text)
        return {
            "original": clean,
            "zh_text": zh_text,
            "encoded": encoded,
        }
