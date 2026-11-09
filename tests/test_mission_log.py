import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from mission_log import MissionLog, split_comparison
from mission_log_report import present
from questing import own_wallet, own_missions


ENTITY = 'urn:sc:reputations:org:geid:123'
CATALOG = {'definition': dict(rewards=[dict(entity=ENTITY, faction='InterSec', scope='FactionReputation', configured_amount=250)], payout=10000),
           '_names': {ENTITY: 'InterSec'}}


def reputation(score, at, character='one', session='session'):
    return dict(source='authenticated_reputation_service', own_character_verified=True, complete=True,
                character_key=character, read_at=at, play_session=session,
                records=[dict(entity=ENTITY, scope='FactionReputation', score=score)])


def wallet(amount, at, character='one'):
    return dict(source='authenticated_ledger_service', own_character_verified=True, character_key=character,
                read_at=at, play_session='session', balances={'AUEC': amount})


class MissionLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.book = MissionLog(self.root/'profile');self.addCleanup(self.book.close)

    def mission(self, mid='one', ended=100, status='Complete'):
        self.book.mission(dict(id=mid, at=70, status='Accepted', title='Test mission', definition_id='definition'), 'one', 'session')
        self.book.mission(dict(id=mid, at=ended, status=status), 'one', 'session')

    def test_actual_five_way_comparison_and_persistent_source_reads(self):
        self.mission();self.book.participation(dict(id='one', participants=5), 'one', 90)
        self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(1050, 110))
        self.book.wallet(wallet(100000, 80));self.book.wallet(wallet(102000, 110))
        row = self.book.view(CATALOG, now=140)['rows'][0]
        self.assertEqual(row['observed_rep'], 50)
        self.assertEqual(row['split'], 'Matches 1/5 split')
        self.assertEqual(row['observed_money'], 2000)
        self.assertEqual(row['money_comparison']['equal_split'], 2000)
        restored = MissionLog(self.root/'profile')
        try:self.assertEqual(restored.db.execute('SELECT count(*) FROM reputation').fetchone()[0], 2)
        finally:restored.close()

    def test_single_completion_inflow_is_named_and_categorized_as_correlated(self):
        self.mission();self.book.wallet(wallet(100000,80));self.book.wallet(wallet(102000,110))
        with self.book.db:self.book.set_meta('sessions',{'session':dict(id='session',started_at=50)})
        view=self.book.view(CATALOG,now=140);change=next(w for w in view['changes'] if w['kind']=='wallets')
        inferred=change['classification']
        self.assertEqual(inferred['category'],'mission_reward')
        self.assertEqual(inferred['source'],'Mission completion correlation')
        self.assertEqual(inferred['mission_title'],'Test mission')
        self.assertEqual(inferred['reward_organizations'],['InterSec'])
        self.assertIsNone(inferred['mission_giver'])
        self.assertEqual(change['annotation'],{})
        shown=present(view,CATALOG,mode='wallet',category='mission_reward')
        self.assertEqual(shown['display_count'],1)
        self.assertIn('correlated',shown['entries'][0]['cells'][1])
        self.assertIn('Test mission',shown['entries'][0]['detail'])
        recap=view['sessions'][0]['wallet_reconciliation']
        self.assertEqual(recap['classified_net'],0)
        self.assertEqual(recap['inferred_mission_net'],2000)
        self.assertEqual(recap['unclassified_net'],0)
        self.book.annotate(change['id'],'player_transfer')
        view=self.book.view(CATALOG,now=140)
        changed=next(w for w in view['changes'] if w['kind']=='wallets')
        self.assertEqual(changed['classification']['category'],'player_transfer')
        self.assertEqual(changed['classification']['source'],'Player classification')

    def test_overlapping_or_unmatched_inflows_are_not_auto_classified_as_missions(self):
        self.mission();self.mission('two',ended=102)
        self.book.wallet(wallet(100000,80));self.book.wallet(wallet(102000,110));self.book.wallet(wallet(103000,150))
        view=self.book.view(CATALOG,now=160)
        self.assertTrue(all(w['classification']['category']=='unclassified' for w in view['changes']))

    def test_overlapping_completions_never_receive_the_same_reward(self):
        self.mission();self.mission('two', ended=102)
        self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(1250, 110))
        rows = self.book.view(CATALOG, now=140)['rows']
        self.assertTrue(all(r['observed_rep'] is None for r in rows))
        self.assertTrue(all(r['analysis_status'] == 'Ambiguous window' for r in rows))

    def test_negative_rep_failure_is_logged_without_a_success_reward(self):
        self.mission(status='Fail')
        self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(900, 110))
        view = self.book.view(CATALOG, now=140);row=view['rows'][0]
        self.assertEqual(row['observed_rep'], -100)
        self.assertIsNone(row['base_rep'])
        data = present(view, CATALOG, mode='reputation', direction='losses')
        self.assertEqual(data['display_count'], 1)
        self.assertIn('-100', data['entries'][0]['detail'])

    def test_characters_and_sessions_never_supply_each_others_baseline(self):
        self.mission()
        self.book.reputation(reputation(1000, 80, 'other'))
        self.book.reputation(reputation(1250, 110))
        self.assertIsNone(self.book.view(CATALOG, now=140)['rows'][0]['observed_rep'])
        self.book.reputation(reputation(1300, 120, session='new-session'))
        windows = self.book.view(CATALOG, now=140)['changes']
        self.assertEqual(windows[0]['reason'], 'Session boundary')
        self.assertFalse(windows[0]['associated'])

    def test_missing_track_and_unverified_reads_are_not_zero(self):
        self.mission()
        self.book.reputation(reputation(1000, 80))
        bad = reputation(0, 110);bad['own_character_verified']=False
        self.assertFalse(self.book.reputation(bad))
        missing = reputation(0, 110);missing['records'][0]['entity']='different'
        self.book.reputation(missing)
        self.assertEqual(self.book.view(CATALOG, now=140)['changes'], [])

    def test_long_gap_and_stale_participant_count_do_not_prove_a_split(self):
        self.mission(ended=200)
        self.book.participation(dict(id='one', participants=5), 'one', 80)
        self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(1050, 210))
        row=self.book.view(CATALOG, now=240)['rows'][0]
        self.assertIsNone(row['participants'])
        self.assertIsNone(row['observed_rep'])
        self.assertEqual(row['windows'][0]['reason'], 'Long gap between reads')

    def test_out_of_order_snapshots_and_duplicate_completions_are_idempotent(self):
        self.mission();self.mission()
        self.book.reputation(reputation(1050, 110));self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(1050, 110))
        view=self.book.view(CATALOG, now=140)
        self.assertEqual(len(view['rows']), 1)
        self.assertEqual(view['reputation_reads'], 2)
        self.assertEqual(view['rows'][0]['observed_rep'], 50)

    def test_notification_event_hash_is_not_a_second_mission_identity(self):
        self.mission()
        self.book.mission(dict(id='notification-hash', mission_id='one', type='contract_completed', name='Test mission', at=100), 'one', 'session')
        self.assertEqual(len(self.book.view(CATALOG, now=140)['rows']), 1)

    def test_wallet_outgoing_and_unknown_transactions_remain_visible(self):
        self.book.wallet(wallet(100000, 80));self.book.wallet(wallet(99500, 110))
        view=self.book.view(CATALOG, now=140)
        data=present(view, CATALOG, mode='wallet', direction='losses')
        self.assertEqual(data['display_count'], 1)
        self.assertIn('No matching mission', data['entries'][0]['detail'])
        self.assertIn('offsetting transactions', data['entries'][0]['detail'])

    def test_session_recap_counts_failure_abandonment_and_measured_losses(self):
        self.mission();self.mission('failure', ended=140, status='Fail');self.mission('abandon', ended=180, status='Abandon')
        with self.book.db:self.book.set_meta('sessions', {'session':dict(id='session', started_at=50, ended_at=200)})
        self.book.reputation(reputation(1000, 80));self.book.reputation(reputation(900, 190))
        recap=self.book.view(CATALOG, now=240)['sessions'][0]
        self.assertEqual((recap['completed'],recap['failed'],recap['abandoned']), (1,1,1))
        self.assertEqual(recap['reputation'][0]['delta'], -100)

    def test_exports_include_wallet_evidence_and_escape_html_and_csv(self):
        self.mission();self.book.mission(dict(id='one', at=100, title='=1+1 <script>'), 'one', 'session')
        self.book.wallet(wallet(100000, 80));self.book.wallet(wallet(99500, 110))
        self.book.export(self.root/'report.csv', CATALOG)
        with (self.root/'report.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
        self.assertTrue(any(r['record_type']=='wallets' for r in rows))
        self.assertTrue(rows[0]['title'].startswith("'="))
        self.book.export(self.root/'report.html', CATALOG)
        text=(self.root/'report.html').read_text();self.assertNotIn('<script>', text);self.assertIn('&lt;script&gt;', text)
        self.book.export(self.root/'report.json', CATALOG)
        self.assertEqual(len(json.loads((self.root/'report.json').read_text())['evidence']['wallets']), 2)
        with self.assertRaises(ValueError):self.book.export(self.root/'profile/reputation_snapshot.json')

    def test_fraction_alone_does_not_invent_a_participant_count(self):
        result=split_comparison(250, 50)
        self.assertIsNone(result['equal_split'])
        self.assertEqual(result['effective_divisor'], 5)
        self.assertNotIn('Matches 1/5', result['match'])

    def test_unclassified_outflow_reconciles_and_player_categories_are_filterable(self):
        with self.book.db:self.book.set_meta('sessions', {'session':dict(id='session', started_at=50)})
        self.book.wallet(wallet(100000, 80));self.book.wallet(wallet(50000, 110))
        view=self.book.view(CATALOG, now=140)
        reconciliation=view['sessions'][0]['wallet_reconciliation']
        self.assertEqual(reconciliation['unclassified_net'], -50000)
        self.assertEqual(reconciliation['observed_decreases'], 50000)
        change=view['changes'][0]
        self.book.annotate(change['id'], 'repair', 'User checked the repair receipt')
        view=self.book.view(CATALOG, now=140)
        self.assertEqual(view['sessions'][0]['wallet_reconciliation']['unclassified_net'], 0)
        self.assertEqual(view['sessions'][0]['wallet_reconciliation']['classified_net'], -50000)
        display=present(view, CATALOG, mode='wallet', category='repair', direction='losses')
        self.assertEqual(display['display_count'], 1)
        self.assertIn('player classification', display['entries'][0]['detail'])
        self.assertEqual(present(view, CATALOG, mode='wallet', category='player_transfer')['display_count'], 0)

    def test_unchanged_wallet_does_not_invent_offsetting_transactions(self):
        self.book.wallet(wallet(100000, 80));self.book.wallet(wallet(100000, 110))
        self.assertEqual(present(self.book.view(CATALOG), CATALOG, mode='wallet')['display_count'], 0)

    def test_contract_carried_across_restart_is_completed_in_the_new_session(self):
        with self.book.db:self.book.set_meta('sessions', {'old':dict(id='old',started_at=50), 'new':dict(id='new',started_at=150)})
        self.book.mission(dict(id='carry',at=70,status='Accepted',title='Carried contract'), 'one', 'old')
        self.book.mission(dict(id='carry',at=200,status='Complete'), 'one', 'old')
        recaps={s['id']:s for s in self.book.view(CATALOG,now=240)['sessions']}
        self.assertEqual(recaps['new']['completed'], 1)
        self.assertEqual(recaps['old']['completed'], 0)

    def test_service_repeated_share_values_are_not_assumed_normalized(self):
        class Queries(list):
            def add(self):value=NS();self.append(value);return value
        class Client:
            subject='ours'
            def message(self, name):return NS(queries=Queries())
            def read(self, domain, service, method, request):
                if method=='QueryActiveMissions':return NS(mission_ids=[NS(mission_id='mission')])
                participants=[NS(player_urn='ours' if i==0 else 'other-'+str(i),share=[1.0]) for i in range(5)]
                return NS(missions=[NS(mission_id='mission',mission_template=NS(contract_definition_id='definition'),
                                      participants=participants,mission_owner_urn='other-1',mission_state=1)])
        row=own_missions(Client())[0]
        self.assertEqual(row['participants'], 5)
        self.assertEqual(row['own_share_values'], [1.0])
        self.assertIsNone(row['own_share'])
        self.assertFalse(row['is_owner'])
        self.assertNotIn('other-1', json.dumps(row))

    def test_historical_base_reward_does_not_change_with_new_game_definitions(self):
        self.mission();self.book.freeze_definitions(CATALOG)
        changed={'definition':dict(rewards=[dict(entity=ENTITY,scope='FactionReputation',configured_amount=999)],payout=999)}
        self.book.freeze_definitions(changed)
        self.assertEqual(self.book.view(changed,now=140)['rows'][0]['base_rep'],250)


class WalletOwnershipTests(unittest.TestCase):
    def test_foreign_wallet_is_rejected(self):
        client=NS(subject='ours', message=lambda _: NS(), read=lambda *args: NS(ledgers=[NS(owner_urn='another-character')]))
        with self.assertRaisesRegex(ValueError, 'ownership'):own_wallet(client)


if __name__ == '__main__':unittest.main()
