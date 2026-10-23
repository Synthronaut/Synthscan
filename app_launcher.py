"""Community entry point. Runs from the bundled Python, without an installer."""
import sys
from pathlib import Path
# Python is isolated from user packages, while application modules stay importable.
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import os
import queue
import threading
import traceback
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from installation import ROOT,PROFILE,game_directory,valid_game


def main():
    PROFILE.mkdir(parents=True,exist_ok=True)
    if '--watch' in sys.argv:
        from native_control import watch
        watch();return
    from app_lifecycle import SingleInstance
    setup_lock=SingleInstance('setup')
    if not setup_lock.acquired:return
    window=tk.Tk();window.title('SynthScan setup');window.geometry('620x230')
    window.configure(padx=24,pady=22)
    title=ttk.Label(window,text='Preparing SynthScan',font=('Segoe UI',16));title.pack(anchor='w')
    label=ttk.Label(window,text='Finding your Star Citizen installation…',wraplength=570);label.pack(anchor='w',pady=16)
    bar=ttk.Progressbar(window,mode='indeterminate');bar.pack(fill='x');bar.start()
    hint=ttk.Label(window,text='Your inventory, histories and account data stay on this Windows profile.',wraplength=570);hint.pack(anchor='w',pady=14)
    try:game=game_directory(True)
    except FileNotFoundError:
        picked=filedialog.askdirectory(parent=window,title='Choose Star Citizen LIVE/PTU folder containing Data.p4k')
        if not picked or not valid_game(picked):window.destroy();return
        game=Path(picked)
    os.environ['SYNTHSCAN_GAME_DIR']=str(game)
    messages=queue.Queue()
    def work():
        try:
            from community_setup import prepare
            note=prepare(lambda s:messages.put(('progress',str(s))))
            from native_control import launch
            launch()
            messages.put(('done',note))
        except Exception:
            # No RPC client or login credential is read on this setup thread.
            (PROFILE/'setup_error.log').write_text(traceback.format_exc(),encoding='utf-8')
            messages.put(('error','Setup could not finish. Details are in '+str(PROFILE/'setup_error.log')))
    def poll():
        try:
            while True:
                kind,value=messages.get_nowait()
                if kind=='progress':label.config(text=value)
                elif kind=='error':bar.stop();messagebox.showerror('SynthScan setup',value,parent=window);window.destroy();return
                elif kind=='done':
                    bar.stop()
                    if not (PROFILE/'welcome_seen').exists():
                        messagebox.showinfo('SynthScan is ready',
                            'Your HUD and library are ready. Reputation is checked for your signed-in character while the game runs. '
                            'After new reputation labels are written, fully restart Star Citizen to load them. '
                            'Enable launch with Star Citizen in SynthScan settings if wanted.\n\nSynthStrings: '+value,parent=window)
                        (PROFILE/'welcome_seen').touch()
                    window.destroy();return
        except queue.Empty:pass
        window.after(150,poll)
    window.protocol('WM_DELETE_WINDOW',lambda:None)
    threading.Thread(target=work,daemon=True).start();poll();window.mainloop()


if __name__=='__main__':main()
