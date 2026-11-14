"""Real-time flight telemetry, sortie tracking, and fleet flight history for Star Citizen.

Tracks active vessel, pilot helm duration, quantum jumps, combat completions, and hull incidents
using deterministic game-log engine events (ClearDriver, channel notifications, navigation).
"""

from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
import time

LOG = logging.getLogger(__name__)

MFG_MAP = {
    'DRAK': ('Drake', '#c2a649'),
    'AEGS': ('Aegis', '#3b82f6'),
    'ANVL': ('Anvil', '#60a5fa'),
    'RSI':  ('RSI', '#2563eb'),
    'ORIG': ('Origin', '#38bdf8'),
    'MISC': ('MISC', '#a855f7'),
    'CRUS': ('Crusader', '#14b8a6'),
    'ARGO': ('ARGO', '#f97316'),
    'MRAI': ('Mirai', '#ec4899'),
    'ESPR': ('Esperia', '#ef4444'),
    'BANU': ('Banu', '#eab308'),
    'AOPOA':('Aopoa', '#06b6d4'),
    'KRIG': ('Kruger', '#64748b'),
    'CO':   ('Consolidated', '#8b5cf6')
}

COMMON_HULLS = {
    'corsair': ('Drake Corsair', 'Drake', '#c2a649'),
    'cutlass': ('Drake Cutlass', 'Drake', '#c2a649'),
    'cutter': ('Drake Cutter', 'Drake', '#c2a649'),
    'caterpillar': ('Drake Caterpillar', 'Drake', '#c2a649'),
    'vulture': ('Drake Vulture', 'Drake', '#c2a649'),
    'buccaneer': ('Drake Buccaneer', 'Drake', '#c2a649'),
    'gladius': ('Aegis Gladius', 'Aegis', '#3b82f6'),
    'sabre': ('Aegis Sabre', 'Aegis', '#3b82f6'),
    'vanguard': ('Aegis Vanguard', 'Aegis', '#3b82f6'),
    'avenger': ('Aegis Avenger', 'Aegis', '#3b82f6'),
    'redeemer': ('Aegis Redeemer', 'Aegis', '#3b82f6'),
    'reclaimer': ('Aegis Reclaimer', 'Aegis', '#3b82f6'),
    'eclipse': ('Aegis Eclipse', 'Aegis', '#3b82f6'),
    'hammerhead': ('Aegis Hammerhead', 'Aegis', '#3b82f6'),
    'arrow': ('Anvil Arrow', 'Anvil', '#60a5fa'),
    'hornet': ('Anvil Hornet', 'Anvil', '#60a5fa'),
    'f7c': ('Anvil Hornet F7C', 'Anvil', '#60a5fa'),
    'f8c': ('Anvil Lightning F8C', 'Anvil', '#60a5fa'),
    'lightning': ('Anvil Lightning', 'Anvil', '#60a5fa'),
    'pisces': ('Anvil Pisces', 'Anvil', '#60a5fa'),
    'c8r': ('Anvil Pisces C8R', 'Anvil', '#60a5fa'),
    'carrack': ('Anvil Carrack', 'Anvil', '#60a5fa'),
    'valkyrie': ('Anvil Valkyrie', 'Anvil', '#60a5fa'),
    'constellation': ('RSI Constellation', 'RSI', '#2563eb'),
    'andromeda': ('RSI Constellation Andromeda', 'RSI', '#2563eb'),
    'taurus': ('RSI Constellation Taurus', 'RSI', '#2563eb'),
    'aquila': ('RSI Constellation Aquila', 'RSI', '#2563eb'),
    'phoenix': ('RSI Constellation Phoenix', 'RSI', '#2563eb'),
    'mantis': ('RSI Mantis', 'RSI', '#2563eb'),
    'aurora': ('RSI Aurora', 'RSI', '#2563eb'),
    'scorpius': ('RSI Scorpius', 'RSI', '#2563eb'),
    'zeus': ('RSI Zeus', 'RSI', '#2563eb'),
    'polaris': ('RSI Polaris', 'RSI', '#2563eb'),
    '890jump': ('Origin 890 Jump', 'Origin', '#38bdf8'),
    '600i': ('Origin 600i', 'Origin', '#38bdf8'),
    '400i': ('Origin 400i', 'Origin', '#38bdf8'),
    '300i': ('Origin 300i', 'Origin', '#38bdf8'),
    '325a': ('Origin 325a', 'Origin', '#38bdf8'),
    '100i': ('Origin 100i', 'Origin', '#38bdf8'),
    '125a': ('Origin 125a', 'Origin', '#38bdf8'),
    '135c': ('Origin 135c', 'Origin', '#38bdf8'),
    'm50': ('Origin M50', 'Origin', '#38bdf8'),
    'prospector': ('MISC Prospector', 'MISC', '#a855f7'),
    'freelancer': ('MISC Freelancer', 'MISC', '#a855f7'),
    'reliant': ('MISC Reliant', 'MISC', '#a855f7'),
    'hull a': ('MISC Hull A', 'MISC', '#a855f7'),
    'hull c': ('MISC Hull C', 'MISC', '#a855f7'),
    'starlifter': ('Crusader Starlifter', 'Crusader', '#14b8a6'),
    'c2': ('Crusader C2 Hercules', 'Crusader', '#14b8a6'),
    'a2': ('Crusader A2 Hercules', 'Crusader', '#14b8a6'),
    'm2': ('Crusader M2 Hercules', 'Crusader', '#14b8a6'),
    'ares': ('Crusader Ares', 'Crusader', '#14b8a6'),
    'ion': ('Crusader Ares Ion', 'Crusader', '#14b8a6'),
    'inferno': ('Crusader Ares Inferno', 'Crusader', '#14b8a6'),
    'mercury': ('Crusader Mercury Star Runner', 'Crusader', '#14b8a6'),
    'msr': ('Crusader Mercury Star Runner', 'Crusader', '#14b8a6'),
    'spirit': ('Crusader Spirit', 'Crusader', '#14b8a6'),
    'c1': ('Crusader C1 Spirit', 'Crusader', '#14b8a6'),
    'a1': ('Crusader A1 Spirit', 'Crusader', '#14b8a6'),
    'mole': ('ARGO MOLE', 'ARGO', '#f97316'),
    'raft': ('ARGO RAFT', 'ARGO', '#f97316'),
    'srv': ('ARGO SRV', 'ARGO', '#f97316'),
    'fury': ('Mirai Fury', 'Mirai', '#ec4899'),
    'guardian': ('Mirai Guardian', 'Mirai', '#ec4899'),
    'merlin': ('Kruger P-52 Merlin', 'Kruger', '#64748b'),
    'archimedes': ('Kruger P-72 Archimedes', 'Kruger', '#64748b'),
    'nomad': ('C.O. Nomad', 'Consolidated', '#8b5cf6')
}


