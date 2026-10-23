"""Presentation, expiry, edit-mode input styles and saved layout integration."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import tkinter as tk

from hud_layout import panel_rows, preferences, placed_rect, position_from_point
from hud_panel import paint_panel, panel_size
from hud_controller import TopTelemetryHUD
from radar_db import parse_signature


class HUDPresentationTests(unittest.TestCase):
    def setUp(self):
        self.state=dict(session_token='join-a',callsign='SHARD 020',shard_id='020',region_display='Asia (Hong Kong)',
                        hop_status='RETURN #2',server_name='GAME-8',health=dict(status='UNKNOWN'))
        self.match=parse_signature(12000)
        self.mining=dict(match=self.match,signature=12000,session_token='join-a',observed_at=100)

    def text(self, **kwargs):
        return '\n'.join(r['text'] for r in panel_rows(self.state,self.mining,now=101,**kwargs))

    def test_identity_and_visits_survive_without_numeric_telemetry(self):
        text=self.text()
        for value in ['SHARD 020','Asia (Hong Kong)','GAME-8','RETURN #2']:
            self.assertIn(value,text)
        for value in ['Player ','Server 0','Players','RTT','UNKNOWN','healthy']:
            self.assertNotIn(value,text)

    def test_mining_retains_ambiguity_in_unified_panel(self):
        text=self.text()
        self.assertIn('3 possible matches',text)
        self.assertIn('3x ROC Deposit',text)
        self.assertIn('4x FPS Minable',text)
        self.assertNotIn('100%',text)

    def test_stale_or_previous_join_scan_is_not_displayed(self):
        self.assertFalse(any(r['role']=='section' for r in panel_rows(self.state,self.mining,now=106)))
        self.state['session_token']='join-b'
        self.assertNotIn('Mining scan',self.text())

    def test_future_reading_is_not_accepted(self):
        self.mining['observed_at']=102
        self.assertNotIn('Mining scan',self.text())

    def test_metrics_preserve_zero_values_and_packet_source_label(self):
        self.state.update(client_fps=65,server_fps=0,ping_ms=12.5,shard_pop=500,srv_pop=0,
                          metric_meta=dict(ping_ms=dict(source='game_udp_ping_pong')))
        text=self.text()
        self.assertIn('Net RTT 12.5 ms',text)
        self.assertIn('Server 0.0 FPS',text)
        self.assertIn('Player 65 FPS',text)
        self.assertIn('Server 0',text)

    def test_session_and_mining_visibility_are_independent(self):
        text=self.text(session=False)
        self.assertNotIn('SHARD',text)
        self.assertIn('Mining scan',text)
        self.assertNotIn('Mining scan',self.text(mining_enabled=False))

    def test_manual_lookups_are_labelled(self):
        self.mining['manual']=True
        self.assertIn('Manual lookup',self.text())

    def test_geometry_handles_negative_monitors_and_resolution_changes(self):
        bounds=dict(left=-1920,top=-200,width=1920,height=1080)
        at=placed_rect(bounds,392,180,dict(x=1,y=1))
        self.assertEqual(at,dict(left=-392,top=700,width=392,height=180))
        self.assertEqual(position_from_point(bounds,392,180,at['left'],at['top']),dict(x=1,y=1))
        new=placed_rect(dict(left=0,top=0,width=2560,height=1440),392,180,dict(x=1,y=1))
        self.assertEqual(new['left'],2168)

    def test_geometry_clamps_drag_and_oversized_hud(self):
        bounds=dict(left=100,top=100,width=300,height=200)
        self.assertEqual(position_from_point(bounds,200,100,-5000,5000),dict(x=0,y=1))
        self.assertEqual(placed_rect(bounds,500,400,dict(x=1,y=1)),dict(left=100,top=100,width=300,height=200))

    def test_bad_preferences_cannot_move_hud_offscreen(self):
        prefs=preferences(dict(hud_scale=float('nan'),hud_position=dict(x='wrong',y=-10)))
        self.assertEqual(prefs['scale'],1)
        self.assertEqual(prefs['x'],.5)
        self.assertEqual(prefs['y'],0)


class HUDWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw()
        self.temp=tempfile.TemporaryDirectory()
        self.patches=[]
        def hidden_init(hud):
            hud.bar_win=tk.Toplevel(hud.master);hud.bar_win.withdraw();hud.bar_win.overrideredirect(True)
            hud.bar_canvas=tk.Canvas(hud.bar_win);hud.bar_canvas.pack()
        for target,value in [('hud_controller.load_config',lambda:dict(overlay_enabled=True,hud_layout='panel')),
                             ('hud_controller.TopTelemetryHUD._init_windows',hidden_init),
                             ('hud_controller.TopTelemetryHUD._sync_visibility',lambda hud:hud.bar_win.withdraw()),
                             ('voice.is_star_citizen_running',lambda:False)]:
            p=patch(target,value);p.start();self.patches.append(p)
        self.hud=TopTelemetryHUD(self.root,game_log_path=Path(self.temp.name)/'Game.log',history_path=Path(self.temp.name)/'history.json')
        self.saved=[];self.hud.on_preferences_changed=lambda change:self.saved.append(change)
        self.hud.render_bar()

    def tearDown(self):
        self.root.destroy()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_real_painter_elides_long_text_at_multiple_scales(self):
        rows=[dict(text='Very long server name '*40,role='title'),dict(text='A location '*80,role='muted')]
        for scale in (.75,1,1.75):
            width,height=paint_panel(self.hud.bar_canvas,rows,scale)
            self.root.update_idletasks()
            for item in self.hud.bar_canvas.find_all():
                if self.hud.bar_canvas.type(item)=='text':
                    box=self.hud.bar_canvas.bbox(item)
                    self.assertGreaterEqual(box[0],0)
                    self.assertLess(box[2],width,repr((scale,self.hud.bar_canvas.itemcget(item,'text'),self.hud.bar_canvas.itemcget(item,'font'),box)))
                    self.assertGreaterEqual(box[1],0)
                    self.assertLess(box[3],height)

    def test_preferences_save_through_owner_and_anchor_survives_scaling(self):
        self.hud.set_anchor(1,1)
        self.hud.set_scale(1.5)
        self.hud.set_opacity(.6)
        self.hud.set_layout('ribbon')
        self.assertEqual(self.hud.position,dict(x=1,y=1))
        self.assertIn(dict(hud_scale=1.5),self.saved)
        self.assertIn(dict(top_hud_opacity=.6),self.saved)
        self.assertIn(dict(hud_layout='ribbon'),self.saved)

    def test_drag_works_only_when_explicitly_unlocked(self):
        event=SimpleNamespace(x_root=100,y_root=100)
        self.hud._drag_start(event)
        self.assertIsNone(self.hud._drag_origin)
        self.hud.set_editing(True)
        self.hud._drag_start(event)
        self.assertIsNotNone(self.hud._drag_origin)
        self.hud._drag_end(SimpleNamespace(x_root=250,y_root=200))
        self.assertIsNone(self.hud._drag_origin)
        self.assertIn('hud_position',self.saved[-1])
        self.hud.set_editing(False)
        self.assertFalse(self.hud.editing)

    def test_click_through_style_is_restored_when_locked(self):
        import ctypes
        from ctypes import wintypes
        user=ctypes.windll.user32
        user.GetParent.restype=wintypes.HWND
        hwnd=user.GetParent(self.hud.bar_win.winfo_id()) or self.hud.bar_win.winfo_id()
        self.hud.set_editing(True)
        self.assertFalse(user.GetWindowLongW(hwnd,-20)&0x20)
        self.hud.set_editing(False)
        self.assertTrue(user.GetWindowLongW(hwnd,-20)&0x20)

    def test_actual_editor_builds_and_switches_both_layout_previews(self):
        from hud_studio_ui import HUDStudioPage
        app=SimpleNamespace(top_hud=self.hud,is_scanning=False,toggle_scanning=lambda:None,
                            on_top_hud_toggle=self.hud.set_enabled,set_mining_hud_enabled=self.hud.set_mining_enabled,
                            sync_mining_overlay_visibility=lambda:None)
        page=HUDStudioPage(self.root,app)
        self.root.update_idletasks()
        page.change_scale(1.25)
        page.change_layout('Classic ribbon')
        page.refresh()
        self.assertEqual(self.hud.layout,'ribbon')
        page.change_layout('Compact panel')
        page.refresh()
        self.assertEqual(self.hud.layout,'panel')
        page.destroy()


class HUDRoutingTests(unittest.TestCase):
    def test_queued_scan_cannot_cross_join_or_refresh_its_capture_time(self):
        from main import SynthScanApp
        app=SynthScanApp.__new__(SynthScanApp)
        app.top_hud=SimpleNamespace(state=dict(session_token='new'),layout='panel',update_mining=Mock())
        app._update_gui_match=Mock()
        match=parse_signature(3170)
        with patch('main.time.time',return_value=100):
            app._on_signature_detected_mainthread(match,3170,'old',99)
            app._on_signature_detected_mainthread(match,3170,'new',90)
            app.top_hud.update_mining.assert_not_called()
            app._on_signature_detected_mainthread(match,3170,'new',98)
            app.top_hud.update_mining.assert_called_once_with(match,3170,manual=False,observed_at=98)

    def test_accepted_result_is_delivered_once_to_the_selected_overlay(self):
        from main import SynthScanApp
        app=SynthScanApp.__new__(SynthScanApp)
        app.top_hud=SimpleNamespace(layout='panel',update_mining=Mock())
        app.overlay=SimpleNamespace(show_result=Mock())
        app._update_gui_match=Mock()
        match=parse_signature(12000)
        app._on_signature_detected_mainthread(match,12000)
        app.top_hud.update_mining.assert_called_once_with(match,12000,manual=False)
        app.overlay.show_result.assert_not_called()
        app.top_hud.layout='ribbon'
        app._present_mining_result(match,12000,manual=True)
        app.overlay.show_result.assert_called_once_with(match,12000)


if __name__=='__main__':unittest.main()
