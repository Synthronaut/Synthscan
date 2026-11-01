import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from executive_hangar import HangarScheduleService,project
from hangar_verification import HangarVerification,installed_build
from hangar_card import card_svg,HangarPublisher
from hangar_reset_feed import parse_resets

ROOT=Path(__file__).resolve().parents[1]


class HangarVerificationTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.directory=Path(self.folder.name);self.watch=HangarVerification(self.directory)
        self.schedule=json.loads((ROOT/'data/executive_hangar_schedule.json').read_text())
        self.now=1793491200
        self.build=dict(patch='4.10.2',fingerprint='build-a',built_on='2026-10-12')

    def evaluate(self,build=None,schedule=None,**kw):
        return self.watch.evaluate(build or self.build,schedule or self.schedule,self.now,self.now,**kw)

    def test_matching_community_patch_is_an_estimate_not_live_verification(self):
        result=self.evaluate();self.assertTrue(result['community_synced']);self.assertIn('estimate',result['reason'])

    def test_new_build_invalidates_same_patch_and_a_fresh_download_does_not_clear_it(self):
        self.evaluate();new=dict(self.build,fingerprint='build-b')
        result=self.evaluate(new);self.assertFalse(result['community_synced']);self.assertTrue(result['build_changed'])
        again=self.evaluate(new);self.assertFalse(again['community_synced']);self.assertEqual(again['reason'],'Timing unverified for this patch')
        self.watch=HangarVerification(self.directory)
        self.assertFalse(self.evaluate(new)['community_synced'])

    def test_new_anchor_auto_recovers_after_patch_without_an_app_update(self):
        self.evaluate();new=dict(self.build,fingerprint='build-b');self.evaluate(new)
        updated=copy.deepcopy(self.schedule);updated['anchor_ms']+=600000
        result=self.evaluate(new,updated);self.assertTrue(result['community_synced']);self.assertFalse(result['needs_resync'])

    def test_cosmetic_source_changes_are_not_a_new_timing_sync(self):
        self.evaluate();new=dict(self.build,fingerprint='build-b');self.evaluate(new)
        updated=dict(self.schedule,source_modified='2026-11-01',source_version='3.0.0',source_sha256='a'*64)
        self.assertFalse(self.evaluate(new,updated)['community_synced'])

    def test_sync_must_match_new_patch_and_not_predate_its_build(self):
        for build in [dict(self.build,patch='4.11.0'),dict(self.build,built_on='2026-11-01')]:
            self.assertFalse(self.evaluate(build)['community_synced'])

    def test_announced_server_reset_invalidates_an_unchanged_client(self):
        self.evaluate()
        reset=self.schedule['anchor_ms']/1000+120
        check=dict(ok=True,checked_at=self.now,latest_reset_at=reset)
        result=self.evaluate(reset_check=check)
        self.assertFalse(result['community_synced']);self.assertIn('maintenance',result['reason'])
        updated=dict(self.schedule,anchor_ms=int((reset+60)*1000))
        self.assertTrue(self.evaluate(schedule=updated,reset_check=check)['community_synced'])

    def test_missing_maintenance_feed_is_not_presented_as_verified(self):
        self.assertFalse(self.evaluate(reset_check=dict(ok=False))['community_synced'])

    def test_official_feed_tracks_server_hotfix_update_time_and_ignores_platform_only_work(self):
        xml=b'''<rss><channel><item><pubDate>Sun, 11 Oct 2026 15:36:00 +0000</pubDate><description><![CDATA[<p>Server Hotfix</p><p>[2026-10-12 Updates]</p><p>2130 UTC - Server Hotfix deployment complete.</p>]]></description></item><item><pubDate>Wed, 21 Oct 2026 14:30:00 +0000</pubDate><description>Server maintenance. This should not impact game connectivity.</description></item></channel></rss>'''
        from datetime import datetime,timezone
        expected=datetime(2026,10,12,21,30,tzinfo=timezone.utc).timestamp()
        self.assertEqual(parse_resets(xml,self.now)['latest_reset_at'],expected)
        with self.assertRaises(ValueError):parse_resets(b'<!DOCTYPE rss><rss/>',self.now)

    def test_missing_game_data_and_offline_cache_are_clearly_unverified(self):
        missing=self.watch.evaluate(None,self.schedule,self.now,self.now)
        self.assertFalse(missing['community_synced']);self.assertIn('could not be verified',missing['reason'])
        old=self.watch.evaluate(self.build,self.schedule,self.now,self.now-90000)
        self.assertFalse(old['community_synced']);self.assertIn('unavailable',old['reason'])
        self.assertFalse(self.evaluate(refresh_error=True)['community_synced'])

    def test_only_reading_the_manifest_is_needed(self):
        game=self.directory/'LIVE';game.mkdir()
        (game/'build_manifest.id').write_text(json.dumps(dict(Data=dict(Branch='sc-alpha-4.10.2',BuildId='abc',RequestedP4ChangeNum='123',BuildDateStamp='Mon Oct 12 2026'))))
        build=installed_build(game);self.assertEqual(build['patch'],'4.10.2');self.assertEqual(build['fingerprint'],'abc:123');self.assertEqual(build['built_on'],'2026-10-12')

    def test_patch_resync_can_bypass_recent_success_but_is_rate_limited(self):
        fetch=Mock(return_value=self.schedule);service=HangarScheduleService(self.directory,fetch)
        try:
            service.fetched_at=self.now
            service.tick(True,self.now,force_refresh=True,retry_interval=120);service.future.result(timeout=2)
            service.tick(True,self.now+1,force_refresh=True,retry_interval=120);fetch.assert_called_once()
            service.tick(True,self.now+121,force_refresh=True,retry_interval=120);service.future.result(timeout=2)
            self.assertEqual(fetch.call_count,2)
        finally:service.close()

    def test_native_card_labels_unverified_lights_and_keeps_count_subtle(self):
        view=project(self.schedule,self.schedule['anchor_ms'])
        svg=card_svg(view,dict(complete_sets=3),dict(community_synced=False,reason='Timing unverified for this patch'))
        self.assertIn('UNVERIFIED',svg);self.assertIn('Timing unverified for this patch',svg)
        self.assertIn('EST. CLOSES IN',svg);self.assertIn('3 sets ready',svg)

    def test_publisher_outputs_png_and_owner_bound_heartbeat_without_a_ui(self):
        service=HangarScheduleService(self.directory,Mock(return_value=self.schedule));publisher=HangarPublisher(self.directory,123)
        publisher.game=None
        try:
            publisher.tick(service,True,self.now)
            raw=(self.directory/'hangar_hud.png').read_bytes();self.assertTrue(raw.startswith(b'\x89PNG'))
            state=json.loads((self.directory/'hangar_hud.json').read_text());self.assertEqual(state['owner_pid'],123);self.assertFalse(state['community_synced'])
            import io
            from PIL import Image
            image=Image.open(io.BytesIO(raw)).convert('RGB');self.assertEqual(image.size,(860,300))
            hero=image.crop((500,110,838,180))
            pixels=hero.tobytes()
            self.assertGreater(sum(1 for i in range(0,len(pixels),3) if min(pixels[i:i+3])>150),100,'Timer glyphs must render with the bundled Windows font choices')
        finally:service.close()

    def test_background_sync_recovers_the_published_card_after_a_build_change(self):
        game=self.directory/'LIVE';game.mkdir();manifest=game/'build_manifest.id'
        data=dict(Data=dict(Branch='sc-alpha-4.10.2',BuildId='a',RequestedP4ChangeNum='1',BuildDateStamp='Mon Oct 12 2026'))
        manifest.write_text(json.dumps(data))
        schedule=copy.deepcopy(self.schedule);schedule['reset_check']=dict(ok=True,checked_at=self.now,latest_reset_at=0)
        updated=copy.deepcopy(schedule);updated['anchor_ms']+=600000
        service=HangarScheduleService(self.directory,Mock(return_value=updated));service.schedule=schedule;service.fetched_at=self.now
        publisher=HangarPublisher(self.directory,321);publisher.game=game
        try:
            publisher.tick(service,True,self.now)
            self.assertTrue(json.loads((self.directory/'hangar_hud.json').read_text())['community_synced'])
            data['Data']['BuildId']='b';manifest.write_text(json.dumps(data));publisher.tick(service,True,self.now+2)
            self.assertFalse(json.loads((self.directory/'hangar_hud.json').read_text())['community_synced'])
            service.future.result(timeout=2);publisher.tick(service,True,self.now+3)
            self.assertTrue(json.loads((self.directory/'hangar_hud.json').read_text())['community_synced'])
        finally:service.close()
