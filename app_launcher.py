"""Guided first run and in-app setup/reputation status for the installed app."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import os
import queue
import subprocess
import threading
import traceback
import tkinter as tk
from tkinter import filedialog,ttk
from installation import ROOT,PROFILE,game_directory,valid_game
from setup_status import ready,reputation_view,error_message,read


def selected_game(folder):
    folder=Path(folder)
    for path in [folder,folder/'LIVE',folder/'StarCitizen/LIVE',folder/'PTU',folder.parent]:
        if valid_game(path):return path.resolve()
    return None


class SetupWindow:
    def __init__(self,window,status_only=False):
        self.window=window;self.busy=False;self.messages=queue.Queue();self.status_only=status_only;self.initial=not ready()
        window.title('SynthScan — Setup & reputation');window.geometry('700x480');window.minsize(660,450)
        style=ttk.Style(window);style.theme_use('clam')
        window.configure(bg='#101820')
        style.configure('.',background='#101820',foreground='#e5edf3',font=('Segoe UI',10))
        style.configure('TButton',background='#243947',padding=(12,7));style.map('TButton',background=[('active','#345569')])
        style.configure('Header.TLabel',font=('Segoe UI',21,'bold'));style.configure('Sub.TLabel',foreground='#9eb3c3')
        style.configure('TProgressbar',background='#69cbbd',troughcolor='#243947',bordercolor='#243947',lightcolor='#69cbbd',darkcolor='#69cbbd')
        outer=ttk.Frame(window,padding=28);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='SynthScan',style='Header.TLabel').pack(anchor='w')
        ttk.Label(outer,text='Your HUD, game library and reputation — set up for this PC.',style='Sub.TLabel').pack(anchor='w',pady=(4,18))
        self.title=ttk.Label(outer,text='Finding Star Citizen…',font=('Segoe UI',13,'bold'),wraplength=630);self.title.pack(anchor='w')
        self.detail=ttk.Label(outer,text='',wraplength=630,justify='left');self.detail.pack(anchor='w',pady=(8,12))
        self.bar=ttk.Progressbar(outer,mode='indeterminate');self.bar.pack(fill='x',pady=(0,12))
        self.game=ttk.Label(outer,text='',style='Sub.TLabel',wraplength=630);self.game.pack(anchor='w')
        controls=ttk.Frame(outer);controls.pack(fill='x',pady=(15,12))
        self.retry=ttk.Button(controls,text='Retry setup',command=self.start);self.retry.pack(side='left',padx=(0,8))
        self.browse=ttk.Button(controls,text='Choose game folder',command=self.choose);self.browse.pack(side='left',padx=(0,8))
        self.allow=ttk.Button(controls,text='Allow game-text access',command=self.permission);self.allow.pack(side='left')
        bottom=ttk.Frame(outer);bottom.pack(fill='x',pady=(8,0))
        self.open=ttk.Button(bottom,text='Open SynthScan',command=self.open_app);self.open.pack(side='left',padx=(0,8))
        self.repair=ttk.Button(bottom,text='Repair setup',command=lambda:self.start(force=True));self.repair.pack(side='left')
        ttk.Button(bottom,text='Close',command=self.close).pack(side='right')
        ttk.Label(outer,text='Your player records stay on this Windows account. Setup never asks for your password.',style='Sub.TLabel',wraplength=630).pack(anchor='w',pady=(18,0))
        self.allow.pack_forget();self.retry.pack_forget()
        window.protocol('WM_DELETE_WINDOW',self.close)
        from app_lifecycle import Signal
        self.show=Signal('setup-show')
        self.stop=Signal('setup-stop')
        window.after(100,self.poll)
        if status_only and ready():self.finished()
        else:window.after(150,self.start)

    def close(self):
        if self.busy:
            self.detail.config(text='Setup is still working safely in the background. You can reopen Setup & reputation from SynthScan.');self.window.withdraw()
        else:self.window.destroy()

    def choose(self):
        if self.busy:return
        picked=filedialog.askdirectory(parent=self.window,title='Choose Star Citizen LIVE, PTU, or the folder containing them')
        if not picked:return
        game=selected_game(picked)
        if not game:
            self.title.config(text='That folder does not contain Star Citizen')
            self.detail.config(text='Choose the LIVE or PTU folder, or its parent folder. If the game is not installed, finish installing it in RSI Launcher first.')
            return
        os.environ['SYNTHSCAN_GAME_DIR']=str(game)
        self.start()

    def start(self,force=False):
        if self.busy:return
        try:game=game_directory(True)
        except FileNotFoundError:
            self.title.config(text='Let’s find your game')
            self.detail.config(text='Open RSI Launcher and finish installing or updating Star Citizen, then choose Retry setup. You can also choose its folder yourself.')
            self.retry.pack(side='left',before=self.browse,padx=(0,8));return
        os.environ['SYNTHSCAN_GAME_DIR']=str(game);self.game.config(text='Game: '+str(game))
        self.busy=True;self.retry.pack_forget();self.allow.pack_forget();self.bar.configure(mode='indeterminate',value=0);self.bar.start(12)
        self.title.config(text='Preparing SynthScan for this PC')
        self.detail.config(text='First setup reads your game files. This can take several minutes; you only need to do this after installation or a game patch.')
        def work():
            try:
                from community_setup import prepare
                note=prepare(lambda text:self.messages.put(('progress',text)),force=force)
                self.messages.put(('done',note))
            except Exception as error:
                (PROFILE/'setup_error.log').write_text(traceback.format_exc(),encoding='utf-8')
                self.messages.put(('error',(error_message(error),isinstance(error,PermissionError))))
        threading.Thread(target=work,daemon=False).start()

    def permission(self):
        try:
            from game_text_access import request
            request()
            self.detail.config(text='Approve the Windows prompt, wait for it to finish, then choose Retry setup. Access is granted only to game text files, not game executables.')
            self.retry.pack(side='left',before=self.browse,padx=(0,8))
        except (OSError,ValueError,AttributeError):self.detail.config(text='Windows did not allow the permission request. Your files have not been replaced. You can retry when ready.')

    def open_app(self):
        if self.busy:return
        if not ready():self.start();return
        from native_control import launch
        launch()
        self.window.withdraw()

    def finished(self):
        self.busy=False;self.bar.stop();self.bar.configure(mode='determinate',value=100);self.title.config(text='Your HUD and library are ready')
        self.detail.config(text='Enter Star Citizen normally. Your own reputation syncs automatically; this window will tell you when the numbers are ready.')
        if self.initial:
            from community_startup import ensure_watcher
            ensure_watcher()
            from native_control import launch
            launch('--autostart' in sys.argv)
            self.initial=False

    def poll(self):
        if self.stop.wait(0) and not self.busy:self.window.destroy();return
        if self.show.wait(0):self.window.deiconify();self.window.lift()
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='progress':self.detail.config(text=value)
                elif kind=='error':
                    self.busy=False;self.bar.stop();self.title.config(text='One step needs attention');self.detail.config(text=value[0])
                    self.retry.pack(side='left',before=self.browse,padx=(0,8))
                    if value[1]:self.allow.pack(side='left')
                elif kind=='done':self.finished()
        except queue.Empty:pass
        if not self.busy and ready():
            status=reputation_view();self.title.config(text=status['title']);self.detail.config(text=status['detail'])
            install=read(PROFILE/'installation.json');self.game.config(text='Game: '+install.get('game_dir','Detected automatically'))
        self.window.after(750,self.poll)


def main():
    PROFILE.mkdir(parents=True,exist_ok=True)
    if '--uninstall' in sys.argv:
        from community_uninstall import cleanup
        cleanup();return
    if '--watch' in sys.argv:
        from native_control import watch
        watch();return
    if '--status' not in sys.argv and '--repair' not in sys.argv and ready():
        from community_startup import ensure_watcher
        ensure_watcher()
        from native_control import launch
        launch('--autostart' in sys.argv);return
    from app_lifecycle import SingleInstance,send_signal
    lock=SingleInstance('setup')
    if not lock.acquired:send_signal('setup-show');return
    window=tk.Tk();ui=SetupWindow(window,'--status' in sys.argv)
    if '--repair' in sys.argv:window.after(250,lambda:ui.start(force=True))
    try:window.mainloop()
    finally:ui.show.close();ui.stop.close();lock.close()


if __name__=='__main__':main()
