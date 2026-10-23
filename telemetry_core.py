"""Telemetry state independent of Tk, screen capture, and the game's process.

Only observations from the game are called game telemetry. Missing data is never
replaced by a network probe, a guessed population, or a synthetic health score.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
import time
from interdiction_watch import InterdictionNotifications

LOG = logging.getLogger(__name__)
from installation import game_directory
DEFAULT_GAME_LOG = str(game_directory()/'Game.log')
SHARD_RE = re.compile(r"pub_([a-z0-9]+)_(\d+)_([a-z0-9_]+)", re.I)
METRIC_LIMITS = {
    "server_fps": (0, 240), "client_fps": (0, 2000),
    "ping_ms": (0, 30000), "loss_pct": (0, 100),
    "bwin_kbps": (0, 1e9), "entities": (0, 1e8),
    "shard_pop": (0, 1e6), "srv_pop": (0, 1e6), "restarts": (0, 1e6),
}


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, TypeError):
        return None


def utc_iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path, value):
    """Replace a whole record atomically; do not silently turn read errors into writes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@dataclass(frozen=True)
class Observation:
    value: float
    source: str
    observed_at: float


class MetricStore:
    """A session-scoped collection. Timestamps belong to observations, not draws."""
    def __init__(self, ttl=5.0):
        self.ttl = ttl
        self.session = None
        self.observations = {}

    def set_session(self, session):
        if session != self.session:
            self.session = session
            self.observations.clear()

    def ingest(self, values, source, observed_at, session):
        if not self.session or session != self.session:
            return
        try:
            observed_at = float(observed_at)
        except (TypeError, ValueError):
            return
        if not math.isfinite(observed_at):
            return
        for key, bounds in METRIC_LIMITS.items():
            value = values.get(key)
            if value is None or isinstance(value, bool):
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue
            if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
                continue
            if key in {"entities", "shard_pop", "srv_pop", "restarts"} and not value.is_integer():
                continue
            old = self.observations.get(key)
            if old is None or observed_at > old.observed_at or (observed_at == old.observed_at and source == old.source):
                self.observations[key] = Observation(value, source, observed_at)

    def snapshot(self, now):
        values, metadata = {}, {}
        for key in METRIC_LIMITS:
            observation = self.observations.get(key)
            age = max(0.0, now - observation.observed_at) if observation else None
            valid = observation is not None and now >= observation.observed_at - 1 and age <= self.ttl
            values[key] = observation.value if valid else None
            metadata[key] = {
                "source": observation.source if observation else None,
                "observed_at": observation.observed_at if observation else None,
                "age_seconds": age,
                "status": "observed" if valid else ("stale" if observation else "unavailable"),
            }
        return values, metadata


