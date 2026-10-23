"""Unconfirmed screen observations survive app restarts without granting ownership."""
import json
from pathlib import Path
from refinery_orders import atomic_json


class FabricatorInbox:
    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).parent / 'fabricator_scan_inbox.json')
        self.pending = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        if not isinstance(self.pending, dict):
            raise ValueError('Unrecognized fabricator scan inbox; original preserved')

    def add(self, candidates):
        changed = False
        for candidate in candidates:
            key = candidate['id']
            if key in self.pending and self.pending[key].get('confidence', 0) >= candidate.get('confidence', 0):
                continue
            if self.pending.get(key) != candidate:
                self.pending[key] = candidate
                changed = True
        if changed:
            atomic_json(self.path, self.pending)

    def remove(self, identifiers):
        for identifier in identifiers:
            self.pending.pop(identifier, None)
        atomic_json(self.path, self.pending)
