import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from item_directory import ItemDirectoryService, SHOP_TTL, shop_rows, shop_text, shop_view, source_lines,vehicle_rows,fetch_shops,is_component,lookup_identity
from native_workspace_data import library_export

A='082c2ffb-1c54-45e5-90bf-f411d9a06425'
B='11111111-2222-3333-4444-555555555555'


def listing(**changes):
    return dict(id_terminal=4,terminal_name='Ship Weapons',star_system_name='Stanton',
                space_station_name='MIC-L2',price_buy=240,price_sell=900,
                game_version='4.10.1',date_modified=80,**changes)


class Future:
    def __init__(self):self.ready=False;self.value=None;self.error=None
    def done(self):return self.ready
    def result(self):
        assert self.ready,'Polling must never wait for a worker'
        if self.error:raise self.error
        return self.value


class Pool:
    def __init__(self):self.jobs=[]
    def submit(self,fn,*args):
        future=Future();self.jobs.append((fn,args,future));return future
    def shutdown(self,**kwargs):pass


class DirectoryTests(unittest.TestCase):
    def test_shop_cards_keep_price_identity_location_and_patch(self):
        row=dict(price=34398000,location='Stanton → ArcCorp → Area 18 → Astro Armada - Area 18',game_version='4.10.1',reported_at=80)
        view=shop_view(dict(item_id='vehicle-1',checked_at=100,rows=[row]),'4.10.2',101)
        self.assertEqual(view['rows'][0]['price'],34398000)
        self.assertEqual(view['rows'][0]['shop'],'Astro Armada')
        self.assertEqual(view['rows'][0]['place'],'ArcCorp · Area 18')
        self.assertTrue(view['rows'][0]['different_patch'])
        self.assertIn('Reported',view['rows'][0]['reported_label'])
        self.assertFalse(view['stale'])
        self.assertTrue(shop_view(dict(checked_at=100,rows=[row]),'4.10.2',101,error='offline')['stale'])
        self.assertEqual(shop_view(None,'4.10.2',101)['rows'],[])

    def test_location_omits_system_and_repeated_terminal_city_including_old_cache(self):
        raw=dict(listing(),planet_name='ArcCorp',city_name='Area 18',space_station_name='',terminal_name='Astro Armada - Area 18')
        rows=shop_rows(dict(status='ok',data=[raw]));self.assertEqual(rows[0]['location'],'ArcCorp → Area 18 → Astro Armada')
        rows[0]['location']='Stanton → ArcCorp → Area 18 → Astro Armada - Area 18'
        text=shop_text(dict(checked_at=100,rows=rows),'4.10.1',101)
        self.assertIn('ArcCorp → Area 18 → Astro Armada — 240',text);self.assertNotIn('Stanton',text);self.assertNotIn('Armada - Area',text)

    def test_shop_purchase_direction_and_terminal_deduplication(self):
        older=listing();newer=dict(older,date_modified=90,price_buy=250)
        sell_only=dict(older,id_terminal=5,price_buy=0,price_sell=800)
        player=dict(older,id_terminal=6,terminal_is_player_owned=1)
        rows=shop_rows(dict(status='ok',data=[older,newer,sell_only,player]))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['price'],250)
        self.assertIn('MIC-L2',rows[0]['location'])
    def test_source_failures_are_not_empty_successes(self):
        for payload in ([],{'status':'error','data':[]},{'status':'ok','data':None}):
            with self.assertRaises(ValueError):shop_rows(payload)
    def test_old_patch_and_cached_age_are_visible(self):
        cache=dict(checked_at=100,rows=shop_rows(dict(status='ok',data=[listing()])))
        text=shop_text(cache,'4.10.2',100+SHOP_TTL+1,error='offline')
        self.assertIn('DIFFERENT PATCH',text);self.assertIn('cached / refresh overdue',text)
        self.assertIn('240 aUEC each',text);self.assertIn('Reported',text);self.assertIn('last successful',text)
    def test_no_listing_is_not_a_claim_of_unavailability(self):
        self.assertIn('does not prove',shop_text(dict(checked_at=100,rows=[]),'4.10.2',101))
    def test_pool_chance_does_not_imply_guaranteed_individual_blueprint(self):
        catalog=SimpleNamespace(sources=lambda bp:[dict(title='Mission',chance=100,pool_size=14)])
        text='\n'.join(source_lines({},catalog,briefings=True))
        self.assertIn('Individual blueprint chance is not specified',text)
        self.assertIn('reference annotations',text)
    def test_catalog_links_by_item_identity_not_identical_display_names(self):
        with TemporaryDirectory() as temp:
            entries=[dict(id=A,name='Same',kind='Item',type='Missile',category='Weapons'),
                     dict(id=B,name='Same',kind='Item',type='Missile',category='Weapons')]
            bp=dict(id='bp1',item_id=A,name='Same',category='Weapons',type='Missile',seconds=30,
                    slots=[],sources=[0],description='',known_from_start=False)
            mission=dict(title='A mission',faction='Faction',system='Pyro',standing='Neutral')
            catalog=SimpleNamespace(items=[bp],sources=lambda b:[mission],data=dict(missions=[mission]),search_text={'bp1':'same a mission'})
            game=SimpleNamespace(entries=entries,image_path=lambda e:None,resolve=lambda value:None,data=dict(provenance={'build':{}}))
            path=Path(temp)/'library.json';library_export(path,game,catalog)
            rows={r['id']:r for r in json.loads(path.read_text())['rows']}
            self.assertIn('A mission',rows[A]['detail']);self.assertNotIn('A mission',rows[B]['detail'])
            self.assertIn('A mission',rows[A]['search']);self.assertEqual(rows['bp1']['item_id'],A)
            self.assertEqual(rows[A]['finder_blueprints'][0]['missions'][0]['title'],'A mission')
            self.assertEqual(rows[A]['finder_blueprints'][0]['reference_index'],-1)
            self.assertEqual(rows[B]['finder_blueprints'],[])

    def test_finder_recipes_keep_quantities_quality_and_exact_ownership_identity(self):
        import native_workspace_data as workspace
        baseline=json.loads((workspace.ROOT/'data/crafting_catalog.json').read_text(encoding='utf-8'))['blueprints']
        original=baseline[0]
        bp=dict(original,item_id=A,native_verified=True,category='Weapons',type='Missile',seconds=30,slots=[dict(name='Metal',material='Copper',amount=2.5,unit='SCU',min_quality=849,effects=[])])
        catalog=SimpleNamespace(items=[bp],sources=lambda b:[],search_text={bp['id']:bp['name']})
        game=SimpleNamespace(entries=[dict(id=A,name='Crafted item',kind='Item',type='Missile',category='Weapons')],image_path=lambda e:None,resolve=lambda value:None,data=dict(provenance={'build':{}}))
        with TemporaryDirectory() as folder:
            path=Path(folder)/'library.json';library_export(path,game,catalog)
            row=next(r for r in json.loads(path.read_text())['rows'] if r['id']==A)
            details=row['finder_blueprints'][0]
            self.assertEqual(details['reference_index'],0);self.assertEqual(details['reference_name'],original['name'])
            self.assertEqual(details['materials'],[dict(material='Copper',amount=2.5,unit='SCU',min_quality=849)])
            self.assertTrue(details['recipe_verified'])


class DirectoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name)
        self.service=ItemDirectoryService(self.root,42,token=lambda:'generation1')
        self.service.pool.shutdown();self.service.pool=Pool()
    def tearDown(self):self.service.close();self.temp.cleanup()
    def request(self,identifier=A,owner=42,at=100):
        (self.root/'item_directory_request.json').write_text(json.dumps(dict(owner_pid=owner,at=at,item_id=identifier,row_id=identifier,request_id=identifier)))
    def result(self):return json.loads((self.root/'item_directory_detail.json').read_text())
    def test_wrong_owner_and_old_requests_do_not_trigger_network(self):
        self.request(owner=99);self.service.tick(100);self.assertIsNone(self.service.lookup)
        self.request(at=1);self.service.tick(101);self.assertIsNone(self.service.lookup)
    def test_loading_is_explicit_until_complete_and_failure_is_terminal(self):
        self.request();self.service.tick(100)
        self.assertTrue(self.result()['loading'])
        self.service.lookup.value=dict(item_id=A,checked_at=101,rows=[]);self.service.lookup.ready=True
        self.service.tick(101)
        self.assertFalse(self.result()['loading']);self.assertFalse(self.result()['error'])
        self.request(B,at=102);self.service.tick(102)
        self.assertTrue(self.result()['loading'])
        self.service.lookup.error=OSError('offline');self.service.lookup.ready=True;self.service.tick(103)
        self.assertFalse(self.result()['loading']);self.assertTrue(self.result()['error'])
    def test_late_lookup_is_cached_but_never_displayed_for_next_selection(self):
        self.request();self.service.tick(100);first=self.service.lookup
        self.request(B,at=101);self.service.tick(101)
        first.value=dict(item_id=A,checked_at=101,rows=[]);first.ready=True
        self.service.tick(102)
        self.assertEqual(self.result()['item_id'],B);self.assertNotIn('No retail',self.result()['text'])
        self.assertEqual(self.service.lookup_id,B)
        self.assertTrue((self.root/'item_shops'/f'{A}.json').exists())
    def test_fresh_persistent_cache_avoids_request_and_failed_refresh_keeps_it(self):
        folder=self.root/'item_shops';folder.mkdir()
        cache=dict(item_id=A,checked_at=100,rows=shop_rows(dict(status='ok',data=[listing()])))
        (folder/f'{A}.json').write_text(json.dumps(cache))
        self.request();self.service.tick(101);self.assertIsNone(self.service.lookup)
        self.assertIn('240 aUEC',self.result()['text'])
        self.assertFalse(self.result()['loading'])
        self.service.tick(101+SHOP_TTL);future=self.service.lookup
        self.assertTrue(self.result()['loading'])
        future.error=OSError('offline');future.ready=True;self.service.tick(102+SHOP_TTL)
        self.assertIn('last successful',self.result()['text']);self.assertIn('240 aUEC',self.result()['text'])
        self.assertIsNone(self.service.lookup)
    def test_catalog_generation_changes_schedule_a_new_background_export(self):
        self.service.tick(100);first=self.service.export
        first.value=dict(revision='one',build=dict(Branch='sc-alpha-4.10.2'));first.ready=True
        self.service.tick(101);self.assertEqual(self.service.current_patch,'4.10.2')
        self.service.token=lambda:'generation2';self.service.tick(131)
        self.assertIsNotNone(self.service.export);self.assertIsNot(self.service.export,first)

    def test_vehicle_requests_use_distinct_cache_identity(self):
        row=vehicle_rows(dict(status='ok',data=[dict(id=122,name='MOLE',uuid=A)]),100)[0]
        self.request(row['item_id']);self.service.tick(100)
        self.assertEqual(self.service.lookup_id,row['item_id'])
        self.assertEqual(self.result()['item_id'],row['item_id'])

    def test_vehicle_catalog_refresh_rebuilds_index_and_failure_keeps_last_catalog(self):
        self.service.next_vehicle_check=0;self.service.tick(100)
        future=self.service.vehicle_future;export=self.service.export
        future.value=dict(checked_at=100,rows=vehicle_rows(dict(status='ok',data=[dict(id=1,name='Ship')]),100));future.ready=True
        export.value=dict(revision='old',build={});export.ready=True
        self.service.tick(101)
        saved=(self.root/'directory_vehicles.json').read_bytes()
        self.assertIsNot(self.service.export,export)
        self.service.next_vehicle_check=0;self.service.tick(102)
        self.service.vehicle_future.error=OSError('offline');self.service.vehicle_future.ready=True
        self.service.tick(103)
        self.assertEqual((self.root/'directory_vehicles.json').read_bytes(),saved)
        self.assertGreater(self.service.next_vehicle_check,103)


