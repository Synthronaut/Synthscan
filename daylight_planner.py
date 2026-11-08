"""Destination-first daylight planning. Opened explicitly; never controls the game."""
from branding import window_icon
from datetime import datetime
import logging
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from daylight import Body, Site, forecast, vector
import daylight_catalogue as catalogue
from refinery_orders import atomic_json


def local_stamp(stamp):
    return datetime.fromtimestamp(stamp).astimezone().strftime('%a %d %b · %H:%M:%S %Z')


def duration(seconds):
    minutes = max(0, round(seconds/60))
    return f'{minutes//60}h {minutes%60:02d}m' if minutes >= 60 else f'{minutes}m'


def arrival_time(mode, minutes, custom, now=None):
    now = time.time() if now is None else now
    if mode == 'Now':
        return now
    if mode == 'In minutes':
        value = float(minutes)
        if not 0 <= value <= 7*24*60:
            raise ValueError('Arrival offset must be from 0 to 10,080 real minutes')
        return now+value*60
    if mode != 'Local date/time':
        raise ValueError('Choose an arrival mode')
    try:
        # Local Windows timezone, same convention as the visible format hint.
        return datetime.strptime(custom.strip(), '%Y-%m-%d %H:%M').timestamp()
    except ValueError:
        raise ValueError('Use local date/time YYYY-MM-DD HH:MM') from None


