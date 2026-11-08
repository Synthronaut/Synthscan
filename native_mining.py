"""Bounded local IPC to the pinned, directly reused C++ mining readers."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import mmap
import uuid

ROOT=Path(__file__).resolve().parent
ENGINE_DIR=ROOT/'third_party/mining_core'


class NativeMiningError(RuntimeError):
    pass


class NativeMiningClient:
    def __init__(self, directory=ENGINE_DIR):
        self.directory=Path(directory)
        self.process=None
        self.lock=threading.RLock()
        self.responses=None
        self.sequence=0
        self.diagnostics=deque(maxlen=24)
        self.closed=False
        self.hello=None

    def start(self):
        with self.lock:
            if self.closed:
                raise NativeMiningError('Mining reader has been closed')
            if self.process and self.process.poll() is None:
                return
            try:
                manifest=json.loads((self.directory/'build_manifest.json').read_text(encoding='utf-8'))
                for name,digest in manifest['binary_files'].items():
                    path=(self.directory/name).resolve()
                    if path.parent!=self.directory.resolve() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                        raise ValueError('Native mining binary does not match its build manifest')
            except (OSError,ValueError,KeyError) as exc:
                raise NativeMiningError('Native mining reader unavailable: '+str(exc)) from exc
            env={k:v for k,v in os.environ.items() if not k.startswith(('SCMINER_','BEDROCK_'))}
            self.responses=responses=queue.Queue(maxsize=4)
            self.process=p=subprocess.Popen([str(self.directory/'synthscan-mining.exe')],cwd=self.directory,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',
                bufsize=1,env=env,creationflags=0x08004000 if os.name=='nt' else 0)
            def output():
                try:
                    while line:=p.stdout.readline(1048577):
                        if len(line)>1048576:
                            raise NativeMiningError('Oversized native response')
                        responses.put_nowait(json.loads(line))
                except (ValueError,queue.Full,NativeMiningError) as exc:
                    self.diagnostics.append(str(exc))
                finally:
                    try:responses.put_nowait(None)
                    except queue.Full:pass
            def errors():
                for line in p.stderr:
                    self.diagnostics.append(line.strip()[:500])
            threading.Thread(target=output,daemon=True).start()
            threading.Thread(target=errors,daemon=True).start()
            self.hello=self._exchange(dict(op='hello'),30)
            if not isinstance(self.hello,dict) or self.hello.get('schema')!=1 or not self.hello.get('neural_ready') or self.hello.get('templates',0)<=0:
                self.close()
                raise NativeMiningError('Native mining reader did not initialize all readers')

    def _exchange(self, request, timeout):
        self.sequence+=1
        payload=dict(request,id=self.sequence)
        raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
        if len(raw.encode('utf-8'))>65536:
            raise NativeMiningError('Native request too large')
        try:
            self.process.stdin.write(raw+'\n');self.process.stdin.flush()
            result=self.responses.get(timeout=timeout)
        except (OSError,ValueError,queue.Empty) as exc:
            self.close()
            raise NativeMiningError('Native mining reader stopped responding') from exc
        if not isinstance(result,dict) or result.get('id')!=self.sequence or result.get('schema')!=1:
            self.close()
            raise NativeMiningError('Invalid native mining response')
        if not result.get('ok'):
            raise NativeMiningError(result.get('error','Native request failed'))
        if 'result' not in result:
            self.close()
            raise NativeMiningError('Native mining response has no result')
        return result['result']

    def request(self, operation, timeout=15, **fields):
        if operation=='scan_live':
            from capture_privacy import GameCapture
            if not hasattr(self,'_capture'):self._capture=GameCapture()
            frame=self._capture.grab()
            if frame is None:return {'inactive':True}
            return self.request_image(frame,**fields)
        with self.lock:
            self.start()
            return self._exchange(dict(fields,op=operation),timeout)

    def request_image(self, image, **fields):
        import cv2,numpy as np
        if isinstance(image,(str,Path)):
            from PIL import Image
            with Image.open(image) as source:frame=cv2.cvtColor(np.asarray(source.convert('RGB')),cv2.COLOR_RGB2BGR)
        elif hasattr(image,'convert'):frame=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2BGR)
        else:frame=np.asarray(image)
        if frame.ndim!=3 or frame.shape[2]!=3 or frame.dtype!=np.uint8:raise NativeMiningError('Expected a BGR image')
        height,width=frame.shape[:2];size=width*height*3
        if not 0<width<=8192 or not 0<height<=8192 or size>128*1024*1024:raise NativeMiningError('Frame size is outside capture limits')
        with self.lock:self.start()
        frame=np.ascontiguousarray(frame);name='Local\\SynthScan.Scan.'+str(os.getpid())+'.'+uuid.uuid4().hex
        with mmap.mmap(-1,size,tagname=name,access=mmap.ACCESS_WRITE) as memory:
            memory.write(frame.tobytes())
            try:return self.request('scan_mapping',mapping=name,width=width,height=height,**fields)
            finally:memory.seek(0);memory.write(bytes(size))

    def close(self):
        # Closing from the UI thread must not wait behind an in-flight read.
        self.closed=True
        if hasattr(self,"_capture"):self._capture.stop()
        p=self.process
        if p:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=2)
                except subprocess.TimeoutExpired:p.kill()
            for pipe in (p.stdin,p.stdout,p.stderr):
                try:pipe.close()
                except (OSError,ValueError):pass
        self.process=None


def marker_match(result):
    """Adapt native exact alternatives for existing HUD/app consumers."""
    marker=result.get('marker')
    if not marker or not marker.get('accepted'):
        return None,None
    candidates=[]
    for row in marker.get('candidates',[]):
        if row.get('difference')!=0:
            continue
        name=row['name']
        label=name if row.get('combination') else f"{row['count']}x {name}"
        candidates.append(dict(row,label=label))
    if not candidates:
        return None,None
    ambiguous=len(candidates)>1
    title=f'{len(candidates)} possible matches' if ambiguous else candidates[0]['label']
    return dict(title=title,speech=title,type='ambiguous' if ambiguous else candidates[0]['category'],
                candidates=candidates,alternates=candidates[1:],ambiguous=ambiguous,count=None if ambiguous else candidates[0]['count'],
                base_rs=None,diff=0,match_kind='native_exact',details=' | '.join(c['label'] for c in candidates),
                reader_score=marker.get('ocr_confidence'),reader_method=marker.get('method'),source='native_mining_core',
                game_version_family='4.10'),marker['value']


def native_refinery_orders(result, station_hint=''):
    """Translate only complete native observations. cSCU stays explicitly typed."""
    from crafting_catalog import get_catalog,normalize_name
    import re
    catalog=get_catalog()
    screen=result.get('refinery') or {}
    stations={normalize_name(s):s for s in catalog.data['refinery_stations']}
    station=stations.get(normalize_name(screen.get('station_text',''))) or station_hint.strip()
    if not station:return []
    materials={normalize_name(name):name for name in catalog.materials}
    orders=[]
    for panel in screen.get('panels',[]):
        if not panel.get('whole') or panel.get('status') not in ('processing','completed'):
            continue
        if not isinstance(panel.get('number'),int) or panel['number']<0:continue
        parts=[]
        valid=True
        for row in panel['rows']:
            name=re.sub(r'\s*\(ORE\)\s*$','',row['material'],flags=re.I)
            material=materials.get(normalize_name(name))
            if not material or not 1<=row['quality']<=1000 or row['yield_cscu']<0:
                valid=False;break
            parts.append(dict(material=material,quality=row['quality'],scu=row['yield_cscu']/100))
        if valid and parts:
            orders.append(dict(station=station,number=panel['number'],status=panel['status'],parts=parts,
                               remaining_seconds=panel['seconds'] if panel['seconds']>=0 else None,source='Native terminal reader',partial=False))
    return orders
