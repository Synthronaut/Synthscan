"""Original top ribbon, fed read-only by the native app's session service."""
import argparse,json,logging,math,os,time
from pathlib import Path
from telemetry_core import SHARD_RE

def server_hud_enabled(settings):
    # show_hud belongs to the pop-out; the server ribbon has its own setting.
    return bool(settings.get('session_strip',True))

def hud_state(snapshot,owner,now):
    stamp=snapshot.get('written_at',0)
    if snapshot.get('owner_pid')!=owner or not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or not 0<=now-stamp<4:
        return dict(connection_status='unavailable',callsign='SESSION SERVICE UNAVAILABLE',session_token=None)
    source=dict(snapshot.get('hud_state') or {})
    full=snapshot.get('full_shard_id','');match=SHARD_RE.fullmatch(full)
    source.update(session_token=snapshot.get('session_token'),full_shard_id=full,
                  shard_id=match.groups()[-1] if match else '--',
                  region_display=snapshot.get('region','--'),shard_name_source=snapshot.get('shard_name_source'),callsign=snapshot.get('game_shard_name') or snapshot.get('shard_name','MAIN MENU'),
                  hop_status=snapshot.get('hop',''),location_display=snapshot.get('location') or '--',
                  connection_status='connected' if snapshot.get('session_token') else ('game_closed' if not snapshot.get('game_pids') else 'main_menu'))
    observation=snapshot.get('shard_observation') or {}
    source['shard_observation']=observation if snapshot.get('session_token') and observation.get('full_shard_id')==full else {}
    for key,ttl in [('client_fps',2),('ping_ms',3)]:
        metadata=(source.get('metric_meta') or {}).get(key) or {}
        age=now-metadata.get('observed_at',0)
        if not -.25<=age<=ttl:source.pop(key,None)
    return source


class RibbonSessionState:
    """Retain labelled identity briefly, never stale live metrics or a join claim."""
    def __init__(self):
        self.last=None

    def update(self,snapshot,owner,now,game_pids=None):
        state=hud_state(snapshot,owner,now)
        if state['connection_status']!='unavailable':
            self.last=dict(snapshot) if state.get('session_token') and SHARD_RE.fullmatch(snapshot.get('full_shard_id','')) else None
            return state
        previous=self.last
        if not previous:return state
        # An owner change, process restart, clock reversal, newer contradictory
        # lifecycle observation or a long outage must not retain a former shard.
        age=now-previous['written_at']
        changed=(isinstance(snapshot.get('written_at'),(int,float)) and snapshot['written_at']>previous['written_at'] and
                 (snapshot.get('session_token')!=previous.get('session_token') or snapshot.get('full_shard_id')!=previous.get('full_shard_id')))
        same_game=bool(game_pids) and set(game_pids)==set(previous.get('game_pids',[]))
        if snapshot.get('owner_pid',owner)!=owner or changed or not same_game or not 0<=age<30:
            self.last=None
            return state
        confirmed=hud_state(previous,owner,previous['written_at'])
        retained={key:confirmed[key] for key in ('callsign','shard_id','full_shard_id','region_raw','region_display','hop_status','shard_observation') if key in confirmed}
        retained.update(connection_status='refreshing',session_token=None,last_known_identity=True,
                        feed_status='UPDATING · LAST KNOWN SHARD',feed_age_seconds=age)
        return retained

