"""Explicitly armed coordinate-only clipboard capture; never sends game input."""
import argparse,ctypes,json,math,re,time
from pathlib import Path
from refinery_orders import atomic_json

def parse_position(text):
    if not isinstance(text,str) or len(text)>4096:return None
    prefix=re.match(r'^\s*Coordinates?\s*:',text,re.I)
    if not prefix:return None
    payload=text[prefix.end():];values={};last=0
    for match in re.finditer(r'\b([xyz])\s*[:=]\s*([-+]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)',payload,re.I):
        if payload[last:match.start()].strip(' ,\r\n\t'):return None
        axis=match[1].lower()
        if axis in values:return None
        try:value=float(match[2].replace(',',''))
        except ValueError:return None
        if not math.isfinite(value) or abs(value)>1e16:return None
        values[axis]=value;last=match.end()
    if set(values)!=set('xyz') or payload[last:].strip(' ,\r\n\t'):return None
    return [values[a] for a in 'xyz']

class CoordinateClipboard:
    def __init__(self):
        self.user=ctypes.WinDLL('user32',use_last_error=True);self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.user.GetClipboardSequenceNumber.restype=ctypes.c_uint32
        self.user.GetClipboardData.argtypes=[ctypes.c_uint32];self.user.GetClipboardData.restype=ctypes.c_void_p
        self.user.OpenClipboard.argtypes=[ctypes.c_void_p];self.user.GetClipboardOwner.restype=ctypes.c_void_p
        self.user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
        self.kernel.GlobalSize.argtypes=[ctypes.c_void_p];self.kernel.GlobalSize.restype=ctypes.c_size_t
        self.kernel.GlobalLock.argtypes=[ctypes.c_void_p];self.kernel.GlobalLock.restype=ctypes.c_void_p
        self.kernel.GlobalUnlock.argtypes=[ctypes.c_void_p]
    def sequence(self):return self.user.GetClipboardSequenceNumber()
    def position(self):
        if not self.user.OpenClipboard(None):return False
        try:
            if not self.user.IsClipboardFormatAvailable(13):return None
            handle=self.user.GetClipboardData(13)
            if not handle:return None
            size=self.kernel.GlobalSize(handle)
            if size<2 or size>8194:return None
            pointer=self.kernel.GlobalLock(handle)
            if not pointer:return None
            try:text=ctypes.wstring_at(pointer,size//2).split('\0',1)[0]
            finally:self.kernel.GlobalUnlock(handle)
            xyz=parse_position(text)
            if xyz is None:return None
            pid=ctypes.c_uint32();self.user.GetWindowThreadProcessId(self.user.GetClipboardOwner(),ctypes.byref(pid))
            return dict(xyz_m=xyz,clipboard_owner_pid=pid.value)
        finally:self.user.CloseClipboard()

class ArmedPosition:
    def __init__(self,clipboard,context,seconds=120,clock=time.time):
        if not context.get('session_token') or not context.get('game_pids'):raise ValueError('Join a shard before arming position capture')
        self.clipboard=clipboard;self.clock=clock;self.context=context;self.started=clock();self.until=self.started+seconds
        self.sequence=clipboard.sequence();self.status='armed';self.fix=None
    def poll(self,context):
        if self.status!='armed':return self.fix
        if context.get('session_token')!=self.context['session_token'] or set(context.get('game_pids',[]))!=set(self.context['game_pids']):
            self.status='session_changed';return None
        if self.clock()>=self.until:self.status='expired';return None
        sequence=self.clipboard.sequence()
        if sequence==self.sequence:return None
        result=self.clipboard.position()
        if result is False:return None
        self.sequence=sequence
        if not result:return None
        pid=result['clipboard_owner_pid']
        self.fix=dict(schema=1,source='/showlocation clipboard',**result,received_at=self.clock(),armed_at=self.started,
                      game_pids=list(context['game_pids']),session_token=context['session_token'],full_shard_id=context['full_shard_id'],
                      frame='system_global_unverified',units='m',producer_verified=pid in context['game_pids'])
        self.status='captured';return self.fix

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seconds',type=int,default=120);p.add_argument('--owner',type=int,required=True);args=p.parse_args()
    from native_bridge import owner_alive
    from native_control import DATA
    def context():
        state=json.loads((DATA/'session_state.json').read_text(encoding='utf-8'))
        if abs(time.time()-state['written_at'])>4:raise ValueError('Session source is stale')
        return state
    destination=Path(args.output);capture=ArmedPosition(CoordinateClipboard(),context(),args.seconds)
    try:
        while owner_alive(args.owner) and capture.status=='armed':
            capture.poll(context());atomic_json(destination,dict(status=capture.status,armed_at=capture.started,until=capture.until,fix=capture.fix));time.sleep(.1)
        if capture.status=='armed':capture.status='owner_exited'
    except (OSError,ValueError):capture.status='session_unavailable'
    atomic_json(destination,dict(status=capture.status,armed_at=capture.started,until=capture.until,fix=capture.fix))

if __name__=='__main__':main()
