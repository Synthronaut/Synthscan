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