class VehicleAndComponentTests(unittest.TestCase):
    def test_vehicles_without_uuid_are_searchable_and_variants_are_distinct(self):
        rows=vehicle_rows(dict(status='ok',data=[dict(id=1,name='Ship'),dict(id=2,name='Ship',is_ground_vehicle=1)]),100)
        self.assertNotEqual(rows[0]['id'],rows[1]['id'])
        self.assertEqual([r['kind'] for r in rows],['Ship','Vehicle'])
        for row in rows:self.assertEqual(lookup_identity(row['item_id']),row['id'])
    def test_reused_vehicle_id_does_not_reuse_price_cache(self):
        def key(name):return vehicle_rows(dict(status='ok',data=[dict(id=1,name=name)]),100)[0]['item_id']
        self.assertNotEqual(key('Ship A'),key('Ship B'))
    def test_bad_or_duplicate_vehicle_ids_fail_closed(self):
        for data in ([dict(id=1,name='A'),dict(id=1,name='B')],[dict(id=True,name='A')],[]):
            with self.assertRaises(ValueError):vehicle_rows(dict(status='ok',data=data),100)
    def test_vehicle_fetch_uses_in_game_purchase_endpoint(self):
        key=vehicle_rows(dict(status='ok',data=[dict(id=148,name='Prospector')]),100)[0]['item_id']
        with patch('item_directory.uex_json',return_value=dict(status='ok',data=[dict(listing(),id_vehicle=148)])) as get:
            result=fetch_shops(key)
        get.assert_called_once_with('vehicles_purchases_prices?id_vehicle=148')
        self.assertEqual(result['rows'][0]['price'],240)
    def test_ship_component_filter_includes_heads_modules_and_weapons(self):
        for typ in ('WeaponMining','MiningModifier','WeaponGun','SalvageHead'):
            self.assertTrue(is_component(dict(type=typ,record='libs/foundry/records/entities/scitem/ships/utility/example.json')))
        self.assertTrue(is_component(dict(category='Ship components',type='Shield')))
        self.assertFalse(is_component(dict(type='WeaponPersonal',record='libs/foundry/records/entities/scitem/weapons/rifle.json')))


if __name__=='__main__':unittest.main()