class DaylightPlanner:
    def __init__(self, root, directory):
        self.root = root
        self.directory = Path(directory)
        self.data = catalogue.load(directory)
        self.build = catalogue.build_identity()
        self.events = queue.Queue()
        self.fetching = False
        self.last_fetch = 0
        self.last_build = time.monotonic()
        self.row = None
        self.result = None
        try:
            self.saved = catalogue.read_json(self.directory/'daylight_preferences.json')
        except (OSError, ValueError):
            self.saved = {}
        if not isinstance(self.saved, dict):
            self.saved = {}
        root.title('SynthScan · Day/Night Forecast')
        root.configure(bg='#14171d')
        root.minsize(720, 640)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Day.TFrame', background='#14171d')
        style.configure('Day.TLabel', background='#14171d', foreground='#e9edf1', font=('Segoe UI', 11))
        style.configure('Muted.Day.TLabel', foreground='#95a0ad', font=('Segoe UI', 10))
        style.configure('Title.Day.TLabel', font=('Segoe UI', 23, 'bold'))
        style.configure('Metric.Day.TLabel', font=('Segoe UI', 18))
        style.configure('Day.TButton', background='#252a33', foreground='#e9edf1', padding=(10, 7))
        style.map('Day.TButton', background=[('active', '#38414d')])
        body = ttk.Frame(root, padding=24, style='Day.TFrame')
        body.grid(sticky='nsew');root.columnconfigure(0, weight=1);root.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text='Day/Night Forecast', style='Title.Day.TLabel').grid(row=0, sticky='w')
        ttk.Label(body, text='Pick your destination. Plan for the light when you arrive.', style='Muted.Day.TLabel').grid(row=1, sticky='w', pady=(3, 18))
        choices = ttk.Frame(body, style='Day.TFrame');choices.grid(row=2, sticky='ew')
        self.system = tk.StringVar(root)
        self.body = tk.StringVar(root)
        self.site = tk.StringVar(root)
        self.combos = []
        for index, (label, var, width) in enumerate([('System',self.system,12),('Planet / moon',self.body,18),('Destination · type to search',self.site,35)]):
            choices.columnconfigure(index, weight=1 if index == 2 else 0)
            ttk.Label(choices, text=label, style='Muted.Day.TLabel').grid(row=0, column=index, sticky='w')
            combo = ttk.Combobox(choices, textvariable=var, width=width, state='normal' if index == 2 else 'readonly', font=('Segoe UI',11))
            combo.grid(row=1, column=index, sticky='ew', padx=(0,8 if index < 2 else 0), pady=(5,0))
            self.combos.append(combo)
        self.combos[0].bind('<<ComboboxSelected>>', lambda e: self.fill_bodies())
        self.combos[1].bind('<<ComboboxSelected>>', lambda e: self.fill_sites())
        self.combos[2].bind('<<ComboboxSelected>>', lambda e: self.calculate())
        self.combos[2].bind('<KeyRelease>', self.filter_sites)
        self.combos[2].bind('<Return>', lambda e: self.calculate())
        arrive = ttk.Frame(body, style='Day.TFrame');arrive.grid(row=3, sticky='ew', pady=(18,16))
        ttk.Label(arrive, text='Arrival', style='Day.TLabel').grid(row=0,column=0,padx=(0,10))
        self.mode = tk.StringVar(root, 'Now');self.minutes = tk.StringVar(root, '15')
        self.custom = tk.StringVar(root, datetime.now().strftime('%Y-%m-%d %H:%M'))
        mode = ttk.Combobox(arrive, textvariable=self.mode, values=('Now','In minutes','Local date/time'), state='readonly', width=16)
        mode.grid(row=0,column=1);mode.bind('<<ComboboxSelected>>', lambda e: self.arrival_controls())
        self.minute_entry = ttk.Entry(arrive, textvariable=self.minutes, width=8)
        self.custom_entry = ttk.Entry(arrive, textvariable=self.custom, width=20)
        for entry in (self.minute_entry, self.custom_entry):
            entry.bind('<Return>', lambda e: self.calculate())
        ttk.Button(arrive, text='Forecast', command=self.calculate, style='Day.TButton').grid(row=0,column=3,padx=(10,0))
        self.state = ttk.Label(body, style='Metric.Day.TLabel');self.state.grid(row=4, sticky='w')
        self.arrival_label = ttk.Label(body, style='Muted.Day.TLabel');self.arrival_label.grid(row=5,sticky='w',pady=(4,12))
        self.sunrise = ttk.Label(body, style='Day.TLabel');self.sunrise.grid(row=6,sticky='w',pady=3)
        self.sunset = ttk.Label(body, style='Day.TLabel');self.sunset.grid(row=7,sticky='w',pady=3)
        self.timeline = tk.Canvas(body, height=52, bg='#14171d', highlightthickness=0)
        self.timeline.grid(row=8, sticky='ew', pady=(16,3))
        self.timeline.bind('<Configure>', lambda e: self.draw_timeline())
        ttk.Label(body,text='GOLD  daylight    /    SLATE  night   ·   real time from arrival',style='Muted.Day.TLabel').grid(row=9,sticky='w')
        ttk.Label(body,text='Upcoming daylight windows',style='Day.TLabel').grid(row=10,sticky='w',pady=(17,6))
        self.windows = ttk.Label(body,style='Muted.Day.TLabel',justify='left');self.windows.grid(row=11,sticky='w')
        self.quality = ttk.Label(body,style='Muted.Day.TLabel',wraplength=680);self.quality.grid(row=12,sticky='w',pady=(18,4))
        self.note = ttk.Label(body,style='Muted.Day.TLabel',wraplength=680);self.note.grid(row=13,sticky='w')
        actions = ttk.Frame(body,style='Day.TFrame');actions.grid(row=14,sticky='ew',pady=(18,0))
        ttk.Button(actions,text='Copy forecast',command=self.copy,style='Day.TButton').grid(row=0,column=0,padx=(0,8))
        ttk.Button(actions,text='Record sunrise / sunset',command=self.observe,style='Day.TButton').grid(row=0,column=1,padx=(0,8))
        ttk.Button(actions,text='Refresh data',command=self.refresh,style='Day.TButton').grid(row=0,column=2)
        self.sync = ttk.Label(body,style='Muted.Day.TLabel');self.sync.grid(row=15,sticky='w',pady=(10,0))
        self.combos[0]['values'] = sorted({s['system'] for s in self.data['sites']})
        self.system.set(self.saved.get('system','Stanton'))
        if self.system.get() not in self.combos[0]['values']:
            self.system.set(self.combos[0]['values'][0])
        self.fill_bodies(initial=True)
        self.arrival_controls();self.refresh();root.after(500,self.poll)

    def fill_bodies(self, initial=False):
        values = sorted({s['body'] for s in self.data['sites'] if s['system'] == self.system.get()})
        self.combos[1]['values'] = values
        preferred = self.saved.get('body','Crusader') if initial else self.body.get()
        self.body.set(preferred if preferred in values else values[0])
        self.fill_sites(initial=initial)

    def fill_sites(self, initial=False):
        values = sorted(s['name'] for s in self.data['sites'] if s['system'] == self.system.get() and s['body'] == self.body.get())
        self.combos[2]['values'] = values
        preferred = self.saved.get('site','Orison') if initial else self.site.get()
        self.site.set(preferred if preferred in values else values[0])
        self.calculate()

    def filter_sites(self, event):
        if event.keysym in ('Return','Up','Down','Escape'):
            return
        query = self.site.get().casefold()
        self.combos[2]['values'] = sorted(s['name'] for s in self.data['sites'] if s['system'] == self.system.get() and s['body'] == self.body.get() and query in s['name'].casefold())
        self.row = self.result = None
        self.state.configure(text='Choose a matching destination')
        self.arrival_label.configure(text='');self.quality.configure(text='')
        self.sunrise.configure(text='');self.sunset.configure(text='');self.windows.configure(text='')
        self.note.configure(text='Type part of a name, then choose it from the dropdown.')
        self.timeline.delete('all')

    def arrival_controls(self):
        self.minute_entry.grid_remove();self.custom_entry.grid_remove()
        if self.mode.get() == 'In minutes':self.minute_entry.grid(row=0,column=2,padx=(8,0))
        if self.mode.get() == 'Local date/time':self.custom_entry.grid(row=0,column=2,padx=(8,0))
        self.calculate()

    def calculate(self):
        try:
            row = next((s for s in self.data['sites'] if s['system'] == self.system.get() and s['body'] == self.body.get() and s['name'] == self.site.get()),None)
            if not row:raise ValueError('Choose a destination from the list')
            model = next(b for b in self.data['bodies'] if b['name'] == row['body'])
            body = Body.from_record(model);site = Site(row['name'],tuple(vector(row['coordinates_km'])))
            at = arrival_time(self.mode.get(),self.minutes.get(),self.custom.get())
            phase, quality = catalogue.calibration(self.directory,self.data,row['body'],self.build)
            result = forecast(body,site,at,phase)
            self.row,self.result = row,result
            label = 'DAYLIGHT' if result['daylight'] else 'NIGHT'
            if result['continuous']:label += ' · no crossing this rotation'
            self.state.configure(text=label+' on arrival',foreground='#8edcff' if result['daylight'] else '#b5c7e2')
            self.arrival_label.configure(text=local_stamp(at)+' · estimated')
            for key,widget,title in [('sunrise',self.sunrise,'Sunrise'),('sunset',self.sunset,'Sunset')]:
                event = result[key]
                widget.configure(text=title+'   '+(local_stamp(event)+'   ·   in '+duration(event-at) if event else 'No crossing in this rotation'))
            self.windows.configure(text='\n'.join(local_stamp(start)+' → '+datetime.fromtimestamp(end).strftime('%H:%M:%S')+'   ('+duration(end-start)+')' for start,end in result['windows'][:3]) or ('Continuous daylight at this destination' if result['daylight'] else 'No daylight window in this rotation'))
            self.quality.configure(text=quality)
            self.note.configure(text=row.get('note','Geometric horizon estimate. Local terrain, buildings, clouds and eclipses can change when sunlight is visible.'))
            preferences = dict(system=row['system'],body=row['body'],site=row['name'])
            if preferences != self.saved:
                atomic_json(self.directory/'daylight_preferences.json',preferences)
                self.saved = preferences
            self.draw_timeline()
        except (ValueError,TypeError,OSError,StopIteration) as exc:
            self.result = None
            self.state.configure(text=str(exc),foreground='#8edcff')
            self.sunrise.configure(text='');self.sunset.configure(text='');self.windows.configure(text='')
            self.timeline.delete('all')

    def draw_timeline(self):
        self.timeline.delete('all')
        if not self.result:return
        result = self.result;start = result['at'];span = result['period_seconds']*2 or 86400
        width = max(200,self.timeline.winfo_width());end = start+span
        self.timeline.create_rectangle(0,7,width,29,fill='#2c3a4c',outline='')
        windows = [(start,end)] if result['continuous']=='daylight' else result['windows']
        for left,right in windows:
            left,right = max(start,left),min(end,right)
            if right > left:self.timeline.create_rectangle((left-start)/span*width,7,(right-start)/span*width,29,fill='#397da8',outline='')
        for fraction in (0,.25,.5,.75,1):
            x = fraction*width
            self.timeline.create_line(x,30,x,34,fill='#95a0ad')
            self.timeline.create_text(max(24,min(width-24,x)),45,text=datetime.fromtimestamp(start+span*fraction).strftime('%H:%M'),fill='#95a0ad',font=('Segoe UI',9))

    def refresh(self):
        if self.fetching:return
        self.fetching = True;self.last_fetch = time.monotonic()
        self.sync.configure(text='Checking the public catalogue…')
        def worker():
            try:self.events.put(('data',catalogue.refresh(self.directory)))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind,value = self.events.get_nowait();self.fetching = False
            if kind == 'data':
                self.data = value
                self.combos[0]['values'] = sorted({s['system'] for s in self.data['sites']})
                if self.system.get() not in self.combos[0]['values']:self.system.set(self.combos[0]['values'][0])
                self.fill_bodies()
                self.sync.configure(text='Public catalogue checked '+datetime.now().strftime('%H:%M')+' · timing calibration is separate')
            else:
                self.sync.configure(text='Offline catalogue in use · automatic refresh will retry')
                logging.info('Daylight catalogue refresh failed: %s',value)
        if time.monotonic()-self.last_build > 60:
            self.build = catalogue.build_identity();self.last_build = time.monotonic()
        if not self.fetching and time.monotonic()-self.last_fetch > 6*3600:self.refresh()
        if self.result:self.calculate()
        self.root.after(5000,self.poll)

    def copy(self):
        if not self.result:return
        text = f"{self.row['system']} / {self.row['body']} / {self.row['name']}\n"+'\n'.join(widget.cget('text') for widget in (self.state,self.arrival_label,self.sunrise,self.sunset,self.quality))
        self.root.clipboard_clear();self.root.clipboard_append(text)
        self.sync.configure(text='Forecast copied. Includes estimate/calibration status.')

    def observe(self):
        if not self.row:return
        selected, source, build = dict(self.row), self.data, self.build
        dialog = tk.Toplevel(self.root);dialog.title('Record observed horizon crossing');dialog.resizable(False,False)
        frame = ttk.Frame(dialog,padding=20,style='Day.TFrame');frame.grid()
        ttk.Label(frame,text=selected['name']+'\nRecord an unobstructed sunrise/sunset here to adjust this body clock.',style='Day.TLabel').grid(row=0,columnspan=2,sticky='w')
        kind = tk.StringVar(dialog,'sunrise');stamp = tk.StringVar(dialog,datetime.now().strftime('%Y-%m-%d %H:%M'))
        ttk.Combobox(frame,textvariable=kind,values=('sunrise','sunset'),state='readonly',width=12).grid(row=1,column=0,pady=15)
        ttk.Entry(frame,textvariable=stamp,width=24).grid(row=1,column=1,padx=10)
        ttk.Label(frame,text='Local time: YYYY-MM-DD HH:MM · expires in 7 days or at a build/model change',style='Muted.Day.TLabel').grid(row=2,columnspan=2)
        def save():
            try:
                at = arrival_time('Local date/time','',stamp.get())
                if not 0 <= time.time()-at <= 7*86400:raise ValueError('Choose an observation from the last seven days')
                if source['signature'] != self.data['signature'] or build != catalogue.build_identity():
                    raise ValueError('Game build or catalogue changed; reopen the observation dialog')
                catalogue.save_observation(self.directory,source,selected,build,at,kind.get())
                dialog.destroy();self.calculate()
            except (OSError,ValueError,KeyError) as exc:messagebox.showerror('Observation not saved',str(exc),parent=dialog)
        ttk.Button(frame,text='Save local observation',command=save,style='Day.TButton').grid(row=3,columnspan=2,pady=(15,0))


