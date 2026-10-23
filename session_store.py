"""Persistent session notebook. Join/leave events come from the shared log reader."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
import uuid

from telemetry_core import atomic_json, timestamp, utc_iso

BASE_DIR = Path(__file__).resolve().parent
SERVER_LOG_FILE = str(BASE_DIR / "server_log.json")
SHARD_HISTORY_FILE = str(BASE_DIR / "shard_history.json")
DEFAULT_GAME_LOG = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"
LOG = logging.getLogger(__name__)


def format_duration(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def format_local_ts(iso_str):
    at = timestamp(iso_str)
    return datetime.fromtimestamp(at, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S") if at is not None else "--"


class ServerLogManager:
    def __init__(self, log_file=SERVER_LOG_FILE, game_log_path=DEFAULT_GAME_LOG, clock=time.time):
        self.log_file = Path(log_file)
        self.game_log_path = game_log_path
        self.clock = clock
        self.sessions = []
        self.active_session_id = None
        self.read_only = False
        self._dirty = False
        self._last_save = clock()
        self._sample_times = {}
        if self.log_file.exists():
            try:
                data = json.loads(self.log_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Session history must be an object")
                self.sessions = data.get("sessions", [])
                if not isinstance(self.sessions, list) or not all(isinstance(session, dict) for session in self.sessions):
                    raise ValueError("Session records must be a list")
                # Persisted 'active' is not evidence that a game is still joined.
                # The shared log reader will explicitly reconcile the current join.
                for session in self.sessions:
                    session["active"] = False
            except (OSError, ValueError, TypeError):
                self.read_only = True
                self.sessions = []
                LOG.exception("Could not load session history; preserving the original file")

    def _save(self):
        if not self.read_only:
            try:
                atomic_json(self.log_file, {"schema_version": 2, "sessions": self.sessions})
            except OSError:
                self.read_only = True
                LOG.exception("Could not save session history; collection continues in memory")
        self._dirty = False
        self._last_save = self.clock()

    def flush(self):
        if self._dirty:
            self._save()

    def get_sessions(self, filter_text="", filter_region=""):
        query = (filter_text or "").lower().strip()
        region = (filter_region or "").lower()
        out = []
        for session in reversed(self.sessions):
            if region not in ("", "all") and region not in session.get("region_raw", "").lower() and region not in session.get("region_display", "").lower():
                continue
            searchable = " ".join(str(session.get(k, "")) for k in ("server_name", "shard_id", "full_shard_id", "region_display", "notes"))
            searchable += " " + " ".join(item.get("name", "") for item in session.get("locations", []))
            if not query or query in searchable.lower():
                out.append(session)
        return out

    def get_active_session(self):
        active = next((session for session in self.sessions if session.get("id") == self.active_session_id and session.get("active")), None)
        if active:
            at = timestamp(active.get("joined_at"))
            active["duration_sec"] = max(0, int(self.clock() - at)) if at is not None else 0
        return active

    def start_new_session(self, reg_raw, env_id, shard_num, ip="", joined_at=None,time_source='game_log_timestamp'):
        at = self.clock() if joined_at is None else joined_at
        full = f"pub_{reg_raw}_{env_id}_{shard_num}".lower()
        iso = utc_iso(at)
        active = self.get_active_session()
        if active and active.get("full_shard_id") == full and active.get("joined_at") == iso:
            return active
        self.end_session(at, "next_join",'next_join_bound')
        candidates = [session for session in self.sessions if session.get("full_shard_id") == full
                      and timestamp(session.get("joined_at")) is not None
                      and abs(timestamp(session["joined_at"]) - at) < (0.002 if session.get("join_source") == "game_log" else 2)]
        existing = min(candidates, key=lambda session: abs(timestamp(session["joined_at"]) - at), default=None)
        if existing:
            if existing.get("joined_at") != iso:
                existing.setdefault("legacy_joined_at", existing.get("joined_at"))
                existing["joined_at"], existing["joined_at_local"] = iso, format_local_ts(iso)
            existing["join_source"] = "game_log"
            existing['joined_time_source']=time_source
            existing["active"] = True
            existing["left_at"] = existing["left_at_local"] = None
            existing.pop('left_time_source',None);existing.pop('end_reason',None)
            self.active_session_id = existing["id"]
            self._sample_times.clear()
            self._save()
            return existing
        # Import formatting only; this module does not instantiate a second reader.
        from displayinfo_reader import translate_region
        entry = {"id": "sess_" + uuid.uuid5(uuid.NAMESPACE_URL, full + ":" + iso).hex,
                 "joined_at": iso, "joined_at_local": format_local_ts(iso), "join_source": "game_log",'joined_time_source':time_source,
                 "left_at": None, "left_at_local": None, "duration_sec": 0,
                 "shard_id": str(shard_num), "full_shard_id": full,
                 "server_name": self._get_known_name(reg_raw, shard_num, full),
                 "region_raw": reg_raw.lower(), "region_display": translate_region(reg_raw),
                 "ip_address": ip, "locations": [], "notes": "", "active": True,
                 "telemetry": {"avg_sfps": None, "avg_ping": None, "restarts": None,
                               "sfps_samples": 0, "ping_samples": 0}}
        self.sessions.append(entry)
        self.active_session_id = entry["id"]
        self._sample_times.clear()
        self._save()
        return entry

    def end_session(self, at=None, reason="disconnected",time_source=None):
        active = self.get_active_session()
        if not active:
            return
        time_source=time_source or ('game_log_timestamp' if at is not None else 'observation')
        at = self.clock() if at is None else at
        iso = utc_iso(at)
        active.update(active=False, left_at=iso, left_at_local=format_local_ts(iso), end_reason=reason,left_time_source=time_source)
        joined = timestamp(active.get("joined_at"))
        active["duration_sec"] = max(0, int(at - joined)) if joined is not None else 0
        self.active_session_id = None
        self._save()

    def confirm_seen(self,at):
        active=self.get_active_session()
        if active:
            prior=timestamp(active.get('last_confirmed_at'))
            if prior is None or at-prior>=15:
                active['last_confirmed_at']=utc_iso(at);self._dirty=True

    def record_location(self, loc_name, observed_at=None):
        active = self.get_active_session()
        if not active or not loc_name or loc_name.upper() in ("--", "UNKNOWN", "DEEP SPACE"):
            return
        locations = active.setdefault("locations", [])
        name = loc_name.upper()
        if locations and locations[-1].get("name") == name:
            return
        at = self.clock() if observed_at is None else observed_at
        locations.append({"name": name, "time": format_local_ts(utc_iso(at))[11:], "observed_at": utc_iso(at)})
        self._save()

    def record_telemetry_sample(self, sfps, ping, restarts, metadata=None):
        active = self.get_active_session()
        if not active:
            return
        tel = active.setdefault("telemetry", {})
        for metric, value, field, counter in (("server_fps", sfps, "avg_sfps", "sfps_samples"),
                                               ("ping_ms", ping, "avg_ping", "ping_samples")):
            observed = (metadata or {}).get(metric, {}).get("observed_at", self.clock())
            if value is None or observed == self._sample_times.get(metric):
                continue
            self._sample_times[metric] = observed
            count = tel.get(counter, 0)
            # Old exponential averages with no count are not a known sample history.
            prior = tel.get(field) if count else None
            tel[field] = value if prior is None else prior + (value - prior) / (count + 1)
            tel[counter] = count + 1
            self._dirty = True
        if restarts is not None and tel.get("restarts") != restarts:
            tel["restarts"] = restarts
            self._dirty = True
        if self._dirty and self.clock() - self._last_save >= 15:
            self._save()

    def _get_known_name(self, region, shard, full_shard_id=None):
        try:
            history = json.loads(Path(SHARD_HISTORY_FILE).read_text(encoding="utf-8"))
            entry = history.get("shards", {}).get(full_shard_id, {}) if full_shard_id else {}
            if entry.get("name"):
                return entry["name"]
        except (OSError, ValueError, TypeError):
            pass
        return f"SHARD {str(shard).lstrip('0') or shard}"

    def set_shard_name(self, shard_id, region_code, new_name, full_shard_id=None):
        # ShardHistory owns its file. Updating both independently loses changes.
        if not full_shard_id:
            candidates = {session.get("full_shard_id") for session in self.sessions
                          if session.get("region_raw") == region_code.lower() and str(session.get("shard_id", "")).lstrip("0") == str(shard_id).lstrip("0")}
            if len(candidates) != 1:
                return False
            full_shard_id = candidates.pop()
        for session in self.sessions:
            if session.get("full_shard_id") == full_shard_id:
                session["server_name"] = new_name.strip().upper()
        self._save()
        return True

    def set_session_note(self, session_id, note_text):
        for session in self.sessions:
            if session.get("id") == session_id:
                session["notes"] = note_text.strip()
                self._save()
                return True
        return False
