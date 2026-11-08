"""Read active port limits, following stock mounts without counting their sockets twice."""
from collections import Counter
import xml.etree.ElementTree as ET

COMPONENTS={'Shield':'Shields','QuantumDrive':'Quantum drive','PowerPlant':'Power plants','Cooler':'Coolers',
            'WeaponMining':'Mining lasers','MiningLaser':'Mining lasers','SalvageHead':'Salvage heads'}


def vehicle_xml(path,modification=''):
    root=ET.parse(path).getroot()
    # CryXML sources use both minSize and minsize (notably the Golem).
    for node in root.iter():node.attrib={k.casefold():v for k,v in node.attrib.items()}
    if modification:
        matches=[m for m in root.findall('./Modifications/Modification') if m.get('name','').casefold()==modification.casefold()]
        if len(matches)!=1:raise ValueError('Vehicle variant patch not resolved')
        mod=matches[0]
        if mod.get('patchfile'):raise ValueError('External vehicle patch not resolved')
        ids={}
        for node in root.iter():
            if node.get('id'):ids.setdefault(node.get('id'),[]).append(node)
        for elem in mod.findall('./Elems/Elem'):
            targets=ids.get(elem.get('idref'),[])
            if not targets and elem.get('name','').casefold() in ('minsize','maxsize','skippart','type','subtypes'):
                raise ValueError('Variant port patch target missing')
            for node in targets:node.set(elem.get('name').casefold(),elem.get('value',''))
    return root


def limits(name,minimum,maximum,types,flags='',tags=''):
    try:minimum,maximum=int(minimum),int(maximum)
    except (TypeError,ValueError):return None
    if not name or minimum<0 or maximum<1 or maximum>32 or minimum>maximum:return None
    return dict(name=name.lower(),minimum=minimum,maximum=maximum,types=types,flags=flags,tags=tags)


def xml_ports(root):
    result={}
    def visit(part):
        if part.get('skippart')=='1':return
        ip=part.find('ItemPort')
        if ip is not None:
            if ip.get('skippart')=='1':return
            types={t.get('type'):t.get('subtypes','').split(',') for t in ip.findall('./Types/Type')}
            port=limits(part.get('name'),ip.get('minsize'),ip.get('maxsize'),types,ip.get('flags',''),ip.get('requiredtags',''))
            if port and types:
                key=port['name']
                if key in result and result[key]!=port:raise ValueError('Ambiguous vehicle port definition')
                result[key]=port
        for child in part.findall('./Parts/Part'):visit(child)
    for part in root.findall('./Parts/Part'):visit(part)
    return result


def record_ports(raw):
    result={}
    for component in raw.get('Components',[]):
        if component.get('_Type_')!='SItemPortContainerComponentParams':continue
        for node in component.get('Ports',[]):
            types={t.get('Type'):t.get('SubTypes',[]) for t in node.get('Types',[])}
            port=limits(node.get('Name'),node.get('MinSize'),node.get('MaxSize'),types,node.get('Flags',''),node.get('RequiredPortTags',''))
            if port and types:result[port['name']]=port
    return result


def loadout(raw,explicit=None):
    base=next((c.get('loadout') for c in raw.get('Components',[]) if c.get('_Type_')=='SEntityComponentDefaultLoadoutParams'),{})
    result={n['itemPortName'].lower():n for n in (base or {}).get('entries',[]) if n.get('itemPortName')}
    result.update({n['itemPortName'].lower():n for n in (explicit or {}).get('entries',[]) if n.get('itemPortName')})
    return result


def extract(store,raw,classes,path,modification=''):
    if not path:return dict(status='unavailable',groups=[])
    try:ports=xml_ports(vehicle_xml(path,modification))
    except (OSError,ValueError,ET.ParseError):return dict(status='unavailable',groups=[])
    ports.update(record_ports(raw))
    counts=Counter();partial=False;restricted=False
    def resolve(entry):
        if entry.get('entityClassReference'):return store.value(entry['entityClassReference'])
        return store.read(classes[entry['entityClassName']])['_RecordValue_']
    def visit(port,entries,turret=False,stack=()):
        nonlocal partial,restricted
        types=port['types'];label=next((COMPONENTS[t] for t in types if t in COMPONENTS),None)
        if label:
            counts[label,port['minimum'],port['maximum']]+=1
            return
        gun='WeaponGun' in types and not any(t in types for t in ('BombLauncher','MissileLauncher')) and (not types['WeaponGun'] or any(t in ('Gun','') for t in types['WeaponGun']))
        mount=any(t in types for t in ('Turret','WeaponMount','UtilityTurret','ToolArm'))
        if not gun and not mount:return
        entry=entries.get(port['name'],{})
        if mount and entry:
            try:component=resolve(entry)
            except (OSError,KeyError,ValueError,TypeError):
                partial=True;return
            child_ports=record_ports(component)
            # A stock gimbal has one gun socket; a turret may carry several.
            weapons=[p for p in child_ports.values() if any(t in p['types'] for t in (*COMPONENTS,'WeaponGun','Turret','WeaponMount','UtilityTurret','ToolArm'))]
            if weapons:
                identity=entry.get('entityClassReference') or entry.get('entityClassName')
                if identity in stack or len(stack)>=8:partial=True;return
                child_entries=loadout(component,entry.get('loadout'))
                is_turret=turret or not gun or len(weapons)>1
                for child in weapons:visit(child,child_entries,is_turret,(*stack,identity))
                if port.get('tags'):restricted=True
                return
            if not gun:partial=True;return
        if gun:
            counts['Turret guns' if turret else 'Guns',port['minimum'],port['maximum']]+=1
            if port.get('tags'):restricted=True
    entries=loadout(raw)
    for port in ports.values():visit(port,entries)
    order=['Shields','Quantum drive','Power plants','Coolers','Guns','Turret guns','Mining lasers','Salvage heads']
    groups=[dict(label=label,count=count,minimum=minimum,maximum=maximum) for (label,minimum,maximum),count in sorted(counts.items(),key=lambda p:(order.index(p[0][0]),-p[0][2]))]
    return dict(status='partial' if partial else 'ready' if groups else 'unavailable',groups=groups,restricted=restricted)
