"""Local mining memories. Only the bridge writes the SQLite journal.

Observed scans never establish extraction, cargo, refinery output or a sale.
Sharing renders an explicit allowlist; no account or network fields are exported.
"""
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid

KINDS = {'scanned': 'Rock scanned', 'mined': 'Rock mined', 'haul': 'Collected haul',
         'refined': 'Refined output', 'sale': 'Completed sale', 'trip': 'Trip / memory'}
TEXT_FIELDS = ('title', 'material', 'system', 'location', 'ship', 'crew', 'notes', 'patch', 'screenshot')
NUMBERS = {'mass_kg': (0, 1e12), 'scu': (0, 1e9), 'quality': (0, 1000), 'proceeds': (0, 1e15)}

def number(value, name):
    if value is None or value == '': return None
    if isinstance(value, bool): raise ValueError(name+' must be a number')
    try: result = float(value)
    except (TypeError, ValueError): raise ValueError(name+' must be a number') from None
    lo, hi = NUMBERS[name]
    if not math.isfinite(result) or not lo <= result <= hi: raise ValueError('Invalid '+name)
    if name == 'quality' and not result.is_integer(): raise ValueError('Quality must be a whole number')
    return result

def stamp(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat(timespec='seconds')

def format_number(value, unit=''):
    return 'Unknown' if value is None else f'{value:,.2f}'.rstrip('0').rstrip('.')+unit

class MiningDiary:
    def __init__(self, directory):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory/'mining_diary.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, body TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, result TEXT NOT NULL)')
        self.db.commit(); self.revision = self.db.total_changes

    def close(self): self.db.close()

    def get(self, key, deleted=False):
        row = self.db.execute('SELECT body,deleted FROM entries WHERE id=?', (key,)).fetchone()
        if not row or (row[1] and not deleted): raise ValueError('Diary entry is unavailable')
        return json.loads(row[0])

    def _put(self, entry):
        self.db.execute('INSERT INTO entries(id,body) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                        (entry['id'], json.dumps(entry, ensure_ascii=False, allow_nan=False)))

    def observe(self, observation):
        """One native encounter ID is updated across frames; deleted IDs stay deleted."""
        key = str(observation.get('id', ''))
        at = float(observation.get('at', 0))
        if not key or len(key)>180 or not math.isfinite(at) or at <= 0: raise ValueError('Invalid encounter')
        mass = number(observation.get('mass_kg'), 'mass_kg')
        if not mass or not observation.get('settled'): return
        row = self.db.execute('SELECT body,deleted FROM entries WHERE id=?', (key,)).fetchone()
        if row and row[1]: return
        old = json.loads(row[0]) if row else None
        if old and at <= old.get('last_observed_at', 0): return
        entry = old or dict(id=key, kind='scanned', source='screen observation', created_at=at,
                           occurred_at=stamp(at), notes='', crew='', title='', overrides=[], observations=0)
        overrides = entry.get('overrides', [])
        for field in ('material','system','location','ship','patch'):
            value = str(observation.get(field,'')).strip()[:200]
            if value and field not in overrides: entry[field]=value
        if 'mass_kg' not in overrides: entry['mass_kg']=max(entry.get('mass_kg') or 0, mass)
        entry['location_source']='Game log context; verify the specific site'
        entry['identity']='Visual encounter; matching mass is not a unique rock ID'
        parts=[]
        if observation.get('composition_complete'):
            for part in observation.get('parts', [])[:32]:
                percent=float(part['percent']);q=number(part.get('quality'),'quality')
                if not math.isfinite(percent) or not 0<=percent<=100: raise ValueError('Invalid composition')
                parts.append(dict(material=str(part.get('material',''))[:120],percent=percent,quality=q,inert=bool(part.get('inert'))))
            if parts and 98<=sum(p['percent'] for p in parts)<=100.1:
                entry['parts']=parts
                qualities=[p['quality'] for p in parts if not p['inert'] and p['quality'] is not None]
                if qualities and 'quality' not in overrides: entry['quality']=max(qualities)
        entry.update(last_observed_at=at, observations=entry['observations']+1, updated_at=time.time())
        with self.db: self._put(entry)
        self.revision += 1

    def save(self, fields, create_id=None):
        key = str(fields.get('id') or create_id or uuid.uuid4())
        exists=self.db.execute('SELECT 1 FROM entries WHERE id=?',(key,)).fetchone()
        entry = self.get(key) if fields.get('id') or exists else dict(id=key,source='player entered',created_at=time.time(),overrides=[])
        kind = fields.get('kind', entry.get('kind','scanned'))
        if kind not in KINDS: raise ValueError('Choose a diary entry type')
        for field in TEXT_FIELDS:
            if field in fields:
                value=str(fields[field]).replace('\r\n','\n').strip()
                if len(value)>(5000 if field=='notes' else 500): raise ValueError(field+' is too long')
                if value!=entry.get(field):entry['overrides']=list(set(entry.get('overrides',[]))|{field})
                entry[field]=value
                if field=='location' and 'location' in entry['overrides']:entry['location_source']='Player entered/corrected'
        for field in NUMBERS:
            if field in fields:
                value=number(fields[field],field)
                if value!=entry.get(field):entry['overrides']=list(set(entry.get('overrides',[]))|{field})
                entry[field]=value
        occurred=str(fields.get('occurred_at') or entry.get('occurred_at') or stamp())
        try: parsed=datetime.fromisoformat(occurred.replace('Z','+00:00'))
        except ValueError: raise ValueError('Use an ISO date/time, for example 2026-10-21T20:00:00+08:00') from None
        if parsed.tzinfo is None: raise ValueError('Date/time needs a timezone')
        entry['occurred_at']=parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
        entry.update(kind=kind,updated_at=time.time(),confirmation='Player confirmed' if kind!='scanned' else 'Scan only')
        if not entry.get('material') and not entry.get('title'): raise ValueError('Enter a title or material')
        if kind in ('scanned','mined') and not entry.get('mass_kg'): raise ValueError('A rock entry needs its mass in kg')
        if kind in ('haul','refined') and not entry.get('scu'): raise ValueError('A haul/output entry needs its volume in SCU')
        if kind=='sale' and entry.get('proceeds') is None: raise ValueError('Enter confirmed sale proceeds in aUEC')
        with self.db: self._put(entry)
        self.revision+=1
        return entry

    def delete(self, key):
        self.get(key)
        with self.db:self.db.execute('UPDATE entries SET deleted=1 WHERE id=?',(key,))
        self.revision+=1

    def merge(self, keys):
        keys=list(dict.fromkeys(keys))
        if len(keys)<2: raise ValueError('Select at least two scan entries to merge')
        entries=[self.get(k) for k in keys]
        if any(e['kind']!='scanned' for e in entries): raise ValueError('Only scan entries can be merged; haul totals are never added implicitly')
        target=copy.deepcopy(entries[0]); target['mass_kg']=max(e.get('mass_kg') or 0 for e in entries)
        target['observations']=sum(e.get('observations',0) for e in entries)
        target['notes']='\n\n'.join(e['notes'] for e in entries if e.get('notes'))
        best=max(entries,key=lambda e:e.get('quality') if e.get('quality') is not None else -1)
        if best.get('quality') is not None:target['quality']=best['quality']
        if best.get('parts'):target['parts']=best['parts']
        target['merged_ids']=list(set(target.get('merged_ids',[]))|set(keys[1:]))
        target['overrides']=list(set(target.get('overrides',[]))|{'mass_kg','notes'})
        target['updated_at']=time.time()
        with self.db:
            self._put(target)
            for key in keys[1:]:self.db.execute('UPDATE entries SET deleted=1 WHERE id=?',(key,))
        self.revision+=1
        return target

    def entries(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT body FROM entries WHERE deleted=0')]

    @staticmethod
    def detail(e):
        lines=[e.get('title') or e.get('material') or 'Mining memory', KINDS[e['kind']],e['occurred_at'],
               f"{e.get('system') or 'Unknown system'} / {e.get('location') or 'Unknown site'}",
               'Rock mass: '+format_number(e.get('mass_kg'),' kg'),'Volume: '+format_number(e.get('scu'),' SCU'),
               'Best observed quality: '+format_number(e.get('quality')),
               'Confirmed proceeds: '+format_number(e.get('proceeds'),' aUEC'),
               'Ship: '+(e.get('ship') or 'Unknown'),'Crew: '+(e.get('crew') or 'Unspecified'),
               'Patch: '+(e.get('patch') or 'Unknown'),'Source: '+e['source'],
               'Observations: '+str(e.get('observations',0)),e.get('confirmation','Scan only'),e.get('identity','')]
        for p in e.get('parts',[]):lines.append(f"{p['percent']:g}% {p['material'] or 'Inert'} · Q{p['quality']:g}" if p['quality'] is not None else f"{p['percent']:g}% {p['material'] or 'Inert'}")
        if e.get('notes'):lines+=['',e['notes']]
        return '\n'.join(lines)

    def view(self, query='', system='', patch='', mode='Recent', offset=0):
        offset=max(0,int(offset));cache_key=(self.revision,query,system,patch,mode,offset)
        if getattr(self,'_cache_key',None)==cache_key:return self._cache
        entries=self.entries()
        systems=sorted({e['system'] for e in entries if e.get('system')});patches=sorted({e['patch'] for e in entries if e.get('patch')})
        filtered=[e for e in entries if (not system or e.get('system')==system) and (not patch or e.get('patch')==patch)
                  and query.casefold() in ' '.join(str(e.get(f,'')) for f in ('occurred_at',)+TEXT_FIELDS if f!='screenshot').casefold()]
        metrics=[('Largest scan','scanned','mass_kg',' kg'),('Largest mined rock','mined','mass_kg',' kg'),
                 ('Largest haul','haul','scu',' SCU'),('Largest refined output','refined','scu',' SCU'),('Largest sale','sale','proceeds',' aUEC')]
        records=[]
        for label,kind,metric,unit in metrics:
            candidates=[e for e in filtered if e['kind']==kind and e.get(metric) is not None]
            winner=max(candidates,key=lambda e:e[metric],default=None)
            records.append(dict(label=label,value=format_number(winner[metric],unit) if winner else 'No record yet',id=winner['id'] if winner else '',entry=winner))
        quality=max((e for e in filtered if e.get('quality') is not None),key=lambda e:e['quality'],default=None)
        records.append(dict(label='Best quality',value='Q'+format_number(quality['quality']) if quality else 'No record yet',id=quality['id'] if quality else '',entry=quality))
        sort={'Rock mass':'mass_kg','Haul SCU':'scu','Sale proceeds':'proceeds','Quality':'quality'}.get(mode)
        if sort:
            allowed={'Rock mass':('scanned','mined'),'Haul SCU':('haul','refined'),'Sale proceeds':('sale',),'Quality':tuple(KINDS)}[mode]
            filtered=[e for e in filtered if e['kind'] in allowed and e.get(sort) is not None]
        filtered.sort(key=lambda e:(e.get(sort) or 0,e['occurred_at']) if sort else (e['occurred_at'],),reverse=True)
        rows=[dict(id=e['id'],name=e.get('title') or (e.get('material') or 'Mining')+' · '+KINDS[e['kind']],
                   kind=KINDS[e['kind']],category=' / '.join(filter(None,[e.get('system'),e.get('location')])),detail=self.detail(e),entry=e) for e in filtered[offset:offset+200]]
        result=dict(rows=rows,records=records,systems=systems,patches=patches,count=len(filtered),revision=self.revision,offset=offset)
        self._cache_key,self._cache=cache_key,result
        return result

    def execute(self, command):
        key=str(command.get('id',''))
        if not key: raise ValueError('Missing diary command ID')
        prior=self.db.execute('SELECT result FROM commands WHERE id=?',(key,)).fetchone()
        if prior:return json.loads(prior[0])
        action=command['action']
        if action=='diary_save':entry=self.save(command['entry'],str(uuid.uuid5(uuid.NAMESPACE_URL,key)));result=dict(note='Diary entry saved.',entry_id=entry['id'],entry=entry)
        elif action=='diary_delete':self.delete(command['entry_id']);result=dict(note='Diary entry deleted.')
        elif action=='diary_merge':entry=self.merge(command['entry_ids']);result=dict(note='Scan encounters merged.',entry_id=entry['id'],entry=entry)
        elif action=='diary_share':
            entry=self.get(command['entry_id']);options=command.get('options',{})
            preview=self.directory/'diary_exports'/'preview.png'
            render_card(entry,preview,options)
            destination=command.get('destination')
            if destination:
                target=Path(destination)
                if target.suffix.lower()=='.png':render_card(entry,target,options)
                elif target.suffix.lower()=='.txt':target.write_text(share_text(entry,options),encoding='utf-8')
                else:raise ValueError('Export as PNG or text')
            result=dict(note='Share card saved.' if destination else 'Share preview ready. Nothing was uploaded.',preview=str(preview),exported=str(destination or ''))
        else:raise ValueError('Unknown diary action')
        with self.db:self.db.execute('INSERT INTO commands VALUES(?,?)',(key,json.dumps(result)))
        return result

def share_lines(entry, options):
    """Allowlist, never a dump of the private diary record."""
    date=datetime.fromisoformat(entry['occurred_at'].replace('Z','+00:00')).astimezone(timezone.utc).strftime('%d %b %Y · %H:%M UTC')
    lines=[entry.get('title') or entry.get('material') or 'A mining memory',KINDS[entry['kind']],
           'Date: '+date,'System: '+(entry.get('system') or 'Unknown')]
    if options.get('location') and entry.get('location'):lines.append('Site: '+entry['location'])
    if entry['kind'] in ('scanned','mined'):lines.append('Whole-rock mass: '+format_number(entry.get('mass_kg'),' kg'))
    if entry['kind'] in ('haul','refined'):lines.append('Volume: '+format_number(entry.get('scu'),' SCU'))
    if entry.get('material'):lines.append('Material: '+entry['material'])
    if entry.get('quality') is not None:lines.append('Best observed quality: Q'+format_number(entry['quality']))
    for part in entry.get('parts',[]):
        if not part.get('inert'):lines.append(f"{part['percent']:g}% {part['material']}"+(f" · Q{part['quality']:g}" if part.get('quality') is not None else ''))
    if options.get('value') and entry['kind']=='sale':lines.append('Confirmed sale: '+format_number(entry.get('proceeds'),' aUEC'))
    if entry.get('ship'):lines.append('Ship: '+entry['ship'])
    if options.get('crew') and entry.get('crew'):lines.append('Crew: '+entry['crew'])
    if entry.get('patch'):lines.append('Patch: '+entry['patch'])
    name=str(options.get('name','')).strip()[:80]
    if name:lines.append('Shared by: '+name)
    if options.get('notes') and entry.get('notes'):lines+=['',entry['notes']]
    lines+=['',('Screen observation · player edited · scan only' if entry.get('overrides') else 'Screen observation · scan only') if entry['kind']=='scanned' and entry['source']=='screen observation' else 'Player-entered / confirmed record',
            'Shared from a personal mining diary']
    return lines

def share_text(entry, options):return 'SYNTHSCAN · MINING DIARY\n\n'+'\n'.join(share_lines(entry,options))+'\n'

def render_card(entry, destination, options):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    fonts=Path('C:/Windows/Fonts')
    def font(size,bold=False):
        try:return ImageFont.truetype(str(fonts/('segoeuib.ttf' if bold else 'segoeui.ttf')),size)
        except OSError:return ImageFont.load_default(size=size)
    body=font(25);title=font(36,True);small=font(19)
    wrapped=[];measure=ImageDraw.Draw(Image.new('RGB',(1,1)))
    for line in share_lines(entry,options):
        current=''
        for char in line:
            if char=='\n' or measure.textlength(current+char,font=body)>966:
                wrapped.append(current);current='' if char=='\n' else char
            else:current+=char
        wrapped.append(current)
    photo=None
    if options.get('screenshot') and entry.get('screenshot'):
        path=Path(entry['screenshot'])
        if not path.is_file():raise ValueError('Selected screenshot is unavailable')
        with Image.open(path) as source:
            source.load();photo=ImageOps.contain(ImageOps.exif_transpose(source).convert('RGB'),(960,360))
    height=190+len(wrapped)*37+(photo.height+30 if photo else 0)
    image=Image.new('RGB',(1080,height),(17,20,26));d=ImageDraw.Draw(image)
    d.rounded_rectangle((24,24,1056,height-24),radius=22,fill=(27,32,40),outline=(69,78,92),width=2)
    d.rectangle((54,57,60,116),fill=(225,166,80));d.text((80,51),'SYNTHSCAN',font=title,fill=(235,180,96))
    d.text((82,99),'MINING DIARY  /  PERSONAL RECORD',font=small,fill=(157,171,189))
    y=150
    for line in wrapped:d.text((58,y),line,font=body,fill=(234,238,243));y+=37
    if photo:image.paste(photo,((1080-photo.width)//2,y+8))
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    image.save(destination,'PNG')
