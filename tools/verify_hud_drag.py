"""Exercise our own offscreen ribbon handlers; no game input or desktop capture."""
import argparse,json,os,sys,time,tempfile,ctypes
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    import app_lifecycle,native_control,native_bridge,hud_controller,snare_alert_ui,native_session_hud,activity_hud,region_history_hud
    from refinery_orders import atomic_json
    profile=out/'ribbon_profile';profile.mkdir(exist_ok=True)
    native_control.DATA=profile
    app_lifecycle.SingleInstance=lambda *a:SimpleNamespace(acquired=True,close=lambda:None)
    native_bridge.owner_alive=lambda owner:True
    # Place only our test window outside the desktop, using a synthetic game rect.
    hud_controller.game_window_rect=lambda:dict(left=-12000,top=-12000,width=1920,height=1080)
    class SilentAlert:
        shown=0
        def __init__(self,*args):pass
        def update(self,*args):pass
    snare_alert_ui.SnareAlertWindow=SilentAlert
    settings=dict(show_hud=True,session_strip=True,hud_mode='mining',hud_locked=False)
    atomic_json(profile/'native_settings.json',settings)
    atomic_json(profile/'ribbon_position.json',dict(locked=False))
    atomic_json(profile/'session_state.json',dict(owner_pid=os.getpid(),written_at=time.time(),session_token='fixture',game_pids=[1],shard_name='SYNTHETIC DRAG TEST',full_shard_id='pub_apse2a_12881860_040',region='AUS-SYD (APSE2A)',hud_state=dict(region_raw='apse2a')))
    native=dict(pid=os.getpid(),at=time.time(),activity_expanded=True);atomic_json(profile/'native_status.json',native)
    buttons=[];old_init=activity_hud.ActivityButton.__init__
    def button_init(button,*args):old_init(button,*args);buttons.append(button)
    activity_hud.ActivityButton.__init__=button_init
    histories=[];old_history_init=region_history_hud.RegionHistory.__init__
    def history_init(history,*args):old_history_init(history,*args);histories.append(history)
    region_history_hud.RegionHistory.__init__=history_init
    result={};errors=[];original=hud_controller.TopTelemetryHUD._init_windows
    def init(ribbon):
        original(ribbon)
        def check_drag():
            try:
                assert ribbon.editing
                hwnd=ctypes.windll.user32.GetParent(ribbon.bar_win.winfo_id()) or ribbon.bar_win.winfo_id()
                assert not ctypes.windll.user32.GetWindowLongW(hwnd,-20)&0x20
                before=dict(ribbon.position)
                ribbon._drag_start(SimpleNamespace(x_root=-11500,y_root=-12000))
                ribbon._drag_end(SimpleNamespace(x_root=-11700,y_root=-11800))
                saved=json.loads((profile/'ribbon_position.json').read_text(encoding='utf-8'))
                assert saved['hud_position']==ribbon.position and ribbon.position!=before
                result['ribbon_drag_saved']=True
                import re
                at=re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',ribbon._last_geometry)
                expected=activity_hud.button_position((int(at[3]),int(at[4]),int(at[1]),int(at[2])),hud_controller.game_window_rect())
                assert buttons[0].geometry==expected
                result['activity_button_tracks_drag_immediately']=True
                history=histories[0];assert history.visible
                values=[item for item in ribbon.bar_canvas.find_all() if ribbon.bar_canvas.type(item)=='text' and ribbon.bar_canvas.itemcget(item,'text')=='AUS-SYD (APSE2A)']
                assert len(values)==1 and ribbon.bar_canvas.itemcget(values[0],'fill')=='#eab308'
                assert ribbon.region_hit['text']=='▾' and ribbon.region_hit['label']==''
                result['original_region_color_preserved_without_duplicate_label']=True
                assert history.geometry[0]==int(at[3])+ribbon.region_hit['left']
                result['region_history_tracks_drag_immediately']=True
                import ctypes.wintypes as wt
                api=ctypes.windll.user32
                api.SendMessageW.argtypes=[wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM];api.SendMessageW.restype=ctypes.c_ssize_t
                assert api.SendMessageW(history.hwnd,0x21,0,0)==3
                assert api.SendMessageW(history.popup_hwnd,0x21,0,0)==3
                result['first_click_not_consumed_or_activating']=True
                position=dict(ribbon.position)
                hx,hy,hw,hh=history.geometry
                # Deliberately disagree with native screen coordinates: input
                # must use local widget coordinates under display scaling.
                history.canvas.event_generate('<ButtonPress-1>',x=hw//2,y=hh//2,rootx=0,rooty=0)
                history.canvas.event_generate('<ButtonRelease-1>',x=hw//2,y=hh//2,rootx=0,rooty=0)
                assert history.open and ribbon.position==position and ribbon._drag_origin is None
                result['region_click_opens_without_dragging']=True
                history.toggle_lock();assert ribbon.server_bar_locked and not ribbon.editing
                assert json.loads((profile/'ribbon_position.json').read_text())['locked']
                result['independent_server_lock_persisted']=True
                button=buttons[0];assert button.visible
                button.press(SimpleNamespace());button.release(SimpleNamespace(x=10,y=10))
                request=json.loads((profile/'activity_hud_command.json').read_text(encoding='utf-8'))
                assert request['owner_pid']==os.getpid() and not request['expanded']
                result['activity_collapse_requested']=True
                native.update(at=time.time(),activity_expanded=False,activity_command_id=request['id']);atomic_json(profile/'native_status.json',native)
                settings['hud_locked']=True;atomic_json(profile/'native_settings.json',settings)
                ribbon.master.after(450,check_lock)
            except Exception as exc:errors.append(repr(exc));ribbon.master.destroy()
        def check_lock():
            try:
                assert not ribbon.editing
                hwnd=ctypes.windll.user32.GetParent(ribbon.bar_win.winfo_id()) or ribbon.bar_win.winfo_id()
                assert ctypes.windll.user32.GetWindowLongW(hwnd,-20)&0x20
                result['ribbon_locked_clickthrough']=True
                button=buttons[0];assert not ctypes.windll.user32.GetWindowLongW(button.hwnd,-20)&0x20
                assert not button.status['activity_expanded'] and button.pending is None
                button.press(SimpleNamespace());button.release(SimpleNamespace(x=10,y=10))
                request=json.loads((profile/'activity_hud_command.json').read_text(encoding='utf-8'))
                assert request['expanded']
                result['activity_button_works_while_locked']=True
                history=histories[0];assert history.visible
                assert not ctypes.windll.user32.GetWindowLongW(history.hwnd,-20)&0x20
                history.toggle();assert history.open
                # A click must survive ordinary telemetry-driven ribbon resizing.
                # Check native placement after Tk has processed deferred geometry.
                import ctypes.wintypes as wt
                saved_position=dict(ribbon.position)
                ribbon.position['x']=max(0,ribbon.position['x']-.02);ribbon._place_bar()
                ribbon.master.update_idletasks();assert history.open
                rect=wt.RECT();ctypes.windll.user32.GetWindowRect(history.popup_hwnd,ctypes.byref(rect))
                assert (rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top)==history.popup_rect
                result['region_dropdown_survives_ribbon_updates']=True
                ribbon.position=saved_position;ribbon._place_bar();assert history.open
                popup_style=ctypes.windll.user32.GetWindowLongW(history.popup_hwnd,-20)
                assert popup_style&0x8 and popup_style&0x08000000
                api=ctypes.windll.user32
                color=wt.DWORD();alpha=wt.BYTE();flags=wt.DWORD()
                api.GetLayeredWindowAttributes.argtypes=[wt.HWND,ctypes.POINTER(wt.DWORD),ctypes.POINTER(wt.BYTE),ctypes.POINTER(wt.DWORD)]
                assert api.GetLayeredWindowAttributes(history.popup_hwnd,ctypes.byref(color),ctypes.byref(alpha),ctypes.byref(flags))
                assert flags.value&2 and alpha.value==255
                result['popup_layered_opacity_initialized']=True
                result['region_dropdown_locked_topmost_noactivate']=True
                history.hide_popup();assert not history.open
                result['region_dropdown_collapses']=True
                native.update(at=time.time(),activity_expanded=True,activity_command_id=request['id']);atomic_json(profile/'native_status.json',native)
                history.toggle_lock();assert not ribbon.server_bar_locked
                settings.update(hud_locked=False,show_hud=False);atomic_json(profile/'native_settings.json',settings)
                ribbon.master.after(450,check_hidden)
            except Exception as exc:errors.append(repr(exc));ribbon.master.destroy()
        def check_hidden():
            try:
                assert ribbon.editing and not ribbon._visible
                result['hidden_while_unlocked']=True
                assert not buttons[0].visible
                result['activity_button_follows_visibility']=True
                assert not histories[0].visible and not histories[0].open
                result['region_history_follows_visibility']=True
            except Exception as exc:errors.append(repr(exc))
            finally:ribbon.master.destroy()
        ribbon.master.after(800,check_drag)
    hud_controller.TopTelemetryHUD._init_windows=init
    sys.argv=['native_session_hud','--owner',str(os.getpid())]
    native_session_hud.main()
    assert not errors,errors
    assert len(result)==17,result
    (out/'ribbon_drag_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
