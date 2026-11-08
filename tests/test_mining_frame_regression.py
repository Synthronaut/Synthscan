"""Optional private real-frame regression; never captures or controls the game.

Set SYNTHSCAN_MINING_TEST_FRAME to the supplied Nov 1 mining screenshot and
SYNTHSCAN_TEST_LOCALIZATION to its game's SynthStrings file. The private image
is not included in the source or a release.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class MiningFrameRegression(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SYNTHSCAN_HAND_MINING_FRAME'), 'Requires the private Glacosite scanner frame')
    def test_ship_scanned_gem_quality_without_piece_count(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='8',SYNTHSCAN_PROBE_RUNTIME='1')
            subprocess.run([str(binary),os.environ['SYNTHSCAN_HAND_MINING_FRAME'],str(output)],env=env,
                           check=True,capture_output=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            reading=json.loads(output.read_text(encoding='utf-8'))
        self.assertTrue(reading['found']);self.assertTrue(reading['piece_quote_ready'])
        self.assertEqual(reading['mass'],1);self.assertEqual(reading['instability'],0)
        self.assertEqual(reading['ore'],'Glacosite')
        self.assertEqual(reading['parts'][0]['quality'],360)
        self.assertAlmostEqual(reading['parts'][0]['percent'],69.74,places=2)
        self.assertTrue(reading['runtime_crop_whole'])
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'quick.json'
            subprocess.run([str(binary),'--piece',os.environ['SYNTHSCAN_HAND_MINING_FRAME'],str(output),
                            '1726','567','.890688','K'],check=True,capture_output=True,timeout=30,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            quick=json.loads(output.read_text(encoding='utf-8'))
        for row in quick:
            self.assertTrue(row['ok']);self.assertEqual(row['ore'],'Glacosite');self.assertEqual(row['quality'],360)

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_GREEN_TURRET_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private held-rock frame for colour variants')
    def test_resistance_white_green_red_variants(self):
        # Change only the resistance glyph colour in a real frame. Geometry,
        # terrain, all figures and composition remain the captured pixels.
        import cv2
        frame=cv2.imread(os.environ['SYNTHSCAN_MINING_GREEN_TURRET_FRAME'])
        region=frame[599:630,1990:2080]
        b,g,r=cv2.split(region.astype('int16'))
        glyphs=(g>120)&(g-r>30)&(g-b>25)
        self.assertGreater(int(glyphs.sum()),30)
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            for colour in ('white','green','red'):
                image=frame.copy();target=image[599:630,1990:2080]
                if colour=='white':
                    strength=region[glyphs,1]
                    target[glyphs]=strength[:,None]
                elif colour=='red':
                    strength=region[glyphs,1]
                    target[glyphs,0]=(strength*.4).astype('uint8')
                    target[glyphs,1]=(strength*.4).astype('uint8')
                    target[glyphs,2]=strength
                path=Path(directory)/(colour+'.png');cv2.imwrite(str(path),image)
                output=Path(directory)/(colour+'.json')
                env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='6',SYNTHSCAN_PROBE_RUNTIME='1')
                subprocess.run([str(binary),str(path),str(output)],env=env,
                               check=True,capture_output=True,timeout=90)
                reading=json.loads(output.read_text(encoding='utf-8'))
                with self.subTest(colour=colour):
                    self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
                    self.assertEqual(reading['mass'],26842)
                    self.assertAlmostEqual(reading['resistance'],35)
                    self.assertAlmostEqual(reading['scu'],12.77,places=2)
                    self.assertEqual(reading['resistance_adjusted'],colour!='white')

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_GREEN_TURRET_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private Nov 2 held Gold turret frame')
    def test_turret_green_resistance_and_fragmented_volume_digits(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='8',SYNTHSCAN_PROBE_RUNTIME='1')
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_GREEN_TURRET_FRAME'],str(output)],
                           env=env,check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text(encoding='utf-8'))
        self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
        self.assertTrue(reading['runtime_crop_whole']);self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertEqual(reading['mass'],26842)
        self.assertAlmostEqual(reading['resistance'],35)
        self.assertAlmostEqual(reading['instability'],149.37,places=2)
        self.assertAlmostEqual(reading['scu'],12.77,places=2)
        expected=[('Bexalite',2.23,597),('Gold',11.59,864),('Gold',62.02,264),('Borase',2.64,584),('',21.50,0)]
        self.assertEqual(len(reading['parts']),len(expected))
        for actual,(ore,percent,quality) in zip(reading['parts'],expected):
            self.assertEqual((actual['ore'],actual['quality']),(ore,quality))
            self.assertAlmostEqual(actual['percent'],percent,places=2)

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_PILOT_OVERLAP_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private Nov 2 pilot/flight overlap frame')
    def test_pilot_small_numbers_and_flight_text_over_composition(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='6',SYNTHSCAN_PROBE_RUNTIME='1')
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_PILOT_OVERLAP_FRAME'],str(output)],
                           env=env,check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text(encoding='utf-8'))
        self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
        self.assertTrue(reading['runtime_crop_whole']);self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertEqual(reading['mass'],21858)
        self.assertAlmostEqual(reading['resistance'],43)
        self.assertAlmostEqual(reading['instability'],121.21,places=2)
        self.assertAlmostEqual(reading['scu'],16.62,places=2)
        expected=[('Bexalite',4.35,597),('Gold',8.37,959),('Gold',34.03,264),('Borase',4.97,676),('',48.25,0)]
        self.assertEqual(len(reading['parts']),len(expected))
        for actual,(ore,percent,quality) in zip(reading['parts'],expected):
            self.assertEqual((actual['ore'],actual['quality']),(ore,quality))
            self.assertAlmostEqual(actual['percent'],percent,places=2)

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_NO_ROCK_FRAME'),
                         'Requires the private Nov 2 flight-only frame')
    def test_flight_instruments_without_rock_are_rejected(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='6',SYNTHSCAN_PROBE_RUNTIME='1')
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_NO_ROCK_FRAME'],str(output)],
                           env=env,check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text(encoding='utf-8'))
        self.assertFalse(reading['found']);self.assertFalse(reading['estimate_ready'])

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_22717_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private Nov 2 scanned Tin frame')
    def test_tin_full_composition_with_warm_runtime_panel_cache(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            spot=Path(directory)/'panel_spot.txt'
            spot.write_text('2560 1440 1892 581 1.03239 K 4\n',encoding='utf-8')
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='12',SYNTHSCAN_PROBE_RUNTIME='1',
                     SYNTHSCAN_PROBE_PANEL_SPOT=str(spot))
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_22717_FRAME'],str(output)],
                           env=env,check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text())
        self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
        self.assertTrue(reading['runtime_crop_whole']);self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertEqual(reading['mass'],22717)
        self.assertAlmostEqual(reading['scu'],40.35,places=2)
        expected=[('Tin',10.18,880),('Tin',37.05,340),('Copper',8.63,593),('',44.12,0)]
        self.assertEqual(len(reading['parts']),len(expected))
        for actual,(ore,percent,quality) in zip(reading['parts'],expected):
            self.assertEqual((actual['ore'],actual['quality']),(ore,quality))
            self.assertAlmostEqual(actual['percent'],percent,places=2)

    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_TEST_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the opt-in private mining screenshot and localization fixture')
    def test_mole_shortened_materials_bright_sand_volume_and_composition(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        if not binary.exists():self.skipTest('Build the offline mining-frame probe first')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_TEST_FRAME'],str(output)],
                           check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text())
        self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
        self.assertTrue(reading['runtime_crop_whole']);self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertEqual(reading['mass'],17104)
        self.assertAlmostEqual(reading['scu'],53.38,places=2)
        expected=[('Aslarite',5.56,575),('Aslarite',62.30,287),('Agricium',4.39,588),('Titanium',2.51,516),('',25.22,0)]
        self.assertEqual(len(reading['parts']),len(expected))
        for actual,(name,percent,quality) in zip(reading['parts'],expected):
            self.assertEqual(actual['ore'],name);self.assertEqual(actual['quality'],quality)
            self.assertAlmostEqual(actual['percent'],percent,places=2)


    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_OVERLAP_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private live overlapping-HUD frame')
    def test_overlapping_flight_hud_has_labelled_partial_estimate(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            env=dict(os.environ,SYNTHSCAN_PROBE_PASSES='3')
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_OVERLAP_FRAME'],str(output)],
                           env=env,check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text())
        self.assertTrue(reading['found'])
        self.assertEqual(reading['mass'],15985)
        self.assertAlmostEqual(reading['scu'],23.89,places=2)
        self.assertFalse(reading['whole'])
        self.assertTrue(reading['partial']);self.assertTrue(reading['estimate_ready'])
        self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertEqual([(p['ore'],p['quality']) for p in reading['parts']],
                         [('Bexalite',597),('Gold',644),('Borase',584),('Borase',359),('',0)])
        self.assertLess(sum(p['percent'] for p in reading['parts']),99.95)


    @unittest.skipUnless(os.environ.get('SYNTHSCAN_MINING_122308_FRAME') and os.environ.get('SYNTHSCAN_TEST_LOCALIZATION'),
                         'Requires the private 12:23 real mining screenshot')
    def test_clear_aslarite_panel_terrain_edge_and_small_volume(self):
        binary=ROOT/'dist/mining-frame-probe/mining_frame_probe.exe'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reading.json'
            subprocess.run([str(binary),os.environ['SYNTHSCAN_MINING_122308_FRAME'],str(output)],
                           check=True,capture_output=True,timeout=90)
            reading=json.loads(output.read_text())
        self.assertTrue(reading['found']);self.assertTrue(reading['whole'])
        self.assertTrue(reading['runtime_crop_whole']);self.assertTrue(reading['runtime_crop_estimate_ready'])
        self.assertFalse(reading['partial']);self.assertEqual(reading['mass'],2075)
        self.assertAlmostEqual(reading['scu'],6.09,places=2)
        expected=[('Aslarite',5.75,575),('Aslarite',67.62,287),('Agricium',4.67,588),('Titanium',3.97,516),('',17.97,0)]
        self.assertEqual(len(reading['parts']),len(expected))
        for actual,(name,percent,quality) in zip(reading['parts'],expected):
            self.assertEqual(actual['ore'],name);self.assertEqual(actual['quality'],quality)
            self.assertAlmostEqual(actual['percent'],percent,places=2)


if __name__=='__main__':unittest.main()
