"""Original top ribbon, fed read-only by the native app's session service."""
import argparse,json,logging,os,time
from pathlib import Path
from telemetry_core import SHARD_RE

def hud_state(snapshot,owner,now):
    if snapshot.get('owner_pid')!=owner or not 0<=now-snapshot.get('written_at',0)<4:
        return dict(connection_status='unavailable',callsign='SESSION SERVICE UNAVAILABLE',session_token=None)
    source=dict(snapshot.get('hud_state') or {})
    full=snapshot.get('full_shard_id','');match=SHARD_RE.fullmatch(full)
    source.update(session_token=snapshot.get('session_token'),full_shard_id=full,
                  shard_id=match.groups()[-1] if match else '--',
                  region_display=snapshot.get('region','--'),callsign=snapshot.get('shard_name','MAIN MENU'),
                  hop_status=snapshot.get('hop',''),location_display=snapshot.get('location') or '--',
                  connection_status='connected' if snapshot.get('session_token') else ('game_closed' if not snapshot.get('game_pids') else 'main_menu'))
    for key,ttl in [('client_fps',2),('ping_ms',3)]:
        metadata=(source.get('metric_meta') or {}).get(key) or {}
        age=now-metadata.get('observed_at',0)
        if not -.25<=age<=ttl:source.pop(key,None)
    return source

