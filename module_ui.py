"""Simple feature checklist. Installs only signed release packages."""
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from feature_modules import FEATURES, DEFAULTS, NOTICES, installed, resolve, modular
from installation import ROOT, PROFILE, INSTALL_ROOT


def start_agent():
    from app_updates import prepare_agent
    agent=prepare_agent(ROOT,PROFILE)
    subprocess.Popen([str(agent/'runtime/pythonw.exe'),'-I','-B',str(agent/'update_agent.py'),
        '--root',str(INSTALL_ROOT),'--current',str(ROOT),'--profile',str(PROFILE)],cwd=agent,
        creationflags=0x08000000|0x01000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def main(first_run=False):
    from app_lifecycle import SingleInstance
    lock=SingleInstance('module-manager')
    if not lock.acquired:return
    window=tk.Tk()
    from branding import window_icon
    window_icon(window)
    window.title('SynthScan — Feature modules')
    from setup_viewport import size
    size(window,850,810)
    style=ttk.Style(window);style.theme_use('clam');window.configure(bg='#10151d')
    style.configure('.',background='#10151d',foreground='#e8eef5',font=('Segoe UI',10))
    style.configure('TButton',background='#243448',padding=(14,8));style.map('TButton',background=[('active','#344c66')])
    style.configure('TCheckbutton',padding=(4,5));style.map('TCheckbutton',background=[('active','#1b2939')])
    outer=ttk.Frame(window,padding=24);outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Make SynthScan yours',font=('Segoe UI',22,'bold')).pack(anchor='w')
    ttk.Label(outer,text='One app. Choose the features you want. Your saved records stay on this PC.',wraplength=760).pack(anchor='w',pady=(8,16))
    ttk.Label(outer,text='Core, verified updates and recovery are always installed.',foreground='#9fb3c9').pack(anchor='w')
    canvas=tk.Canvas(outer,bg='#10151d',highlightthickness=0,bd=0);bar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y',pady=(12,78));canvas.pack(fill='both',expand=True,pady=(12,8))
    content=ttk.Frame(canvas);handle=canvas.create_window((0,0),window=content,anchor='nw')
    content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(handle,width=e.width))
    def wheel(event):canvas.yview_scroll(-int(event.delta/120),'units');return 'break'
    def bind_wheel(widget):
        widget.bind('<MouseWheel>',wheel)
        for child in widget.winfo_children():bind_wheel(child)
    chosen=set(DEFAULTS) if first_run else installed()
    if first_run:
        from app_updates import load
        saved=load(PROFILE/'module_selection.json')
        if saved.get('schema')==1:chosen=set(resolve(saved.get('modules',[])))
    values={name:tk.BooleanVar(value=name in chosen) for name in FEATURES}
    def dependencies(name):
        if values[name].get():
            for required in FEATURES[name][1]:values[required].set(True)
        elif name=='mining_tools':values['mining_recognition'].set(False)
    for name,(label,requires,notices,detail) in FEATURES.items():
        card=ttk.Frame(content,padding=(8,4));card.pack(fill='x',pady=4)
        tag='  [SCREEN READING]' if 'screen_reading' in notices else '  [AUTOMATED INPUT]' if 'automated_input' in notices else ''
        ttk.Checkbutton(card,text=label+tag,variable=values[name],command=lambda n=name:dependencies(n)).pack(anchor='w')
        ttk.Label(card,text=detail,foreground='#adbed0',wraplength=700).pack(anchor='w',padx=(29,0))
        for notice in notices:
            ttk.Label(card,text=NOTICES[notice],foreground='#d8bd83' if notice=='screen_reading' else '#8da7bf',wraplength=700,font=('Segoe UI',9)).pack(anchor='w',padx=(29,0),pady=(3,0))
    bind_wheel(canvas);bind_wheel(content)
    status=ttk.Label(outer,text='Shared UI and game-data infrastructure stay installed. Optional providers and reader components follow your selection.',wraplength=740,foreground='#adbed0');status.pack(fill='x',pady=8)
    controls=ttk.Frame(outer);controls.pack(fill='x')
    messages=queue.Queue();busy=False
    def finish():
        if not busy:window.destroy()
    window.protocol('WM_DELETE_WINDOW',finish)
    def apply():
        nonlocal busy
        if busy:return
        if not modular():
            status.config(text='This development/legacy build is not a modular installation. Install the new unified installer to choose features. No files were changed.');return
        selected=resolve([name for name,value in values.items() if value.get()])
        busy=True;button.state(['disabled']);status.config(text='Checking the signed feature catalog…')
        def work():
            try:
                from module_distribution import prepare
                result=prepare(ROOT,PROFILE,selected,progress=lambda text:messages.put(('progress',text)))
                messages.put(('done',result))
            except Exception as error:messages.put(('error',str(error)))
        threading.Thread(target=work,daemon=True,name='feature-downloads').start()
    button=ttk.Button(controls,text='Download & apply selected features',command=apply);button.pack(side='left')
    ttk.Button(controls,text='Close',command=finish).pack(side='right')
    def poll():
        nonlocal busy
        try:
            while True:
                kind,value=messages.get_nowait()
                if kind=='progress':status.config(text=value)
                elif kind=='error':
                    busy=False;button.state(['!disabled']);status.config(text='Unable to apply features: '+value+' Your current app and records were kept.')
                else:
                    busy=False;button.state(['!disabled']);status.config(text=value['detail'])
                    if value['status']=='staged':
                        start_agent()
                        if first_run:window.destroy();return
        except queue.Empty:pass
        window.after(150,poll)
    try:poll();window.mainloop()
    finally:lock.close()


if __name__=='__main__':main('--first-run' in sys.argv)
