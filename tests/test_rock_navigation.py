import copy,json,math,tempfile,unittest
from pathlib import Path
from position_capture import parse_position,ArmedPosition
from rock_navigation import RockNavigation,guidance,rotated_target,quat_rotate

class Clipboard:
    def __init__(self):self.seq=5;self.value=None;self.reads=0
    def sequence(self):return self.seq
    def position(self):self.reads+=1;return self.value
    def put(self,xyz):self.seq+=1;self.value=dict(xyz_m=xyz,clipboard_owner_pid=42)

CONTEXT=dict(session_token='joined-1',game_pids=[42],full_shard_id='test-shard')
BODY=dict(id='Test/Moon',name='Moon',system='Test',center=[1e10,-2e10,0],radius_m=300000,
          period_s=21600,quaternion=[1,0,0,0],fingerprint='test-model')

class PositionTests(unittest.TestCase):
    def test_formats(self):
        for s in ['Coordinates: x: 1000 y: -2 z: .5','Coordinates: X=1,000, Y=-2, Z=5e-1']:
            self.assertEqual(parse_position(s),[1000,-2,.5])
    def test_reject_private_or_malformed(self):
        for s in ['secret x:1 y:2 z:3','Coordinates: secret x:1 y:2 z:3','Coordinates: x:.1.2 y:2 z:3',
                  'Coordinates: x:1 x:2 y:2 z:3','Coordinates: x:NaN y:2 z:3','Coordinates: x:1e99 y:2 z:3',
                  'Coordinates: x:1 y:2','Coordinates: x:1 y:2 z:3 secret','x'*4097]:
            self.assertIsNone(parse_position(s),s)
    def test_old_clipboard_not_freshened_and_one_shot(self):
        c=Clipboard();c.value=dict(xyz_m=[1,2,3],clipboard_owner_pid=42)
        a=ArmedPosition(c,CONTEXT,clock=lambda:100)
        self.assertIsNone(a.poll(CONTEXT));self.assertEqual(c.reads,0)
        c.put([4,5,6]);fix=a.poll(CONTEXT);self.assertEqual(fix['xyz_m'],[4,5,6]);self.assertTrue(fix['producer_verified'])
        c.put([7,8,9]);self.assertEqual(a.poll(CONTEXT),fix)
    def test_locked_clipboard_retry_and_session_change(self):
        c=Clipboard();a=ArmedPosition(c,CONTEXT,clock=lambda:100);c.seq+=1;c.value=False
        self.assertIsNone(a.poll(CONTEXT));c.value=dict(xyz_m=[1,2,3],clipboard_owner_pid=0)
        self.assertFalse(a.poll(CONTEXT)['producer_verified'])
        a=ArmedPosition(c,CONTEXT,clock=lambda:100)
        self.assertIsNone(a.poll(dict(CONTEXT,session_token='joined-2')));self.assertEqual(a.status,'session_changed')
    def test_timeout(self):
        t=[100];a=ArmedPosition(Clipboard(),CONTEXT,seconds=10,clock=lambda:t[0]);t[0]=111
        self.assertIsNone(a.poll(CONTEXT));self.assertEqual(a.status,'expired')

