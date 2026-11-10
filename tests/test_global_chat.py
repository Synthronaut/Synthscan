"""Join lifecycle and input eligibility; no real game input is sent."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from contract_share import GlobalChatOnJoin
from telemetry_core import IncrementalGameLog,utc_iso


def snapshot(**changes):
    value=dict(owner_pid=4,written_at=105,session_token='join-a',game_pids=[20],
               joined_at=95,gameplay_ready_at=96,is_loading_screen=False,
               connection_status='connected',full_shard_id='pub_use1b_100_020')
    value.update(changes);return value


JOIN=('pub_use1b_100_020',95)


class GlobalChatTests(unittest.TestCase):
    def setUp(self):
        self.chat=GlobalChatOnJoin(90,True)
        self.chat.focused_at=90
    def candidate(self,**changes):return self.chat.candidate(snapshot(**changes),4,105,20)

    def test_default_off_and_enabling_in_loaded_world_waits_for_next_load(self):
        chat=GlobalChatOnJoin(90)
        self.assertIsNone(chat.candidate(snapshot(),4,105,20))
        chat.set_enabled(True,104)
        self.assertIsNone(chat.candidate(snapshot(),4,105,20))
        chat.focused_at=100
        self.assertEqual(chat.candidate(snapshot(joined_at=105,gameplay_ready_at=105,written_at=114),4,114,20),('pub_use1b_100_020',105))

    def test_tabbed_out_join_waits_for_focus_and_only_attempts_once(self):
        for pid in (0,4,999):
            self.assertIsNone(self.chat.candidate(snapshot(),4,105,pid))
        self.assertIsNone(self.chat.candidate(snapshot(),4,105,20))
        self.assertEqual(self.chat.message,'Waiting for Star Citizen focus to stabilize')
        self.assertEqual(self.chat.candidate(snapshot(written_at=106),4,106,20),JOIN)
        self.assertTrue(self.chat.attempted_once(JOIN))
        self.assertIsNone(self.candidate())
        self.assertFalse(self.chat.attempted_once(JOIN))
        self.chat.candidate(snapshot(written_at=90),4,106,999)
        self.assertIsNone(self.chat.candidate(snapshot(written_at=107),4,107,20))
        self.chat.set_enabled(False,108);self.chat.set_enabled(True,109)
        self.assertIsNone(self.chat.candidate(snapshot(gameplay_ready_at=110,written_at=113),4,113,20))

    def test_completion_and_settle_required_and_duplicates_do_not_rearm(self):
        for changes in (dict(gameplay_ready_at=None),dict(is_loading_screen=True),
                        dict(connection_status='recovering'),dict(gameplay_ready_at=98)):
            self.assertIsNone(self.candidate(**changes))
        self.assertEqual(self.candidate(),JOIN)
        self.chat.attempted_once(JOIN)
        self.assertIsNone(self.candidate(gameplay_ready_at=97))
        self.assertIsNone(self.candidate(session_token='new-reader-generation'))
        self.assertEqual(self.candidate(session_token='same-shard-new-join',joined_at=96),('pub_use1b_100_020',96))

    def test_stale_wrong_owner_menu_crash_and_missing_data_never_authorize(self):
        for changes in (dict(written_at=102),dict(written_at=106),dict(owner_pid=8),
                        dict(session_token=None),dict(game_pids=[]),dict(is_loading_screen=None),
                        dict(connection_status='game_closed'),dict(joined_at=97),
                        dict(gameplay_ready_at=94),dict(gameplay_ready_at=106)):
            self.assertIsNone(self.candidate(**changes),changes)
        for field in ('written_at','joined_at','gameplay_ready_at'):
            for value in (None,'102',True,float('nan'),float('inf')):
                self.assertIsNone(self.candidate(**{field:value}),(field,value))
        self.assertIsNone(self.chat.candidate({},4,105,20))

    def test_modifiers_and_held_f12_pause_but_normal_movement_does_not(self):
        for key in (0x10,0x11,0x12,0x5b,0x5c,0xa0,0xa5,0x7b):
            self.assertIsNone(self.chat.candidate(snapshot(),4,105,20,[key]))
        self.assertEqual(self.chat.candidate(snapshot(),4,105,20,[0x57,0x41,0x01]),JOIN)

    def test_restarting_helper_does_not_toggle_existing_loaded_join(self):
        restarted=GlobalChatOnJoin(98,True)
        restarted.focused_at=90
        self.assertIsNone(restarted.candidate(snapshot(),4,105,20))

    def test_crash_cancels_pending_join_even_if_old_log_is_replayed(self):
        self.assertIsNone(self.chat.candidate(snapshot(),4,105,999))
        replay=snapshot(session_token='new-reader-generation',game_pids=[21])
        self.assertIsNone(self.chat.candidate(replay,4,105,21))
        rejoin=snapshot(session_token='rejoined',game_pids=[21],joined_at=97)
        self.assertIsNone(self.chat.candidate(rejoin,4,105,21))
        rejoin.update(gameplay_ready_at=98,written_at=107)
        self.assertEqual(self.chat.candidate(rejoin,4,107,21),('pub_use1b_100_020',97))

    def test_focus_stabilization_delay(self):
        chat=GlobalChatOnJoin(90,True)
        self.assertIsNone(chat.candidate(snapshot(),4,105,20))
        self.assertEqual(chat.message,'Waiting for Star Citizen focus to stabilize')
        self.assertIsNone(chat.candidate(snapshot(written_at=105.8),4,105.8,20))
        self.assertEqual(chat.message,'Waiting for Star Citizen focus to stabilize')
        self.assertEqual(chat.candidate(snapshot(written_at=106),4,106,20),JOIN)


class GameReadinessTests(unittest.TestCase):
    def test_only_final_completion_in_current_join_marks_game_ready(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'Game.log';path.write_text('')
            reader=IncrementalGameLog(path)
            def feed(at,text):reader.feed(f'<{utc_iso(at)}> {text}\n'.encode())
            join='<Join PU> shard[pub_use1b_100_020]'
            feed(99,'StopLoadingScreen Finished')
            self.assertIsNone(reader.gameplay_ready_at)
            feed(100,join)
            self.assertIsNone(reader.gameplay_ready_at)
            feed(101,'OpenLoadingScreen')
            feed(102,'StopLoadingScreen Starting CET')
            self.assertIsNone(reader.gameplay_ready_at)
            feed(103,'StopLoadingScreen Finished')
            self.assertFalse(reader.is_loading_screen)
            self.assertEqual(reader.gameplay_ready_at,103)
            feed(104,'StopLoadingScreen Finished')
            self.assertEqual(reader.gameplay_ready_at,103)
            feed(105,'OpenLoadingScreen')
            self.assertIsNone(reader.gameplay_ready_at)
            feed(106,'StopLoadingScreen Finished')
            feed(107,join)
            self.assertIsNone(reader.gameplay_ready_at)
            feed(108,'StopLoadingScreen Finished')
            self.assertEqual(reader.gameplay_ready_at,108)
            feed(109,'Connection closed')
            self.assertIsNone(reader.gameplay_ready_at)
            feed(110,join)
            reader.feed(b'StopLoadingScreen Finished\n')
            self.assertIsNone(reader.gameplay_ready_at)


if __name__=='__main__':unittest.main()
