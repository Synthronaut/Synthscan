"""Optional People/Piracy alerts when the permanent server ribbon is not installed.

Only draws existing, fresh observations. No capture, game input or RPC calls.
"""
import argparse
import math
import time
from pathlib import Path

from telemetry_core import SHARD_RE


def fresh_token(snapshot,owner,now):
    if not isinstance(snapshot,dict) or snapshot.get('owner_pid')!=owner:return None
    at=snapshot.get('written_at')
    if type(at) not in (int,float) or not math.isfinite(at) or not 0<=now-at<4:return None
    token=snapshot.get('session_token');full=snapshot.get('full_shard_id')
    if not isinstance(token,str) or not token or len(token)>512 or not isinstance(full,str) or not SHARD_RE.fullmatch(full) or not snapshot.get('game_pids'):return None
    return token


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--owner',type=int,required=True);args=parser.parse_args()
    from app_lifecycle import SingleInstance
    from feature_modules import enabled
    from installation import PROFILE
    from native_bridge import owner_alive
    from telemetry_ipc import read_shared_json
    from hud_controller import game_window_rect
    import tkinter as tk
    lock=SingleInstance('native-top-hud')
    if not lock.acquired:return
    root=tk.Tk();root.withdraw();started=time.time()
    pirate_gate=pirate_window=people_gate=people_window=None
    if enabled('piracy'):
        from interdiction_watch import AlertGate
        from snare_alert_ui import SnareAlertWindow
        pirate_gate=AlertGate(started);pirate_window=SnareAlertWindow(root,game_window_rect)
    if enabled('people'):
        from companion_toasts import NoticeGate,CompanionToast
        people_gate=NoticeGate(started);people_window=CompanionToast(root,game_window_rect)
    def read(name,limit=8*1024*1024):
        try:return read_shared_json(PROFILE/name,limit=limit) or {}
        except (OSError,ValueError):return {}
    def poll():
        if not owner_alive(args.owner):root.destroy();return
        now=time.time();snapshot=read('session_ribbon.json');settings=read('native_settings.json');token=fresh_token(snapshot,args.owner,now)
        visible=bool(token and settings.get('show_hud',True) and game_window_rect())
        if pirate_gate:
            from interdiction_watch import piracy_alerts_enabled
            active=visible and piracy_alerts_enabled(settings,True)
            pirate_window.update(pirate_gate.consume(snapshot,args.owner,now,active),token,active)
        if people_gate:
            notices=people_gate.consume(read('companion_alerts.json',65536),args.owner,token,visible,now)
            people_window.update(notices,visible,now,token)
        root.after(250,poll)
    try:poll();root.mainloop()
    finally:lock.close()


if __name__=='__main__':main()
