"""Readable source freshness and a manual check without blocking the HUD."""
from pathlib import Path
import time
import uuid
import webbrowser
import os
import tkinter as tk
from tkinter import ttk
from installation import PROFILE
from telemetry_ipc import publish_json,read_shared_json
from data_updates import DataUpdateService,status_lines,optional_json


def main():
    from app_lifecycle import SingleInstance,game_process_ids
    lock=SingleInstance('data-update-window')
    if not lock.acquired:return
    PROFILE.mkdir(parents=True,exist_ok=True)
    window=tk.Tk();window.title('SynthScan — Data updates');window.geometry('850x720');window.minsize(720,560)
    style=ttk.Style(window);style.theme_use('clam')
    style.configure('.',background='#101820',foreground='#e5edf3',font=('Segoe UI',10))
    window.configure(bg='#101820')
    outer=ttk.Frame(window,padding=22);outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Data updates',font=('Segoe UI',20,'bold')).pack(anchor='w')
    ttk.Label(outer,text='Source checks run automatically. Game references rebuild after the game closes.').pack(anchor='w',pady=(6,16))
    automatic=tk.BooleanVar(value=optional_json(PROFILE/'update_preferences.json').get('automatic_app',True) is True)
    def save_automatic():
        prefs=optional_json(PROFILE/'update_preferences.json');prefs['automatic_app']=automatic.get();publish_json(PROFILE/'update_preferences.json',prefs)
    ttk.Checkbutton(outer,text='Automatically download and install verified app updates while out of game',variable=automatic,command=save_automatic).pack(anchor='w',pady=(0,12))
    frame=ttk.Frame(outer);frame.pack(fill='both',expand=True)
    body=tk.Text(frame,bg='#14212c',fg='#e5edf3',font=('Segoe UI',10),wrap='word',relief='flat',padx=16,pady=12)
    bar=ttk.Scrollbar(frame,command=body.yview);body.configure(yscrollcommand=bar.set)
    bar.pack(side='right',fill='y');body.pack(fill='both',expand=True)
    controls=ttk.Frame(outer);controls.pack(fill='x',pady=(16,0))
    def request():
        publish_json(PROFILE/'data_update_command.json',dict(id=uuid.uuid4().hex,at=time.time()))
        # The hangar owner consumes its own request and retains independent rate limits.
        publish_json(PROFILE/'hangar_update_command.json',dict(id=uuid.uuid4().hex,at=time.time()))
    ttk.Button(controls,text='Check for updates',command=request).pack(side='left')
    ttk.Button(controls,text='SCMDB',command=lambda:webbrowser.open('https://scmdb.net/')).pack(side='left',padx=(8,0))
    ttk.Button(controls,text='App releases',command=lambda:webbrowser.open('https://github.com/Synthronaut/Synthscan/releases')).pack(side='left',padx=(8,0))
    ttk.Button(controls,text='Close',command=window.destroy).pack(side='right')
    ttk.Label(outer,text='Version-matched reference data refreshes separately. App updates use signed packages and retain the previous version for rollback.\nChecks, downloads, source imports and successful app activation are reported separately.',wraplength=780).pack(anchor='w',pady=(12,0))
    service=None;last='';hangar_service=None;hangar_publisher=None
    def poll():
        nonlocal service,last,hangar_service,hangar_publisher
        state=optional_json(PROFILE/'data_update_status.json')
        # An open HUD owns monitoring; this window also works when the HUD is closed.
        if service is None and not 0<=time.time()-state.get('at',0)<15:service=DataUpdateService(PROFILE,exclusive=True)
        if service:service.tick(game_running=bool(game_process_ids()))
        hangar_state=optional_json(PROFILE/'hangar_update_status.json')
        other_owner=hangar_state.get('owner_pid')!=os.getpid() and 0<=time.time()-hangar_state.get('at',0)<15
        if hangar_service and other_owner:
            hangar_service.close();hangar_service=None;hangar_publisher=None
        elif not other_owner:
            if hangar_service is None:
                from executive_hangar import HangarScheduleService
                from hangar_card import HangarPublisher
                hangar_service=HangarScheduleService(PROFILE);hangar_publisher=HangarPublisher(PROFILE,os.getpid())
            hangar_publisher.tick(hangar_service,False)
        value=status_lines(PROFILE)
        if value!=last:
            position=body.yview()[0];body.configure(state='normal');body.delete('1.0','end');body.insert('1.0',value);body.configure(state='disabled');body.yview_moveto(position);last=value
        window.after(1000,poll)
    window.after(50,poll)
    try:window.mainloop()
    finally:
        if service:service.close()
        if hangar_service:hangar_service.close()
        lock.close()

if __name__=='__main__':main()
