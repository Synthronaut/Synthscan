"""Feature identities shared by packaging, setup and service startup.

The native shell and game-data engine are shared infrastructure, not a sandbox.
Optional Python providers, capture runtime/models and feature resources are
packaged separately. No player records belong in these packages.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FEATURES = {
    'synthstrings': ('SynthStrings & Reputation', (), ('account', 'game_text'),
        'In-game text, verified corporation reputation and blueprint ownership labels.'),
    'mining_tools': ('Mining Tools', (), ('internet',),
        'Mining planner, diary, rock bookmarks, manual refinery records and value calculations.'),
    'mining_recognition': ('Live Mining Recognition', ('mining_tools',), ('screen_reading',),
        'Reads the Star Citizen window for rock signatures, composition, quality and supported refinery imports.'),
    'blueprints': ('Crafting & Blueprints', (), (),
        'Blueprint library, owned checkboxes, recipes, material quality effects and acquisition information.'),
    'item_finder': ('Item & Ship Finder', (), ('internet',),
        'Search items, ships, equipment, shops and public market listings.'),
    'server_hud': ('Server HUD', (), (),
        'The permanent region and shard ribbon, using supported background sources.'),
    'server_history': ('Server History', (), (),
        'Timestamped visits, shard identities, hop history and notes.'),
    'people': ('People', (), ('account',),
        'Player tags, relationships, presence and optional social actions.'),
    'piracy': ('Piracy', (), (),
        'Manual wait timer and available game-log reports. Does not detect every interdiction.'),
    'missions': ('Missions & Ledger', (), ('account',),
        'Contracts, durations, wallet and verified reputation changes.'),
    'hangars': ('Hangars & Compboards', (), ('internet',),
        'Executive hangar schedule estimates and your local compboard inventory.'),
    'daylight': ('Day/Night Forecast', (), (),
        'Plan daylight at a selected system, body and destination.'),
    'acceptance': ('Automatic Acceptance', (), ('automated_input',),
        'Opt-in notification helper. Sends the configured accept key to the focused game.'),
    'patch_prep': ('Patch Preparation & Staging', (), (),
        'Pre-load upcoming PTU patch builds, stage Release Candidates to LIVE, and preserve keybinds and character appearance.'),
}
RETIRED = {'notes'}  # Accept old saved selections without reinstalling retired features.
DEFAULTS = tuple(FEATURES)  # One installer, everything checked; the player opts out.
NOTICES = {
    'screen_reading': 'SCREEN READING · Captures the game window for local recognition. Screen frames are not uploaded. This is optional and adds capture/OCR components.',
    'account': 'ACCOUNT ACCESS · Uses your locally signed-in game session for supported account requests. Never asks you to share a password or token.',
    'game_text': 'GAME TEXT · Changes the managed English localization file and language setting. Recovery copies stay in AppData. A game restart loads new labels.',
    'automated_input': 'AUTOMATED INPUT · Can send keys to the focused game when you enable the helper. Disabled by default.',
    'internet': 'INTERNET · Fetches public catalogs, prices or community schedules. Availability and estimates depend on those sources.',
}


def resolve(selected):
    if not isinstance(selected, (list, tuple, set)) or any(not isinstance(v, str) or v not in FEATURES and v not in RETIRED for v in selected):
        raise ValueError('Unknown feature selection')
    result = set(selected) - RETIRED
    for feature in tuple(result):
        result.update(FEATURES[feature][1])
    return sorted(result)


def installed(root=ROOT):
    path = Path(root) / 'release.json'
    if not path.exists():
        return set(FEATURES)  # Existing development checkout.
    value = json.loads(path.read_text(encoding='utf-8'))
    selected = value.get('modules')
    if selected is None:
        result = set(FEATURES)
        if value.get('edition') == 'standard': result.discard('mining_recognition')
        return result
    resolved = resolve(selected)
    if set(resolved) != set(selected) - RETIRED: raise ValueError('Installed feature dependencies are incomplete')
    return set(resolved)


def enabled(name, root=ROOT):
    if name not in FEATURES: raise ValueError('Unknown feature')
    return name in installed(root)


def modular(root=ROOT):
    path = Path(root) / 'release.json'
    return path.exists() and json.loads(path.read_text(encoding='utf-8')).get('module_schema') == 1

