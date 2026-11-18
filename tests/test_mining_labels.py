import unittest
from mining_labels import compact_mining_labels
from blueprint_strings import annotate_blueprint_text

class MiningLabelTests(unittest.TestCase):
    def test_exact_labels_only_preserve_bom_endings_and_prose(self):
        text='\ufeffactor_species_creature_valakkar_juvenile=Valakkar (Juvenile)\r\nactor_species_creature_valakkar_juvenile_irradiated=Irradiated Valakkar (Juvenile)\r\nactor_species_creature_valakkar=Valakkar (Adult)\r\nmission_desc=Collect Juvenile Valakkar\r\n'
        result,n=compact_mining_labels(text,targets={'cyan':[],'red':[],'amounts':{}});self.assertEqual(n,3)
        self.assertTrue(result.startswith('\ufeffactor_species_creature_valakkar_juvenile=<EM3>Vlk Jr</EM3>\r\n'))
        self.assertIn('=<EM3>Irr Vlk Jr</EM3>\r\n',result);self.assertIn('=<EM3>Valakkar (Adult)</EM3>\r\n',result);self.assertIn('mission_desc=Collect Juvenile Valakkar\r\n',result)
        self.assertEqual(compact_mining_labels(result,targets={'cyan':[],'red':[],'amounts':{}}),(result,0))
    def test_native_blueprint_sync_also_applies_labels(self):
        text='actor_species_creature_valakkar_juvenile=Valakkar (Juvenile)\n'
        result,stats=annotate_blueprint_text(text,[])
        self.assertIn('=<EM3>Vlk Jr</EM3>\n',result);self.assertEqual(stats['mining_label_updates'],1)
    def test_user_cyan_and_red_targets_with_craft_amounts(self):
        text='mineabletype_primary_riccite=Riccite\nhud_mining_fps_rock_name_3=Hadanite\nmineabletype_primary_iron=Iron\nactor_species_creature_quaziGrazer=Quasi\n'
        targets={'cyan':['Riccite','Hadanite'],'red':['Iron'],'amounts':{'Riccite':'12 SCU'}}
        result,n=compact_mining_labels(text,targets=targets);self.assertEqual(n,4)
        self.assertIn('mineabletype_primary_riccite=<EM1>RIC (need 12 SCU)</EM1>\n',result)
        self.assertIn('hud_mining_fps_rock_name_3=<EM1>HAD</EM1>\n',result)
        self.assertIn('mineabletype_primary_iron=<EM4>IRON</EM4>\n',result)
        self.assertIn('actor_species_creature_quaziGrazer=<EM3>QzG</EM3>\n',result)
    def test_harvestables_default_yellow_and_support_cyan_red(self):
        text='items_commodities_decaripod=Decari Pod\nitems_commodities_sunsetberry=Sunset Berries\nitems_commodities_fotiascrub=Fotia Seedpod\n'
        default_res,_=compact_mining_labels(text,targets={'cyan':[],'red':[],'amounts':{}})
        self.assertIn('items_commodities_decaripod=<EM3>Decari Pod</EM3>\n',default_res)
        self.assertIn('items_commodities_sunsetberry=<EM3>Sunset Berries</EM3>\n',default_res)
        targeted,_=compact_mining_labels(text,targets={'cyan':['Sunset Berries'],'red':['Fotia Seedpod'],'amounts':{}})
        self.assertIn('items_commodities_sunsetberry=<EM1>Sunset Berries</EM1>\n',targeted)
        self.assertIn('items_commodities_fotiascrub=<EM4>Fotia Seedpod</EM4>\n',targeted)

if __name__=='__main__':unittest.main()