class IncrementalGameLog:
    """One owner must call poll(). Binary offsets and a partial-line buffer survive appends."""
    def __init__(self, log_path=DEFAULT_GAME_LOG, translate_location=None):
        self.interdiction_notifications=InterdictionNotifications()
        self.log_path = str(log_path)
        self.translate_location = translate_location or (lambda text: text.replace("_", " ").upper())
        self.last_pos = 0
        self._file_identity = None
        self._pending = b""
        self._generation = 0
        self.player_name = ""
        self.events = []
        self.observations = {}
        self.reset()
        self.poll()

    def reset(self, reason="disconnected", event_at=None, time_source=None):
        self.interdiction_notifications.reset()
        previous = getattr(self, "session_token", None)
        self.connected = False
        self.connection_status = reason
        self.shard_id = "--"
        self.full_shard_id = ""
        self.region_raw = ""
        self.env_id = ""
        self.ip_address = ""
        self.port = ""
        self.connection_id = None
        self.session_token = None
        self.joined_at = None
        self.location_hint = ""
        self.location_observed_at = None
        self.medical_imprint = ""
        self.entities = None
        self.is_loading_screen = False
        self.observations.clear()
        if previous:
            self.events.append({"type": "left", "session": previous, "at": event_at if event_at is not None else time.time(), "reason": reason,
                                "time_source":time_source or ('game_log_timestamp' if event_at is not None else 'observation')})

    def rewind(self):
        """The process stopped. A later launch may rewrite the same file in place."""
        self.last_pos = 0
        self._pending = b""
        self._file_identity = None
        self.player_name = ""
        self._generation += 1

    def poll(self):
        try:
            stat = os.stat(self.log_path)
            identity = (stat.st_dev, stat.st_ino)
            if self._file_identity is not None and (identity != self._file_identity or stat.st_size < self.last_pos):
                self.reset("log_restarted")
                self.player_name = ""
                self.last_pos = 0
                self._pending = b""
                self._generation += 1
            self._file_identity = identity
            with open(self.log_path, "rb") as stream:
                stream.seek(self.last_pos)
                chunk = stream.read(1024 * 1024)
                self.last_pos = stream.tell()
            if chunk:
                self.feed(chunk)
        except FileNotFoundError:
            if self._file_identity is not None:
                self.reset("log_unavailable")
                self.last_pos = 0
                self._pending = b""
                self._file_identity = None
        except OSError:
            LOG.exception("Could not read game log")

    def feed(self, chunk):
        self._pending += chunk
        lines = self._pending.split(b"\n")
        self._pending = lines.pop()
        for line in lines:
            self._parse_line(line.decode("utf-8", errors="replace").rstrip("\r"))

    def _parse_chunk(self, text):
        """Compatibility helper for complete text fixtures; poll() uses buffered bytes."""
        self.feed(text.encode("utf-8"))

    def _is_local_player(self, line):
        if not self.player_name:
            return False
        escaped = re.escape(self.player_name)
        return bool(re.search(rf"(?:\[|')({escaped})(?:\]|')|Player:\s*{escaped}(?:\s|$)", line, re.I))

    def _parse_line(self, line):
        tm = re.match(r"<([^>]+)>", line)
        at = timestamp(tm.group(1)) if tm else None
        time_source='game_log_timestamp' if at is not None else 'observation'
        at = at if at is not None else time.time()
        if self.connected:
            report=self.interdiction_notifications.feed(line,at,time_source)
            if report:self.events.append(dict(type='interdiction',**report,session=self.session_token,full_shard_id=self.full_shard_id,joined_at=self.joined_at))
        match = re.search(r"User Login Success - Handle\[([^\]]+)\]", line)
        if match:
            self.player_name = match.group(1)
        if "OpenLoadingScreen" in line:
            self.is_loading_screen = True
        if "StopLoadingScreen" in line and ("Finished" in line or "Starting CET" in line):
            self.is_loading_screen = False

        # Match specific lifecycle events, not generic references to frontend components.
        if any(term in line for term in (
            "RequestQuitLobby", "SystemQuit", "FastShutdown", "CSystem::Quit",
            "Connection closed", "Client disconnected", "OnConnectionError",
        )):
            self.reset("disconnected", at,time_source)

        if "<Join PU>" in line:
            shard = SHARD_RE.search(line)
            if shard:
                self._join(shard, at, line,time_source)
        elif "New Shard Id:" in line:
            shard = SHARD_RE.search(line.split("New Shard Id:", 1)[1])
            if shard and shard.group(0).lower() != self.full_shard_id:
                self._join(shard, at, line,time_source)

        if not self.connected:
            return
        # A PU join destroys the local frontend channel too. Only a disconnect
        # of the current remote replication channel ends the PU session.
        if "<Channel Created>" in line and f"remoteAddr={self.ip_address}:{self.port} " in line:
            channel = re.search(r"connection=\{([^}]+)\}", line)
            if channel:
                self.connection_id = channel.group(1)
        if "<Channel Disconnected>" in line and self.connection_id is not None:
            channel = re.search(r"connection=\{([^}]+)\}", line)
            if channel and channel.group(1) == self.connection_id and f"remoteAddr={self.ip_address}:{self.port} " in line:
                self.reset("connection_lost", at,time_source)
                return
        if "net_dialog_server_error" in line and re.search(r"(?:=|value\[)\s*1", line):
            self.connection_status = "recovering"
        if "StopLoadingScreen" in line and "Finished" in line:
            self.connection_status = "connected"

        # Prefer explicit, player-scoped location names. Numeric inventory IDs are
        # not assumed to be universal station identifiers.
        if self._is_local_player(line):
            location = re.search(r"requested inventory for Location\[([^\]]+)\]", line)
            if location:
                self.location_hint = self.translate_location(location.group(1))
                self.location_observed_at = at
                self.events.append({"type": "location", "name": self.location_hint, "at": at})

        # These parsers accept actual measurement lines, never cvar echoes or help.
        sfps = re.search(r"(?:^|>\s*|\]\s*)Server FPS\s*[:=]?\s*(\d+(?:\.\d+)?)", line, re.I)
        if sfps:
            self._observe("server_fps", sfps.group(1), at)
        net = re.search(r"Net:\s*ping\s+([\d.]+)ms,?\s*loss\s+([\d.]+)%\s*BwIn\s+([\d.]+)([KM]?)", line, re.I)
        if net:
            self._observe("ping_ms", net.group(1), at)
            self._observe("loss_pct", net.group(2), at)
            self._observe("bwin_kbps", float(net.group(3)) * (1000 if net.group(4).upper() == "M" else 1), at)
        population = re.search(r"Server:\s*([^,]+),\s*restarts\s+(\d+),\s*pop\.\s*\[shard\s+(\d+),\s*srv\s+(\d+)\]", line, re.I)
        if population:
            for key, value in zip(("restarts", "shard_pop", "srv_pop"), population.groups()[1:]):
                self._observe(key, value, at)

    def _join(self, shard, at, line,time_source='game_log_timestamp'):
        full_id = shard.group(0).lower()
        token = f"{self._generation}:{full_id}:{at:.3f}"
        if token == self.session_token:
            return
        if self.session_token:
            self.reset("rejoined", at,'next_join_bound')
        self.connected = True
        self.connection_status = "connected"
        self.full_shard_id = full_id
        self.region_raw, self.env_id, self.shard_id = shard.groups()
        self.region_raw = self.region_raw.lower()
        self.session_token = token
        self.joined_at = at
        ip = re.search(r"address\[([^\]]+)\]", line)
        self.ip_address = ip.group(1) if ip else ""
        port = re.search(r"port\[([^\]]+)\]", line)
        self.port = port.group(1) if port else ""
        self.events.append({"type": "joined", "full_shard_id": full_id, "at": at, "session": token, "ip": self.ip_address,'time_source':time_source})

    def _observe(self, key, value, at):
        self.observations[key] = Observation(float(value), "game_log", at)

    def drain_events(self):
        events, self.events = self.events, []
        return events


