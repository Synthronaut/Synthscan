"""One place to configure, preview and unlock SynthScan's in-game HUD."""
import tkinter as tk
import customtkinter as ctk
from types import SimpleNamespace
from hud_panel import paint_panel, panel_size

BG, CARD, TEXT, MUTED = '#181b22', '#1e222a', '#f1f5f9', '#94a3b8'


class HUDStudioPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent,fg_color=BG)
        self.pack(fill='both',expand=True)
        self.app,self.hud = app,app.top_hud
        self._refresh_job = None
        self.label(self,'Your HUD',26)
        self.label(self,'Keep the session details you like. Bring mining results into the same movable panel.',14,MUTED)
        controls = ctk.CTkFrame(self,fg_color=CARD)
        controls.pack(fill='x',padx=14,pady=8)
        row = ctk.CTkFrame(controls,fg_color='transparent')
        row.pack(fill='x',padx=14,pady=14)
        self.layout = ctk.CTkOptionMenu(row,values=['Compact panel','Classic ribbon'],width=160,command=self.change_layout)
        self.layout.set('Compact panel' if self.hud.layout=='panel' else 'Classic ribbon')
        self.layout.pack(side='left',padx=(0,12))
        self.edit = ctk.CTkButton(row,text='Edit position',width=130,command=self.toggle_edit)
        self.edit.pack(side='left')
        ctk.CTkButton(row,text='Lock HUD',width=100,fg_color='#354155',command=lambda:self.hud.set_editing(False)).pack(side='left',padx=8)
        self.label(controls,'Edit position makes the HUD draggable. Right-click the HUD or press Lock HUD here to return to click-through play.',12,MUTED)
        self.session = ctk.BooleanVar(value=self.hud.enabled)
        self.mining = ctk.BooleanVar(value=self.hud.mining_enabled)
        ctk.CTkCheckBox(controls,text='Server, region & visit history',variable=self.session,
                        command=lambda:app.on_top_hud_toggle(self.session.get())).pack(anchor='w',padx=14,pady=8)
        ctk.CTkCheckBox(controls,text='Mining scan results',variable=self.mining,command=self.change_mining).pack(anchor='w',padx=14,pady=8)
        self.scanner = ctk.CTkButton(controls,text='Start mining scanner',command=self.toggle_scanner,fg_color='#354155')
        self.scanner.pack(anchor='w',padx=14,pady=6)
        ctk.CTkButton(controls,text='Rock view & fitted equipment →',command=lambda:app.switch_page('radar'),fg_color='#354155').pack(anchor='w',padx=14,pady=6)
        self.label(controls,'Size · compact panel',13)
        self.scale = ctk.CTkSlider(controls,from_=.75,to=1.75,number_of_steps=20,command=self.change_scale)
        self.scale.set(self.hud.scale)
        self.scale.pack(fill='x',padx=14,pady=6)
        self.label(controls,'Opacity',13)
        opacity=ctk.CTkSlider(controls,from_=.25,to=1,number_of_steps=30,command=self.hud.set_opacity)
        opacity.set(self.hud.opacity)
        opacity.pack(fill='x',padx=14,pady=6)
        presets=ctk.CTkFrame(controls,fg_color='transparent')
        presets.pack(fill='x',padx=14,pady=12)
        for name,x,y in [('Top left',0,0),('Top center',.5,0),('Top right',1,0),('Bottom right',1,1)]:
            ctk.CTkButton(presets,text=name,width=112,fg_color='#354155',command=lambda x=x,y=y:self.hud.set_anchor(x,y)).pack(side='left',padx=(0,7))
        self.label(self,'Preview · current readings',18)
        self.label(self,'Unavailable measurements are omitted. The preview below does not add sample readings to your live HUD.',12,MUTED)
        self.preview=tk.Canvas(self,bg='#0c1016',highlightthickness=0)
        self.preview.pack(anchor='w',padx=14,pady=8)
        self.preview_scroll=ctk.CTkScrollbar(self,orientation='horizontal',command=self.preview.xview)
        self.preview.configure(xscrollcommand=self.preview_scroll.set)
        self.sources=self.label(self,'',12,MUTED)
        self.label(self,'Server FPS and population still require a working source. This layout uses the existing log, packet-timing and frame sources; it does not make those missing measurements available.',12,MUTED)
        self.bind('<Destroy>',self.on_destroy,add='+')
        self.refresh()

    def label(self,parent,text,size=13,color=TEXT):
        widget=ctk.CTkLabel(parent,text=text,anchor='w',justify='left',font=('Bahnschrift',size),text_color=color,wraplength=680)
        widget.pack(fill='x',padx=14,pady=6)
        widget.bind('<Configure>',lambda e:widget.configure(wraplength=max(150,e.width-4)))
        return widget

    def change_layout(self,value):
        self.hud.set_layout('panel' if value=='Compact panel' else 'ribbon')
        self.app.sync_mining_overlay_visibility()
        self.scale.configure(state='normal' if self.hud.layout=='panel' else 'disabled')

    def change_scale(self,value):
        self.hud.set_scale(value)

    def change_mining(self):
        self.app.set_mining_hud_enabled(self.mining.get())

    def toggle_scanner(self):
        if not self.app.is_scanning:self.app.set_mining_hud_enabled(True)
        self.app.toggle_scanning()

    def toggle_edit(self):
        self.hud.set_editing(not self.hud.editing)

    def refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job=None
        self.edit.configure(text='Editing · drag HUD' if self.hud.editing else 'Edit position')
        self.session.set(self.hud.enabled)
        self.mining.set(self.hud.mining_enabled)
        self.scanner.configure(text='Pause mining scanner' if self.app.is_scanning else 'Start mining scanner')
        self.scale.configure(state='normal' if self.hud.layout=='panel' else 'disabled')
        rows=self.hud.presentation_rows()
        if self.hud.layout=='panel':
            width,height=panel_size(rows,self.hud.scale)
            self.preview.configure(width=width,height=height,scrollregion=(0,0,width,height))
            paint_panel(self.preview,rows,self.hud.scale)
            self.preview_scroll.pack_forget()
        else:
            from hud_appearance import render_original_bar
            height=24 if self.hud.compact else 28
            adapter=SimpleNamespace(state=self.hud.state,bar_canvas=self.preview,bar_width=1680,BAR_HEIGHT=height,
                                    compact=self.hud.compact,shard_tracker=self.hud.shard_tracker)
            render_original_bar(adapter)
            self.preview.configure(width=700,height=height,scrollregion=(0,0,max(700,adapter._content_width),height))
            self.preview_scroll.pack(fill='x',padx=14,pady=4,before=self.sources)
        names = {'game_udp_ping_pong':'Game packet timing','presentmon_application_presents':'Player frame timing',
                 'displayinfo_capture':'Visible game telemetry','game_log':'Game log'}
        fresh = {meta['source'] for meta in self.hud.state.get('metric_meta',{}).values() if meta.get('status')=='observed'}
        self.sources.configure(text='Sources · '+(' · '.join(sorted({names.get(source,'Game telemetry') for source in fresh})) or 'Game log; no fresh numeric measurements'))
        self._refresh_job=self.after(750,self.refresh)

    def on_destroy(self,event):
        if event.widget is self and self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job=None
