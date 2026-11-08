import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from ship_hardpoints import extract


def raw(ports=(),entries=()):
    return dict(Components=[dict(_Type_='SItemPortContainerComponentParams',Ports=list(ports)),dict(_Type_='SEntityComponentDefaultLoadoutParams',loadout=dict(entries=list(entries)))])


def port(name,size,types):
    return dict(Name=name,MinSize=size,MaxSize=size,Types=[dict(Type=t,SubTypes=['Gun']) for t in types])


class Store:
    def __init__(self,values):self.values=values
    def value(self,key):return self.values[key]
    def read(self,key):return {'_RecordValue_':self.values[key]}


class ShipHardpointTests(unittest.TestCase):
    def run_extract(self,xml,record=None,values=None,mod=''):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'ship.xml';path.write_text(xml,encoding='utf-8')
            return extract(Store(values or {}),record or raw(),{},path,mod)

    def test_disabled_third_shield_is_not_a_slot_until_variant_activates_it(self):
        xml='<Vehicle><Parts><Part name="left"><ItemPort minSize="3" maxSize="3"><Types><Type type="Shield"/></Types></ItemPort></Part><Part name="right"><ItemPort minSize="3" maxSize="3"><Types><Type type="Shield"/></Types></ItemPort></Part><Part name="center"><ItemPort id="center" skipPart="1" minSize="3" maxSize="3"><Types><Type type="Shield"/></Types></ItemPort></Part></Parts><Modifications><Modification name="three"><Elems><Elem idRef="center" name="skipPart" value="0"/></Elems></Modification></Modifications></Vehicle>'
        self.assertEqual(self.run_extract(xml)['groups'][0]['count'],2)
        self.assertEqual(self.run_extract(xml,mod='three')['groups'][0]['count'],3)
        self.assertEqual(self.run_extract(xml)['groups'][0]['count'],2)

    def test_gimbal_socket_not_counted_twice_or_confused_with_turret_mount_size(self):
        p=port('root',5,['Turret']);record=raw([p],[dict(itemPortName='root',entityClassReference='turret',loadout=dict(entries=[dict(itemPortName='a',entityClassReference='gimbal'),dict(itemPortName='b',entityClassReference='gimbal')]))])
        turret=raw([port('a',4,['WeaponGun','Turret']),port('b',4,['WeaponGun','Turret'])])
        gimbal=raw([port('gun',4,['WeaponGun'])])
        result=self.run_extract('<Vehicle/>',record,dict(turret=turret,gimbal=gimbal))
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['groups'],[dict(label='Turret guns',count=2,minimum=4,maximum=4)])

    def test_dcb_limits_override_xml_and_personal_weapon_racks_are_ignored(self):
        xml='<Vehicle><Parts><Part name="qt"><ItemPort minSize="1" maxSize="1"><Types><Type type="QuantumDrive"/></Types></ItemPort></Part></Parts></Vehicle>'
        result=self.run_extract(xml,raw([port('qt',3,['QuantumDrive']),port('rack',1,['WeaponPersonal'])]))
        self.assertEqual(result['groups'],[dict(label='Quantum drive',count=1,minimum=3,maximum=3)])

    def test_missing_exact_turret_record_is_partial_not_an_invented_gun_size(self):
        result=self.run_extract('<Vehicle/>',raw([port('turret',7,['Turret'])],[dict(itemPortName='turret',entityClassReference='missing')]))
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['groups'],[])

    def test_lowercase_golem_xml_attributes_preserve_component_slots(self):
        xml='<Vehicle><Parts><Part name="shield"><ItemPort minsize="1" maxsize="1"><Types><Type type="Shield"/></Types></ItemPort></Part></Parts></Vehicle>'
        result=self.run_extract(xml)
        self.assertEqual(result['groups'],[dict(label='Shields',count=1,minimum=1,maximum=1)])

    def test_mining_cab_size_is_not_mistaken_for_laser_size(self):
        record=raw([port('cab',4,['UtilityTurret'])],[dict(itemPortName='cab',entityClassReference='cab')])
        cab=raw([port('laser',2,['WeaponMining'])])
        result=self.run_extract('<Vehicle/>',record,dict(cab=cab))
        self.assertEqual(result['groups'],[dict(label='Mining lasers',count=1,minimum=2,maximum=2)])

    def test_external_or_unknown_variant_patch_is_unavailable(self):
        xml='<Vehicle><Modifications><Modification name="external" patchFile="other.xml"/></Modifications></Vehicle>'
        self.assertEqual(self.run_extract(xml,mod='external')['status'],'unavailable')
        self.assertEqual(self.run_extract(xml,mod='missing')['status'],'unavailable')

    def test_uninstalled_turret_does_not_invent_gun_capacity(self):
        result=self.run_extract('<Vehicle/>',raw([port('turret',10,['Turret'])]))
        self.assertEqual(result['groups'],[])


if __name__=='__main__':unittest.main()