def main():
    started_at=time.time()
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,required=True);args=p.parse_args()
    from app_lifecycle import SingleInstance
    from app_lifecycle import game_process_ids
    lock=SingleInstance('native-top-hud')
    if not lock.acquired:return
    from native_control import DATA
    from native_bridge import owner_alive
    from telemetry_ipc import read_shared_json
    logging.basicConfig(filename=DATA/'top_hud.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import ctypes,tkinter as tk,tkinter.font as tkfont
    from config import load_config
    from hud_controller import TopTelemetryHUD
    from hud_controller import game_window_rect
    from hud_controller import get_monitor_by_id
    from activity_hud import ActivityButton,ActivityQuickControls
    from feature_modules import enabled as feature_enabled
    from region_history_hud import RegionHistory
    from interdiction_watch import AlertGate,piracy_alerts_enabled
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
        def _drag_start(self,event):
            from overlay_input import input_blocked
            if not input_blocked(self):super()._drag_start(event)
        def _drag_move(self,event):
            from overlay_input import input_blocked
            if not input_blocked(self):super()._drag_move(event)
        def _drag_end(self,event):
            from overlay_input import input_blocked
            if input_blocked(self):self._drag_origin=None;return
            super()._drag_end(event)
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
                self.bar_canvas.create_text(12,self.BAR_HEIGHT//2,anchor='w',text='SERVER INFORMATION UNAVAILABLE · waiting for session service',fill='#62ccff',font=('Consolas',9,'bold'))
                self._last_rendered_key=None;return
            super().render_bar()
    class SilentVisual:
        shown=0
        def update(self,*args,**kwargs):pass
        def consume(self,*args,**kwargs):return []
    root=tk.Tk();root.withdraw();ribbon=Ribbon(root);gate=AlertGate(started_at);alert=SilentVisual();activity=ActivityButton(root,DATA,args.owner);collapse=ActivityQuickControls(root,DATA,args.owner);ribbon.activity_button=activity
    if feature_enabled('piracy'):
        from snare_alert_ui import SnareAlertWindow
        alert=SnareAlertWindow(root,game_window_rect)
    companion_gate=companion_toast=SilentVisual()
    if feature_enabled('people'):
        from companion_toasts import NoticeGate,CompanionToast
        companion_gate=NoticeGate(started_at);companion_toast=CompanionToast(root,game_window_rect)
    session_view=RibbonSessionState();cached_settings={};last_feed_status=None
    def callback_error(kind,value,traceback):
        logging.error('HUD input callback failed',exc_info=(kind,value,traceback))
    root.report_callback_exception=callback_error
    history=RegionHistory(root);ribbon.region_history=history
    def protected_now():
        from overlay_input import foreground_process_id,protect_game_input
        return protect_game_input(foreground_process_id(),{os.getpid(),args.owner},bool(game_window_rect()))
    ribbon.input_guard=protected_now
    # The region arrow/popup are explicit controls, like HUD +/-. Keep their
    # non-activating click handling available while the ribbon body is passive.
    for control in (history,history.window,history.popup):control.input_guard=lambda:False
    def protect_input():
        from overlay_input import set_passthrough
        protected=protected_now()
        history.input_protected=False
        api=ctypes.windll.user32
        from ctypes import wintypes as w
        api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        bar_hwnd=api.GetParent(ribbon.bar_win.winfo_id()) or ribbon.bar_win.winfo_id()
        set_passthrough(bar_hwnd,protected)
        for hwnd in (history.hwnd,history.popup_hwnd,activity.hwnd,collapse.hwnd):set_passthrough(hwnd,False)
        return protected
    def poll():
        nonlocal last_feed_status
        if not owner_alive(args.owner):root.destroy();return
        protected=protect_input()  # independent of snapshot/JSON parsing failures
        try:
            try:
                path=DATA/'session_ribbon.json'
                snapshot=read_shared_json(path if path.exists() else DATA/'session_state.json',limit=8*1024*1024)
                if not isinstance(snapshot,dict):raise ValueError('Invalid session snapshot')
            except (OSError,ValueError):snapshot={}
            try:cached_settings.update(read_shared_json(DATA/'native_settings.json'))
            except (OSError,ValueError,TypeError):pass
            settings=cached_settings;now=time.time()
            games=None
            if hud_state(snapshot,args.owner,now)['connection_status']=='unavailable':
                try:games=game_process_ids()
                except OSError:games=None
            ribbon.state=session_view.update(snapshot,args.owner,now,games)
            feed_status=ribbon.state.get('connection_status')
            if feed_status!=last_feed_status:
                logging.info('Session ribbon feed: %s',feed_status);last_feed_status=feed_status
            history_snapshot=snapshot
            if ribbon.state.get('last_known_identity'):history_snapshot=dict(session_view.last,session_token=None)
            ribbon.shard_tracker.snapshot=history_snapshot;history.snapshot=history_snapshot
            ribbon.enabled=server_hud_enabled(settings)
            editable=not ribbon.server_bar_locked and not protected
            if ribbon.editing!=editable:ribbon.set_editing(editable)
            ribbon._sync_visibility();ribbon.render_bar()
            try:native=read_shared_json(DATA/'native_status.json')
            except (OSError,ValueError):native={}
            activity.sync(ribbon,native,game_window_rect() or get_monitor_by_id(ribbon.game_monitor))
            collapse.sync(ribbon,native,game_window_rect() or get_monitor_by_id(ribbon.game_monitor))
            history.follow(ribbon,game_window_rect() or get_monitor_by_id(ribbon.game_monitor))
            enabled=feature_enabled('piracy') and piracy_alerts_enabled(settings,bool(game_window_rect()))
            notices=gate.consume(snapshot,args.owner,time.time(),enabled)
            alert.update(notices,ribbon.state.get('session_token'),enabled)
            try:companion_snapshot=read_shared_json(DATA/'companion_alerts.json',limit=65536)
            except (OSError,ValueError):companion_snapshot={}
            companion_enabled=bool(settings.get('show_hud',True) and game_window_rect())
            companion_events=companion_gate.consume(companion_snapshot,args.owner,ribbon.state.get('session_token'),companion_enabled,now)
            companion_toast.update(companion_events,companion_enabled,now,ribbon.state.get('session_token'))
            # The HUD body stays passive; the region dropdown and compact
            # controls accept bounded clicks without activating the app.
            protected=protect_input()
            from telemetry_ipc import publish_json
            publish_json(DATA/'top_hud_status.json',dict(at=time.time(),pid=os.getpid(),owner_pid=args.owner,
                        visible=bool(ribbon._visible),geometry=ribbon._last_geometry,input_protected=protected,
                        session_token=ribbon.state.get('session_token'),callsign=ribbon.state.get('callsign'),layout='ribbon',
                        connection_status=feed_status,last_known_identity=bool(ribbon.state.get('last_known_identity')),feed_age_seconds=ribbon.state.get('feed_age_seconds',0),
                        draggable=ribbon.editing,server_bar_locked=ribbon.server_bar_locked,position=ribbon.position,region_history_visible=history.visible,region_history_open=history.open,region_color=(getattr(ribbon,'region_hit',None) or {}).get('color'),region_text=(getattr(ribbon,'region_hit',None) or {}).get('text'),region_last_input=getattr(history,'last_input',None),region_transition=getattr(history,'last_transition',None),region_canvas_size=[history.canvas.winfo_width(),history.canvas.winfo_height()],region_geometry=history.geometry,region_popup_geometry=getattr(history,'popup_rect',None),activity_button_visible=activity.visible,activity_button_geometry=activity.geometry,collapse_button_visible=collapse.visible,collapse_button_geometry=collapse.geometry,activity_expanded=native.get('activity_expanded',True),snare_watch_enabled=enabled,snare_alerts_shown=alert.shown))
        except (OSError,ValueError,TypeError,KeyError):
            try:games=game_process_ids()
            except OSError:games=None
            ribbon.state=session_view.update({},args.owner,time.time(),games)
            ribbon.render_bar();alert.update([],None,False)
            companion_toast.update([],False)
            logging.exception('Top HUD refresh failed')
        root.after(250,poll)
    try:poll();root.mainloop()
    finally:lock.close()

if __name__=='__main__':main()
