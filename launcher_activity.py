"""RSI launcher sessions and OS file-change events, never timed patch polling."""
import ctypes
from ctypes import wintypes as w
from pathlib import Path
import time

from installation import PROFILE
from app_lifecycle import launcher_session_key
from synthstrings_guard import channels,request_check,SETTLE_SECONDS,digest


def signature(game):
    """Metadata only, read on session opening or an OS change notification."""
    result=[]
    for name in ('build_manifest.id','Data.p4k'):
        try:
            stat=(Path(game)/name).stat()
            result.append((stat.st_size,stat.st_mtime_ns,stat.st_ino))
        except OSError:result.append(None)
    return result


class DirectoryChanges:
    def __init__(self,path):
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.FindFirstChangeNotificationW.argtypes=[w.LPCWSTR,w.BOOL,w.DWORD]
        self.api.FindFirstChangeNotificationW.restype=w.HANDLE
        self.api.FindNextChangeNotification.argtypes=[w.HANDLE]
        self.api.FindCloseChangeNotification.argtypes=[w.HANDLE]
        self.api.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
        self.handle=self.api.FindFirstChangeNotificationW(str(path),False,0x1|0x8|0x10)
        if self.handle in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())

    def changed(self):
        result=self.api.WaitForSingleObject(self.handle,0)
        if result==258:return False
        if result!=0:raise ctypes.WinError(ctypes.get_last_error())
        if not self.api.FindNextChangeNotification(self.handle):raise ctypes.WinError(ctypes.get_last_error())
        return True

    def close(self):
        if self.handle:self.api.FindCloseChangeNotification(self.handle);self.handle=None


class LauncherActivity:
    def __init__(self,profile=PROFILE,watch_factory=DirectoryChanges):
        self.profile=Path(profile);self.watch_factory=watch_factory
        self.session=None;self.rows={};self.playing=False;self.pending_start=False

    def update(self,launchers,games=(),now=None):
        now=time.time() if now is None else now
        session=launcher_session_key(launchers) if launchers else None
        opened=session is not None and session!=self.session
        if session!=self.session:
            self.close();self.session=session;self.pending_start=bool(session)
        if not session:return False
        # Observe process names only during play. No game-file checks or watches.
        if games:
            for row in self.rows.values():
                if row['watch']:row['watch'].close();row['watch']=None
            self.playing=True
            return opened
        if self.pending_start:
            request_check(self.profile,'launcher_open',session)
            for game in channels(self.profile):
                values=signature(game)
                recent=values[1] and now-values[1][1]/1e9<SETTLE_SECONDS
                self.rows[game]=dict(watch=self.watch_factory(game),signature=values,
                                     pending=bool(recent),due=now+SETTLE_SECONDS if recent else 0)
            self.pending_start=False
        for game,row in self.rows.items():
            resumed=row['watch'] is None
            if resumed:row['watch']=self.watch_factory(game)
            if resumed or row['watch'].changed():
                values=signature(game)
                if values!=row['signature']:
                    if not row['pending']:
                        request_check(self.profile,'patch_started',session+':'+str(game)+':'+str(now))
                    row.update(signature=values,pending=True,due=now+SETTLE_SECONDS)
            if row['pending'] and now>=row['due']:
                request_check(self.profile,'patch_finished',session+':'+str(game)+':'+digest(repr(row['signature']).encode()))
                row['pending']=False
        self.playing=False
        return opened

    def close(self):
        for row in self.rows.values():
            if row['watch']:row['watch'].close()
        self.rows={}
