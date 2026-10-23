import unittest
from unittest.mock import patch
from piracy_watch import PopulationWatch,PiracyReader

def sample(shard=500,server=80):
    return dict(shard_pop=shard,srv_pop=server,server_fps=30,ping_ms=42,
                _validated_fields=['shard_pop','srv_pop','server_fps','ping_ms'])

class PopulationWatchTests(unittest.TestCase):
    def setUp(self):
        self.watch=PopulationWatch(None);self.watch.session('join-a',1000)

    def test_fresh_values_expire_and_zero_is_valid(self):
        self.watch.observe(sample(0,0),1000,'join-a',1000)
        self.assertEqual(self.watch.view(1001)['metrics']['shard_pop'],0)
        self.assertEqual(self.watch.view(1005)['metrics'],{})
        self.assertIsNone(self.watch.view(1005)['delta_5m'])

    def test_old_frames_and_other_shards_cannot_publish(self):
        self.assertFalse(self.watch.observe(sample(),900,'join-a',1000))
        self.assertFalse(self.watch.observe(sample(),1000,'join-b',1000))
        self.assertFalse(self.watch.observe(sample(),1001,'join-a',1000))
        self.watch.observe(sample(),1000,'join-a',1000)
        self.assertFalse(self.watch.observe(sample(700),1000,'join-a',1001))
        self.assertEqual(self.watch.view(1001)['metrics']['shard_pop'],500)

    def test_unvalidated_or_inconsistent_population_is_unknown(self):
        v=sample();v['_validated_fields']=[]
        self.watch.observe(v,1000,'join-a',1000)
        self.assertEqual(self.watch.view(1000)['metrics'],{})
        self.watch.observe(sample(10,50),1001,'join-a',1001)
        self.assertNotIn('shard_pop',self.watch.view(1001)['metrics'])
        self.watch.observe(sample(float('nan'),80),1002,'join-a',1002)
        self.assertNotIn('shard_pop',self.watch.view(1002)['metrics'])

    def test_true_elapsed_time_delta_not_sample_count(self):
        self.watch.observe(sample(480),1000,'join-a',1000)
        self.assertIsNone(self.watch.view(1000)['delta_5m'])
        self.watch.observe(sample(500),1300,'join-a',1300)
        self.assertEqual(self.watch.view(1300)['delta_5m'],20)
        self.assertIsNone(self.watch.view(1300)['delta_15m'])
        self.watch.observe(sample(490),1900,'join-a',1900)
        self.assertEqual(self.watch.view(1900)['delta_15m'],10)

    def test_timer_is_manual_and_resets_on_shard_change(self):
        self.assertEqual(self.watch.view(1100)['waiting_s'],0)
        self.watch.command('toggle_wait',1100)
        self.assertEqual(self.watch.view(1165)['waiting_s'],65)
        self.watch.command('toggle_wait',1170)
        self.assertEqual(self.watch.view(1200)['waiting_s'],70)
        self.watch.command('reset_wait',1200)
        self.assertEqual(self.watch.view(1201)['waiting_s'],0)
        self.watch.command('toggle_wait',1202)
        self.watch.session('join-b',1300)
        view=self.watch.view(1300)
        self.assertEqual(view['waiting_s'],0);self.assertFalse(view['waiting_active'])
        self.assertEqual(view['points'],[])

    def test_turning_displayinfo_off_clears_metrics_not_history(self):
        self.watch.observe(sample(),1000,'join-a',1000)
        self.watch.observe({},1001,'join-a',1001)
        view=self.watch.view(1001)
        self.assertFalse(view['fresh']);self.assertEqual(view['metrics'],{})
        self.assertEqual(len(view['points']),1)
        self.assertNotIn('catch',view)

    def test_series_is_bounded_and_downsampled(self):
        for i in range(3000):self.watch.observe(sample(),1000+i,'join-a',1000+i)
        view=self.watch.view(3999)
        self.assertLessEqual(len(view['points']),181)
        self.assertTrue(all(p['at']>=3099 for p in view['points']))

    def test_switching_tabs_pauses_manual_timer_and_hides_metrics(self):
        with patch('piracy_watch.threading.Thread.start'):
            reader=PiracyReader(None)
        reader.tick(True,'join-a',1000)
        reader.watch.command('toggle_wait',1000)
        reader.latest=(sample(),1001,'join-a')
        self.assertTrue(reader.tick(True,'join-a',1001)['fresh'])
        view=reader.tick(False,'join-a',1010)
        self.assertFalse(view['waiting_active']);self.assertEqual(view['waiting_s'],10)
        self.assertEqual(view['metrics'],{})
        self.assertEqual(reader.tick(True,'join-a',1020)['waiting_s'],10)

    def test_inflight_frame_from_old_join_does_not_repopulate_new_join(self):
        with patch('piracy_watch.threading.Thread.start'):
            reader=PiracyReader(None)
        reader.tick(True,'join-a',1000)
        reader.latest=(sample(),1001,'join-a')
        view=reader.tick(True,'join-b',1001)
        self.assertFalse(view['fresh']);self.assertEqual(view['metrics'],{})
        self.assertEqual(view['points'],[])
