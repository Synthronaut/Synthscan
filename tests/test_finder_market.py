import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from finder_market import catalog,listings,market_view,enrich_directory,FinderMarketService,comparable_prices,typical_range
from material_qualities import bundled,lookup
from tests.test_item_directory import Pool

NOW=1800000000
UUID='11111111-2222-3333-4444-555555555555'
def ad(**changes):
    row=dict(id=1,id_item=7,operation='sell',type='item',slug='ore-one',title='Ore',unit='scu',currency='UEC',price='4000000',quality=930,is_sold_out=0,date_added=NOW-10,date_approved=NOW-5,date_expiration=NOW+100)
    row.update(changes);return row
def payload(*rows):return dict(status='ok',data=list(rows))
def index():return catalog(payload(dict(id_item=7,item_name='Lindinium',item_uuid=UUID,quality_tier=6,operation='sell',currency='UEC',unit='scu',price_avg=4000000,listings_count=1,game_version='4.10.2')),NOW)

class MarketTests(unittest.TestCase):
    def test_parsing_excludes_expired_sold_wrong_currency_and_bad_links(self):
        rows,cap=listings(payload(ad(),ad(id=2,is_sold_out=1),ad(id=3,currency='USD'),ad(id=4,date_expiration=NOW-1),ad(id=5,slug='https://bad.test')),7,'sell',NOW)
        self.assertEqual([r['id'] for r in rows],[1]);self.assertFalse(cap)
    def test_wrong_market_identity_is_rejected(self):
        with self.assertRaises(ValueError):listings(payload(ad(id_item=8)),7,'sell',NOW)
    def test_quality_selection_is_exact_and_older_listings_are_excluded(self):
        rows,_=listings(payload(ad(),ad(id=2,quality=954,title='wrong quality'),ad(id=3,quality=None,title='unknown'),ad(id=4,title='too old',date_added=NOW-40*86400,date_approved=0)),7,'sell',NOW)
        view=market_view(index()['items']['7'],dict(checked_at=NOW,rows=rows),930,'4.10.2',NOW,exact=True)
        self.assertEqual(len(view['links']),1);self.assertNotIn('wrong quality',view['text']);self.assertNotIn('too old',view['text']);self.assertIn('930 exactly',view['text'])
    def test_prices_of_pieces_and_scu_are_never_combined(self):
        rows,_=listings(payload(ad(),ad(id=2,unit='unit',price=8000000)),7,'sell',NOW)
        text=market_view(index()['items']['7'],dict(checked_at=NOW,rows=rows),0,'4.10.2',NOW)['text']
        self.assertIn('4,000,000 aUEC / scu',text);self.assertIn('8,000,000 aUEC / unit',text)
        self.assertIn('No reliable estimate',text)
    def test_470_is_retained_as_entered_but_cannot_set_typical_market_floor(self):
        raw=[ad(id=i+1,quality=975,price=price) for i,price in enumerate([470,300000,350000,400000,450000,500000,1500000])]
        offers,_=listings(payload(*raw),7,'sell',NOW);good,warnings=comparable_prices(offers)
        self.assertIn(1,warnings);self.assertEqual(offers[0]['price'],470)
        self.assertEqual(typical_range([r['price'] for r in good]),(362500,487500,425000))
        text=market_view(index()['items']['7'],dict(checked_at=NOW,rows=offers),975,'4.10.2',NOW,exact=True)['text']
        self.assertIn('Typical asks: 362,500–487,500',text);self.assertNotIn('470 aUEC / scu',text);self.assertIn('excluded from all estimates and results',text)
        self.assertNotIn('470,000',text)
    def test_structured_hud_cards_share_the_filtered_prices_and_units(self):
        raw=[ad(id=i+1,quality=975,price=p) for i,p in enumerate([470,300000,350000,400000,450000,500000,1500000])]
        raw.append(ad(id=99,quality=975,unit='unit',price=8000000))
        offers,_=listings(payload(*raw),7,'sell',NOW)
        view=market_view(index()['items']['7'],dict(checked_at=NOW,rows=offers),975,'4.10.2',NOW,exact=True)
        self.assertEqual(view['presentation_schema'],1)
        sellers=view['sections'][0]
        self.assertEqual(sellers['operation'],'sell')
        self.assertNotIn(470,[r['price'] for r in sellers['offers']])
        groups={g['unit']:g for g in sellers['summaries']}
        self.assertEqual(groups['scu']['low'],362500)
        self.assertEqual(groups['scu']['high'],487500)
        self.assertEqual(groups['scu']['median'],425000)
        self.assertFalse(groups['unit']['reliable'])
        self.assertNotIn('low',groups['unit'])
        self.assertEqual(sellers['rejected'],1)
        self.assertTrue(all(r['url'].startswith('https://uexcorp.space/marketplace/') for r in sellers['offers']))

    def test_outlier_checks_do_not_mix_units_or_quality_values(self):
        raw=[ad(id=i+1,price=p) for i,p in enumerate([300000,350000,400000,450000,500000])]
        raw+=[ad(id=20,quality=348,price=470),ad(id=21,unit='cscu',price=4000)]
        offers,_=listings(payload(*raw),7,'sell',NOW);good,warnings=comparable_prices(offers,False)
        self.assertFalse(warnings);self.assertEqual(len(good),7)
    def test_multi_quality_ad_does_not_claim_its_cheapest_price_is_selected_grade(self):
        offers,_=listings(payload(ad(title='Aphorite 975q, 916q, 861q, 717q',quality=975,price=150000)),7,'sell',NOW)
        good,warnings=comparable_prices(offers);self.assertFalse(good);self.assertIn('another grade',warnings[1])
    def test_sparse_market_does_not_invent_missing_thousands(self):
        offers,_=listings(payload(ad(price=470)),7,'sell',NOW);good,warnings=comparable_prices(offers)
        self.assertFalse(warnings);self.assertEqual(good[0]['price'],470)
    def test_unclean_uex_averages_are_never_used_even_as_sparse_market_fallback(self):
        item=index()['items']['7'];item['averages'][0]['price_avg']=478
        offers,_=listings(payload(ad(price=400000)),7,'sell',NOW)
        text=market_view(item,dict(checked_at=NOW,rows=offers),930,'4.10.2',NOW,exact=True)['text']
        self.assertIn('No reliable estimate',text);self.assertNotIn('478',text);self.assertNotIn('QUALITY-TIER REFERENCE',text)
        self.assertNotIn('Typical asks',text)
    def test_old_patch_averages_do_not_become_current_quotes(self):
        item=index()['items']['7'];item['averages'][0]['game_version']='4.9.0'
        text=market_view(item,None,930,'4.10.2',NOW,exact=True)['text'];self.assertNotIn('QUALITY-TIER REFERENCE',text)
    def test_material_values_match_installed_lindinium_record(self):
        reference=bundled();row=lookup(reference,'Lindinium')
        self.assertEqual(row['values'],[305,585,618,729,853,930,954,1000]);self.assertEqual(lookup(reference,'Raw Lindinium')['values'],row['values'])
        for material in reference['materials']:
            self.assertTrue(material['values']);self.assertEqual(material['bands'][0]['start'],0);self.assertEqual(material['bands'][-1]['end'],1000)
    def test_directory_links_by_uuid_and_adds_compboard_aliases(self):
        market=[dict(market_uuid=UUID,market_item_id=7,market_identity='fingerprint',name='Lindinium')]
        row=dict(id=UUID,item_id=UUID,name='Lindinium',kind='Item',search='Lindinium')
        board=dict(id='board',item_id='board',name='DCHS-04 Power Processing Comp-Board',kind='Item',search='board')
        value=enrich_directory(dict(rows=[row,board]),market,bundled())
        self.assertEqual(row['market_item_id'],7);self.assertEqual(row['quality_values'],[305,585,618,729,853,930,954,1000]);self.assertEqual(board['market_board'],4);self.assertIn('comp4',board['search']);self.assertEqual(len(value['rows']),2)
    def test_market_only_material_also_receives_exact_quality_choices(self):
        market=[dict(id='market-7-key',item_id='market-7-key',market_uuid='',market_item_id=7,market_identity='key',name='Lindinium',kind='Market item',search='Lindinium')]
        value=enrich_directory(dict(rows=[]),market,bundled())
        self.assertEqual(value['rows'][0]['quality_values'],[305,585,618,729,853,930,954,1000])

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'finder_market_index.json').write_text(json.dumps(index()))
        self.service=FinderMarketService(self.root,42);self.service.pool.shutdown();self.service.pool=Pool();self.service.index_due=NOW+100
    def tearDown(self):self.service.close();self.temp.cleanup()
    def request(self,request='one',identifier=7,identity=None,owner=42):
        value=dict(owner_pid=owner,at=NOW,request_id=request,row_id=str(identifier),item_id=UUID,market_item_id=identifier,market_identity=identity or index()['items']['7']['identity'],quality_min=930,quality_exact=True)
        (self.root/'finder_market_request.json').write_text(json.dumps(value))
    def test_wrong_owner_cannot_start_lookup(self):
        self.request(owner=99);self.service.tick(NOW);self.assertIsNone(self.service.job)
    def test_pending_offers_are_not_published_as_finished_details(self):
        self.request();self.service.tick(NOW)
        path=self.root/'finder_market_detail.json'
        self.assertTrue(json.loads(path.read_text())['loading'])
        self.service.job.ready=True;self.service.job.value=dict(item=7,checked_at=NOW+1,rows=[])
        self.service.tick(NOW+1)
        self.assertFalse(json.loads(path.read_text())['loading'])
        self.service.tick(NOW+2)
        self.assertFalse(json.loads(path.read_text())['loading'])
    def test_wrong_fingerprint_cannot_start_lookup(self):
        self.request(identity='wrong');self.service.tick(NOW);self.assertIsNone(self.service.job)
    def test_late_result_never_replaces_next_item(self):
        self.request();self.service.tick(NOW);job=self.service.job
        self.request('two',8);job.ready=True;job.value=dict(item=7,checked_at=NOW,rows=[])
        self.service.tick(NOW+1);value=json.loads((self.root/'finder_market_detail.json').read_text())
        self.assertEqual(value['request_id'],'two');self.assertEqual(value['row_id'],'8');self.assertIn('No exact UEX',value['text'])
    def test_failed_lookup_retries_and_retains_last_good_cache(self):
        self.request();self.service.tick(NOW);job=self.service.job;job.ready=True;job.error=OSError('offline')
        self.service.tick(NOW+1);self.assertGreater(self.service.retry[7],NOW+1);self.assertIsNone(self.service.job)
        value=json.loads((self.root/'finder_market_detail.json').read_text())
        self.assertFalse(value['loading']);self.assertTrue(value['error'])

if __name__=='__main__':unittest.main()