class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.clip=Clipboard();self.t=1000
        self.nav=RockNavigation(self.path,lambda:self.clip,lambda:self.t,{BODY['id']:copy.deepcopy(BODY)})
        self.context=copy.deepcopy(CONTEXT)
    def tearDown(self):self.nav.close();self.tmp.cleanup()
    def command(self,action,**kw):
        self.nav.command(dict(action=action,id='test',session_token=self.context['session_token'],**kw),self.context)
        self.assertFalse(self.nav.result['error'],self.nav.message)
    def capture(self,role,xyz):
        self.command('nav_arm',body_id=BODY['id'],role=role,name='Test rock',stand_off_m=20)
        self.clip.put(xyz);return self.nav.tick(self.context)
    def mark(self):
        self.capture('mark',[BODY['center'][0]+BODY['radius_m'],BODY['center'][1],0]);return self.nav.mark()
    def test_rotating_point_check_and_guidance(self):
        mark=self.mark();self.t+=60;target=rotated_target(mark,BODY,self.t)
        self.capture('check',target);self.assertTrue(self.nav.mark()['rotation_check']['passed'])
        current=[target[0],target[1]+100,target[2]];self.t+=.1
        state=self.capture('current',current)
        self.assertGreater(state['guidance']['distance_m'],90)
        self.assertLess(state['guidance']['distance_m'],120)
        self.t+=16;self.assertIn('stale',self.nav.tick(self.context)['guidance']['unavailable'])
    def test_wrong_model_check_fails(self):
        mark=self.mark();self.t+=60;self.capture('check',mark['fix']['xyz_m'])
        self.assertFalse(self.nav.mark()['rotation_check']['passed'])
        self.assertIn('required',self.nav.tick(self.context)['guidance']['unavailable'])
    def test_rejoin_cancels_even_captured_pending_fix(self):
        self.command('nav_arm',body_id=BODY['id']);self.clip.put([1,2,3]);self.nav.capture.poll(self.context)
        self.context['session_token']='new-join';self.nav.tick(self.context);self.assertEqual(self.nav.marks,[])
    def test_wrong_body_rejected(self):
        self.capture('mark',[1,2,3]);self.assertEqual(self.nav.marks,[])
    def test_import_export_privacy_and_corrupt_storage(self):
        self.mark();p=self.path/'share.json';self.command('nav_export',path=str(p))
        public=json.loads(p.read_text());self.assertNotIn('session_token',public['bookmark']['fix']);self.assertNotIn('game_pids',public['bookmark']['fix'])
        public['bookmark']['rotation_check']=dict(passed=True);p.write_text(json.dumps(public))
        self.command('nav_import',path=str(p));self.assertNotIn('rotation_check',self.nav.mark())
        original=b'{bad json';self.nav.path.write_bytes(original)
        broken=RockNavigation(self.path,bodies={BODY['id']:BODY});self.assertTrue(broken.read_only)
        broken.command(dict(action='nav_import',id='test',path=str(p)),self.context)
        self.assertTrue(broken.result['error']);self.assertEqual(broken.marks,[]);self.assertEqual(broken.path.read_bytes(),original)
    def test_select_cancels_capture_and_shard_mismatch_blocks(self):
        mark=self.mark();self.command('nav_arm',body_id=BODY['id']);self.command('nav_select',bookmark_id=mark['id']);self.assertIsNone(self.nav.capture)
        self.context['full_shard_id']='other';self.nav.command(dict(action='nav_arm',id='test',body_id=BODY['id'],role='current',session_token=self.context['session_token']),self.context)
        self.assertTrue(self.nav.result['error'])
    def test_quaternion_inverse(self):
        v=[13,8,-7];q=[.5,.5,.5,.5];back=quat_rotate(quat_rotate(v,q),q,True)
        for a,b in zip(v,back):self.assertAlmostEqual(a,b)
    def test_shared_estimate_is_explicitly_unverified(self):
        mark=self.mark();p=self.path/'share.json';self.command('nav_export',path=str(p));self.command('nav_import',path=str(p))
        self.t+=1;view=self.capture('current',mark['fix']['xyz_m'])
        self.assertIn('Unverified shared estimate',view['guidance']['status'])
    def test_numeric_strings_cannot_break_guidance(self):
        mark=self.mark();mark=copy.deepcopy(mark);mark['fix']['received_at']='1000'
        with self.assertRaises(ValueError):self.nav.validate_mark(mark)
    def test_fixed_space_range_after_check(self):
        body=dict(BODY,space=True,period_s=0,radius_m=0);self.nav.bodies[BODY['id']]=body
        self.capture('mark',[1,2,3]);self.t+=60;self.capture('check',[1,2,3]);self.assertTrue(self.nav.mark()['rotation_check']['passed'])
        view=self.capture('current',[1001,2,3]);self.assertEqual(view['guidance']['distance_m'],1000)
        self.assertNotIn('bearing_deg',view['guidance'])

if __name__=='__main__':unittest.main()
