"""Keep existing SynthStrings blueprint pools in sync with the native library.

Library/log updates work during play. Localization is loaded by the game at
startup. Only supported reward sections and existing title tags are changed.
"""
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from localization_lock import localization_lock

HEADING = re.compile(r'<EM4>(?:Potential Blueprints|Multiple Blueprint Pools)(?:\s*\([^<]*\))?</EM4>', re.I)
ITEM = re.compile(r'^(\s*-\s*)(?:\[(?:OWNED|X|✔|\s*)\]\s*)?(.+?)(\s*)$')
# Remove category annotations, never identity such as (S1) or magazine capacity.
CATEGORY = re.compile(r'\s*\((?:Cooler|Shield|Shield Generator|Power Plant|Quantum Drive|Salvage Mod|Salvage Module|Mining Laser|Mining Head|Weapon|Armor|Clothing)\)\s*$', re.I)


def normalise_name(name):
    name = re.sub(r'<[^>]*>', '', name).replace('[BP]', '')
    name = re.sub(r'[^a-z0-9]+', ' ', name.casefold()).strip()
    return re.sub(r'^[a-z]{3} [0-9] [a-d] ', '', name)


def item_key(name):
    return normalise_name(CATEGORY.sub('', name))


def annotate_blueprint_text(text, owned_names):
    """Pure transform. Exact identities prevent substring-based false unlocks."""
    from synthstrings_sync import update_title_tag
    owned = {item_key(n) for n in owned_names}
    lines = text.splitlines(keepends=True)
    counts = {}
    desc_updates = title_updates = 0
    def key(line):
        return line.partition('=')[0].lstrip('\ufeff').split(',')[0].casefold()
    for i, line in enumerate(lines):
        left, sep, value = line.partition('=')
        heading = HEADING.search(value) if sep else None
        if not heading:
            continue
        ending = '\r\n' if value.endswith('\r\n') else '\n' if value.endswith('\n') else ''
        body = value[:-len(ending)] if ending else value
        parts = body[heading.end():].split(r'\n')
        seen, have = set(), set()
        active = True
        for j, part in enumerate(parts):
            match = ITEM.fullmatch(part) if active else None
            if match:
                name = match[2]
                identity = item_key(name)
                seen.add(identity)
                if identity in owned:
                    have.add(identity)
                parts[j] = match[1] + ('[OWNED] ' if identity in owned else '[  ] ') + name + match[3]
            elif part.strip() and not re.fullmatch(r'\s*<EM4>.*</EM4>\s*', part, re.I):
                # Explanatory prose ends the section; later instructions are
                # not blueprint rewards. Pool/region/level headings stay intact.
                active = False
        if not seen:
            continue
        counts[re.sub(r'_(?:desc|description)(?=_|$)', '_title', key(line))] = len(have), len(seen)
        updated = left + '=' + body[:heading.end()] + r'\n'.join(parts) + ending
        desc_updates += updated != line
        lines[i] = updated
    for i, line in enumerate(lines):
        if key(line) in counts:
            updated = update_title_tag(line, *counts[key(line)])
            title_updates += updated != line
            lines[i] = updated
    return ''.join(lines), dict(total_missions_with_bp=len(counts),
        complete_missions=sum(h == n for h, n in counts.values()),
        partial_missions=sum(0 < h < n for h, n in counts.values()),
        desc_updates=desc_updates, title_updates=title_updates,
        owned_blueprints_checked=len(owned_names))


def sync_blueprint_text(ini, owned_names):
    """Backup once, preserve bytes outside edited lines, replace atomically."""
    ini = Path(ini)
    with localization_lock(ini):
        before = ini.read_bytes()
        text, stats = annotate_blueprint_text(before.decode('utf-8'), owned_names)
        after = text.encode('utf-8')
        stats['changed'] = after != before
        if after == before:
            return stats
        backup = ini.with_name(ini.name + '.synthscan-blueprints.bak')
        if not backup.exists():
            shutil.copy2(ini, backup)
        descriptor, name = tempfile.mkstemp(prefix=ini.name + '.synthscan-bp-', suffix='.tmp', dir=ini.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            if ini.read_bytes() != before:
                raise ValueError('Localization changed concurrently; update will be retried')
            temporary.replace(ini)
        finally:
            temporary.unlink(missing_ok=True)
        return stats


def native_owned_names(path):
    """Native records only; missing/incomplete files must never mean zero owned."""
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Blueprint library is being written; retrying')
    owned, denied = set(), set()
    for line in raw.decode('utf-8-sig').splitlines():
        if not line or line.startswith('#'):
            continue
        fields = line.split('\t')
        if fields[0] in ('owned', 'not-owned'):
            if len(fields) < 3 or not fields[2].strip():
                raise ValueError('Incomplete blueprint record; retrying')
            (owned if fields[0] == 'owned' else denied).add(fields[2])
    denied_keys = {normalise_name(n) for n in denied}
    return {n for n in owned if normalise_name(n) not in denied_keys}


class BlueprintTextSync:
    """Poll in every HUD mode, including while the game is closed."""
    def __init__(self, directory, game_log):
        self.directory = Path(directory)
        self.game_log = Path(game_log)
        self.stamp = None
        self.next_check = 0

    def tick(self, now=None):
        from telemetry_ipc import publish_json
        now = time.time() if now is None else now
        if now < self.next_check:
            return
        self.next_check = now + 3
        channel = self.game_log.parent
        name = channel.name.upper()
        filename = 'owned_blueprints.txt' if name in ('LIVE', 'HOTFIX') else f'owned_blueprints_{name}.txt'
        library = self.directory / filename
        ini = channel / 'Data/Localization/english/global.ini'
        def stamp():
            return (library.stat().st_mtime_ns, library.stat().st_size, ini.stat().st_mtime_ns, ini.stat().st_size)
        try:
            before = stamp()
            if before == self.stamp:
                return
            owned = native_owned_names(library)
            stats = sync_blueprint_text(ini, owned)
            after = stamp()
            if after[:2] != before[:2]:
                raise ValueError('Blueprint library changed during sync; retrying')
            self.stamp = after
            publish_json(self.directory / 'blueprint_strings_status.json', dict(
                at=now, ok=True, channel=name, requires_game_text_reload=True, **stats))
        except (OSError, ValueError, TimeoutError) as exc:
            publish_json(self.directory / 'blueprint_strings_status.json', dict(at=now, ok=False, error=str(exc)))