def resolve_ship_identity(raw):
    raw_clean = str(raw).strip()
    m = re.match(r'^([A-Z]+)_([A-Za-z0-9]+)(?:_([A-Za-z0-9_]+?))?(?:_\d+)?$', raw_clean)
    if m:
        mfg_code, model, variant = m.groups()
        mfg_name, color = MFG_MAP.get(mfg_code.upper(), (mfg_code, "#62ccff"))
        var_clean = ""
        if variant and not variant.isdigit():
            v = variant.replace('ShipATCDataManager', '').replace('StealthIndustrial', '').replace('GS_Rear', '')
            v = re.sub(r'_\d+', '', v).strip('_')
            if v.lower() == 'exec':
                var_clean = "Executive"
            elif v:
                var_clean = v.replace('_', ' ')
        disp = f"{model} ({var_clean})" if var_clean else model
        return f"{mfg_name} {disp}", mfg_name, color

    raw_lower = raw_clean.lower()
    for key, (full_name, mfg, col) in COMMON_HULLS.items():
        if key in raw_lower:
            if 'exec' in raw_lower:
                return f"{full_name} (Executive)", mfg, col
            return full_name, mfg, col

    return raw_clean, "Unknown", "#62ccff"


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as s:
            json.dump(data, s, indent=2, ensure_ascii=False)
            s.flush()
            os.fsync(s.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class FlightTracker:
    """Tails Star Citizen's Game.log incrementally to track real-time sorties and fleet history."""
    def __init__(self, directory=None, log_path=None):
        self.directory = Path(directory) if directory else None
        self.history_path = (self.directory / "flight_history.json") if self.directory else None
        if log_path is not None:
            self.log_path = str(log_path)
        elif self.directory is not None:
            self.log_path = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"
        else:
            self.log_path = ""
        self.last_pos = 0
        self._file_identity = None
        self._pending = b""
        
        self.active_sortie = None
        self.sorties = []
        self.current_state = "ON_FOOT"  # ON_FOOT, BOARDED, IN_FLIGHT
        self.last_activity_at = 0
        self.active_route = ""
        self.jurisdiction = "Unknown"
        self.monitored = None
        self.entitlements = 0
        self.load()
        if self.log_path:
            self.poll()

    def load(self):
        if self.history_path and self.history_path.exists():
            try:
                data = json.loads(self.history_path.read_text(encoding="utf-8"))
                if data.get("schema") == 1 and isinstance(data.get("sorties"), list):
                    self.sorties = data["sorties"]
            except Exception:
                LOG.exception("Could not load flight history")

    def save(self):
        if not self.history_path:
            return
        try:
            atomic_json(self.history_path, {
                "schema": 1,
                "sorties": self.sorties[-150:]
            })
        except Exception:
            LOG.exception("Could not save flight history")

    def poll(self):
        if not self.log_path:
            return
        try:
            stat = os.stat(self.log_path)
            identity = (stat.st_dev, stat.st_ino)
            if self._file_identity is not None and (identity != self._file_identity or stat.st_size < self.last_pos):
                self.last_pos = 0
                self._pending = b""
                if self.active_sortie:
                    self._close_sortie(time.time(), "Game Restarted")
            self._file_identity = identity
            with open(self.log_path, "rb") as stream:
                stream.seek(self.last_pos)
                chunk = stream.read(1024 * 1024)
                self.last_pos = stream.tell()
            if chunk:
                self.feed(chunk)
        except (FileNotFoundError, OSError):
            pass

    def feed(self, chunk):
        self._pending += chunk
        lines = self._pending.split(b"\n")
        self._pending = lines.pop()
        for raw in lines:
            self._parse_line(raw.decode("utf-8", errors="replace").rstrip("\r"))

    def _parse_line(self, line):
        tm = re.match(r"^<([^>]+)>", line)
        if not tm:
            return
        ts_str = tm.group(1)
        try:
            at = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            at = time.time()

        # 1. Ship Channel Join (Boarding)
        m = re.search(r'Added notification \"You have joined channel \'([^\']+)\'', line)
        if m:
            ch = m.group(1)
            parts = ch.split(" : ")
            ship_raw = parts[0].strip()
            # If not already aboard this exact ship, initialize new sortie
            if not self.active_sortie or ship_raw.lower() not in self.active_sortie['ship_name'].lower():
                if self.active_sortie:
                    self._close_sortie(at, "Disembarked (Switched Vessel)")
                full_name, mfg, color = resolve_ship_identity(ship_raw)
                self.active_sortie = {
                    "ship_name": full_name,
                    "mfg": mfg,
                    "color": color,
                    "boarded_at": at,
                    "helm_start": None,
                    "helm_seconds": 0,
                    "ended_at": None,
                    "quantum_jumps": 0,
                    "routes_plotted": 0,
                    "contracts_completed": 0,
                    "incident": None,
                    "status": "BOARDED",
                    "departure_time": datetime.fromtimestamp(at, timezone.utc).astimezone().strftime("%H:%M")
                }
                self.current_state = "BOARDED"
                self.last_activity_at = at

        # 2. Pilot Control / Navigation Actions (Sitting at Helm & Flying)
        if '<Calculate Route>' in line or '<Player Selected Quantum Target' in line:
            self.last_activity_at = at
            dest_match = re.search(r"Calculate Route to '([^']+)'", line)
            dest = dest_match.group(1).strip() if dest_match else ""
            if dest:
                self.active_route = dest
            m_ship = re.search(r'\|\s*([A-Za-z0-9_]+)\[\d+\]', line)
            ship_entity = m_ship.group(1) if m_ship else ""
            if not self.active_sortie:
                full_name, mfg, color = resolve_ship_identity(ship_entity if ship_entity else "Starship")
                self.active_sortie = {
                    "ship_name": full_name,
                    "mfg": mfg,
                    "color": color,
                    "boarded_at": at,
                    "helm_start": at,
                    "helm_seconds": 0,
                    "ended_at": None,
                    "quantum_jumps": 0,
                    "routes_plotted": 1,
                    "contracts_completed": 0,
                    "destination": dest,
                    "incident": None,
                    "status": "IN_FLIGHT",
                    "departure_time": datetime.fromtimestamp(at, timezone.utc).astimezone().strftime("%H:%M")
                }
                self.current_state = "IN_FLIGHT"
            else:
                self.active_sortie['routes_plotted'] += 1
                if dest:
                    self.active_sortie['destination'] = dest
                if self.current_state != "IN_FLIGHT":
                    self.current_state = "IN_FLIGHT"
                    self.active_sortie['status'] = "IN_FLIGHT"
                    if self.active_sortie['helm_start'] is None:
                        self.active_sortie['helm_start'] = at

        # 3. Quantum Destination Arrival
        if 'Quantum Drive Arrived - Arrived at Final Destination' in line:
            self.last_activity_at = at
            self.active_route = ""
            if self.active_sortie:
                self.active_sortie['quantum_jumps'] += 1

        # 3b. Jurisdiction / Comm-Array Transitions (Game.log deterministic signals)
        if 'Entered Ungoverned Jurisdiction' in line or 'Entered Unmonitored Space' in line:
            self.jurisdiction = "Ungoverned"
            self.monitored = False
        elif 'Entered Monitored Space' in line or 'Entered UEE Jurisdiction' in line:
            self.jurisdiction = "UEE Monitored"
            self.monitored = True

        # 3c. Fleet Entitlement Count
        if '<VehicleListQuery>' in line:
            m_ent = re.search(r'Retrieved\s+(\d+)\s+entitlements', line)
            if m_ent:
                self.entitlements = int(m_ent.group(1))

        # 4. ClearDriver (Standing up from pilot seat)
        if 'CVehicleMovementBase::ClearDriver' in line:
            self.last_activity_at = at
            if self.active_sortie:
                if self.active_sortie['helm_start'] is not None:
                    elapsed = max(0, at - self.active_sortie['helm_start'])
                    self.active_sortie['helm_seconds'] += elapsed
                    self.active_sortie['helm_start'] = None
                self.current_state = "BOARDED"
                self.active_sortie['status'] = "BOARDED"

        # 5. Contract Complete while in flight
        if 'Added notification "Contract Complete:' in line:
            if self.active_sortie:
                self.active_sortie['contracts_completed'] += 1

        # 6. Fatal Collision
        if '<FatalCollision> Fatal Collision occured for vehicle' in line:
            if self.active_sortie:
                self.active_sortie['incident'] = "Fatal Collision"
                self._close_sortie(at, "Hull Destroyed (Collision)")

        # 7. Death
        if '<[ActorState] Dead>' in line:
            if self.active_sortie:
                if not self.active_sortie['incident']:
                    self.active_sortie['incident'] = "K.I.A."
                self._close_sortie(at, "Pilot K.I.A.")

        # 8. Station Inventory Request (Definitive Station Disembark)
        if 'requested inventory for Location[' in line:
            if self.active_sortie:
                self._close_sortie(at, "Landed & Disembarked")

        # 9. Disconnect / Lobby Quit
        if any(term in line for term in ("RequestQuitLobby", "Connection closed", "Client disconnected")):
            if self.active_sortie:
                self._close_sortie(at, "Disconnected")

    def _close_sortie(self, at, reason):
        if not self.active_sortie:
            return
        if self.active_sortie['helm_start'] is not None:
            self.active_sortie['helm_seconds'] += max(0, at - self.active_sortie['helm_start'])
            self.active_sortie['helm_start'] = None
        self.active_sortie['ended_at'] = at
        self.active_sortie['boarded_seconds'] = max(0, at - self.active_sortie['boarded_at'])
        self.active_sortie['end_reason'] = reason
        self.active_sortie['status'] = "COMPLETED"
        # Only retain sorties with measurable aboard duration (> 5 seconds)
        if self.active_sortie['boarded_seconds'] > 5 or self.active_sortie['helm_seconds'] > 0:
            self.sorties.append(self.active_sortie)
            self.save()
        self.active_sortie = None
        self.current_state = "ON_FOOT"
        self.active_route = ""

    def tick(self, now=None):
        self.poll()
        return self.summary(now)

    def summary(self, now=None):
        now = time.time() if now is None else now
        fleet = {}
        for s in self.sorties:
            name = s['ship_name']
            f = fleet.setdefault(name, {
                'name': name, 'mfg': s['mfg'], 'color': s['color'],
                'sorties': 0, 'seconds': 0, 'jumps': 0, 'contracts': 0, 'losses': 0
            })
            f['sorties'] += 1
            f['seconds'] += int(s['helm_seconds'])
            f['jumps'] += s['quantum_jumps']
            f['contracts'] += s['contracts_completed']
            if s.get('incident'):
                f['losses'] += 1

        active = None
        active_ship_name = "--"
        active_mfg = "--"
        active_color = "#62ccff"
        active_helm_s = 0
        active_boarded_s = 0
        active_jumps = 0
        active_contracts = 0

        if self.active_sortie:
            s = dict(self.active_sortie)
            helm_sec = s['helm_seconds']
            if s['helm_start'] is not None:
                helm_sec += max(0, now - s['helm_start'])
            boarded_sec = max(0, now - s['boarded_at'])
            active_ship_name = s['ship_name']
            active_mfg = s['mfg']
            active_color = s['color']
            active_helm_s = int(helm_sec)
            active_boarded_s = int(boarded_sec)
            active_jumps = s['quantum_jumps']
            active_contracts = s['contracts_completed']
            active = s

            # Incorporate live sortie into fleet metrics
            name = s['ship_name']
            f = fleet.setdefault(name, {
                'name': name, 'mfg': s['mfg'], 'color': s['color'],
                'sorties': 0, 'seconds': 0, 'jumps': 0, 'contracts': 0, 'losses': 0
            })
            f['sorties'] += 1
            f['seconds'] += int(helm_sec)
            f['jumps'] += s['quantum_jumps']
            f['contracts'] += s['contracts_completed']

        total_helm = sum(f['seconds'] for f in fleet.values())
        sorted_fleet = sorted(fleet.values(), key=lambda x: -x['seconds'])
        for f in sorted_fleet:
            f['pct'] = int(round((f['seconds'] / total_helm * 100))) if total_helm > 0 else 0

        recent_formatted = []
        for s in reversed(self.sorties[-15:]):
            recent_formatted.append({
                'ship': s['ship_name'],
                'mfg': s['mfg'],
                'color': s.get('color', '#62ccff'),
                'duration_s': int(s['helm_seconds']),
                'jumps': s['quantum_jumps'],
                'contracts': s['contracts_completed'],
                'destination': s.get('destination', ''),
                'incident': s.get('incident') or "",
                'reason': s.get('end_reason', 'Landed'),
                'time': s.get('departure_time', '--:--')
            })

        return {
            'state': self.current_state,
            'active_ship': active_ship_name,
            'active_mfg': active_mfg,
            'active_color': active_color,
            'active_helm_s': active_helm_s,
            'active_boarded_s': active_boarded_s,
            'active_jumps': active_jumps,
            'active_contracts': active_contracts,
            'active_route': self.active_route,
            'jurisdiction': self.jurisdiction,
            'monitored': self.monitored,
            'entitlements': self.entitlements,
            'total_sorties': len(self.sorties) + (1 if self.active_sortie else 0),
            'total_helm_s': total_helm,
            'total_jumps': sum(f['jumps'] for f in fleet.values()),
            'total_contracts': sum(f['contracts'] for f in fleet.values()),
            'total_losses': sum(f['losses'] for f in fleet.values()),
            'fleet': sorted_fleet[:12],
            'recent': recent_formatted
        }
