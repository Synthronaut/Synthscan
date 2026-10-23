"""Export verified references for the native UI; preserve legacy player records."""
import hashlib,json,shutil,time
from pathlib import Path
from refinery_orders import atomic_json

ROOT=Path(__file__).resolve().parent
PLAYER_FILES=['inventory.json','blueprints_library.json','blueprints_favorites.json','crafting_recipes.json',
              'fabricator_scan_inbox.json','refinery_orders.json','shard_history.json','server_log.json','mining_loadout.json']

def migrate(data_dir,root=ROOT):
    """Copy once into an isolated profile. Never modify/overwrite the originals."""
    data_dir=Path(data_dir);data_dir.mkdir(parents=True,exist_ok=True)
    from installation import RELEASE
    if RELEASE and Path(root)==ROOT:return dict(schema=1,files={},ownership='Fresh local profile; no automatic import')
    report_path=data_dir/'legacy_import.json'
    if report_path.exists():return json.loads(report_path.read_text(encoding='utf-8'))
    legacy=data_dir/'legacy';legacy.mkdir(exist_ok=True)
    records={}
    for name in PLAYER_FILES:
        source=Path(root)/name
        if not source.exists():continue
        raw=source.read_bytes();json.loads(raw.decode('utf-8'))
        target=legacy/name
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Import destination differs: '+name)
        if not target.exists():shutil.copy2(source,target)
        records[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        # The bridge owns these migrated histories. Other records stay a reviewed import.
        if name in ('shard_history.json','server_log.json','fabricator_scan_inbox.json') and not (data_dir/name).exists():
            shutil.copy2(source,data_dir/name)
    report=dict(schema=1,imported_at=time.time(),source=str(root),files=records,
                ownership='Legacy ownership retained for review; no pre-wipe unlock is silently granted',
                cargo='Legacy cargo retained separately; refinery completion never credits cargo')
    atomic_json(report_path,report)
    return report

def library_export(destination):
    from crafting_catalog import get_catalog
    from game_library import get_game_library
    c,g=get_catalog(),get_game_library()
    rows=[]
    for e in g.entries:
        if e.get('internal'):continue
        icon=g.image_path(e)
        details=f"{e['name']}\n{e['category']} · {e['type']}\n\n{e.get('description') or 'No localized description in this record.'}\n\nGame record: {e['id']}\nClient data can contain unavailable items."
        if e['kind']=='Material':
            uses=[b['name'] for b in c.items if any(s['material']==e['name'] for s in b['slots'])]
            details+='\n\nUsed to craft:\n'+'\n'.join(uses)
        rows.append(dict(id=e['id'],name=e['name'],kind=e['kind'],category=e['category'],detail=details,icon=str(icon) if icon else ''))
    for b in c.items:
        details=f"{b['name']}\n{b['category']} · {b['type']} · Size {b.get('size','?')} · Grade {b.get('grade','?')}\n\n{b.get('description','')}\n\nCraft time: {b['seconds']:g} seconds\nRecipe: {b.get('recipe_source','Reference table')}\n"
        for slot in b['slots']:
            details+=f"\n{slot['name']}: {slot['amount']:g} {slot['unit']} {slot['material']} · minimum Q{slot['min_quality']}\n"
            for effect in slot['effects']:
                details+=f"  Affects {effect['stat']} · {effect.get('better','unknown')} is better"
                if 'at_min' in effect:details+=f" · {effect['at_min']:g} at Q{effect['quality_min']} → {effect['at_max']:g} at Q{effect['quality_max']}"
                details+='\n'
        details+='\nUnlock sources (reference annotations):\n'
        if b.get('known_from_start'):details+='Known from start\n'
        if not b['sources'] and not b.get('known_from_start'):details+='No verified unlock source in the current reference.\n'
        for index in b['sources']:
            mission=c.data['missions'][index]
            details+=f"\n{mission['title']}\n{mission.get('faction','')} · {mission.get('system','')}\nStanding: {mission.get('standing','Unknown')} · cooldown {mission.get('cooldown','?')} min\n"
            details+=f"Reward chance: {mission.get('chance','?')}% · reward pool {mission.get('pool_size','?')} blueprints\n{mission.get('briefing','')}\n"
        image=g.image_path(g.resolve(b.get('item_id','')))
        rows.append(dict(id=b['id'],name=b['name'],kind='Blueprint',category=b['category'],detail=details,icon=str(image) if image else ''))
    rows.sort(key=lambda e:(e['name'].casefold(),e['id']))
    atomic_json(destination,dict(schema=1,build=g.data['provenance'].get('build'),rows=rows))
    return len(rows)

def plan_rows(targets,system='All',family='Ship'):
    from mining_planner import get_mining_planner
    planner=get_mining_planner();rows=[]
    for candidate in planner.candidates(targets,system=system,family=family):
        loc=candidate['location']
        details=f"{loc['name']} · {loc['system']} · {candidate['family']}\n\nConfigured preset weights; these are not measured live spawn rates.\n"
        for material,stats in candidate['matches'].items():
            details+=f"\n{material}: primary in {stats['primary_share']:.1%} of configured deposits; present in {stats['containing_share']:.1%}.\n"
        details+='\nRock compositions and secondaries:\n'
        for comp in planner.relevant_compositions(candidate):
            details+=f"\n{comp['name']} · configured weight {comp['weight']:.1%}\n"
            for part in comp['parts']:
                if part['probability']>0:details+=f"  {part['material']}: up to {part['max_percent']:g}% · quality scale {part['quality_scale']:g} · occurrence {part['probability']:g}\n"
        rows.append(dict(id=loc['id']+candidate['family'],name=loc['name'],category=loc['system'],kind=f"{candidate['score']:.1%} primary",detail=details,icon=''))
    return rows
