"""Observed shard names only. Loading OCR is optional and Full-edition-only."""
from concurrent.futures import ThreadPoolExecutor
import re,time

LABEL=re.compile(r"(?:connecting\s+to(?:\s+(?:shard|server))?\s*:?|shard\s*(?:name)?\s*[:\-])\s*[\"']?([A-Za-z][A-Za-z'-]{1,31}[\s_]+[A-Za-z][A-Za-z'-]{1,31})",re.I)
GENERIC={'YOUR','CURRENT','POSITION','IN','QUEUE','IS','THE','SERVER','SHARD','LOADING','CONNECTING','UNKNOWN','PLEASE','WAIT','MAIN','MENU','LOCAL','FRONTEND','TO','UNIVERSE'}
def clean_name(value):
    if not isinstance(value,str):return None
    words=value.replace('_',' ').strip().upper().split()
    if len(words)!=2 or any(not re.fullmatch(r"[A-Z][A-Z'-]{1,31}",w) or w in GENERIC for w in words):return None
    return ' '.join(words)

def loading_name(boxes):
    # A labelled, high-confidence name; never arbitrary two-word loading tips.
    rows=[b for b in boxes if b.confidence>=.90]
    text=' '.join(b.text for b in sorted(rows,key=lambda b:(b.top,b.left)))
    names={name for match in LABEL.finditer(text) if (name:=clean_name(match.group(1)))}
    return names.pop() if len(names)==1 else None

class ShardNameCollector:
    def __init__(self,enabled=None,sample=None,executor=None):
        if enabled is None:
            from app_edition import screen_reading
            enabled=screen_reading()
        self.enabled=enabled;self.sample=sample or self._sample;self.executor=executor
        self.future=None;self.key=None;self.job_key=None;self.started=0.;self.next_at=0.;self.candidate=None;self.count=0;self.done=None;self.capture=None;self.note=''
    def _release(self):
        if self.capture:self.capture.stop();self.capture=None
    def _sample(self):
        # No capture imports, DLLs or OCR models are required by Standard.
        from app_edition import require_screen_reading
        require_screen_reading()
        from capture_privacy import GameCapture
        if self.capture is None:self.capture=GameCapture()
        image=self.capture.grab()
        if image is None:return None
        h,w=image.shape[:2];image=image[int(h*.20):int(h*.78),int(w*.16):int(w*.84)]
        from screen_readers import read_image
        return loading_name(read_image(image))
    def tick(self,full_id,token,loading,now=None):
        now=time.time() if now is None else now;key=(full_id,token) if full_id and token else None
        if key!=self.key:
            self.key=key;self.candidate=None;self.count=0;self.started=now;self.next_at=now;self.done=None
        result=None
        if self.future is not None and self.future.done():
            try:name=clean_name(self.future.result())
            except Exception:name=None;self.note='Loading-name read unavailable; saved names remain available.'
            self.future=None
            if loading and key and self.job_key==key and name:
                if name==self.candidate:self.count+=1
                else:self.candidate=name;self.count=1
                if self.count>=2:self.done=key;result=dict(full_shard_id=full_id,name=name,source='loading_screen_ocr',observed_at=now)
            elif self.job_key==key:self.candidate=None;self.count=0
        active=self.enabled and bool(key) and loading and self.done!=key and now-self.started<=120
        if not active:
            if self.future is None and self.capture and self.executor:self.future=self.executor.submit(self._release);self.job_key=None
            return result
        if self.future is None and now>=self.next_at:
            if self.executor is None:self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='shard-name')
            self.job_key=key;self.future=self.executor.submit(self.sample);self.next_at=now+1
        return result
    def close(self):
        if self.executor:
            self.executor.submit(self._release);self.executor.shutdown(wait=False,cancel_futures=False)
