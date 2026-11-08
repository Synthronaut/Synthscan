import unittest
from shard_observations import observation_index,popup_context
from telemetry_core import utc_iso
from native_session_hud import hud_state
from session_timeline import timeline

ASIA='pub_ape1a_12881860_110'
US='pub_use1b_12881860_110'
OTHER='pub_ape1a_12913470_110'


def visit(full,at,**changes):
    return dict(id=str(at),full_shard_id=full,joined_at=utc_iso(at),left_at=None,
                region_raw=full.split('_')[1],shard_id=full.rsplit('_',1)[1],locations=[],notes='',**changes)


class ShardObservationTests(unittest.TestCase):
    def test_first_visit_never_implies_server_creation_or_uptime(self):
        value=observation_index([visit(ASIA,100)],{},200)[ASIA]
        self.assertEqual(value['visit_label'],'FIRST RECORDED VISIT')
        self.assertEqual(value['first_recorded_at'],utc_iso(100))
        for key in ('server_started_at','server_age_seconds','last_restart_at'):self.assertIsNone(value[key])
        self.assertIn('not shard creation',value['explanation'])
    def test_same_short_number_does_not_merge_regions_or_environments(self):
        view=observation_index([visit(ASIA,100),visit(US,200),visit(OTHER,300)],{},400)
        self.assertEqual(len(view),3)
        for entry in view.values():self.assertEqual(entry['visits'],1)
    def test_observation_span_includes_gaps_without_claiming_continuous_uptime(self):
        now=100+9*86400
        value=observation_index([visit(ASIA,100),visit(ASIA,now-10)],{},now)[ASIA]
        self.assertEqual(value['history_label'],'HISTORY 9d');self.assertEqual(value['visits'],2)
        self.assertIsNone(value['server_age_seconds'])
    def test_saved_earlier_observation_and_complete_history_are_retained(self):
        sessions=[visit(ASIA,100+i*20) for i in range(130)]
        value=observation_index(sessions,{ASIA:dict(first_seen=50,visits=130)},10000)[ASIA]
        self.assertEqual(value['visits'],130);self.assertEqual(value['first_recorded_at'],utc_iso(50))
    def test_same_log_join_after_app_restart_does_not_increment_observed_visits(self):
        value=observation_index([visit(ASIA,100),visit(ASIA,100),visit(ASIA,100.001)],{ASIA:dict(first_seen=120,visits=1)},200)[ASIA]
        self.assertEqual(value['visits'],1);self.assertEqual(value['first_recorded_at'],utc_iso(100))
    def test_future_invalid_and_ambiguous_short_history_is_not_accepted(self):
        history={'ASIA_110':dict(first_seen=10),ASIA:dict(first_seen=float('nan'),visits=1)}
        self.assertEqual(observation_index([visit(US,999)],history,200),{})
    def test_reading_history_does_not_change_player_records(self):
        sessions=[visit(ASIA,100)];history={ASIA:dict(first_seen=80,visits=1)}
        import copy
        before=copy.deepcopy((sessions,history));observation_index(sessions,history,200)
        self.assertEqual((sessions,history),before)
    def test_popup_distinguishes_history_from_actual_server_age(self):
        value=observation_index([visit(ASIA,100)],{},200)[ASIA]
        snapshot=dict(session_token='join',full_shard_id=ASIA,shard_observation=value)
        text='\n'.join(popup_context(snapshot));self.assertIn('First recorded:',text);self.assertIn('uptime / reset unknown',text)
        snapshot['full_shard_id']=US;self.assertEqual(popup_context(snapshot),[])
        snapshot.update(full_shard_id=ASIA,session_token=None);self.assertEqual(popup_context(snapshot),[])
    def test_stale_hud_snapshot_does_not_keep_shard_history(self):
        value=observation_index([visit(ASIA,100)],{},200)[ASIA]
        snapshot=dict(owner_pid=42,written_at=200,session_token='join',full_shard_id=ASIA,shard_observation=value)
        self.assertEqual(hud_state(snapshot,42,201)['shard_observation'],value)
        self.assertNotIn('shard_observation',hud_state(snapshot,42,205))
        snapshot['session_token']=None;self.assertEqual(hud_state(snapshot,42,201)['shard_observation'],{})
    def test_server_log_contains_history_and_unknown_reset_explanation(self):
        row=timeline([visit(ASIA,100),visit(ASIA,200)],300)['rows'][0]
        self.assertEqual(row['shard_recorded_visits'],2)
        self.assertEqual(row['shard_first_recorded_utc'],utc_iso(100))
        self.assertIn('Server start / last reset: Unknown',row['detail'])


if __name__=='__main__':unittest.main()
