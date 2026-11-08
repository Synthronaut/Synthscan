"""Small browse taxonomy. Source categories remain available on every row."""
import math


def vehicle_metadata(vehicle):
    result=dict(source='UEX Corp',patch=str(vehicle.get('game_version') or 'not reported'),
                crew=str(vehicle.get('crew') or 'Not reported'),concept=bool(vehicle.get('is_concept')))
    for key in ('scu','length','width','height','mass'):
        value=vehicle.get(key)
        if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and (value>0 or key=='scu' and value==0):result[key]=value
    roles=[label for flag,label in [('mining','Mining'),('salvage','Salvage'),('racing','Racing'),('exploration','Exploration'),('cargo','Freight'),('medical','Medical'),('refuel','Refueling'),('repair','Repair'),('industrial','Industrial'),('passenger','Passenger'),('carrier','Carrier')] if vehicle.get('is_'+flag)]
    result['roles']=roles
    return result


def ship_category(role):
    """Group source roles for browsing; keep the full game role in the overview."""
    role=role.casefold()
    if 'mining' in role:return 'Mining'
    if 'salvage' in role:return 'Salvage'
    if 'racing' in role:return 'Racing'
    if 'freight' in role or 'cargo' in role:
        if 'fighter' in role or 'gun' in role:return 'Generalists'
        if 'light' in role:return 'Light haulers'
        if 'medium' in role:return 'Medium haulers'
        if 'heavy' in role:return 'Large haulers'
        return 'Haulers'
    if any(word in role for word in ('expedition','exploration','pathfinder','scout')):return 'Exploration'
    if 'fighter' in role:return role.title()
    if 'bomber' in role:return 'Bombers'
    if 'corvette' in role or 'frigate' in role:return 'Corvettes & frigates'
    if 'destroyer' in role:return 'Destroyers'
    if 'carrier' in role:return 'Carriers'
    if any(word in role for word in ('industrial','refuel','repair','recovery','data','reporting','science')):return 'Industrial & support'
    if role=='starter':return 'Generalists'
    return role.title() if role else ''


def category(row):
    kind=row.get('kind');typ=row.get('item_type','');record=row.get('item_record','').lower()
    if kind in ('Ship','Vehicle'):
        role=row.get('ship_stats',{}).get('role')
        if role:return ship_category(role)
        roles=row.get('ship_overview',{}).get('roles',[])
        return ship_category(' / '.join(roles[:2])) if roles else row.get('category','Ships')
    if kind=='Blueprint':
        if '/ships/' in record or row.get('category')=='Ship components':return 'Ship equipment'
        if row.get('category')=='Armor & suits':return 'Armor'
        if row.get('category')=='Personal weapons':return 'Personal weapons & ammo'
        if row.get('category')=='Equipment':return 'Tools & equipment'
        if typ.startswith(('Armor','Char_Armor')) or typ in ('Helmet','Undersuit'):return 'Armor'
        if typ.startswith(('Clothing','Char_Clothing')):return 'Clothing'
        if typ.startswith(('Weapon','Magazine','Gun')) or typ in ('Grenade','Bomb'):return 'Personal weapons & ammo'
        if typ.startswith(('Mining','Salvage')) or typ in ('TractorBeam','ToolArm'):return 'Tools & equipment'
    return row.get('category','Other')


def enrich(rows,ship_reference):
    ships=ship_reference.get('ships',{})
    for row in rows:
        identity=row.get('game_vehicle_id')
        if identity and identity in ships:
            row['ship_stats']=dict(ships[identity],patch=ship_reference.get('build',{}).get('Branch','Unknown build'))
        row['source_category']=row['category']
        row['category']=category(row)
        row['search']=row.get('search','')+' '+row['category']+' '+row['source_category']+' '+row.get('ship_stats',{}).get('role','')
