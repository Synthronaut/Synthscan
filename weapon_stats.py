"""Nominal stock projectile-weapon statistics from exact local game references."""
import math


def positive(value, zero=False):
    return type(value) in (int,float) and math.isfinite(value) and (value>=0 if zero else value>0)


def extract(store, raw):
    components=raw.get('Components',[])
    weapon=next((c for c in components if c.get('_Type_')=='SCItemWeaponComponentParams'),None)
    container=next((c for c in components if c.get('_Type_')=='SAmmoContainerComponentParams' and c.get('ammoParamsRecord')),None)
    unavailable=dict(status='unavailable',modes=[],source='Installed game files',note='Statistics unavailable for this firing model or ammo reference.')
    if not weapon or not container:return unavailable
    try:ammo=store.value(container['ammoParamsRecord'])
    except (OSError,ValueError,KeyError,TypeError):return unavailable
    projectile=ammo.get('projectileParams') or {}
    damage=projectile.get('damage') or {}
    if projectile.get('_Type_')!='BulletProjectileParams' or any(not positive(damage.get(k),True) for k in ('DamagePhysical','DamageEnergy')):return unavailable
    modes=[]
    for mode in weapon.get('fireActions',[]):
        action=mode;entry=None
        if mode.get('_Type_')=='SWeaponActionSequenceParams':
            entries=mode.get('sequenceEntries',[])
            if len(entries)!=1:continue
            entry=entries[0];action=entry.get('weaponAction') or {}
        if action.get('_Type_') not in ('SWeaponActionFireSingleParams','SWeaponActionFireRapidParams'):continue
        launch=action.get('launchParams') or {}
        pellets,multiplier,rpm=launch.get('pelletCount'),launch.get('damageMultiplier'),action.get('fireRate')
        if launch.get('_Type_')!='SProjectileLauncher' or type(pellets) is not int or pellets<1 or not positive(multiplier):continue
        scale=pellets*multiplier
        alpha=(damage['DamagePhysical']+damage['DamageEnergy'])*scale
        distortion=damage.get('DamageDistortion',0)*scale if positive(damage.get('DamageDistortion',0),True) else None
        row=dict(name=mode.get('name') or 'Primary',alpha=alpha,physical_alpha=damage['DamagePhysical']*scale,
                 energy_alpha=damage['DamageEnergy']*scale,distortion_alpha=distortion,pellets=pellets)
        if positive(rpm):row['rpm']=rpm
        if positive(action.get('spinUpTime')):row['spin_up_seconds']=action['spinUpTime']
        if positive(ammo.get('speed')):row['projectile_speed']=ammo['speed']
        simple=entry is None or (mode.get('mode')=='Looping' and entry.get('repetitions')==1 and entry.get('unit')=='RPM'
                                 and positive(entry.get('delay')) and positive(rpm) and math.isclose(entry['delay'],rpm))
        if simple and positive(rpm) and not projectile.get('additionalProjectilesParams') and not projectile.get('detonationParams'):
            row['burst_dps']=alpha*rpm/60
            if distortion is not None:row['distortion_dps']=distortion*rpm/60
        if all(not isinstance(v,float) or math.isfinite(v) for v in row.values()):modes.append(row)
    return dict(status='ready' if modes else 'unavailable',modes=modes,source='Installed game files',
                note='Stock direct-hit values at full firing rate. Burst DPS is calculated from alpha × RPM / 60; excludes spin-up, recharge, heat pauses, hit chance, range loss and crafted bonuses.')