def main():
    from app_lifecycle import SingleInstance,Signal,send_signal
    from native_control import DATA
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--embedded',action='store_true');parser.add_argument('--owner',type=int)
    args=parser.parse_args()
    if args.embedded and not args.owner:parser.error('Embedded pages require a native owner')
    name='daylight-planner'+(f'-embedded-{args.owner}' if args.embedded else '')
    lock = SingleInstance(name)
    if not lock.acquired:send_signal(name+'-show');return
    show = Signal(name+'-show')
    root = tk.Tk();window_icon(root);root.withdraw()
    try:
        DaylightPlanner(root,DATA)
        embedded=None
        if args.embedded:
            from embedded_window import EmbeddedWindow
            embedded=EmbeddedWindow(root,DATA,args.owner)
        def poll_show():
            if show.wait(0):
                if embedded:embedded.show()
                else:root.deiconify();root.lift()
            root.after(250,poll_show)
        poll_show()
        if not embedded:root.deiconify()
        root.mainloop()
    except Exception:
        logging.exception('Day/Night Forecast failed')
        if not args.embedded:messagebox.showerror('Day/Night Forecast','Unable to open daylight data. No game files were changed.',parent=root)
        root.destroy()
    finally:show.close();lock.close()


if __name__ == '__main__':main()
