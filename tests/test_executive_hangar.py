import copy,json,math,tempfile,time,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock
from executive_hangar import parse_source,validate,project,countdown,HangarScheduleService
from executive_hangar_hud import hangar_position,hangar_svg,render_png

ROOT=Path(__file__).resolve().parents[1]

def seed():return json.loads((ROOT/'data/executive_hangar_schedule.json').read_text())

def script_fixture():
    data=seed()
    online=[('12/65',['green']*5),('24/65',['green']*4+['empty']),('36/65',['green']*3+['empty']*2),('48/65',['green']*2+['empty']*3),('60/65',['green']+['empty']*4),('1',['empty']*5)]
    charging=[(f'{i+1}/5' if i<4 else '1',['green']*i+['red']*(5-i)) for i in range(5)]
    rows=','.join('{until: '+until+', colors: '+repr(colors)+'}' for until,colors in online+charging)
    return "const CYCLE_DRIFT_MS = 350; const DESIGN_ONLINE_MIN = 65; const DESIGN_OFFLINE_MIN = 120; const INITIAL_OPEN_TIME = new Date('2026-10-29T18:01:09.073-04:00'); /** @version 2.2.32 @lastModified 2026-Oct-29 */ const thresholds=["+rows+"];"

class ExecutiveHangarTests(unittest.TestCase):
    def test_literal_source_parser_reproduces_authors_published_model(self):
        parsed=parse_source(script_fixture(),'Star Citizen Patch 4.10.2-LIVE (Server Version 12974691)',now=1793491200)
        expected=seed()
        for key in ['anchor_ms','cycle_ms','segments','source_modified','source_version','patch','server_build']:self.assertEqual(parsed[key],expected[key],key)
    def test_timezone_anchor_and_cycle_drift_are_preserved(self):
        data=seed();self.assertEqual(data['anchor_ms'],1793311269073);self.assertEqual(data['cycle_ms'],11100350)
        parsed=parse_source(script_fixture().replace('2026-10-29T18:01:09.073-04:00','2026-10-29T22:01:09.073Z'),now=1793491200)
        self.assertEqual(parsed['anchor_ms'],data['anchor_ms'])
    def test_all_light_transitions_use_correct_boundary_including_next_cycle(self):
        data=seed();anchor=data['anchor_ms']
        for i,row in enumerate(data['segments']):
            with self.subTest(segment=i):
                self.assertEqual(project(data,anchor+row['start_ms'])['lights'],row['lights'])
                self.assertEqual(project(data,anchor+row['end_ms']-1)['lights'],row['lights'])
                next_row=data['segments'][(i+1)%len(data['segments'])]
                self.assertEqual(project(data,anchor+row['end_ms'])['lights'],next_row['lights'])
    def test_blackout_is_reset_not_usable_open_time(self):
        data=seed();view=project(data,data['anchor_ms']+3600114)
        self.assertEqual(view['phase'],'reset');self.assertEqual(view['lights'],['empty']*5)
        self.assertEqual(view['remaining_ms'],300009);self.assertIsNone(view['closes_ms'])
        self.assertEqual(view['next_open_ms'],data['anchor_ms']+11100350)
    def test_charging_with_four_green_lights_is_still_closed(self):
        data=seed();view=project(data,data['anchor_ms']+data['segments'][-1]['start_ms'])
        self.assertEqual(view['phase'],'charging');self.assertEqual(view['lights'],['green']*4+['red'])
    def test_clock_before_anchor_wraps_mathematically(self):
        data=seed();self.assertEqual(project(data,data['anchor_ms']-1)['phase'],'charging')
        self.assertEqual(project(data,data['anchor_ms']-1)['next_open_ms'],data['anchor_ms'])
    def test_invalid_remote_definitions_are_rejected_without_executing_code(self):
        original=script_fixture()
        for altered in [original.replace('= 350;','= 999999;'),original.replace('= 65;','= -1;'),original.replace('2026-10-29T18:01:09.073-04:00','2026-10-29T18:01:09'),original.replace("'green'","'blue'",1)]:
            with self.subTest(source=altered[:50]),self.assertRaises(ValueError):parse_source(altered,now=1793491200)
        data=parse_source(original+'; throw new Error("must not execute");',now=1793491200)
        self.assertEqual(data['cycle_ms'],11100350)
    def test_invalid_cached_segments_and_nonfinite_clock_are_rejected(self):
        data=seed();broken=copy.deepcopy(data);broken['segments'][2]['start_ms']+=1
        with self.assertRaises(ValueError):validate(broken)
        with self.assertRaises(ValueError):project(data,math.nan)
    def test_feature_disabled_makes_no_network_request(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher=Mock(return_value=seed());service=HangarScheduleService(directory,fetcher)
            try:self.assertIsNone(service.tick(False,1793491200));fetcher.assert_not_called()
            finally:service.close()
    def test_background_sync_is_cached_and_not_repeated_on_each_render(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher=Mock(return_value=seed());service=HangarScheduleService(directory,fetcher);now=1793491200
            try:
                self.assertIsNotNone(service.tick(True,now));service.future.result(timeout=2)
                model=service.tick(True,now+1);self.assertFalse(model['cached']);self.assertTrue((Path(directory)/'executive_hangar_sync.json').exists())
                service.tick(True,now+2);fetcher.assert_called_once()
                cached=HangarScheduleService(directory,fetcher)
                try:cached.tick(True,now+3);self.assertIsNone(cached.future)
                finally:cached.close()
            finally:service.close()
    def test_source_failure_retains_seed_and_does_not_expose_error_body(self):
        with tempfile.TemporaryDirectory() as directory:
            service=HangarScheduleService(directory,Mock(side_effect=RuntimeError('private error body')))
            try:
                service.tick(True,1793491200)
                try:service.future.result(timeout=2)
                except RuntimeError:pass
                model=service.tick(True,1793491201);self.assertTrue(model['cached']);self.assertTrue(model['refresh_error'])
                self.assertEqual(service.note,'RuntimeError');self.assertNotIn('private',repr(model))
            finally:service.close()
    def test_corrupt_profile_cache_falls_back_to_bundled_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'executive_hangar_sync.json').write_text('{broken')
            service=HangarScheduleService(directory)
            try:self.assertEqual(service.schedule['anchor_ms'],seed()['anchor_ms'])
            finally:service.close()
    def test_structurally_invalid_cache_cannot_stop_the_server_hud(self):
        values=[[],{'schedule':[]},dict(seed(),segments=None),dict(seed(),segments=[None]*11),dict(seed(),patch=None)]
        for value in values:
            with self.subTest(value=value),tempfile.TemporaryDirectory() as directory:
                (Path(directory)/'executive_hangar_sync.json').write_text(json.dumps(value))
                service=HangarScheduleService(directory)
                try:self.assertEqual(service.schedule['anchor_ms'],seed()['anchor_ms'])
                finally:service.close()
    def test_countdowns_round_up_and_never_go_negative(self):
        self.assertEqual(countdown(1),'00:01');self.assertEqual(countdown(-1),'00:00');self.assertEqual(countdown(3600000),'01:00:00')
    def test_strip_positions_stay_on_negative_and_small_monitors(self):
        bounds=dict(left=-1920,top=-100,width=1920,height=1080)
        x,y,w,h=hangar_position((-1800,-100,700,24),bounds);self.assertGreaterEqual(x,-1920);self.assertGreaterEqual(y,-100);self.assertLessEqual(x+w,0)
        x,y,w,h=hangar_position((0,0,300,24),dict(left=0,top=0,width=300,height=80));self.assertLessEqual(x+w,300);self.assertLessEqual(y+h,80)
    def test_svg_has_five_correct_lights_and_an_explicit_schedule_label(self):
        data=seed();view=project(data,data['anchor_ms']);svg=hangar_svg(view);root=ET.fromstring(svg)
        circles=root.findall('{http://www.w3.org/2000/svg}circle');self.assertEqual(len(circles),5);self.assertTrue(all(c.attrib['fill']=='#4ade80' for c in circles));self.assertIn('Schedule estimate',svg)
        view=project(data,data['anchor_ms']+3600114);self.assertIn('PYAM · RESET',hangar_svg(view));self.assertNotIn('OPEN WINDOW',hangar_svg(view))
    def test_renderer_produces_exact_sized_png_without_creating_ui_windows(self):
        import io
        from PIL import Image
        data=seed();png=render_png(hangar_svg(project(data,data['anchor_ms'])))
        image=Image.open(io.BytesIO(png));self.assertEqual(image.size,(430,94));self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
