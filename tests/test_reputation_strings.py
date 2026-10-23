import unittest
from reputation_strings import annotate_names


class ReputationNameTests(unittest.TestCase):
    def setUp(self):
        self.text='\ufeffAdagio_Name=Adagio Holdings\r\nNeutral=Neutral\r\nMission=Keep [OWNED] tags\r\n'
        self.snapshot=dict(own_character_verified=True,complete=True,read_at=100,character_key='character',
                           records=[dict(entity='adagio',scope='FactionReputation',score=249)])
        self.factions={'adagio':dict(key='@Adagio_Name')}
        self.scopes={'FactionReputation':dict(display_name='Standing',standings=[dict(minimum=0),dict(minimum=800),dict(minimum=2200)])}

    def test_only_specific_name_changes_preserving_bom_newlines_and_other_patches(self):
        result,state=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        self.assertEqual(result,'\ufeffAdagio_Name=Adagio Holdings (249 / 800)\r\nNeutral=Neutral\r\nMission=Keep [OWNED] tags\r\n')
        self.assertEqual(state['entries']['adagio_name']['tracks'][0]['next_minimum'],800)

    def test_refresh_replaces_annotation_instead_of_appending(self):
        first,state=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        self.snapshot['records'][0]['score']=349
        second,_=annotate_names(first,self.snapshot,self.factions,self.scopes,state)
        self.assertIn('Adagio Holdings (349 / 800)',second)
        self.assertNotIn('(249',second)

    def test_primary_track_is_labeled_when_affinity_also_exists(self):
        self.snapshot['records'].append(dict(entity='adagio',scope='Affinity',score=50))
        result,_=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        self.assertIn('(Standing: 249 / 800)',result)

    def test_lost_record_restores_owned_annotation_not_zero(self):
        first,state=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        self.snapshot['records']=[]
        second,_=annotate_names(first,self.snapshot,self.factions,self.scopes,state)
        self.assertEqual(second,self.text)

    def test_user_edit_conflict_is_not_overwritten(self):
        first,state=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        with self.assertRaises(ValueError):
            annotate_names(first.replace('Adagio Holdings','Custom name'),self.snapshot,self.factions,self.scopes,state)

    def test_shared_name_key_is_not_annotated(self):
        self.factions['other']=dict(key='@Adagio_Name')
        result,state=annotate_names(self.text,self.snapshot,self.factions,self.scopes)
        self.assertEqual(result,self.text)
        self.assertFalse(state['entries'])

    def test_unverified_snapshot_is_rejected(self):
        self.snapshot['own_character_verified']=False
        with self.assertRaises(ValueError):annotate_names(self.text,self.snapshot,self.factions,self.scopes)


if __name__=='__main__':unittest.main()
