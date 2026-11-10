"""Direct SynthStrings controls opened from Home; no tray navigation required."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import os
import tkinter as tk
from tkinter import ttk

from installation import PROFILE,game_directory
from game_text_lifecycle import Manager,INI,digest,atomic
from synthstrings_guard import check_once,view,current_pids


def replace_pack(game,profile=PROFILE,native=None,expected=None,cancel=None):
    manager=Manager(game,profile)
    manager.set_enabled(True)
    config=Path(profile)/'region_config.txt'
    before=config.read_text(encoding='utf-8-sig') if config.exists() else ''
    after='\n'.join([line for line in before.splitlines() if not line.startswith('gametexts=')]+['gametexts=1'])+'\n'
    if after!=before:atomic(config,after.encode('utf-8'))
    if expected is not None:manager.suspend(current_pids(),replace_sha256=expected)
    from game_text_lifecycle import apply_native
    result=apply_native(game,'-',profile,native,cancel)
    if result.get('error'):raise ValueError(result['note'])
    return result


class StringsWindow:
    def __init__(self,window,native=None):
        from branding import window_icon
        self.window=window;self.native=native;self.future=None;self.stop=threading.Event()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='strings-settings')
        from app_lifecycle import Signal
        self.show=Signal('strings-settings-show')
        window_icon(window);window.title('SynthScan — Text settings');window.geometry('780x560');window.minsize(720,540)
        window.configure(bg='#101820');style=ttk.Style(window);style.theme_use('clam')
        style.configure('.',background='#101820',foreground='#e5edf3',font=('Segoe UI',10))
        style.configure('TButton',background='#243947',padding=(12,7))
        outer=ttk.Frame(window,padding=26);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Game-text enhancements',font=('Segoe UI',21,'bold')).pack(anchor='w')
        self.patch=ttk.Label(outer,font=('Segoe UI',11,'bold'));self.patch.pack(anchor='w',pady=(8,0))
        self.title=ttk.Label(outer,font=('Segoe UI',13,'bold'),wraplength=650);self.title.pack(anchor='w',pady=(18,8))
        self.detail=ttk.Label(outer,wraplength=650,justify='left');self.detail.pack(anchor='w')
        ttk.Label(outer,text='SynthStrings adds blueprint and reputation information to in-game text. Use SynthStrings saves a backup of your current text, then prepares these additions for your installed patch. Future launcher updates trigger a text update automatically.',wraplength=650,justify='left').pack(anchor='w',pady=(18,12))
        actions=ttk.Frame(outer);actions.pack(fill='x')
        self.check=ttk.Button(actions,text='Check now',command=self.check_now);self.check.pack(side='left')
        self.replace=ttk.Button(actions,text='Use SynthStrings',command=self.use_generated);self.replace.pack(side='left',padx=8)
        self.allow=ttk.Button(outer,text='Allow game-text access',command=self.permission)
        self.allow.pack(anchor='w',pady=(14,0))
        self.allow.pack_forget()
        ttk.Button(outer,text='Close',command=self.close).pack(anchor='e',pady=(20,0))
        self.refresh();window.protocol('WM_DELETE_WINDOW',self.close);window.after(250,self.poll)

    def refresh(self):
        result=view(PROFILE,current_pids())
        self.patch.config(text=result.get('patch_label','Star Citizen · patch number unavailable'))
        self.title.config(text=result.get('status_label','Check game-text enhancements'))
        detail=result.get('summary','Choose Check now to read the installed patch and check SynthStrings.')
        if result.get('state')=='external':detail+=' You can leave this as it is. Use SynthStrings is optional; choose it if you want SynthScan to manage game-text updates.'
        self.detail.config(text=detail)

    def start(self,action):
        if self.future:return
        self.check.state(['disabled']);self.replace.state(['disabled'])
        self.title.config(text='Preparing game text…');self.detail.config(text='You can keep this window open or read the result on Home. A restart notice appears only if the running game needs to reload text.')
        self.future=self.pool.submit(action)

    def check_now(self):self.start(lambda:check_once(PROFILE,self.native,self.stop))

    def use_generated(self):
        try:
            game=game_directory(True);path=Manager(game,PROFILE).target(INI)
            expected=digest(path.read_bytes()) if path.exists() else ''
            self.start(lambda:replace_pack(game,PROFILE,self.native,expected,self.stop))
        except (OSError,ValueError) as error:self.detail.config(text=str(error))

    def permission(self):
        from game_text_access import request
        try:request();self.detail.config(text='After approving Windows access, choose Check now or Use generated SynthStrings again.')
        except (OSError,ValueError) as error:self.detail.config(text=str(error))

    def poll(self):
        if self.show.wait(0):self.window.deiconify();self.window.lift()
        if self.future and self.future.done():
            try:self.future.result();self.refresh()
            except Exception as error:
                self.title.config(text='The text update could not finish');self.detail.config(text=str(error))
                if isinstance(error,PermissionError) or 'access' in str(error).lower():self.allow.pack(anchor='w',pady=(14,0))
            self.future=None;self.check.state(['!disabled']);self.replace.state(['!disabled'])
        self.window.after(250,self.poll)

    def close(self):
        self.stop.set();self.pool.shutdown(wait=False,cancel_futures=True);self.window.destroy()


def main():
    global PROFILE
    parser=argparse.ArgumentParser();parser.add_argument('--native',type=Path);parser.add_argument('--profile',type=Path,default=PROFILE);args=parser.parse_args()
    PROFILE=args.profile
    import installation
    installation.PROFILE=PROFILE;os.environ['SYNTHSCAN_DATA_DIR']=str(PROFILE)
    from app_lifecycle import SingleInstance,send_signal
    lock=SingleInstance('strings-settings')
    if not lock.acquired:send_signal('strings-settings-show');return
    window=tk.Tk();ui=StringsWindow(window,args.native)
    try:window.mainloop()
    finally:ui.show.close();lock.close()


if __name__=='__main__':main()
