import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from daylight import Body, Site, EPOCH, forecast, observed_phase, rotate
import daylight_catalogue as catalogue
from daylight_planner import arrival_time


class SunlightMathTests(unittest.TestCase):
    def setUp(self):
        self.body = Body('Test', 100, 3600, 0, 0)
        self.site = Site('Equator', (100, 0, 0))

    def test_noon_and_real_seconds(self):
        result = forecast(self.body, self.site, EPOCH)
        self.assertTrue(result['daylight'])
        self.assertAlmostEqual(result['altitude_degrees'], 90)
        self.assertAlmostEqual(result['sunset']-EPOCH, 900)
        self.assertAlmostEqual(result['sunrise']-EPOCH, 2700)
        self.assertEqual(result['windows'][0], (EPOCH, EPOCH+900))

    def test_arrival_at_night_and_next_window(self):
        result = forecast(self.body, self.site, EPOCH+1800)
        self.assertFalse(result['daylight'])
        self.assertAlmostEqual(result['sunrise']-result['at'], 900)
        self.assertEqual(result['windows'][0], (EPOCH+2700, EPOCH+4500))

    def test_longitude_opposite_side_and_time_periodicity(self):
        other = Site('Opposite', (-100, 0, 0))
        self.assertFalse(forecast(self.body, other, EPOCH)['daylight'])
        first = forecast(self.body, self.site, EPOCH+123)
        later = forecast(self.body, self.site, EPOCH+123+3600*50000)
        self.assertAlmostEqual(first['sunrise']-first['at'], later['sunrise']-later['at'])

    def test_signed_declination_and_polar_day_night(self):
        body = Body('Tilted', 100, 3600, 0, -.5)
        north, south = Site('North',(0,0,100)), Site('South',(0,0,-100))
        self.assertEqual(forecast(body,north,EPOCH)['continuous'],'night')
        self.assertEqual(forecast(body,south,EPOCH)['continuous'],'daylight')

    def test_stationary_body_has_no_invented_events(self):
        body = Body('Stationary',100,0,0,0)
        result = forecast(body,self.site,EPOCH)
        self.assertEqual(result['continuous'],'daylight')
        self.assertIsNone(result['sunrise'])
        self.assertEqual(result['events'],[])

    def test_elevation_and_stellar_disc_extend_daylight(self):
        ground = forecast(self.body,self.site,EPOCH)
        high = forecast(self.body,Site('High',(110,0,0)),EPOCH)
        disc = forecast(Body('Large sun',100,3600,0,0,.1),self.site,EPOCH)
        self.assertGreater(high['sunset'],ground['sunset'])
        self.assertLess(high['sunrise'],ground['sunrise'])
        self.assertGreater(disc['sunset'],ground['sunset'])

    def test_retrograde_and_observation_roundtrip(self):
        for period in (3600,-3600):
            body = Body('Retro',100,period,.7,-.1)
            for kind in ('sunrise','sunset'):
                phase = observed_phase(body,self.site,EPOCH+1000,kind)
                before = forecast(body,self.site,EPOCH+999,phase)
                after = forecast(body,self.site,EPOCH+1001,phase)
                self.assertEqual((before['daylight'],after['daylight']),
                                 (False,True) if kind=='sunrise' else (True,False))
                self.assertAlmostEqual(before[kind],EPOCH+1000,places=5)

    def test_crossing_boundary_classifies_departing_state(self):
        self.assertFalse(forecast(self.body,self.site,EPOCH+900)['daylight'])
        self.assertTrue(forecast(self.body,self.site,EPOCH+2700)['daylight'])

    def test_quaternion_convention_and_reject_bad_inputs(self):
        result = rotate((math.sqrt(.5),0,0,math.sqrt(.5)),(1,0,0))
        self.assertAlmostEqual(result[0],0,places=12)
        self.assertAlmostEqual(result[1],1,places=12)
        for values in ((0,0,0),(float('nan'),1,1)):
            with self.assertRaises(ValueError):Site('Bad',values)
        with self.assertRaises(ValueError):Body('Bad',100,1,0,0)
        with self.assertRaises(ValueError):forecast(self.body,self.site,float('nan'))

    def test_arrival_minutes_and_bad_dates(self):
        self.assertEqual(arrival_time('Now','','',1000),1000)
        self.assertEqual(arrival_time('In minutes','15','',1000),1900)
        for bad in ('nan','inf','-1','10081'):
            with self.assertRaises(ValueError):arrival_time('In minutes',bad,'',1000)
        with self.assertRaises(ValueError):arrival_time('Local date/time','','tomorrow')


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.data = catalogue.validate_catalogue(catalogue.read_json(catalogue.BUNDLED))

    def test_bundled_destinations_and_all_models_forecast(self):
        self.assertGreater(len(self.data['sites']),400)
        self.assertEqual({s['system'] for s in self.data['sites']},{'Stanton','Pyro'})
        self.assertTrue(any(s['name'].startswith('Siege of Orison') and s.get('note') for s in self.data['sites']))
        models = {b['name']:Body.from_record(b) for b in self.data['bodies']}
        for row in self.data['sites']:
            result = forecast(models[row['body']],Site(row['name'],tuple(row['coordinates_km'])),1793600000)
            self.assertTrue(math.isfinite(result['altitude_degrees']))
            self.assertTrue(all(e['at']>result['at'] for e in result['events']))

    def test_corrupt_cache_falls_back_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'daylight_catalogue.json'
            path.write_text('{broken',encoding='utf-8')
            self.assertEqual(catalogue.load(directory)['signature'],self.data['signature'])
            self.assertEqual(path.read_text(encoding='utf-8'),'{broken')
        corrupt = copy.deepcopy(self.data);corrupt['bodies'][0]['period_seconds']=1
        with self.assertRaises(ValueError):catalogue.validate_catalogue(corrupt)

    def test_observation_expires_on_patch_model_or_age(self):
        row = next(s for s in self.data['sites'] if s['name']=='Orison')
        build = {'fingerprint':'test:1','patch':'4.test'}
        at = 1793600000
        with tempfile.TemporaryDirectory() as directory:
            catalogue.save_observation(directory,self.data,row,build,at,'sunrise')
            phase,label = catalogue.calibration(directory,self.data,row['body'],build,at+100)
            self.assertIn('Local observation',label)
            self.assertTrue(math.isfinite(phase))
            for changed,version,now in [
                (self.data,dict(build,fingerprint='test:2'),at+100),
                (dict(self.data,signature='changed'),build,at+100),
                (self.data,build,at+8*86400),
                (self.data,None,at+100)]:
                phase,label = catalogue.calibration(directory,changed,row['body'],version,now)
                self.assertEqual(phase,0)
                self.assertIn('not calibrated',label)

    def test_failed_refresh_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'daylight_catalogue.json'
            path.write_text(json.dumps(self.data),encoding='utf-8')
            before = path.read_bytes()
            def failing(*args,**kwargs):raise OSError('offline')
            with self.assertRaises(OSError):catalogue.refresh(directory,opener=failing)
            self.assertEqual(path.read_bytes(),before)


if __name__ == '__main__':unittest.main()
