"""Explicitly opened desktop controls; no game input, hotkeys or always-on-top UI."""
import logging
import sqlite3
import tkinter as tk
from tkinter import ttk
from compboard_inventory import CompboardInventory, BOARD_LOCATIONS, MAX_COUNT, valid_counts


class CompboardTracker:
    def __init__(self, root, directory):
        self.root = root
        self.repository = CompboardInventory(directory)
        self.state = self.repository.view()
        self.cooldown = False
        root.title('SynthScan · Compboard inventory')
        root.configure(bg='#14171d')
        root.resizable(False, False)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Boards.TFrame', background='#14171d')
        style.configure('Boards.TLabel', background='#14171d', foreground='#e9edf1', font=('Segoe UI', 11))
        style.configure('Muted.Boards.TLabel', foreground='#95a0ad', font=('Segoe UI', 10))
        style.configure('Title.Boards.TLabel', font=('Segoe UI', 18, 'bold'))
        style.configure('Boards.TButton', font=('Segoe UI', 11), padding=(10, 6), background='#1d2129', foreground='#e9edf1')
        style.map('Boards.TButton', background=[('active', '#334155')], foreground=[('disabled', '#687386')])
        body = ttk.Frame(root, style='Boards.TFrame', padding=22)
        body.grid(sticky='nsew')
        ttk.Label(body, text='Compboard inventory', style='Title.Boards.TLabel').grid(row=0, column=0, columnspan=5, sticky='w')
        ttk.Label(body, text='Manual counts · saved on this PC', style='Muted.Boards.TLabel').grid(row=1, column=0, columnspan=5, sticky='w', pady=(4, 18))
        self.entries = []
        self.minus = []
        self.plus = []
        self.vars = [tk.StringVar(root, str(n)) for n in self.state['counts']]
        for i, variable in enumerate(self.vars):
            row = i+2
            ttk.Label(body, text=f'Board {i+1}', width=10, style='Boards.TLabel').grid(row=row, column=0, sticky='w', pady=5)
            ttk.Label(body, text=BOARD_LOCATIONS[i], width=15, style='Muted.Boards.TLabel').grid(row=row, column=1, sticky='w', padx=(0, 16))
            minus = ttk.Button(body, text='−', width=3, style='Boards.TButton', command=lambda index=i: self.adjust(index, -1))
            minus.grid(row=row, column=2, padx=(0, 6))
            entry = ttk.Entry(body, textvariable=variable, width=7, justify='center', font=('Consolas', 12))
            entry.grid(row=row, column=3)
            entry.bind('<Return>', lambda event: self.save())
            entry.bind('<FocusOut>', lambda event: self.save())
            plus = ttk.Button(body, text='+', width=3, style='Boards.TButton', command=lambda index=i: self.adjust(index, 1))
            plus.grid(row=row, column=4, padx=(6, 0))
            variable.trace_add('write', lambda *args: self.update_buttons())
            self.entries.append(entry);self.minus.append(minus);self.plus.append(plus)
        self.summary = ttk.Label(body, style='Boards.TLabel')
        self.summary.grid(row=9, column=0, columnspan=5, sticky='w', pady=(18, 10))
        actions = ttk.Frame(body, style='Boards.TFrame')
        actions.grid(row=10, column=0, columnspan=5, sticky='ew')
        self.use_button = ttk.Button(actions, text='Use one set (−1 of each)', style='Boards.TButton', command=self.use_set)
        self.use_button.grid(row=0, column=0, padx=(0, 8))
        self.undo_button = ttk.Button(actions, text='Undo last set', style='Boards.TButton', command=self.undo_set)
        self.undo_button.grid(row=0, column=1)
        ttk.Button(actions, text='Save counts', style='Boards.TButton', command=self.save).grid(row=0, column=2, padx=(8, 0))
        self.note = ttk.Label(body, text='Use one set updates your tracker only; it does not claim a ship in game.',
                              wraplength=520, style='Muted.Boards.TLabel')
        self.note.grid(row=11, column=0, columnspan=5, sticky='w', pady=(12, 0))
        self.update_buttons()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def counts(self):
        values = [v.get().strip() for v in self.vars]
        if any(not v.isascii() or not v.isdecimal() or len(v) > 4 for v in values):
            raise ValueError(f'Use whole-number quantities from 0 to {MAX_COUNT}.')
        return valid_counts([int(v) for v in values])

    def update_buttons(self):
        if not hasattr(self, 'use_button'):
            return
        try:
            counts = self.counts();sets = min(counts)
            self.summary.configure(text=f'{sets} complete '+('set' if sets == 1 else 'sets')+f' ready · {sum(counts)} boards total')
            self.use_button.configure(state='normal' if sets and not self.cooldown else 'disabled')
            self.undo_button.configure(state='normal' if self.state['can_undo'] and counts == self.state['counts'] else 'disabled')
            for i, n in enumerate(counts):
                self.minus[i].configure(state='normal' if n else 'disabled')
                self.plus[i].configure(state='normal' if n < MAX_COUNT else 'disabled')
        except ValueError:
            self.summary.configure(text='Enter valid quantities for boards 1–7.')
            for button in [self.use_button, self.undo_button, *self.minus, *self.plus]:
                button.configure(state='disabled')

    def refresh(self, state):
        self.state = state
        for variable, n in zip(self.vars, state['counts']):
            variable.set(str(n))
        self.update_buttons()

    def action(self, callback, message):
        try:
            self.refresh(callback());self.note.configure(text=message);return True
        except (ValueError, sqlite3.Error, OSError) as exc:
            try:self.refresh(self.repository.view())
            except (ValueError, sqlite3.Error, OSError):pass
            self.note.configure(text=str(exc));return False

    def save(self):
        try:counts = self.counts()
        except ValueError as exc:self.note.configure(text=str(exc));return False
        return self.action(lambda: self.repository.set_counts(counts, self.state['revision']), 'Counts saved locally. The hangar HUD updates automatically.')

    def adjust(self, index, delta):
        try:
            counts = self.counts();counts[index] += delta;valid_counts(counts)
        except ValueError as exc:self.note.configure(text=str(exc));return
        self.action(lambda: self.repository.set_counts(counts, self.state['revision']), 'Counts saved locally.')

    def use_set(self):
        if self.cooldown:
            return
        try:
            if min(self.counts()) < 1:raise ValueError('You need at least one of all seven boards.')
        except ValueError as exc:self.note.configure(text=str(exc));return
        if not self.save():return
        if self.action(lambda: self.repository.use_set(self.state['revision']), 'Used one set: subtracted one of every board. Undo is available until you edit counts.'):
            self.cooldown = True;self.update_buttons();self.root.after(800, self.end_cooldown)

    def end_cooldown(self):
        self.cooldown = False;self.update_buttons()

    def undo_set(self):
        self.action(lambda: self.repository.undo_set(self.state['revision']), 'Restored the seven boards from the last set use.')

    def close(self):
        self.save()  # Invalid drafts leave the last saved counts intact.
        self.repository.close();self.root.destroy()


def main():
    from app_lifecycle import SingleInstance, Signal, send_signal
    from native_control import DATA
    lock = SingleInstance('compboard-inventory')
    if not lock.acquired:
        send_signal('compboard-inventory-show');return
    show = Signal('compboard-inventory-show')
    root = tk.Tk();root.withdraw()
    try:
        tracker = CompboardTracker(root, DATA)
        def poll():
            if show.wait(0):root.deiconify();root.lift()  # only a deliberate menu request
            root.after(250, poll)
        poll();root.deiconify();root.mainloop()
    except (ValueError, sqlite3.Error, OSError):
        logging.exception('Cannot open saved compboard inventory')
        from tkinter import messagebox
        messagebox.showerror('Compboard inventory', 'The saved compboard inventory could not be opened. No counts were reset or overwritten.', parent=root)
        root.destroy()
    finally:show.close();lock.close()


if __name__ == '__main__':
    main()
