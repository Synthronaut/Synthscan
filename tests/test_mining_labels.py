import unittest
from mining_labels import compact_mining_labels
from blueprint_strings import annotate_blueprint_text

class MiningLabelTests(unittest.TestCase):
    def test_exact_labels_only_preserve_bom_endings_and_prose(self):
        text='\ufeffactor_species_creature_valakkar_juvenile=Valakkar (Juvenile)\r\nactor_species_creature_valakkar_juvenile_irradiated=Irradiated Valakkar (Juvenile)\r\nactor_species_creature_valakkar=Valakkar (Adult)\r\nmission_desc=Collect Juvenile Valakkar\r\n'
        result,n=compact_mining_labels(text);self.assertEqual(n,3)
        self.assertTrue(result.startswith('\ufeffactor_species_creature_valakkar_juvenile=<EM4>Vlk Jr</EM4>\r\n'))
        self.assertIn('=<EM4>Irr Vlk Jr</EM4>\r\n',result);self.assertIn('=<EM4>Valakkar (Adult)</EM4>\r\n',result);self.assertIn('mission_desc=Collect Juvenile Valakkar\r\n',result)
        self.assertEqual(compact_mining_labels(result),(result,0))
    def test_native_blueprint_sync_also_applies_labels(self):
        text='actor_species_creature_valakkar_juvenile=Valakkar (Juvenile)\n'
        result,stats=annotate_blueprint_text(text,[])
        self.assertIn('=<EM4>Vlk Jr</EM4>\n',result);self.assertEqual(stats['mining_label_updates'],1)

if __name__=='__main__':unittest.main()
