import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from ship_stats import extract
from finder_categories import enrich,vehicle_metadata,ship_category,category


class Store:
    def text(self,key):return 'Light Fighter' if key=='fighter' else ''
    def read(self,key):
        if key=='shield':return {'_RecordValue_':{'Components':[{'_Type_':'SCItemShieldGeneratorParams','MaxShieldHealth':100}]}}
        raise ValueError('Unresolved component')
    def value(self,key):return self.read(key)['_RecordValue_']


def record(modification=''):
    return dict(_RecordId_='exact-id',_RecordValue_=dict(Components=[
        dict(_Type_='VehicleComponentParams',vehicleDefinition='scripts/ship.xml',modification=modification),
        dict(_Type_='SCItemPurchasableParams',displayType='fighter'),
        dict(_Type_='SHealthComponentParams',Health=1),
        dict(_Type_='SEntityComponentDefaultLoadoutParams',loadout=dict(entries=[
            dict(itemPortName='hardpoint_shield_generator_left',entityClassName='SHLD_one'),
            dict(itemPortName='hardpoint_shield_generator_right',entityClassName='SHLD_one')]))]))


class ShipStatsTests(unittest.TestCase):
    def test_physical_ports_count_separately_and_placeholder_health_is_ignored(self):
        result=extract(Store(),record(),{'SHLD_one':'shield'},{})
        self.assertEqual(result['shield_hp'],200)
        self.assertEqual(result['shield_count'],2)
        self.assertNotIn('body_hp',result)
        self.assertEqual(result['role'],'Light Fighter')

    def test_missing_stock_component_never_becomes_partial_total(self):
        raw=record();raw['_RecordValue_']['Components'][-1]['loadout']['entries'][1]['entityClassName']='SHLD_missing'
        self.assertNotIn('shield_hp',extract(Store(),raw,{'SHLD_one':'shield'},{}))

    def test_variant_does_not_inherit_unmodified_body_hp(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'ship.xml';path.write_text('<Vehicle><Parts><Part name="body" damageMax="2050"/><Part name="body"/></Parts></Vehicle>')
            self.assertEqual(extract(Store(),record(),{'SHLD_one':'shield'},{'scripts/ship.xml':path})['body_hp'],2050)
            self.assertNotIn('body_hp',extract(Store(),record('military'),{'SHLD_one':'shield'},{'scripts/ship.xml':path}))

    def test_exact_identity_preserves_role_and_blueprint_source_category(self):
        rows=[dict(name='Arrow',kind='Ship',category='Ships',game_vehicle_id='exact-id'),
              dict(name='Arrow AI',kind='Ship',category='Ships',game_vehicle_id='other-id'),
              dict(name='Gun blueprint',kind='Blueprint',category='Weapons & ammunition',item_type='WeaponGun',item_record='libs/entities/scitem/ships/gun.json')]
        enrich(rows,dict(ships={'exact-id':dict(role='Light Fighter',body_hp=2050)},build=dict(Branch='4.10.2')))
        self.assertEqual(rows[0]['category'],'Light Fighter')
        self.assertNotIn('ship_stats',rows[1])
        self.assertEqual(rows[2]['category'],'Ship equipment')
        self.assertEqual(rows[2]['source_category'],'Weapons & ammunition')

    def test_blueprint_reference_labels_do_not_create_duplicate_browse_groups(self):
        self.assertEqual(category(dict(kind='Blueprint',category='Armor & suits',item_type='Arms (Armor)')),'Armor')
        self.assertEqual(category(dict(kind='Blueprint',category='Personal weapons',item_type='FPS Weapon')),'Personal weapons & ammo')
        self.assertEqual(category(dict(kind='Blueprint',category='Equipment',item_type='Other')),'Tools & equipment')
        self.assertEqual(category(dict(kind='Blueprint',category='Equipment',item_record='libs/entities/scitem/ships/part.json')),'Ship equipment')

    def test_browse_groups_keep_mining_and_salvage_separate(self):
        self.assertEqual(ship_category('Medium Mining'),'Mining')
        self.assertEqual(ship_category('Light Salvage'),'Salvage')
        self.assertEqual(ship_category('Heavy Freight'),'Large haulers')
        self.assertEqual(ship_category('Medium Fighter / Medium Freight'),'Generalists')
        self.assertEqual(ship_category('Expedition'),'Exploration')
        self.assertEqual(ship_category('Corvette'),'Corvettes & frigates')

    def test_basic_specs_reject_invalid_numbers_and_preserve_source_patch(self):
        data=vehicle_metadata(dict(crew='1 - 3',game_version='4.8.2',scu=0,length=float('nan'),width=-4))
        self.assertEqual(data['scu'],0)
        self.assertEqual(data['crew'],'1 - 3')
        self.assertEqual(data['patch'],'4.8.2')
        self.assertNotIn('length',data)
        self.assertNotIn('width',data)


if __name__=='__main__':unittest.main()
