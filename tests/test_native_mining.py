"""Offline native reader and integration checks. Never capture or control the game."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from native_mining import ROOT,ENGINE_DIR,NativeMiningClient,NativeMiningError,marker_match,native_refinery_orders
from mining_loadout import validate_fit,load_fit,save_fit,hardware
from hud_layout import panel_rows


def fit(ship='prospector',laser='thcn_helix_s1',slot=1):
    return dict(ship=ship,heads=[dict(slot=slot,laser=laser,modules=[],crafted_power=0)],distance=0,actives=False,gadget='')


class FitAndAdapterTests(unittest.TestCase):
    def test_fit_preserves_mole_position_and_normalizes_numbers(self):
        raw=fit('mole','thcn_helix_s2',3)
        raw['distance']='30';raw['heads'][0]['crafted_power']='5.5'
        result=validate_fit(raw)
        self.assertEqual(result['heads'][0]['slot'],3)
        self.assertEqual(result['heads'][0]['crafted_power'],5.5)
        self.assertEqual(result['distance'],30)
        self.assertEqual(raw['distance'],'30')

    def test_incompatible_fits_are_rejected(self):
        values=[fit(laser='thcn_helix_s2'),fit(laser='drak_golem_s1'),fit(slot=True),fit(slot=1.5)]
        duplicate=fit('mole');duplicate['heads']*=2;values.append(duplicate)
        over=fit();over['heads'][0]['modules']=['active_surge']*3;values.append(over)
        invalid=fit();invalid['distance']=float('nan');values.append(invalid)
        for value in values:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_fit(value)

    def test_save_roundtrip_and_invalid_file_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fit.json'
            self.assertIsNone(load_fit(path))
            expected=save_fit(fit(),path)
            self.assertEqual(load_fit(path),expected)
            path.write_text('{bad',encoding='utf-8')
            with self.assertRaises(ValueError):load_fit(path)
            self.assertEqual(path.read_text(),'{bad')

    def test_marker_repeat_and_ambiguity_are_preserved(self):
        marker=dict(value=12000,accepted=False,ocr_confidence=.99,method='glyphs',candidates=[
            dict(name='ROC Deposit',count=3,category='roc',difference=0,combination=False),
            dict(name='FPS Minable',count=4,category='hand',difference=0,combination=False)])
        self.assertEqual(marker_match(dict(marker=marker)),(None,None))
        marker['accepted']=True
        match,value=marker_match(dict(marker=marker))
        self.assertEqual(value,12000);self.assertTrue(match['ambiguous'])
        self.assertEqual(len(match['candidates']),2)
        self.assertNotIn('ocr_confidence',match)
        self.assertEqual(match['reader_score'],.99)

    def test_refinery_units_and_incomplete_observations(self):
        panel=dict(number=12,status='completed',whole=True,seconds=-1,
                   rows=[dict(material='Iron (Ore)',quality=325,yield_cscu=257)])
        result=dict(refinery=dict(station_text='',panels=[panel]))
        self.assertEqual(native_refinery_orders(result),[])
        orders=native_refinery_orders(result,'Levski')
        self.assertEqual(orders[0]['parts'],[dict(material='Iron',quality=325,scu=2.57)])
        self.assertIsNone(orders[0]['remaining_seconds'])
        panel['whole']=False
        self.assertEqual(native_refinery_orders(result,'Levski'),[])
        panel['whole']=True;panel['rows'][0]['quality']=0
        self.assertEqual(native_refinery_orders(result,'Levski'),[])

    def test_native_binary_tampering_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'synthscan-mining.exe').write_bytes(b'changed')
            (path/'build_manifest.json').write_text(json.dumps(dict(binary_files={'synthscan-mining.exe':'wrong'})))
            client=NativeMiningClient(path)
            with patch('native_mining.subprocess.Popen') as popen,self.assertRaises(NativeMiningError):client.start()
            popen.assert_not_called()


@unittest.skipUnless(os.name=='nt' and (ENGINE_DIR/'synthscan-mining.exe').exists(),'Built Windows native worker')
class NativeReaderReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=NativeMiningClient()
        cls.client.start()

    @classmethod
    def tearDownClass(cls):cls.client.close()

    def test_all_vendored_files_and_adapter_hashes_match_build(self):
        manifest=json.loads((ENGINE_DIR/'build_manifest.json').read_text())
        for name,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/'native/mining_worker/vendor'/name).read_bytes()).hexdigest(),digest,name)
        for name,digest in manifest['adapter_files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)

    def test_real_handshake_and_hardware(self):
        self.assertTrue(self.client.hello['neural_ready'])
        self.assertEqual(self.client.hello['templates'],976)
        actual=self.client.request('hardware')
        for key,count in [('lasers',13),('modules',29),('gadgets',6),('ships',3)]:
            self.assertEqual(len(actual[key]),count)
            self.assertEqual(actual[key],hardware()[key])

    def test_four_original_marker_crops_require_two_reads(self):
        for name,value in [('canopy_marker_60000',60000),('lamp_marker_21350',21350),('lamp_marker_3170',3170),('mfd_marker_15420',15420)]:
            path=ROOT/'research/bedrock_upstream/tests'/(name+'.png')
            with self.subTest(name=name):
                args=dict(path=str(path),session=name,cropped=True)
                first=self.client.request('scan_file',**args)
                second=self.client.request('scan_file',**args)
                self.assertEqual(first['marker']['value'],value)
                self.assertFalse(first['marker']['accepted'])
                self.assertTrue(second['marker']['accepted'])
                self.assertEqual(marker_match(second)[1],value)

    def test_unicode_frame_path_and_session_reset(self):
        source=ROOT/'research/bedrock_upstream/tests/lamp_marker_3170.png'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'礦石 é.png';shutil.copyfile(source,path)
            for session in ['unicode-a','unicode-b']:
                result=self.client.request('scan_file',path=str(path),session=session,cropped=True)
                self.assertEqual(result['marker']['value'],3170)
                self.assertFalse(result['marker']['accepted'])

    def test_mixed_signature_retains_multiple_explanations(self):
        candidates=self.client.request('analyze',value=39350)
        self.assertGreater(len(candidates),1)
        self.assertTrue(any(row['combination'] for row in candidates))
        self.assertTrue(all(row['difference']==0 for row in candidates))

    def test_marker_locator_in_a_reconstructed_frame_at_three_resolutions(self):
        from PIL import Image
        frame=Image.new('RGB',(2560,1440),(30,34,30))
        with Image.open(ROOT/'research/bedrock_upstream/tests/canopy_marker_60000.png') as crop:
            frame.paste(crop,(1280-crop.width//2,475-crop.height//2))
        for height in [1080,1440,2160]:
            with self.subTest(height=height):
                image=frame.resize((round(2560*height/1440),height),Image.Resampling.BICUBIC)
                for _ in range(2):
                    result=self.client.request_image(image,session='resolution-'+str(height))
                self.assertIsNotNone(result['marker'])
                self.assertEqual(result['marker']['value'],60000)
                self.assertTrue(result['marker']['accepted'])

    def test_real_panels_and_separate_quality_portions(self):
        fixtures=[('panel_prospector_1440.png',2895,'Iron',[325]),
                  ('panel_mole_cockpit_1440.png',25005,'Taranite',[957,310]),
                  ('panel_turret_copper.png',21126,'Copper',[])]
        for name,mass,ore,qualities in fixtures:
            with self.subTest(name=name):
                args=dict(path=str(ROOT/'research/native_mining_replay'/name),session=name,marker=False,panel=True,contents=True)
                result=self.client.request('scan_file',**args)
                for _ in range(2):
                    if result['panel']['settled']:break
                    result=self.client.request('scan_file',**args)
                panel=result['panel'];self.assertTrue(panel['settled'])
                self.assertEqual(panel['stats']['mass'],mass)
                self.assertEqual(panel['stats']['ore'],ore)
                self.assertNotIn('advice',result)
                contents=panel['contents']
                self.assertEqual(contents['whole'],bool(qualities))
                self.assertEqual([p['quality'] for p in contents['parts'] if not p['inert']],qualities)

    def test_blank_frame_cannot_create_a_rock_or_marker(self):
        from PIL import Image
        result=self.client.request_image(Image.new('RGB',(1920,1080)),panel=True,contents=True,refinery=True,session='blank')
        self.assertIsNone(result['marker'])
        self.assertFalse(result['panel']['settled'])
        self.assertEqual(native_refinery_orders(result,'Levski'),[])

    def test_advice_uses_actual_head_slot_and_range(self):
        args=fit('mole','thcn_helix_s2',3)
        args['rock']=dict(mass=10000,resistance=0,instability=1,distance=0)
        result=self.client.request('advice',**args)
        self.assertEqual(result['heads'][0]['head'],3)
        self.assertEqual(result['selected_heads'],[3])
        self.assertEqual(result['safest_single_head'],3)
        self.assertAlmostEqual(result['combined_hold_percent'],2000/4930*100,places=3)
        args['rock']['distance']=100
        distant=self.client.request('advice',**args)
        self.assertFalse(distant['possible'])
        self.assertIsNone(distant['combined_hold_percent'])
        args['heads'][0]['slot']=1.5
        with self.assertRaises(NativeMiningError):self.client.request('advice',**args)
        self.assertEqual(len(self.client.request('hardware')['ships']),3)


class NativeRoutingTests(unittest.TestCase):
    def test_previous_session_or_old_rock_cannot_update_hud(self):
        from main import SynthScanApp
        app=SynthScanApp.__new__(SynthScanApp)
        app.top_hud=SimpleNamespace(state=dict(session_token='current'),update_rock=Mock())
        app.native_fit=None;app.native_rock=None;app.native_detected_fit=None
        result=dict(observed_at=99,panel=dict(settled=True,stats=dict(mass=100)))
        with patch('main.time.time',return_value=100):
            app._apply_native_mining_reading(result,'old')
            app._apply_native_mining_reading(dict(result,observed_at=90),'current')
            app.top_hud.update_rock.assert_not_called()
            app._apply_native_mining_reading(result,'current')
        self.assertEqual(app.native_rock['observed_at'],99)
        app.top_hud.update_rock.assert_called_once()

    def test_fit_changes_remove_old_advice_but_keep_observation(self):
        from main import SynthScanApp
        app=SynthScanApp.__new__(SynthScanApp)
        app.top_hud=SimpleNamespace(state=dict(session_token='current'),update_rock=Mock())
        app.native_fit=fit();app.native_rock=None
        result=dict(observed_at=99,_fit=None,panel=dict(settled=True,stats=dict(mass=100)),advice=dict(old=True))
        with patch('main.time.time',return_value=100):app._apply_native_mining_reading(result,'current')
        self.assertIsNone(app.native_rock['advice'])
        self.assertNotIn('advice',app.top_hud.update_rock.call_args.args[0])
        self.assertIn('advice',result)

    def test_terminal_worker_is_separate_and_closed_worker_can_restart(self):
        from detector import SignatureDetector
        import threading
        detector=SignatureDetector.__new__(SignatureDetector)
        detector.native_client=None;detector.terminal_native_client=None
        detector._native_create_lock=threading.Lock()
        first=detector.get_native_client();second=detector.get_native_client(terminal=True)
        self.assertIsNot(first,second)
        first.close()
        self.assertIsNot(detector.get_native_client(),first)
        detector.close()
        self.assertTrue(second.closed)
        with self.assertRaises(NativeMiningError):detector.get_native_client(terminal=True)

    @unittest.skipUnless((ROOT/'research/native_mining_replay/panels.json').exists(),'Private capture fixture is not distributed')
    def test_rock_hud_expires_and_preserves_duplicate_material_qualities(self):
        panel=next(row['result']['panel'] for row in json.loads((ROOT/'research/native_mining_replay/panels.json').read_text()) if row['name']=='panel_mole_cockpit_1440.png' and row['result']['panel'].get('settled'))
        rock=dict(panel=copy.deepcopy(panel),observed_at=100,session_token='a')
        def text(now=101):return '\n'.join(row['text'] for row in panel_rows(dict(session_token='a'),now=now,rock=rock))
        self.assertIn('Q957',text());self.assertIn('Q310',text())
        self.assertNotIn('Scanned rock',text(106))
        rock['panel']['stats']['scu']=0
        self.assertIn('volume unread',text())

    def test_setup_page_builds_and_collects_actual_mole_head_positions(self):
        import tkinter as tk
        from mining_setup_ui import MiningSetupPage
        root=tk.Tk();root.withdraw()
        app=SimpleNamespace(native_fit=fit('mole','thcn_helix_s2',3),native_reader_status='Offline test',native_rock=None,
                            native_detected_fit=None,top_hud=SimpleNamespace(state={}),is_scanning=False)
        try:
            page=MiningSetupPage(root,app)
            root.update_idletasks()
            value=page.collect()
            self.assertEqual([head['slot'] for head in value['heads']],[3])
            with patch('mining_setup_ui.save_fit',side_effect=lambda value:value) as save:
                page.save()
                self.assertEqual(save.call_args.args[0]['heads'][0]['slot'],3)
            page.destroy()
        finally:root.destroy()


if __name__=='__main__':unittest.main()
