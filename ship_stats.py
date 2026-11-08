"""Exact-identity stock ship reference extraction; no name/variant guessing."""
import math
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from game_records import walk_nodes


def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def extract(store,record,classes,xml_paths):
    raw=record['_RecordValue_'];components=raw.get('Components',[])
    vehicle=next((c for c in components if c.get('_Type_')=='VehicleComponentParams'),{})
    purchase=next((c for c in components if c.get('_Type_')=='SCItemPurchasableParams'),{})
    role=store.text(purchase.get('displayType'))
    # Some source displayType fields incorrectly contain entire descriptions.
    if len(role)>70 or '\n' in role:role=''
    result=dict(role=role,record_id=record['_RecordId_'])
    attach=next((c.get('AttachDef',{}) for c in components if c.get('_Type_')=='SAttachableComponentParams'),{})
    if positive(attach.get('Size')):result['size']=attach['Size']
    reference=str(vehicle.get('vehicleDefinition','')).replace('\\','/').lower().removeprefix('data/')
    xml_path=xml_paths.get(reference)
    # Variant modifications can replace part values; never use unmodified hull HP.
    if xml_path and not vehicle.get('modification') and not vehicle.get('maelstromVehicle'):
        xml=ET.parse(xml_path).getroot()
        parts=[e for parent in xml.findall('Parts') for e in parent.iter('Part')]
        bodies=[float(e.get('damageMax','0')) for e in parts if e.get('name','').lower()=='body' and 'damageMax' in e.attrib]
        if len(bodies)==1 and positive(bodies[0]):result['body_hp']=bodies[0]
    loadout=next((c.get('loadout',{}) for c in components if c.get('_Type_')=='SEntityComponentDefaultLoadoutParams'),{})
    shields=[];unresolved=False;armors=[]
    for node in walk_nodes(loadout):
        if 'itemPortName' not in node:continue
        name=node.get('entityClassName','');port=str(node['itemPortName']).lower()
        ref=node.get('entityClassReference')
        relevant=name.startswith(('SHLD_','ARMR_')) or 'shield_generator' in port or port=='hardpoint_armor'
        if not relevant:continue
        try:
            component=store.value(ref) if ref else store.read(classes[name])['_RecordValue_']
        except (OSError,KeyError,ValueError,TypeError):
            if name.startswith('SHLD_') or 'shield_generator' in port:unresolved=True
            continue
        for c in component.get('Components',[]):
            if c.get('_Type_')=='SCItemShieldGeneratorParams':
                capacity=c.get('MaxShieldHealth')
                if positive(capacity):shields.append(capacity)
                else:unresolved=True
            if c.get('_Type_')=='SCItemVehicleArmorParams':armors.append(c.get('damageMultiplier',{}))
        if (name.startswith('SHLD_') or 'shield_generator' in port) and not any(c.get('_Type_')=='SCItemShieldGeneratorParams' for c in component.get('Components',[])):unresolved=True
    if shields and not unresolved:
        result.update(shield_hp=sum(shields),shield_count=len(shields))
    if len(armors)==1:
        for source,target in [('DamagePhysical','armor_physical'),('DamageEnergy','armor_energy')]:
            value=armors[0].get(source)
            if positive(value):result[target]=value
    return result


def export(store,xml_root,build):
    classes={}
    for folder in ('shieldgenerator','armor'):
        for p in (store.root/'libs/foundry/records/entities/scitem/ships'/folder).rglob('*.json'):
            record=store.read(p);classes[record['_RecordName_'].split('.',1)[-1]]=p
    xml_paths={}
    for p in Path(xml_root).rglob('*.xml'):
        key=p.relative_to(xml_root).as_posix().lower().removeprefix('data/')
        xml_paths[key]=p
    result={}
    for p in (store.root/'libs/foundry/records/entities/spaceships').rglob('*.json'):
        record=store.read(p)
        result[record['_RecordId_']]=extract(store,record,classes,xml_paths)
    return dict(schema=1,build=build,ships=result,xml_hashes={p.relative_to(xml_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(xml_root).rglob('*.xml')})
