"""Verify social scope from a shared incremental game-log reader, not HUD age."""
from pathlib import Path
from threading import RLock
import math


def _game_pids():
    from app_lifecycle import game_process_ids
    return game_process_ids()


def _log_path():
    from installation import game_directory
    return game_directory(True)/'Game.log'


def _reader(path):
    from telemetry_core import IncrementalGameLog
    return IncrementalGameLog(path)


class SessionVerifier:
    def __init__(self,processes=None,path=None,reader=None):
        self.processes=processes;self.path=path;self.factory=reader
        self.lock=RLock();self.key=None;self.reader=None;self.anchors=()

    def matches(self,context):
        joined=context.get('joined_at')
        if not context.get('session_token') or not context.get('full_shard_id') or type(joined) not in (int,float) or not math.isfinite(joined):return False
        with self.lock:
            processes=frozenset((self.processes or _game_pids)())
            if not processes:
                self.reader=None;self.key=None;self.anchors=();return False
            if 'game_pids' in context and set(context['game_pids'])!=processes:return False
            path=Path((self.path or _log_path)())
            key=(path,processes)
            same=key==self.key
            if same and self.anchors:
                with path.open('rb') as stream:
                    for offset,expected in self.anchors:
                        stream.seek(offset)
                        if stream.read(len(expected))!=expected:same=False;break
            # Detect an in-place log restart even if it has already regrown to
            # its old length between ticks. Normal appends keep these bytes.
            if not same:
                self.reader=(self.factory or _reader)(path);self.key=key
            reader=self.reader;length=path.stat().st_size
            reader.poll()
            while reader.last_pos<length:
                previous=reader.last_pos;reader.poll()
                if reader.last_pos==previous:break
            reader.drain_events()
            position=reader.last_pos
            with path.open('rb') as stream:
                prefix=stream.read(min(256,position));offset=max(0,position-256);stream.seek(offset);tail=stream.read(position-offset)
            self.anchors=((0,prefix),(offset,tail))
            return bool(processes==frozenset((self.processes or _game_pids)()) and reader.connected
                        and reader.connection_status=='connected' and not reader.is_loading_screen
                        and reader.full_shard_id==context['full_shard_id'] and reader.joined_at==joined)


_verifier=SessionVerifier()


def require_current_session(context):
    if not _verifier.matches(context):raise ValueError('Session changed or game is loading. Refresh the player list.')
