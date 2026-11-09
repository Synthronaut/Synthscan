from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mission_log_service import Logger
from tests.test_mission_log import reputation, CATALOG


class LoggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.game=self.root/'Game.log'
        self.start=1794200000
        self.game.write_text(self.line('Session started', self.start), encoding='utf-8')
        self.logger=Logger(self.root, self.game);self.addCleanup(self.logger.close)
        self.patches=[patch('mission_log_service.load_catalog', return_value=CATALOG),
                      patch('app_lifecycle.game_process_ids', return_value=set())]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def line(self, text, at):
        return '<'+datetime.fromtimestamp(at,timezone.utc).isoformat().replace('+00:00','Z')+'> '+text+'\n'

    def save(self, name, data):
        (self.root/name).write_text(json.dumps(data), encoding='utf-8')

    def test_disabled_account_collection_stops_new_samples_and_queries(self):
        self.save('capture_privacy.json', dict(schema=1, account_access=False))
        self.save('reputation_snapshot.json', reputation(1000, self.start+10))
        with patch.object(self.logger, 'query') as query:
            view=self.logger.tick(self.start+20)
            query.assert_not_called()
        self.assertFalse(view['recording'])
        self.assertEqual(view['reputation_reads'], 0)

    def test_hud_is_published_independently_of_desktop_filters(self):
        self.save('capture_privacy.json', dict(schema=1, account_access=True))
        self.logger.tick(self.start+5)
        self.logger.book.mission(dict(id='hud-mission',at=self.start+10,status='Accepted',title='HUD mission',source='game_log'),session=self.logger.session)
        self.save('native_status.json',dict(pid=42))
        self.save('session_state.json',dict(written_at=self.start+20,game_pids=[99],questing=dict(selected_id='hud-mission',active_ids=['hud-mission'])))
        self.logger.filters.update(query='does not match',outcome='failed')
        self.logger.mode='wallet'
        self.logger.tick(self.start+20)
        hud=json.loads((self.root/'mission_hud.json').read_text())
        self.assertEqual(hud['active']['id'],'hud-mission')
        self.assertEqual(hud['active']['elapsed_seconds'],10)
        self.assertEqual(hud['owner_pid'],42)

    def test_unchanged_catalog_is_reused_and_changed_references_reload(self):
        self.save('capture_privacy.json', dict(schema=1, account_access=True))
        with patch.object(self.logger,'catalog_stamp',return_value={'build':'one'}) as stamp, patch('mission_log_service.load_catalog',return_value=CATALOG) as load:
            self.logger.tick(self.start+20)
            self.logger.tick(self.start+321)
            self.assertEqual(load.call_count,1)
            stamp.return_value={'build':'two'}
            self.logger.tick(self.start+622)
            self.assertEqual(load.call_count,2)

    def test_passive_capture_replays_failure_and_retains_each_snapshot(self):
        self.save('capture_privacy.json', dict(schema=1, account_access=True))
        self.save('reputation_snapshot.json', reputation(1000,self.start+20))
        self.logger.tick(self.start+25)
        with self.game.open('a',encoding='utf-8') as stream:
            stream.write(self.line('<EndMission> MissionId[11111111-1111-1111-1111-111111111111] CompletionType[Fail]',self.start+35))
        self.save('reputation_snapshot.json', reputation(900,self.start+45))
        view=self.logger.tick(self.start+50)
        self.assertEqual(view['reputation_reads'], 2)
        self.assertTrue(any('Fail' in e['detail'] for e in view['entries']))
        self.assertTrue(any('-100' in e['detail'] for e in view['entries']))
        # The UI payload is bounded; raw source samples remain in SQLite/export.
        self.assertNotIn('rows', view)
        self.assertNotIn('changes', view)

    def test_incomplete_log_line_is_read_when_completed(self):
        self.save('capture_privacy.json', dict(schema=1, account_access=True))
        self.save('reputation_snapshot.json', reputation(1000,self.start+20))
        self.logger.tick(self.start+25)
        line=self.line('<EndMission> MissionId[11111111-1111-1111-1111-111111111111] CompletionType[Abandon]',self.start+35)
        with self.game.open('a',encoding='utf-8') as stream:stream.write(line[:-5])
        self.logger.tick(self.start+40)
        self.assertEqual(self.logger.book._missions(), [])
        with self.game.open('a',encoding='utf-8') as stream:stream.write(line[-5:])
        self.logger.tick(self.start+45)
        self.assertEqual(self.logger.book._missions()[0]['status'], 'Abandon')


if __name__=='__main__':unittest.main()
