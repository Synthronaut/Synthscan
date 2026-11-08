"""Publish a complete immutable catalog generation with one atomic pointer swap."""
import hashlib
import json
import os
from pathlib import Path
import uuid

NAMES = ('local_game_catalog.json', 'local_mining_catalog.json', 'local_game_library.json')


def catalogue_path(root, name):
    if name not in NAMES: raise ValueError('Unknown reference catalogue')
    root = Path(root)
    pointer = root / 'data/catalogue_current.json'
    if not pointer.exists(): return root / 'data' / name  # Existing installs migrate on their next refresh.
    if pointer.stat().st_size > 8192: raise ValueError('Invalid catalogue pointer')
    data = json.loads(pointer.read_text(encoding='utf-8'))
    generation = data['generation']
    if not isinstance(generation, str) or len(generation) != 32 or any(c not in '0123456789abcdef' for c in generation):
        raise ValueError('Invalid catalogue generation')
    path = root / 'data/catalogues' / generation / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != data['hashes'][name]:
        raise ValueError('Reference catalogue integrity check failed')
    return path


def publish_catalogues(root, catalogues, build, guard=lambda: None):
    if set(catalogues) != set(NAMES): raise ValueError('A complete reference generation is required')
    folder = Path(root) / 'data/catalogues' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    hashes = {}
    for name in NAMES:
        raw = (json.dumps(catalogues[name], ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        (folder / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    pointer = folder.parents[1] / 'catalogue_current.json'
    prepared = folder / 'pointer.json'
    prepared.write_text(json.dumps(dict(schema=1, generation=folder.name, hashes=hashes, build=build)), encoding='utf-8')
    guard()  # Recheck the game immediately before making any of the files active.
    os.replace(prepared, pointer)
    return folder
