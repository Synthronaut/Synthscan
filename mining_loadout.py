"""Local player-selected mining fit. Never imports another app's private settings."""
import copy
import json
from pathlib import Path
from refinery_orders import atomic_json

ROOT=Path(__file__).resolve().parent
FIT_PATH=ROOT/'mining_loadout.json'


def hardware():
    return json.loads((ROOT/'data/mining_hardware.json').read_text(encoding='utf-8'))


def validate_fit(fit):
    data=hardware()
    ships={s['id']:s for s in data['ships']}
    lasers={l['id']:l for l in data['lasers']}
    modules={m['id'] for m in data['modules']}
    gadgets={g['id'] for g in data['gadgets']}
    if not isinstance(fit,dict) or fit.get('ship') not in ships:
        raise ValueError('Choose a supported mining ship')
    ship=ships[fit['ship']]
    heads=fit.get('heads')
    if not isinstance(heads,list) or not 1<=len(heads)<=ship['heads']:
        raise ValueError('Choose at least one fitted head; include only crewed heads')
    slots=set()
    for index,head in enumerate(heads):
        if not isinstance(head,dict) or head.get('laser') not in lasers:
            raise ValueError('Choose a known mining laser')
        laser=lasers[head['laser']]
        slot=head.get('slot',index+1)
        if isinstance(slot,bool) or not isinstance(slot,int) or not 1<=slot<=ship['heads'] or slot in slots:
            raise ValueError('Choose a unique head position on this ship')
        slots.add(slot)
        if laser['size']>ship['size'] or (ship.get('fixed_laser') and laser['id']!=ship['fixed_laser']):
            raise ValueError('That laser does not fit this ship')
        if not ship.get('fixed_laser') and laser['id']=='drak_golem_s1':
            raise ValueError('Pitman is built into the Golem')
        mods=head.get('modules',[])
        if not isinstance(mods,list) or len(mods)>laser['slots'] or any(m not in modules for m in mods):
            raise ValueError('Check the laser’s module slots')
        try:power=float(head.get('crafted_power',0))
        except (TypeError,ValueError):raise ValueError('Crafted power must be a number')
        if not -50<=power<=100:
            raise ValueError('Crafted power must be between -50 and +100 percent')
    if fit.get('gadget') and fit['gadget'] not in gadgets:
        raise ValueError('Choose a known gadget')
    try:distance=float(fit.get('distance',0))
    except (TypeError,ValueError):raise ValueError('Distance must be a number')
    if not 0<=distance<=100000:
        raise ValueError('Distance must be zero or a positive number of metres')
    if not isinstance(fit.get('actives',False),bool):
        raise ValueError('Active-module selection must be on or off')
    validated=copy.deepcopy(fit)
    for index,head in enumerate(validated['heads']):
        head['slot']=head.get('slot',index+1)
        head['crafted_power']=float(head.get('crafted_power',0))
        head['modules']=list(head.get('modules',[]))
    validated['distance']=distance
    validated['actives']=fit.get('actives',False)
    return validated


def load_fit(path=FIT_PATH):
    try:
        return validate_fit(json.loads(Path(path).read_text(encoding='utf-8')))
    except FileNotFoundError:
        return None


def save_fit(fit,path=FIT_PATH):
    validated=validate_fit(fit)
    atomic_json(Path(path),validated)
    return validated
