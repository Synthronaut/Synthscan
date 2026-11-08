"""Version-matched SCMDB JSON imports; public data only, never website code."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.request
import uuid

from telemetry_ipc import publish_json,read_shared_json

BASE='https://scmdb.net/data/'
INTERVAL=6*3600
RETRY=300
FILES=('crafting_blueprints','merged','mining_equipment')


def read_json(path,limit=32*1024*1024):
    return read_shared_json(path,limit=limit)


def fetch_json(name,limit=32*1024*1024):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+\.json',name):raise ValueError('Invalid reference resource')
    request=urllib.request.Request(BASE+name,headers={'User-Agent':'SynthScan-References/1.0','Accept':'application/json','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=15) as response:
        if not response.geturl().startswith(BASE):raise ValueError('Unexpected reference source redirect')
        raw=response.read(limit+1)
    if len(raw)>limit:raise ValueError('Reference resource exceeds limit')
    from update_signing import strict_json
    return strict_json(raw),hashlib.sha256(raw).hexdigest()


def installed_version(game=None):
    from installation import game_directory
    game=Path(game) if game else game_directory(True)
    build=read_json(game/'build_manifest.id')['Data']
    found=re.search(r'(\d+\.\d+\.\d+)',str(build.get('Branch','')))
    number=str(build.get('RequestedP4ChangeNum',''));tag=str(build.get('Tag','')).lower()
    if not found or not number.isdigit():raise ValueError('Cannot identify installed game data version')
    channel='ptu' if 'ptu' in tag or game.name.upper() in ('PTU','EPTU') else 'live' if tag in ('public','live') else None
    if channel is None:raise ValueError('Game channel is not supported by the reference source')
    return found[1]+'-'+channel+'.'+number,build['BuildId']


def guid(value):return str(uuid.UUID(value))


def number(value,low=-10000,high=10000):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid reference number')
    return value


def normalize_annotations(blueprints,merged,checked,version):
    records={};missions=[]
    if not isinstance(blueprints.get('blueprints'),list) or not isinstance(merged.get('contracts'),list) or not isinstance(merged.get('blueprintPools'),dict):raise ValueError('SCMDB annotation schema changed')
    if (blueprints.get('meta') or {}).get('totalBlueprints')!=len(blueprints['blueprints']):raise ValueError('Incomplete blueprint reference')
    for blueprint in blueprints['blueprints']:
        key=guid(blueprint['guid'])
        if key in records:raise ValueError('Duplicate blueprint identity')
        default=blueprint.get('isDefault',False)
        if not isinstance(default,bool):raise ValueError('Invalid default blueprint flag')
        records[key]=dict(sources=[],known_from_start=default)
    if len(records)<1:raise ValueError('Empty blueprint reference')
    pools=merged['blueprintPools']
    for contract in merged['contracts']:
        for reward in contract.get('blueprintRewards') or []:
            pool_id=guid(reward['blueprintPool']);pool=pools.get(pool_id)
            if not pool or not isinstance(pool.get('blueprints'),list):raise ValueError('Missing blueprint reward pool')
            chance=number(reward['chance'],0,1)*100;trigger=reward.get('trigger')
            if trigger not in ('accept','complete'):raise ValueError('Unknown blueprint reward trigger')
            members=[guid(item['blueprintRecord']) for item in pool['blueprints'] if number(item['weight'],0,1e9)>0]
            if not members or chance==0:continue
            systems=contract.get('availableSystems') or contract.get('systems') or []
            if not isinstance(systems,list) or any(not isinstance(s,str) for s in systems):raise ValueError('Invalid mission systems')
            title=str(contract.get('title') or contract.get('debugName') or 'Unknown mission')
            if trigger=='accept':title+=' (reward on acceptance)'
            mission=dict(title=title,faction=str(contract.get('contractorName') or 'Unknown'),system=', '.join(systems) or 'Unknown',
                standing=str((contract.get('minStanding') or {}).get('name') or 'Unknown'),type=str(contract.get('missionType') or ''),
                briefing=str(contract.get('description') or '').replace('\\n','\n'),cooldown=number(contract.get('personalCooldownTime') or 0,0,100000),
                chance=chance,pool_size=len(members),trigger=trigger,source_id=guid(contract['id']),source='SCMDB',source_version=version,source_checked_at=checked)
            index=len(missions);missions.append(mission)
            for key in set(members):
                if key not in records:records[key]=dict(sources=[])
                records[key]['sources'].append(index)
    return dict(blueprints=records,missions=missions)


def normalize_hardware(raw,known):
    result=dict(lasers=[],modules=[],gadgets=[])
    modifiers={'window':'optimalChargeWindowSize','rate':'optimalChargeRate','resistance':'resistance','instability':'instability','filter':'filter'}
    for laser in known['lasers']:
        candidates=[entry for entry in raw['lasers'] if entry.get('name')==laser['name'] and entry.get('size')==laser['size'] and not entry.get('vehicleBuiltIn')]
        if len(candidates)!=1:raise ValueError('Missing or ambiguous mining laser: '+laser['name'])
        item=candidates[0];beam=item['miningBeam'];row=dict(id=laser['id'],fracture=number(beam['damagePerSecond'],0,1e8),
            extraction=number(item['extractionBeam']['damagePerSecond'],0,1e8),fullRange=number(beam['fullDamageRange'],0,1e6),zeroRange=number(beam['zeroDamageRange'],0,1e6),
            throttleMin=number(item['throttleMinimum'],0,1),slots=number(item['moduleSlots'],0,3))
        if row['zeroRange']<=row['fullRange'] or int(row['slots'])!=row['slots']:raise ValueError('Invalid laser ranges or slots')
        row.update({key:number(item['modifiers'][source]) for key,source in modifiers.items()});result['lasers'].append(row)
    for module in known['modules']:
        candidates=[entry for entry in raw['modules'] if entry.get('name')==module['name'] and entry.get('type')==('active' if module['active'] else 'passive')]
        if len(candidates)!=1:raise ValueError('Missing or ambiguous mining module: '+module['name'])
        item=candidates[0];row=dict(id=module['id'],power=number(item['miningDamageMultiplier'],0,100),extraction=(number(item['extractionMultiplier'],0,100)-1)*100)
        row.update({key:number(item['modifiers'].get(source,0) if key=='filter' else item['modifiers'][source]) for key,source in modifiers.items()})
        row.update(shatter=number(item['modifiers']['shatterDamage']),danger=number(item['modifiers']['catastrophicChargeRate']))
        result['modules'].append(row)
    for gadget in known['gadgets']:
        candidates=[entry for entry in raw['gadgets'] if entry.get('name')==gadget['name']]
        if len(candidates)!=1:raise ValueError('Missing or ambiguous mining gadget: '+gadget['name'])
        item=candidates[0];mods=item['modifiers'];row=dict(id=gadget['id'])
        row.update({key:number(mods[source]) for key,source in dict(instability='instability',window='optimalChargeWindowSize',rate='optimalChargeRate',resistance='resistance',cluster='clusterFactor').items()})
        result['gadgets'].append(row)
    return result


def refresh(directory,game=None,fetch=fetch_json,known=None):
    from installation import ROOT
    version,build=installed_version(game);versions,_=fetch('versions.json',1024*1024)
    if not isinstance(versions,list):raise ValueError('Invalid source version index')
    if not any(isinstance(row,dict) and row.get('version')==version for row in versions):
        return dict(status='not_published',version=version,detail='SCMDB has not published data for this exact installed game version/channel. Existing references remain labelled.')
    payloads={};hashes={};checked=time.time()
    for resource in FILES:
        payload,digest=fetch(resource+'-'+version+'.json')
        if not isinstance(payload,dict) or payload.get('version')!=version:raise ValueError('Reference version/channel mismatch')
        payloads[resource]=payload;hashes[resource]=digest
    normalized=normalize_annotations(payloads['crafting_blueprints'],payloads['merged'],checked,version)
    known=known or read_json(ROOT/'data/mining_hardware.json')
    hardware=normalize_hardware(payloads['mining_equipment'],known)
    normalized.update(schema=1,version=version,build_id=build,checked_at=checked,hashes=hashes,
                      source='SCMDB',urls=[BASE+resource+'-'+version+'.json' for resource in FILES])
    # Do not publish a generation built across a launcher patch or channel switch.
    if installed_version(game)!=(version,build):raise ValueError('Installed game changed during source refresh')
    directory=Path(directory);generation=uuid.uuid4().hex;folder=directory/'directory_sources'/generation;folder.mkdir(parents=True)
    publish_json(folder/'sources.json',normalized)
    raw=(folder/'sources.json').read_bytes();revision=hashlib.sha256(raw).hexdigest()
    hardware.update(schema=1,revision=revision,version=version,build_id=build,source='SCMDB',checked_at=checked)
    if not publish_json(directory/'mining_reference.json',hardware):raise OSError('Could not publish mining hardware')
    pointer=dict(schema=1,generation=generation,sha256=revision,version=version,build_id=build,applied_at=time.time(),checked_at=checked)
    if not publish_json(directory/'reference_source_current.json',pointer):raise OSError('Could not activate source references')
    # Leave a grace period for readers holding the previous immutable generation.
    import shutil
    for old in (directory/'directory_sources').iterdir():
        if re.fullmatch('[0-9a-f]{32}',old.name) and old.name!=generation and not old.is_symlink() and old.resolve().parent==(directory/'directory_sources').resolve() and checked-old.stat().st_mtime>7*86400:
            try:shutil.rmtree(old)
            except OSError:pass
    return dict(status='applied',version=version,revision=revision,applied_at=pointer['applied_at'],checked_at=checked,
        detail=f"Applied SCMDB references for {version}: {len(normalized['blueprints'])} blueprint identities and {len(normalized['missions'])} reward-pool sources. Mining hardware is published for the native engine.",
        url='https://scmdb.net/')


def active_annotations(build,directory=None):
    from installation import PROFILE
    directory=Path(directory or PROFILE)
    try:
        pointer=read_json(directory/'reference_source_current.json',8192)
        if pointer.get('schema')!=1 or pointer.get('build_id')!=build.get('BuildId'):return None
        generation=pointer.get('generation','')
        if not re.fullmatch('[0-9a-f]{32}',generation):raise ValueError('Invalid source generation')
        path=directory/'directory_sources'/generation/'sources.json'
        if path.stat().st_size>32*1024*1024:raise ValueError('Source catalog exceeds limit')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pointer['sha256']:raise ValueError('Source reference integrity failed')
        value=json.loads(raw)
        if value.get('build_id')!=build.get('BuildId') or value.get('version')!=pointer.get('version'):raise ValueError('Reference build mismatch')
        return value
    except (OSError,ValueError,KeyError,TypeError):return None


def apply_annotations(data,directory=None):
    value=active_annotations(data.get('native_provenance',{}).get('build',{}),directory)
    if value is None:return 0
    offset=len(data['missions']);data['missions'].extend(value['missions']);matched=0
    for blueprint in data['blueprints']:
        fresh=value['blueprints'].get(blueprint.get('native_id'))
        if fresh is None:continue
        blueprint['sources']=[offset+index for index in fresh['sources']]
        if 'known_from_start' in fresh:blueprint['known_from_start']=fresh['known_from_start']
        blueprint['mission_count']=len(fresh['sources']);blueprint['unlock_source']='SCMDB '+value['version']
        blueprint['unlock_checked_at']=value['checked_at'];matched+=1
    data['unlock_provenance']=dict(source='SCMDB',version=value['version'],checked_at=value['checked_at'],matched=matched)
    return matched


class ReferenceSourceService:
    def __init__(self,directory):
        self.directory=Path(directory);self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='reference-data')
        self.future=None;self.next_check=0;self.last_version=None;self.force_after=0
        try:self.state=read_json(self.directory/'reference_source_status.json',16384)
        except (OSError,ValueError):self.state={}

    def tick(self,force=False):
        now=time.time()
        try:current=installed_version()
        except (OSError,ValueError,KeyError):current=None
        if current!=self.last_version:self.last_version=current;self.next_check=0
        if self.future is not None and self.future.done():
            try:
                self.state=self.future.result();self.state.setdefault('checked_at',now)
                self.next_check=now+(INTERVAL if self.state.get('status')=='applied' else RETRY)
            except Exception as error:self.state=dict(status='unavailable',detail=str(error),checked_at=now);self.next_check=now+RETRY
            self.future=None
        if self.future is None and (now>=self.next_check or (force and now>=self.force_after)):
            self.future=self.pool.submit(refresh,self.directory)
            self.force_after=now+30
        result=dict(self.state,at=now,checking=self.future is not None,installed_version=current[0] if current else None)
        publish_json(self.directory/'reference_source_status.json',result)
        return result

    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
