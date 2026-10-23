"""Live native rock observations and explicit player loadouts, without guessed fits."""
import time
import customtkinter as ctk
from mining_loadout import hardware,validate_fit,save_fit

BG,CARD,TEXT,MUTED,GOLD='#181b22','#1e222a','#f1f5f9','#94a3b8','#d99b43'


class MiningSetupPage(ctk.CTkScrollableFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color=BG)
        self.pack(fill='both',expand=True)
        self.app=app
        self.data=hardware()
        self.lasers={l['name']:l for l in self.data['lasers']}
        self.modules={m['name']:m for m in self.data['modules']}
        self.gadgets={g['name']:g for g in self.data['gadgets']}
        self.ships={s['name']:s for s in self.data['ships']}
        self.none='Not fitted'
        self.job=None
        self.label(self,'Mining · rock view & loadout',25)
        self.status=self.label(self,'',12,MUTED)
        ctk.CTkButton(self,text='Start / pause mining scanner',command=self.toggle_scan).pack(anchor='w',padx=14,pady=6)
        self.reading=ctk.CTkFrame(self,fg_color=CARD)
        self.reading.pack(fill='x',padx=14,pady=8)
        self.reading_text=self.label(self.reading,'No settled rock scan yet.',14)
        self.label(self,'Your fitted equipment',20)
        self.label(self,'Configure the heads your crew will use. Readings of rocks do not add material to your inventory. Head advice is an estimate using the configured fit and range.',12,MUTED)
        self.ship=ctk.CTkOptionMenu(self,values=list(self.ships),command=lambda _:self.build_heads())
        self.ship.pack(anchor='w',padx=14,pady=6)
        existing=app.native_fit
        if existing:
            name=next((s['name'] for s in self.data['ships'] if s['id']==existing['ship']),None)
            if name:self.ship.set(name)
        self.heads_frame=ctk.CTkFrame(self,fg_color=CARD)
        self.heads_frame.pack(fill='x',padx=14,pady=8)
        self.heads=[]
        self.build_heads()
        options=ctk.CTkFrame(self,fg_color=CARD)
        options.pack(fill='x',padx=14,pady=8)
        self.actives=ctk.BooleanVar(value=bool(existing and existing.get('actives')))
        ctk.CTkCheckBox(options,text='Assume configured active modules are running',variable=self.actives).pack(anchor='w',padx=14,pady=10)
        self.label(options,'Distance to rock (metres). Zero uses the laser’s full-power range; distance is not read automatically.',12,MUTED)
        self.distance=ctk.CTkEntry(options,width=140)
        self.distance.insert(0,str(existing.get('distance',0) if existing else 0))
        self.distance.pack(anchor='w',padx=14,pady=6)
        self.label(options,'One gadget fitted to the rock',13)
        self.gadget=ctk.CTkOptionMenu(options,values=[self.none]+list(self.gadgets),width=220)
        if existing and existing.get('gadget'):
            name=next((g['name'] for g in self.data['gadgets'] if g['id']==existing['gadget']),None)
            if name:self.gadget.set(name)
        self.gadget.pack(anchor='w',padx=14,pady=6)
        buttons=ctk.CTkFrame(self,fg_color='transparent')
        buttons.pack(fill='x',padx=14,pady=8)
        ctk.CTkButton(buttons,text='Save fitted equipment',command=self.save).pack(side='left',padx=(0,10))
        ctk.CTkButton(buttons,text='Use last detected fit',command=self.use_detected,fg_color='#354155').pack(side='left')
        self.notice=self.label(self,'Detected fits are offered for review. MOLE crew heads remain separately configured.',12,MUTED)
        self.label(self,'Hardware reference · 13 lasers, 29 modules and 6 gadgets. Source credits are in Licenses & data sources.',11,MUTED)
        self.bind('<Destroy>',self.on_destroy,add='+')
        self.refresh()

    def label(self,parent,text,size=13,color=TEXT):
        w=ctk.CTkLabel(parent,text=text,anchor='w',justify='left',font=('Bahnschrift',size),text_color=color,wraplength=650)
        w.pack(fill='x',padx=14,pady=6)
        w.bind('<Configure>',lambda e:w.configure(wraplength=max(150,e.width-4)))
        return w

    def build_heads(self):
        for child in self.heads_frame.winfo_children():child.destroy()
        self.heads=[]
        ship=self.ships[self.ship.get()]
        fit=self.app.native_fit if self.app.native_fit and self.app.native_fit['ship']==ship['id'] else None
        choices=[l['name'] for l in self.data['lasers'] if (l['id']==ship['fixed_laser'] if ship.get('fixed_laser') else l['size']<=ship['size'] and l['id']!='drak_golem_s1')]
        for i in range(ship['heads']):
            h=next((h for n,h in enumerate(fit['heads']) if h.get('slot',n+1)==i+1),{}) if fit else {}
            enabled=ctk.BooleanVar(value=bool(h) or ship['heads']==1)
            ctk.CTkCheckBox(self.heads_frame,text=f'Head {i+1} · crewed / available',variable=enabled).pack(anchor='w',padx=14,pady=8)
            row=ctk.CTkFrame(self.heads_frame,fg_color='transparent')
            row.pack(fill='x',padx=14,pady=4)
            laser=ctk.CTkOptionMenu(row,values=['Choose laser']+choices,width=240)
            name=next((l['name'] for l in self.data['lasers'] if l['id']==h.get('laser')),None)
            if name:laser.set(name)
            elif ship.get('fixed_laser'):laser.set(choices[0])
            laser.pack(side='left',padx=(0,10))
            power=ctk.CTkEntry(row,width=140,placeholder_text='Crafted power %')
            power.insert(0,str(h.get('crafted_power',0)))
            power.pack(side='left')
            self.label(self.heads_frame,'Crafted power is the item’s displayed bonus percent; zero means stock.',11,MUTED)
            mods_row=ctk.CTkFrame(self.heads_frame,fg_color='transparent')
            mods_row.pack(fill='x',padx=14,pady=6)
            mods=[]
            for n in range(3):
                menu=ctk.CTkOptionMenu(mods_row,values=[self.none]+list(self.modules),width=155)
                old=h.get('modules',[])
                if n<len(old):
                    mod=next((m['name'] for m in self.data['modules'] if m['id']==old[n]),None)
                    if mod:menu.set(mod)
                menu.pack(side='left',padx=(0,6));mods.append(menu)
            self.heads.append(dict(enabled=enabled,laser=laser,power=power,modules=mods))

    def collect(self):
        heads=[]
        for i,head in enumerate(self.heads):
            if not head['enabled'].get():continue
            laser=self.lasers.get(head['laser'].get())
            if not laser:raise ValueError('Choose a laser for every available head')
            heads.append(dict(slot=i+1,laser=laser['id'],crafted_power=float(head['power'].get()),
                              modules=[self.modules[m.get()]['id'] for m in head['modules'] if m.get()!=self.none]))
        gadget=self.gadgets.get(self.gadget.get())
        return validate_fit(dict(ship=self.ships[self.ship.get()]['id'],heads=heads,actives=self.actives.get(),
                                 gadget=gadget['id'] if gadget else '',distance=float(self.distance.get())))

    def save(self):
        try:self.app.native_fit=save_fit(self.collect())
        except (OSError,ValueError) as exc:
            self.notice.configure(text=str(exc),text_color=GOLD);return
        self.notice.configure(text='Fitted equipment saved. The next settled rock reading will include head advice.',text_color='#9ed5d2')

    def use_detected(self):
        seen=self.app.native_detected_fit
        token=self.app.top_hud.state.get('session_token')
        if not seen or seen['session_token']!=token or not 0<=time.time()-seen['observed_at']<=30:
            self.notice.configure(text='No recent complete loadout read. Start scanning and show your single-seat mining HUD.',text_color=GOLD);return
        if self.ships[self.ship.get()]['heads']!=1:
            self.notice.configure(text='Configure each MOLE head separately; a single HUD does not show all three crew fits.',text_color=GOLD);return
        h=self.heads[0]
        laser=next((l for l in self.data['lasers'] if l['id']==seen['laser']),None)
        if not laser:return
        h['enabled'].set(True);h['laser'].set(laser['name']);h['power'].delete(0,'end');h['power'].insert(0,'0')
        for i,menu in enumerate(h['modules']):
            m=next((m for m in self.data['modules'] if i<len(seen['modules']) and m['id']==seen['modules'][i]),None)
            menu.set(m['name'] if m else self.none)
        self.notice.configure(text='Detected fit copied for review. Check crafted power, then save.',text_color=GOLD)

    def toggle_scan(self):
        if not self.app.is_scanning:self.app.set_mining_hud_enabled(True)
        self.app.toggle_scanning()

    def refresh(self):
        self.status.configure(text=self.app.native_reader_status)
        seen=self.app.native_rock
        token=self.app.top_hud.state.get('session_token')
        if seen and seen['session_token']==token:
            r=seen['panel']['stats'];age=max(0,time.time()-seen['observed_at'])
            volume=f"{r['scu']:.2f} SCU" if r['scu']>0 else 'volume unread'
            text=f"{r.get('ore') or 'Rock'} · {r['mass']:,.0f} kg · {volume}\nResistance {r['resistance']:g}% · Instability {r['instability']:.2f} · observed {age:.0f}s ago"
            contents=seen['panel'].get('contents',{})
            if contents.get('whole'):
                text+='\n'+'\n'.join(f"{p['percent']:.2f}% {'Inert' if p['inert'] else p['ore']}"+((f" · Q{p['quality']}"+(f" · {r['scu']*p['percent']/100:.3f} SCU in rock" if r['scu']>0 else '')) if not p['inert'] else '') for p in contents['parts'])
            else:text+='\nComposition has not been fully read.'
            advice=seen.get('advice')
            if advice:
                text+='\n\nEstimated head options\n'+'\n'.join(f"Head {h['head']}: {h['laser']} · "+(f"{h['hold_percent']:.0f}% hold" if h['hold_percent'] is not None else 'no power at this range')+(' · minimum throttle too high' if h['overpowered'] else '') for h in advice['heads'])
                text+='\n'+advice['assumptions']
            self.reading_text.configure(text=text,text_color=TEXT if age<=5 else MUTED)
        else:self.reading_text.configure(text='No settled rock scan in this session. Show the scan-results panel while the scanner is running.',text_color=MUTED)
        self.job=self.after(750,self.refresh)

    def on_destroy(self,event):
        if event.widget is self and self.job:self.after_cancel(self.job);self.job=None
