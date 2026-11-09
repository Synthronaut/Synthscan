import csv
import json
from pathlib import Path
import tempfile
import unittest
from mission_log import MissionLog
from mission_hud import snapshot


class MissionHUDTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.book=MissionLog(self.root/'profile');self.addCleanup(self.book.close)

    def accepted(self, at=100, source='game_log'):
        self.book.mission(dict(id='m',at=at,status='Accepted',title='Demo',source=source),session='s')

    def test_active_timer_uses_acceptance_and_stays_stable_across_app_restarts(self):
        self.accepted()
        row=self.book.view(now=140)['rows'][0]
        self.assertEqual(row['elapsed_seconds'],40)
        reopened=MissionLog(self.root/'profile')
        try:self.assertEqual(reopened.view(now=170)['rows'][0]['elapsed_seconds'],70)
        finally:reopened.close()

    def test_end_freezes_duration_duplicate_events_do_not_restart_it(self):
        self.accepted();self.book.mission(dict(id='m',at=160,status='Complete'))
        self.accepted(130)
        row=self.book.view(now=500)['rows'][0]
        self.assertEqual(row['duration_seconds'],60)
        self.assertIsNone(row['elapsed_seconds'])
        self.assertEqual(row['status'],'Complete')

    def test_service_first_observation_is_not_an_acceptance_timestamp(self):
        self.accepted(source='own_mission_service')
        row=self.book.view(now=140)['rows'][0]
        self.assertIsNone(row['elapsed_seconds']);self.assertEqual(row['timing_status'],'unknown')
        self.accepted(90)
        self.assertEqual(self.book.view(now=140)['rows'][0]['elapsed_seconds'],50)

    def test_missing_or_reversed_acceptance_stays_unknown(self):
        self.book.mission(dict(id='m',at=160,status='Complete'))
        self.assertIsNone(self.book.view(now=200)['rows'][0]['duration_seconds'])
        self.accepted(170)
        self.assertIsNone(self.book.view(now=200)['rows'][0]['duration_seconds'])

    def test_active_selection_uses_id_and_does_not_guess_between_duplicate_titles(self):
        self.accepted();self.book.mission(dict(id='other',at=110,status='Accepted',title='Demo',source='game_log'),session='s')
        view=self.book.view(now=140)
        q=dict(active_ids=['m','other'],title='Demo')
        self.assertEqual(snapshot(view,q,'s',now=140,recording=True)['active'],{})
        q['selected_id']='m'
        self.assertEqual(snapshot(view,q,'s',now=140,recording=True)['active']['elapsed_seconds'],40)
        self.assertEqual(snapshot(view,q,'s',now=140,recording=True,game_running=False)['active'],{})

    def test_ledger_keeps_losses_and_separates_session_and_currency(self):
        changes=[dict(kind=k,track=t,delta=d,end=at,session=s) for k,t,d,at,s in [
            ('wallets','AUEC',1000,120,'s'),('wallets','AUEC',-200,130,'s'),
            ('wallets','UEC',90000,135,'s'),('wallets','AUEC',9999,90,'old'),
            ('reputation','entity|Standing',-25,132,'s')]]
        view=dict(rows=[],changes=changes,sessions=[])
        hud=snapshot(view,{},'s',now=140,recording=True,names={'entity':'Demo Org'})
        self.assertEqual(hud['wallet']['incoming'],1000);self.assertEqual(hud['wallet']['outgoing'],200)
        self.assertIsNone(hud['wallet']['balance'])
        self.assertEqual(hud['reputation']['entries'][0]['delta'],-25)
        self.assertEqual(hud['reputation']['entries'][0]['label'],'Demo Org / Standing')

    def test_duration_is_in_reports_and_exports(self):
        self.accepted();self.book.mission(dict(id='m',at=160,status='Complete'))
        from mission_log_report import present
        shown=present(self.book.view(now=200),mode='missions')
        self.assertIn(['Duration',94],shown['columns']);self.assertIn('01:00',shown['entries'][0]['cells'])
        target=self.root/'export.csv';self.book.export(target)
        with target.open(encoding='utf-8-sig',newline='') as stream:row=next(csv.DictReader(stream))
        self.assertEqual(float(row['duration_seconds']),60)
        target=self.root/'export.json';self.book.export(target)
        self.assertEqual(json.loads(target.read_text())['rows'][0]['duration_seconds'],60)

    def test_merged_objective_without_acceptance_evidence_cannot_start_timer(self):
        self.book.mission(dict(id='m',at=120,status='Accepted',objective='Later objective'))
        self.assertIsNone(self.book.view(now=140)['rows'][0]['elapsed_seconds'])

    def test_preserved_acceptance_in_merged_journal_uses_original_timestamp(self):
        self.book.mission(dict(id='m',at=130,status='Accepted',objective='Later objective',accepted_log_at=100))
        self.assertEqual(self.book.view(now=140)['rows'][0]['elapsed_seconds'],40)

    def test_completion_summary_reports_actual_five_way_gain_not_configured_base(self):
        from tests.test_mission_log import CATALOG, reputation, wallet
        self.book.mission(dict(id='m',at=70,status='Accepted',title='Demo contract',definition_id='definition',source='game_log'),'one','session')
        self.book.participation(dict(id='m',participants=5),'one',90)
        self.book.reputation(reputation(1000,80));self.book.wallet(wallet(100000,80))
        self.book.mission(dict(id='m',at=100,status='Complete'),'one','session')
        pending=snapshot(self.book.view(CATALOG,now=102),{},'session',now=102,recording=True)
        self.assertIsNone(pending['latest_completion']['rep_observed'])
        self.book.reputation(reputation(1050,110));self.book.wallet(wallet(102000,110))
        hud=snapshot(self.book.view(CATALOG,now=115),{},'session',now=115,recording=True,names=CATALOG['_names'])
        completion=hud['latest_completion']
        self.assertEqual(completion['rep_base'],250)
        self.assertEqual(completion['rep_observed'],50)
        self.assertEqual(completion['participants'],5)
        self.assertEqual(completion['comparison'],'Matches 1/5 split')
        self.assertEqual(hud['reputation']['entries'][0]['before'],1000)
        self.assertEqual(hud['reputation']['entries'][0]['after'],1050)
        self.assertEqual(hud['reputation']['entries'][0]['label'],'InterSec')
        self.assertIn('1,000 → 1,050','\n'.join(completion['lines']))
        self.assertIn('Demo contract',hud['wallet']['entries'][0]['label'])
        after_restart=snapshot(self.book.view(CATALOG,now=200),{},'new-session',now=200,recording=True)
        self.assertEqual(after_restart['latest_completion']['id'],'m')
        self.assertIn('Previous session',after_restart['latest_completion']['time'])


if __name__=='__main__':unittest.main()
