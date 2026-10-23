"""Organization-specific reputation snapshot annotations for SynthStrings.

Never edits shared standing/rank labels. Does not imply hot reload or live text.
"""
from collections import defaultdict
import re


def annotate_names(text, snapshot, factions, scopes, previous=None):
    if not snapshot.get('own_character_verified') or not snapshot.get('complete'):
        raise ValueError('A complete verified own-character snapshot is required')
    lines=text.splitlines(keepends=True)
    positions={}
    values={}
    for index,line in enumerate(lines):
        key,sep,value=line.rstrip('\r\n').partition('=')
        if sep:
            canonical=key.lstrip('\ufeff').split(',')[0].casefold()
            if canonical in positions:raise ValueError('Duplicate localization key: '+canonical)
            positions[canonical]=index;values[canonical]=value
    restored={}
    for key,entry in (previous or {}).get('entries',{}).items():
        key=key.casefold()
        if key not in positions:raise ValueError('Previously annotated name is missing: '+key)
        if values[key] not in (entry['written'],entry['original']):
            raise ValueError('Organization name changed outside this patch: '+key)
        values[key]=entry['original'];restored[key]=entry['original']
    by_entity=defaultdict(list)
    for record in snapshot['records']:
        by_entity[record['entity']].append(record)
    key_owners=defaultdict(set)
    for entity,faction in factions.items():key_owners[faction['key'].lstrip('@').casefold()].add(entity)
    entries={};skipped=[]
    for entity,records in sorted(by_entity.items()):
        faction=factions.get(entity)
        if not faction:
            skipped.append(dict(entity=entity,reason='Unknown organization'));continue
        key=faction['key'].lstrip('@').casefold()
        if key not in positions or len(key_owners[key])!=1:
            skipped.append(dict(entity=entity,reason='Missing or shared organization-name key'));continue
        preferred=[r for r in records if r['scope']=='FactionReputation']
        if not preferred:preferred=[r for r in records if r['scope'] not in ('Affinity','NPC_Reliability','NPC_Fired')]
        if not preferred:preferred=records
        pieces=[];tracks=[]
        for record in sorted(preferred,key=lambda r:r['scope']):
            scope=scopes.get(record['scope'])
            if not scope:
                skipped.append(dict(entity=entity,scope=record['scope'],reason='Unmapped track'));continue
            score=record['score']
            if type(score) is not int:raise ValueError('Reputation score must be an integer')
            targets=[s for s in scope['standings'] if s['minimum']>score]
            target=min(targets,key=lambda s:s['minimum']) if targets else None
            progress=f"{score:,} / {target['minimum']:,}" if target else f'{score:,} / MAX'
            label=scope.get('display_name') or 'Rep'
            if len(records)>1:progress=label+': '+progress
            pieces.append(progress)
            tracks.append(dict(scope=record['scope'],score=score,next_minimum=target['minimum'] if target else None))
        if pieces:
            original=values[key]
            # An untracked annotation must not silently become a new base name.
            if re.search(r'\(.*\d[\d,]*\s*/\s*(?:\d|MAX)',original):
                raise ValueError('Untracked reputation annotation already exists: '+key)
            written=original+' ('+'; '.join(pieces)+')'
            values[key]=written
            entries[key]=dict(original=original,written=written,tracks=tracks)
    for key in set(restored)|set(entries):
        index=positions[key];line=lines[index];left=line.partition('=')[0]
        ending='\r\n' if line.endswith('\r\n') else ('\n' if line.endswith('\n') else '')
        lines[index]=left+'='+values[key]+ending
    return ''.join(lines),dict(entries=entries,skipped=skipped,read_at=snapshot['read_at'],character_key=snapshot['character_key'])
