"""Compact, read-only game encyclopedia. Extraction never runs on the UI thread."""
from functools import lru_cache
import json
from pathlib import Path
from installation import output_root, game_directory

ROOT = Path(__file__).resolve().parent


class GameLibrary:
    def __init__(self, path=None):
        self.path = Path(path or output_root() / 'data/local_game_library.json')
        self.error = ''
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(self.data, dict) or not isinstance(self.data.get('entries'), list)
                    or not isinstance(self.data.get('assets'), dict) or not isinstance(self.data.get('provenance'), dict)):
                raise ValueError('Invalid game library structure')
            required = {'id', 'name', 'kind', 'type', 'category', 'artwork'}
            if any(not isinstance(e, dict) or not required.issubset(e) for e in self.data['entries']):
                raise ValueError('Invalid game library entry')
            if len({e['id'] for e in self.data['entries']}) != len(self.data['entries']):
                raise ValueError('Duplicate game record identity')
        except (OSError, ValueError, TypeError) as exc:
            self.data = dict(entries=[], assets={}, provenance={})
            self.error = str(exc)
        self.entries = self.data['entries']
        self.by_id = {e['id']: e for e in self.entries}
        self.by_name = {}
        for entry in self.entries:
            self.by_name.setdefault(entry['name'].casefold(), []).append(entry)
        self.matches_installation = False
        try:
            manifest = json.loads((game_directory()/'build_manifest.id').read_text())
            self.matches_installation = manifest['Data']['BuildId'] == self.data['provenance']['build']['BuildId']
        except (OSError, ValueError, KeyError):
            pass

    def resolve(self, value, kind=None):
        if value in self.by_id:
            entry = self.by_id[value]
            return entry if kind is None or entry['kind'] == kind else None
        candidates = [e for e in self.by_name.get(str(value).casefold(), []) if kind is None or e['kind'] == kind]
        return candidates[0] if len(candidates) == 1 else None

    def query(self, search='', kind='All', category='All', artwork_only=False, include_internal=False):
        words = search.casefold().split()
        result = []
        for entry in self.entries:
            if entry.get('internal') and not include_internal:
                continue
            if kind != 'All' and entry['kind'] != kind:
                continue
            if category != 'All' and entry['category'] != category:
                continue
            if artwork_only and not entry.get('artwork'):
                continue
            haystack = ' '.join(str(entry.get(k, '')) for k in ('name', 'description', 'type', 'manufacturer', 'tag', 'category')).casefold()
            if all(w in haystack for w in words):
                result.append(entry)
        return sorted(result, key=lambda e: (e['name'].casefold(), e['id']))

    def image_path(self, entry):
        if not entry:
            return None
        for key in entry.get('artwork', []):
            asset = self.data.get('assets', {}).get(key)
            if asset:
                path = (output_root() / asset['file']).resolve()
                if path.is_relative_to((output_root() / 'assets/game').resolve()) and path.is_file():
                    return path
        return None


@lru_cache(maxsize=1)
def get_game_library():
    return GameLibrary()


class ArtworkImages:
    """Per-view CTk images; references live with widgets, with bounded decoded cache."""
    def __init__(self, library=None):
        self.library = library or get_game_library()
        self.cache = {}

    def get(self, entry, size=48):
        path = self.library.image_path(entry)
        if path is None:
            return None
        key = (path, size)
        if key not in self.cache:
            from PIL import Image, ImageOps
            import customtkinter as ctk
            try:
                with Image.open(path) as source:
                    picture = ImageOps.contain(source.convert('RGBA'), (size, size))
                image = ctk.CTkImage(picture, picture, size=picture.size)
            except (OSError, ValueError):
                return None
            if len(self.cache) >= 160:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = image
        return self.cache[key]

    def blueprint(self, bp, size=48):
        return self.get(self.library.resolve(bp.get('item_id', ''), 'Item'), size)

    def material(self, name, size=40):
        return self.get(self.library.resolve(name, 'Material'), size)
