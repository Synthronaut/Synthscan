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

def library_export(destination,game=None,catalog=None,extra_rows=()):
    from directory_audit import display_name,validate
    from crafting_catalog import get_catalog
    from game_library import get_game_library
    from item_directory import source_lines,is_component
    c,g=catalog or get_catalog(),game or get_game_library()
    build=g.data['provenance'].get('build') or {}
    catalog_label='\n\nCatalog: '+str(build.get('Branch','unknown patch'))+' · build '+str(build.get('RequestedP4ChangeNum','unknown'))
    by_item={}
    material_uses={}
    baseline=json.loads((ROOT/'data/crafting_catalog.json').read_text(encoding='utf-8'))['blueprints']
    baseline_indices={bp['id']:(index,bp['name']) for index,bp in enumerate(baseline)}
    def finder_blueprints(linked):
        result=[]
        for bp in linked:
            index,reference_name=baseline_indices.get(bp['id'],(-1,''))
            result.append(dict(name=bp['name'],reference_index=index,reference_name=reference_name,
                known_from_start=bp.get('known_from_start',False),recipe_verified=bp.get('native_verified',False),
                materials=[dict(material=s['material'],amount=s['amount'],unit=s['unit'],min_quality=s['min_quality']) for s in bp['slots']],
                missions=[dict(title=m.get('title','Unknown'),faction=m.get('faction',''),system=m.get('system',''),standing=m.get('standing','')) for m in c.sources(bp)],
                unlock_source=bp.get('unlock_source','Older bundled reference')))
        return result
    for blueprint in c.items:
        if not display_name(blueprint.get('name')):continue
        if blueprint.get('item_id'):by_item.setdefault(blueprint['item_id'],[]).append(blueprint)
        for slot in blueprint['slots']:material_uses.setdefault(slot['material'],set()).add(blueprint['name'])
    rows=[]
    public_blueprints=[b for b in c.items if display_name(b.get('name'))]
    excluded=[dict(id=b.get('id'),reason='Unresolved blueprint display name',native_tag=b.get('native_tag','')) for b in c.items if not display_name(b.get('name'))]
    for e in g.entries:
        if e.get('internal') or not display_name(e.get('name')):continue
        icon=g.image_path(e)
        linked=by_item.get(e['id'],[])
        details=f"{e['name']}\n{e['category']} · {e['type']}\n\nCRAFTING & BLUEPRINTS\n"
        if not linked:details+='No linked creation blueprint in this catalog. This does not prove the item cannot be crafted.\n'
        for blueprint in linked:
            details+=f"\n{blueprint['name']} — blueprint\nRecipe: {blueprint.get('recipe_source','Reference table')}\n"
            details+='\n'.join(source_lines(blueprint,c))+'\n'
            details+='Search this name with Type = Blueprint to see ingredients and reward-pool details.\n'
        details+=f"\nDESCRIPTION\n{e.get('description') or 'No localized description in this record.'}\n\nGame record: {e['id']}\nGame-file presence alone does not guarantee availability."
        if e['kind']=='Material':
            uses=sorted(material_uses.get(e['name'],[]))
            details+='\n\nUsed to craft:\n'+'\n'.join(uses)
        rows.append(dict(id=e['id'],item_id=e['id'] if e['kind']=='Item' else '',name=e['name'],kind='Component' if is_component(e) else e['kind'],category=e['category'],detail=details+catalog_label,icon=str(icon) if icon else '',
                         finder_blueprints=finder_blueprints(linked),item_type=e.get('type',''),item_record=e.get('record',''),weapon_stats=e.get('weapon_stats',{}),
                         search=' '.join([e['name'],e['category'],e['type'],e.get('manufacturer',''),*[m.get(k,'') for b in linked for m in c.sources(b) for k in ('title','faction','system')]])))
    game_by_id={e['id']:e for e in g.entries}
    for b in public_blueprints:
        details=f"{b['name']}\n{b['category']} · {b['type']} · Size {b.get('size','?')} · Grade {b.get('grade','?')}\n\nBLUEPRINT UNLOCK SOURCES\n"
        details+='\n'.join(source_lines(b,c,briefings=True))+'\n'
        details+=f"\nCRAFTING RECIPE\nCraft time: {b['seconds']:g} seconds\nRecipe: {b.get('recipe_source','Reference table')}\n"
        for slot in b['slots']:
            details+=f"\n{slot['name']}: {slot['amount']:g} {slot['unit']} {slot['material']} · minimum Q{slot['min_quality']}\n"
            for effect in slot['effects']:
                details+=f"  Affects {effect['stat']} · {effect.get('better','unknown')} is better"
                if 'at_min' in effect:details+=f" · {effect['at_min']:g} at Q{effect['quality_min']} → {effect['at_max']:g} at Q{effect['quality_max']}"
                details+='\n'
        details+='\nDESCRIPTION\n'+b.get('description','')+'\n'
        image=g.image_path(g.resolve(b.get('item_id','')))
        rows.append(dict(id=b['id'],item_id=b.get('item_id',''),name=b['name'],kind='Blueprint',category=b['category'],detail=details+catalog_label,icon=str(image) if image else '',
                         finder_blueprints=finder_blueprints([b]),weapon_stats=game_by_id.get(b.get('item_id'),{}).get('weapon_stats',{}),
                         search=c.search_text.get(b['id'],b['name'])))
    for row in extra_rows:
        if display_name(row.get('name')):rows.append(row)
        else:excluded.append(dict(id=row.get('id'),reason='Unresolved external display name'))
    rows.sort(key=lambda e:(e['name'].casefold(),e['id']))
    atomic_json(destination,dict(schema=2,build=g.data['provenance'].get('build'),rows=rows,audit=validate(rows),excluded_records=excluded))
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
