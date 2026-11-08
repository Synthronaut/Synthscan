"""Explicit opt-in contract prompt helper; ordinary Win32 input only."""
import argparse,ctypes,json,time,logging
from ctypes import wintypes as w
from pathlib import Path
from contract_share import ContractQueue,acceptance_settings,LogRecords,accept_scan_code,ContractSession,accept_blockers

def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,required=True);p.add_argument('--watch',action='store_true');a=p.parse_args()
    from app_lifecycle import SingleInstance,Signal,send_signal
    lock=SingleInstance('contract-share')
    if not lock.acquired:
        if not a.watch:send_signal('contract-share-show')
        return
    from installation import game_directory
    from native_control import DATA
    from native_bridge import owner_alive
    from telemetry_ipc import read_shared_json,publish_json
    import tkinter as tk
    from tkinter import ttk
    DATA.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'contract_share.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    game=game_directory(True);reader=LogRecords(game/'Game.log');q=ContractQueue();show=Signal('contract-share-show')
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetForegroundWindow.restype=w.HWND
    api.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    class Mouse(ctypes.Structure):_fields_=[('dx',w.LONG),('dy',w.LONG),('data',w.DWORD),('flags',w.DWORD),('time',w.DWORD),('extra',ctypes.c_size_t)]
    class Key(ctypes.Structure):_fields_=[('vk',w.WORD),('scan',w.WORD),('flags',w.DWORD),('time',w.DWORD),('extra',ctypes.c_size_t)]
    class Payload(ctypes.Union):_fields_=[('mouse',Mouse),('key',Key)]
    class Input(ctypes.Structure):_fields_=[('type',w.DWORD),('payload',Payload)]
    api.SendInput.argtypes=[w.UINT,ctypes.POINTER(Input),ctypes.c_int];api.SendInput.restype=w.UINT
    api.MapVirtualKeyW.argtypes=[w.UINT,w.UINT];api.MapVirtualKeyW.restype=w.UINT
    root=tk.Tk();root.withdraw();root.title('SynthScan — Contract shares');root.geometry('540x280')
    try:settings=acceptance_settings(read_shared_json(DATA/'contract_share_preferences.json'))
    except (OSError,ValueError):settings=acceptance_settings({})
    switches={kind:tk.BooleanVar(value=value) for kind,value in settings.items()}
    armed=switches['contract'];q.enabled=settings
    enabled=armed.get();label=tk.StringVar(value='Starting contract watcher')
    logging.info('Started: enabled=%s owner=%s',enabled,a.owner)
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Automatic acceptance',font=('Segoe UI',16,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Choose which incoming requests to accept automatically.\nKeep Star Citizen focused. Menus may block the game accept key.',justify='left').pack(anchor='w',pady=10)
    snapshot={};context=ContractSession();sampled=0;down=None;disabled_reason='';pause='';decision=''
    stop=Signal('contract-share-stop')
    def save_settings():
        q.enabled={kind:var.get() for kind,var in switches.items()}
        return publish_json(DATA/'contract_share_preferences.json',dict(enabled=q.enabled['contract'],party_enabled=q.enabled['party'],friend_enabled=q.enabled['friend']))
    def disarm():
        for var in switches.values():var.set(False)
        save_settings()
    def any_enabled():return any(var.get() for var in switches.values())
    def release_key():
        nonlocal down,disabled_reason
        if down is None:return
        event=Input();event.type=1;event.payload.key=Key(0,down,0x0008|0x0002,0,0)
        if api.SendInput(1,ctypes.byref(event),ctypes.sizeof(Input))!=1:
            disarm();disabled_reason='Windows could not release the accept key; release it manually'
        down=None
    def arm_changed():
        nonlocal reader,disabled_reason
        release_key();q.reset();reader=LogRecords(game/'Game.log');disabled_reason=''
        if not save_settings():
            disarm();disabled_reason='Could not save automatic acceptance setting'
        logging.info('User setting changed: enabled=%s',armed.get())
    for kind,title in (('contract','Automatically accept shared contracts'),('party','Automatically accept party invitations'),('friend','Automatically accept friend requests')):
        ttk.Checkbutton(frame,text=title,variable=switches[kind],command=arm_changed).pack(anchor='w',pady=5)
    ttk.Label(frame,textvariable=label,wraplength=495,justify='left').pack(anchor='w',pady=12)
    ttk.Label(frame,text='Closing keeps this running. Uncheck to disable. Blocked accepts\nretry while the same request prompt stays active; menus may block the game key.',foreground='#777777').pack(anchor='w')
    def hide():
        logging.info('Window hidden: enabled=%s',armed.get());root.withdraw()
    root.protocol('WM_DELETE_WINDOW',hide)
    def tick():
        nonlocal snapshot,sampled,down,disabled_reason,reader,pause,decision
        if stop.wait(0) or not owner_alive(a.owner):
            release_key();root.destroy();return
        now=time.time()
        try:
            if show.wait(0):root.deiconify();root.lift()
            if now-sampled>=.25:
                snapshot=read_shared_json(DATA/'session_state.json',limit=8*1024*1024);sampled=now
                external=acceptance_settings(read_shared_json(DATA/'contract_share_preferences.json'))
                if external!=q.enabled:
                    release_key();q.reset();reader=LogRecords(game/'Game.log');disabled_reason=''
                    q.enabled=external
                    for kind,value in external.items():switches[kind].set(value)
            valid,changed=context.update(snapshot,a.owner,now)
            if changed:
                q.reset();reader=LogRecords(game/'Game.log');release_key()
                logging.info('Fresh session changed: queue reset; enabled=%s',armed.get())
            records,reset=reader.read()
            if reset:q.reset()
            for record in records:q.feed(record)
            candidate=q.candidate(now)
            pause='Automatic acceptance is OFF' if not any_enabled() else 'Waiting for fresh connected session data' if not valid else ''
            if any_enabled() and valid and candidate and down is None:
                pid=w.DWORD();foreground=api.GetForegroundWindow();api.GetWindowThreadProcessId(foreground,ctypes.byref(pid))
                if pid.value in snapshot.get('game_pids',[]):
                    try:key,scan=accept_scan_code(game/'user/client/0/Profiles/default/actionmaps.xml')
                    except (ValueError,OSError) as exc:
                        disarm();disabled_reason=str(exc)
                        raise
                    accept_vk=api.MapVirtualKeyW(scan,1)
                    if not accept_vk:raise ValueError('Cannot identify the accept key; no input sent')
                    blockers=accept_blockers((k for k in range(1,255) if api.GetAsyncKeyState(k)&0x8000),accept_vk)
                    pause='Waiting for modifier/accept key release: '+','.join(hex(k) for k in blockers) if blockers else ''
                    # The binding read may overlap a prompt being replaced.
                    # Consume those transitions before authorizing another press.
                    latest,reset=reader.read()
                    if reset:q.reset()
                    for record in latest:q.feed(record)
                    # Final focus check after reading the current binding.
                    if not blockers and api.GetForegroundWindow()==foreground and q.attempted_once(candidate,time.time()):
                        event=Input();event.type=1;event.payload.key=Key(0,scan,0x0008,0,0)
                        if api.SendInput(1,ctypes.byref(event),ctypes.sizeof(Input))==1:
                            down=scan;root.after(60,release_key)
                            logging.info('Accept input sent: queue=%s key=%s attempt=%s',candidate['queue_id'],key,q.inputs[q.prompt_key(candidate)][0])
                        else:
                            disarm();disabled_reason='Windows rejected the accept key; automation disabled'
                else:pause='Game is not foreground'
            view=q.view(now)
            text=disabled_reason or pause or view['message']
            if text!=decision:
                decision=text;logging.info('Status: enabled=%s %s',armed.get(),text)
            label.set(('ON — ' if any_enabled() else 'OFF — ')+text+f"\nQueued: {view['queued']} · Attempts: {view['attempts']} · Contracts confirmed: {view['confirmed']}")
            if now-getattr(tick,'published',0)>=.25:
                publish_json(DATA/'contract_share_status.json',dict(at=now,owner_pid=a.owner,armed=any_enabled(),enabled_types=dict(q.enabled),**view,error=disabled_reason,paused_reason=pause,decision=text))
                tick.published=now
        except Exception as exc:
            # A transient read/JSON error pauses this tick; it must not revoke
            # the user's setting. Actual input failures still disarm above.
            release_key();pause='Temporary read error: '+str(exc);label.set(('ON — ' if any_enabled() else 'OFF — ')+pause)
            publish_json(DATA/'contract_share_status.json',dict(at=now,owner_pid=a.owner,armed=any_enabled(),enabled_types=dict(q.enabled),**q.view(now),error=disabled_reason,paused_reason=pause,decision=disabled_reason or pause))
            logging.exception('Contract helper paused')
        root.after(50,tick)
    if not a.watch:root.deiconify()
    try:tick();root.mainloop()
    finally:release_key();show.close();stop.close();lock.close()

if __name__=='__main__':main()