class ShardHistory:
    """Full shard IDs are identity; names are labels. Legacy records stay separate."""
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.shards = {}
        self.legacy = {}
        self.current_key = None
        self.current_token = None
        self.previous_visit_at = None
        self.current_is_repeat = False
        self.read_only = False
        self._last_saved = clock()
        needs_migration = not self.path.exists()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Shard history must be an object")
                if data.get("schema_version") == 2:
                    self.shards = data.get("shards", {})
                    self.legacy = data.get("legacy", {})
                else:
                    self.legacy = data
                    needs_migration = True
                if not all(isinstance(records, dict) and all(isinstance(entry, dict) for entry in records.values())
                           for records in (self.shards, self.legacy)):
                    raise ValueError("Invalid shard history entries")
            except (OSError, ValueError, TypeError):
                self.read_only = True
                self.shards, self.legacy = {}, {}
                LOG.exception("History could not be loaded; preserving the original file")
        if needs_migration:
            self._import_session_identities()

    def _import_session_identities(self):
        """Recover precise old identities from the notebook, not ambiguous short keys."""
        sessions_path = self.path.parent / "server_log.json"
        if not sessions_path.exists():
            return
        try:
            sessions = json.loads(sessions_path.read_text(encoding="utf-8")).get("sessions", [])
            seen = set()
            latest_by_shard = {}
            for session in sorted(sessions, key=lambda item: item.get("joined_at", "")):
                full = session.get("full_shard_id", "").lower()
                match = SHARD_RE.fullmatch(full)
                joined = timestamp(session.get("joined_at"))
                if not match or joined is None or (full, joined) in seen:
                    continue
                seen.add((full, joined))
                if full in latest_by_shard and abs(joined - latest_by_shard[full]) < 2:
                    continue
                latest_by_shard[full] = joined
                region, _, shard = match.groups()
                left = timestamp(session.get("left_at")) or joined
                entry = self.shards.setdefault(full, {"full_shard_id": full, "region_raw": region,
                    "region": region.upper(), "shard_id": shard, "first_seen": joined, "visits": 0})
                entry["previous_visit_at"] = entry.get("last_left_at")
                entry.update(visits=entry["visits"] + 1, last_seen=left, last_left_at=left,
                             last_join_token=f"0:{full}:{joined:.3f}", last_join_at=joined, join_source="legacy_session")
                name = session.get("server_name", "")
                if name and not name.startswith("SHARD "):
                    entry.update(name=name, callsign=name, name_source="legacy_session_label")
        except (OSError, ValueError, TypeError, AttributeError):
            LOG.exception("Could not recover old session identities")

    def _save(self):
        if not self.read_only:
            try:
                atomic_json(self.path, {"schema_version": 2, "shards": self.shards, "legacy": self.legacy})
                self._last_saved = self.clock()
            except OSError:
                self.read_only = True
                LOG.exception("Could not save shard history; collection continues in memory")

    def get_last_visited(self):
        entries = list(self.shards.values()) + list(self.legacy.values())
        return max(entries, key=lambda entry: entry.get("last_seen", 0), default=None)

    def _resolve_key(self, region, shard, full_shard_id=None):
        if full_shard_id:
            return full_shard_id.lower()
        matches = [key for key, entry in self.shards.items()
                   if entry.get("region_raw") == region.lower() and str(entry.get("shard_id", "")).lstrip("0") == str(shard).lstrip("0")]
        if self.current_key in matches:
            return self.current_key
        return matches[0] if len(matches) == 1 else None

    def get_known_name(self, region, shard, full_shard_id=None):
        key = self._resolve_key(region, shard, full_shard_id)
        return self.shards.get(key, {}).get("name") if key else None

    def set_shard_name(self, region, shard, name, full_shard_id=None, source="manual"):
        key = self._resolve_key(region, shard, full_shard_id)
        if not key or key not in self.shards:
            return
        self.shards[key].update(name=name.strip().upper(), callsign=name.strip().upper(), name_source=source)
        self._save()

    def observe_shard(self, region, shard, callsign="", full_shard_id=None, join_token=None):
        if not full_shard_id or str(shard) == "--":
            self.leave_current()
            return "STANDBY", 0
        key, now = full_shard_id.lower(), self.clock()
        token = join_token or key
        if token != self.current_token:
            self.leave_current()
            entry = self.shards.get(key)
            if entry is None:
                entry = {"full_shard_id": key, "shard_id": str(shard), "region_raw": region.lower(),
                         "region": region.upper(), "first_seen": now, "last_seen": now, "visits": 0}
                self.shards[key] = entry
            # Reloading SynthScan in the same join does not count as another visit.
            try:
                joined = float(token.rsplit(":", 1)[1])
            except (ValueError, IndexError):
                joined = None
            # The reader generation is process-local. Restarting the HUD after
            # a log rotation changes that prefix, but not the actual join.
            tolerance = 2 if entry.get("join_source") == "legacy_session" else 0.002
            same_join = (joined is not None and entry.get("last_join_at") is not None
                         and abs(joined - entry["last_join_at"]) < tolerance)
            if entry.get("last_join_token") != token and not same_join:
                self.previous_visit_at = entry.get("last_left_at", entry.get("last_seen")) if entry.get("visits", 0) else None
                entry["previous_visit_at"] = self.previous_visit_at
                entry["visits"] = entry.get("visits", 0) + 1
                entry["last_join_token"] = token
            else:
                self.previous_visit_at = entry.get("previous_visit_at")
            entry.update(last_join_token=token, last_join_at=joined, join_source="game_log")
            entry["last_seen"] = now
            self.current_key, self.current_token = key, token
            self.current_is_repeat = entry["visits"] > 1
            self._save()
        else:
            self.shards[key]["last_seen"] = now
            if now - self._last_saved >= 30:
                self._save()
        entry = self.shards[key]
        count = sum(e.get("region_raw") == region.lower() and now - e.get("last_seen", 0) < 86400 for e in self.shards.values())
        if entry["visits"] > 1:
            ago = max(0, int(now - (self.previous_visit_at or now)))
            elapsed = f"{ago // 3600}h {(ago % 3600) // 60}m" if ago >= 3600 else f"{max(1, ago // 60)}m"
            return f"RETURN #{entry['visits']} ({elapsed} AGO)", count
        return "FIRST VISIT", count

    def leave_current(self):
        if self.current_key and self.current_key in self.shards:
            self.shards[self.current_key]["last_left_at"] = self.clock()
            self.shards[self.current_key]["last_seen"] = self.clock()
            self._save()
        self.current_key = self.current_token = None

    def mark_cooldown(self, label, minutes):
        if self.read_only:
            raise ValueError("History storage is unavailable; the original file has been preserved")
        if not self.current_key:
            raise ValueError("Join a shard before adding a reminder")
        if not label.strip() or not 1 <= minutes <= 1440:
            raise ValueError("Enter a label and a duration between 1 and 1440 minutes")
        now = self.clock()
        reminder = {"label": label.strip()[:80], "recorded_at": now, "until": now + minutes * 60, "source": "manual"}
        self.shards[self.current_key].setdefault("cooldowns", []).append(reminder)
        self._save()
        return reminder

    def active_cooldowns(self, full_shard_id=None):
        key = full_shard_id or self.current_key
        return [item for item in self.shards.get(key, {}).get("cooldowns", []) if item.get("until", 0) > self.clock()]


