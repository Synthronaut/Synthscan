"""Read-only access to StarBreaker's JSON export and packaged localization.

No game process access and no writes to the installation. References are
resolved only inside the explicitly selected export directory.
"""
from functools import lru_cache
import json
from pathlib import Path
import re


MANUFACTURER_NAMES = {
    'KSAR': 'Kastak Arms',
    'BEHR': 'Behring',
    'BEH': 'Behring',
    'KLWE': 'Klaus & Werner',
    'KLA': 'Klaus & Werner',
    'GEMI': 'Gemini',
    'GEM': 'Gemini',
    'APAR': 'Apocalypse Arms',
    'GATS': 'Gallenson Tactical Systems',
    'GAT': 'Gallenson Tactical Systems',
    'GRIN': 'Greycat Industrial',
    'HDGW': 'Hedeby Gunworks',
    'UTFL': 'UltiFlex',
    'JOKP': 'Joker Engineering',
    'JOK': 'Joker Engineering',
    'KBAR': 'KnightBridge Arms',
    'KRI': 'Kruger Intergalactic',
    'KRON': 'Kroneg',
    'MXOX': 'MaxOx',
    'AMRS': 'Amon & Reese Co.',
    'ANVL': 'Anvil Aerospace',
    'AEGS': 'Aegis Dynamics',
    'AEG': 'Aegis Dynamics',
    'DRAK': 'Drake Interplanetary',
    'CRUS': 'Crusader Industries',
    'ARGO': 'Argo Astronautics',
    'CNOU': 'Consolidated Outland',
    'RSI': 'Roberts Space Industries',
    'MISC': 'Musashi Industrial & Starflight Concern',
    'MIS': 'Musashi Industrial & Starflight Concern',
    'ORIG': 'Origin Jumpworks',
    'ESPR': 'Esperia',
    'TMBL': 'Tumbril Land Systems',
    'VNCL': 'Vanduul',
    'VNC': 'Vanduul',
    'BANU': 'Banu',
    'AOPOA': 'Aopoa',
    'XNAA': 'Aopoa',
    'GATA': 'Gatac Manufacture',
    'GAM': 'Gatac Manufacture',
    'VOLK': 'Volker',
    'CHAS': 'Cascadia Heavy Armaments',
    'PREP': 'Preacher Armament',
    'HURT': 'Hurston Dynamics',
    'HRST': 'Hurston Dynamics',
    'ASD': 'Associated Science and Development',
    'ASAD': 'Associated Science and Development',
    'CDS': 'Clark Defense Systems',
}


def walk_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_nodes(child)


class GameRecords:
    def __init__(self, root, localization):
        self.root = Path(root).resolve()
        self.localization = {}
        for line in Path(localization).read_text(encoding='utf-8-sig', errors='replace').splitlines():
            key, sep, value = line.partition('=')
            if sep:
                self.localization[key.strip().split(',')[0].casefold()] = value.strip()
        custom = Path(__file__).resolve().parent / 'data/custom_synthstrings.json'
        if custom.exists():
            try:
                for k, v in json.loads(custom.read_text(encoding='utf-8')).items():
                    ck = k.casefold()
                    if ck not in self.localization or not self.localization[ck]:
                        self.localization[ck] = v
            except Exception:
                pass
        self.used = set()
        self.resources = {}
        resource_path = self.root / 'libs/foundry/records/resourcetypedatabase/resourcetypedatabase.json'
        for node in walk_nodes(self.read(resource_path)):
            if node.get('_Type_') == 'ResourceType' and node.get('_RecordId_'):
                self.resources[node['_RecordId_']] = node

    @lru_cache(maxsize=128)
    def read(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Record reference leaves the export directory')
        self.used.add(path)
        return json.loads(path.read_text(encoding='utf-8'))

    def reference_path(self, reference):
        if isinstance(reference, dict):
            reference = reference.get('_RecordPath_')
        if not isinstance(reference, str):
            raise ValueError('Missing game-record reference')
        match = re.search(r'(?:^|/)libs/foundry/records/(.+)$', reference.replace('\\', '/'), re.I)
        if not match:
            raise ValueError('Unrecognized game-record reference: ' + reference)
        return self.root / 'libs/foundry/records' / match[1]

    def resolve(self, reference):
        return self.read(self.reference_path(reference))

    def value(self, reference):
        return self.resolve(reference)['_RecordValue_']

    def text(self, key, fallback=''):
        if not key:
            return fallback
        text = self.localization.get(key.lstrip('@').casefold(), fallback)
        if text in ('', 'PLACEHOLDER', 'UNINITIALIZED'):
            return fallback
        return re.sub(r'<[^>]+>', '', text).replace('\\n', '\n').strip()

    def resource_name(self, reference, refined=False):
        guid = reference.get('_RecordId_')
        resource = self.resources[guid]
        visited = set()
        while refined and resource.get('refinedVersion'):
            if resource['_RecordId_'] in visited:
                raise ValueError('Cyclic refined-resource reference')
            visited.add(resource['_RecordId_'])
            resource = resource['refinedVersion']
        return self.text(resource['displayName'], resource['_RecordName_'].split('.', 1)[-1])

    def item(self, reference):
        record = self.resolve(reference)
        components = [c for c in record['_RecordValue_'].get('Components', []) if isinstance(c, dict)]
        attach = next((c['AttachDef'] for c in components if c.get('_Type_') == 'SAttachableComponentParams'), {})
        loc = attach.get('Localization') or next((n for n in walk_nodes(components) if n.get('_Type_') == 'SCItemLocalization'), {})
        name = self.text(loc.get('Name'))
        name = re.sub(r'^[A-Za-z]{2,5}/[\dSs]+/[A-Da-d]\s+', '', name)
        maker = self.value(attach['Manufacturer']) if attach.get('Manufacturer') else {}
        maker_code = maker.get('Code', '')
        maker_loc = maker.get('Localization', {}) if isinstance(maker, dict) else {}
        maker_name = self.text(maker_loc.get('Name')) if maker_loc else ''
        if not maker_name and maker_code:
            maker_name = MANUFACTURER_NAMES.get(maker_code.upper(), '')
        if maker_name and maker_code and maker_name != maker_code:
            manufacturer = f"{maker_name} ({maker_code})"
        else:
            manufacturer = maker_name or maker_code
        return dict(guid=record['_RecordId_'], name=name,
                    description=self.text(loc.get('Description')),
                    type=attach.get('Type'), size=attach.get('Size'), grade=attach.get('Grade'),
                    manufacturer=manufacturer, components=components)