def main():
    started_at=time.time()
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,required=True);args=p.parse_args()
    from app_lifecycle import SingleInstance
    lock=SingleInstance('native-top-hud')
    if not lock.acquired:return
    from native_control import DATA
    from native_bridge import owner_alive
    from telemetry_ipc import read_shared_json
    logging.basicConfig(filename=DATA/'top_hud.log',level=logging.INFO)
    import ctypes,tkinter as tk,tkinter.font as tkfont
    from config import load_config
    from hud_controller import TopTelemetryHUD
    from hud_controller import game_window_rect
    from hud_controller import get_monitor_by_id
    from activity_hud import ActivityButton
    from region_history_hud import RegionHistory
    from interdiction_watch import AlertGate,piracy_alerts_enabled
    from snare_alert_ui import SnareAlertWindow
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:pass
    class ReadOnlyHistory:
        snapshot={}
        def get_last_visited(self):
            from telemetry_core import timestamp
            sessions=self.snapshot.get('sessions',[])
            last=max(sessions,key=lambda s:timestamp(s.get('joined_at')) or 0,default=None)
            return dict(last,name=last.get('server_name')) if last else None
    class Ribbon(TopTelemetryHUD):
        def __init__(self,master):
            # Initialize presentation only: no second log/history/OCR writer.
            self.master=master;self.cfg=load_config();self.game_monitor=int(self.cfg.get('game_monitor',1))
            self.enabled=True;self.opacity=float(self.cfg.get('top_hud_opacity',.7));self.layout='ribbon';self.scale=1.
            self.position=dict(x=.5,y=0)
            self.server_bar_locked=True
            try:
                preferences=read_shared_json(DATA/'ribbon_position.json')
                self.position.update(preferences.get('hud_position',{}))
                self.server_bar_locked=bool(preferences.get('locked',True))
            except (OSError,ValueError,TypeError):pass
            self.editing=False;self.mining=None;self.rock=None;self.mining_enabled=False
            self._drag_origin=None;self._redraw_job=None;self.compact=bool(self.cfg.get('top_hud_compact',True))
            self.BAR_HEIGHT=24 if self.compact else 28;self._content_width=None;self.state={};self._last_rendered_key=None
            self.bar_win=None;self.bar_canvas=None;self.shard_tracker=ReadOnlyHistory()
            self.font=tkfont.Font(root=master,family='Consolas',size=9,weight='bold');self._init_windows()
        def _place_bar(self):
            super()._place_bar()
            button=getattr(self,'activity_button',None)
            if button:button.follow(self,game_window_rect() or get_monitor_by_id(self.game_monitor))
            history=getattr(self,'region_history',None)
            if history:history.follow(self,game_window_rect() or get_monitor_by_id(self.game_monitor))
        def _save_preferences(self, changes):
            from telemetry_ipc import publish_json
            try:preferences=read_shared_json(DATA/'ribbon_position.json')
            except (OSError,ValueError):preferences={}
            preferences.update(changes);publish_json(DATA/'ribbon_position.json',preferences)
        def _sync_visibility(self):
            # Placement input must not override the player's show/hide setting.
            editing=self.editing;self.editing=False
            try:super()._sync_visibility()
            finally:self.editing=editing
        def close(self):
            if self._redraw_job:self.bar_canvas.after_cancel(self._redraw_job)
            self.bar_win.destroy()
        def render_bar(self):
            if self.state.get('connection_status')=='unavailable':
                self.bar_canvas.delete('all');self.bar_canvas.create_rectangle(0,0,self.bar_width,self.BAR_HEIGHT,fill='#070a0f',outline='#1e293b')
                self.bar_canvas.create_text(12,self.BAR_HEIGHT//2,anchor='w',text='SERVER INFORMATION UNAVAILABLE · waiting for session service',fill='#f59e0b',font=('Consolas',9,'bold'))
                self._last_rendered_key=None;return
            super().render_bar()
    root=tk.Tk();root.withdraw();ribbon=Ribbon(root);gate=AlertGate(started_at);alert=SnareAlertWindow(root,game_window_rect);activity=ActivityButton(root,DATA,args.owner);ribbon.activity_button=activity
    from reputation_notice import ReputationNotice
    reputation_notice=ReputationNotice(root,DATA,game_window_rect)
    def callback_error(kind,value,traceback):
        logging.error('HUD input callback failed',exc_info=(kind,value,traceback))
    root.report_callback_exception=callback_error
    history=RegionHistory(root);ribbon.region_history=history
    def poll():
        if not owner_alive(args.owner):root.destroy();return
        try:
            snapshot=read_shared_json(DATA/'session_state.json',limit=8*1024*1024)
            settings=read_shared_json(DATA/'native_settings.json')
            ribbon.state=hud_state(snapshot,args.owner,time.time())
            ribbon.shard_tracker.snapshot=snapshot;history.snapshot=snapshot
            ribbon.enabled=bool(settings.get('show_hud',True) and settings.get('session_strip',True))
            editable=not ribbon.server_bar_locked
            if ribbon.editing!=editable:ribbon.set_editing(editable)
            ribbon._sync_visibility();ribbon.render_bar()
            try:native=read_shared_json(DATA/'native_status.json')
            except (OSError,ValueError):native={}
            activity.sync(ribbon,native,game_window_rect() or get_monitor_by_id(ribbon.game_monitor))
            history.follow(ribbon,game_window_rect() or get_monitor_by_id(ribbon.game_monitor))
            enabled=piracy_alerts_enabled(settings,bool(game_window_rect()))
            notices=gate.consume(snapshot,args.owner,time.time(),enabled)
            alert.update(notices,ribbon.state.get('session_token'),enabled)
            reputation_notice.poll()
            from telemetry_ipc import publish_json
            publish_json(DATA/'top_hud_status.json',dict(at=time.time(),pid=os.getpid(),owner_pid=args.owner,
                        visible=bool(ribbon._visible),geometry=ribbon._last_geometry,
                        session_token=ribbon.state.get('session_token'),callsign=ribbon.state.get('callsign'),layout='ribbon',
                        draggable=ribbon.editing,server_bar_locked=ribbon.server_bar_locked,position=ribbon.position,region_history_visible=history.visible,region_history_open=history.open,region_color=(getattr(ribbon,'region_hit',None) or {}).get('color'),region_text=(getattr(ribbon,'region_hit',None) or {}).get('text'),region_last_input=getattr(history,'last_input',None),region_transition=getattr(history,'last_transition',None),region_canvas_size=[history.canvas.winfo_width(),history.canvas.winfo_height()],region_geometry=history.geometry,region_popup_geometry=getattr(history,'popup_rect',None),activity_button_visible=activity.visible,activity_button_geometry=activity.geometry,activity_expanded=native.get('activity_expanded',True),snare_watch_enabled=enabled,snare_alerts_shown=alert.shown))
        except (OSError,ValueError,TypeError,KeyError):
            ribbon.state=hud_state({},args.owner,time.time());ribbon.render_bar();alert.update([],None,False)
            logging.exception('Top HUD refresh failed')
        root.after(250,poll)
    try:poll();root.mainloop()
    finally:lock.close()

if __name__=='__main__':main()