class EvidenceHealth:
    """Describe observed symptoms. No crash probabilities or invented health percentages."""
    def __init__(self, clock=time.time):
        self.clock = clock
        self.stall_start_ts = None
        self.last_voice_alert_ts = -1e9
        self.last_alert_status = None

    def evaluate(self, sfps=None, ping_ms=None, restarts=None, bwin=None, loss_pct=None,
                 is_in_server=True, connection_status="connected"):
        now = self.clock()
        reasons = []
        status, label, color = "UNKNOWN", "HEALTH: NO LIVE DATA", "#94a3b8"
        alert = False
        if not is_in_server:
            if connection_status == "connection_lost":
                status, label, color = "DISCONNECTED", "CONNECTION LOST", "#ef4444"
                reasons.append("The game's current remote connection closed")
                alert = True
            else:
                status, label = "STANDBY", "OFFLINE"
            self.stall_start_ts = None
        elif connection_status == "recovering":
            status, label, color = "RECOVERING", "SERVER RECOVERING", "#f59e0b"
            reasons.append("Game reported a server recovery state")
        elif sfps is not None:
            if sfps <= 0.5:
                self.stall_start_ts = self.stall_start_ts if self.stall_start_ts is not None else now
                status, label, color = "STALLED", "SERVER: STALLED", "#ef4444"
                alert = now - self.stall_start_ts >= 3
                reasons.append(f"Observed server rate {sfps:.1f} FPS")
            else:
                self.stall_start_ts = None
                if sfps < 5:
                    status, label, color = "SLOW", "SERVER: VERY SLOW", "#ef4444"
                    alert = True
                elif sfps < 15:
                    status, label, color = "SLOW", "SERVER: SLOW", "#f59e0b"
                else:
                    status, label, color = "OBSERVED", "SERVER: RESPONDING", "#48bb78"
                reasons.append(f"Observed server rate {sfps:.1f} FPS; other services may still have problems")
        else:
            self.stall_start_ts = None
        if is_in_server and loss_pct is not None and loss_pct >= 5:
            status, label, color = "PACKET_LOSS", f"NET: {loss_pct:.0f}% LOSS", "#ef4444"
            alert = True
            reasons.append("Game reported packet loss; cause may be local, on the route, or remote")
        elif is_in_server and ping_ms is not None and ping_ms >= 250:
            reasons.append(f"Game latency is high ({ping_ms:.0f} ms)")
            if status in ("UNKNOWN", "OBSERVED"):
                status, label, color = "LATENCY", "NET: HIGH LATENCY", "#f59e0b"
        if restarts is not None and restarts > 0:
            reasons.append(f"Game reports {int(restarts)} server restart(s); this alone does not predict another failure")
        should_voice = alert and now - self.last_voice_alert_ts >= 90
        if should_voice:
            self.last_voice_alert_ts = now
        self.last_alert_status = status
        return {"score": None, "status": status, "label": label, "color": color,
                "bg_color": "#171e29", "border_color": color,
                "is_alert": alert, "should_voice": should_voice,
                "voice_msg": label.replace(":", ".") if alert else "", "reasons": reasons}
