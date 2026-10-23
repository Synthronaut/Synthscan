"""On-demand graphics inventory and measured-run comparison for the MFD."""
import json
import os
from pathlib import Path
import subprocess
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from performance_lab import (CATALOG, compare_runs, packaged_setting_evidence, read_json, setting_inventory,
                             snapshot, summarize_frame_csv, utc_now, write_json)


class PerformanceLabPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color='#181b22', corner_radius=0)
        self.pack(fill='both', expand=True)
        self.runs = {}
        self.saved = None
        self.run_directory = Path(__file__).parent / 'research' / 'performance'
        ctk.CTkLabel(self, text='GRAPHICS LAB // QUALITY, CLARITY & FRAME PACING',
                     font=('Bahnschrift', 21, 'bold')).pack(anchor='w', pady=(0, 6))
        ctk.CTkLabel(self, text='Saved values require menu verification. Resource costs are hypotheses until measured in the relevant scene.',
                     text_color='#d99b43', wraplength=850, justify='left').pack(anchor='w')
        tabs = ctk.CTkTabview(self, fg_color='#1e222a')
        tabs.pack(fill='both', expand=True, pady=8)
        settings = tabs.add('Settings inventory')
        record = tabs.add('Record a run')
        compare = tabs.add('Compare runs')
        self._build_inventory(settings)
        self._build_record(record)
        self._build_compare(compare)
        self.refresh_inventory()

    def _button(self, parent, text, command):
        button = ctk.CTkButton(parent, text=text, command=command, fg_color='#38404f', hover_color='#505b6d')
        button.pack(side='left', padx=(0, 6), pady=4)
        return button

    def _build_inventory(self, parent):
        bar = ctk.CTkFrame(parent, fg_color='transparent')
        bar.pack(fill='x')
        self._button(bar, 'Read saved settings', self.refresh_inventory)
        self._button(bar, 'Export inventory', self.export_inventory)
        self.inventory_status = ctk.CTkLabel(parent, text='', anchor='w', justify='left', wraplength=850)
        self.inventory_status.pack(fill='x', pady=4)
        box = ctk.CTkFrame(parent)
        box.pack(fill='both', expand=True)
        style = ttk.Style()
        style.configure('GraphicsLab.Treeview', background='#1e222a', fieldbackground='#1e222a',
                        foreground='#f8fafc', rowheight=26, font=('Bahnschrift', 11))
        self.tree = ttk.Treeview(box, columns=('label', 'raw', 'resource'), show='headings',
                                 style='GraphicsLab.Treeview', height=8, selectmode='browse')
        for key, label, width in [('label', 'Setting', 220), ('raw', 'Saved raw value', 110),
                                  ('resource', 'Likely cost — unmeasured', 340)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70)
        scrollbar = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.show_setting)
        self.detail = ctk.CTkTextbox(parent, height=145, wrap='word', font=('Bahnschrift', 13))
        self.detail.pack(fill='x', pady=(8, 0))

    def _set_text(self, widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def refresh_inventory(self):
        self.saved = snapshot()
        self.inventory = {row['key']: row for row in setting_inventory(self.saved)}
        self.tree.delete(*self.tree.get_children())
        for row in self.inventory.values():
            value = row['saved_raw'] if row['saved_raw'] is not None else 'Unknown / absent'
            if row.get('observed_menu_label'):
                value = f"{value} — {row['observed_menu_label']}"
            self.tree.insert('', 'end', iid=row['key'], values=(row['label'],
                             value,
                             row['resource_hypothesis']))
        build = self.saved['build'].get('RequestedP4ChangeNum', 'unknown')
        issues = len(self.saved['errors'])
        overrides = len(self.saved['potential_overrides'])
        self.inventory_status.configure(text=f'Build {build}  |  {len(self.inventory)} candidates; menu presence varies  |  '
                                               f'{overrides} startup overrides need verification  |  {issues} read errors')
        self.tree.selection_set('SysSpec_Shading')
        self.show_setting()

    def show_setting(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        row = self.inventory[selected[0]]
        evidence = packaged_setting_evidence(self.saved, row['key'])
        packaged = ('\nBuild-matched packaged configuration (static, not a live query):\n' +
                    json.dumps(evidence, indent=2)) if evidence else ''
        self._set_text(self.detail, f"{row['label']} [{row['key']}]\n"
                       f"Observed menu label for this saved value: {row.get('observed_menu_label') or 'Unverified'}\n"
                       f"Test scene: {row['test_scene']}\n{row['visual_notes']}\n"
                       'Evidence: not measured by this inventory. Raw enum numbers are not verified menu labels.\n'
                       'A single idle room cannot establish the cost of clouds, water, combat effects, or travel streaming.' + packaged)

    def export_inventory(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.json', initialfile='graphics-inventory.json')
        if path:
            self._guard(lambda: write_json(path, {'snapshot': self.saved, 'inventory': list(self.inventory.values())}))

    def _entry(self, parent, label, default=''):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', pady=3)
        ctk.CTkLabel(row, text=label, width=155, anchor='w').pack(side='left')
        entry = ctk.CTkEntry(row)
        entry.pack(side='left', fill='x', expand=True)
        entry.insert(0, default)
        return entry

    def _build_record(self, parent):
        body = ctk.CTkScrollableFrame(parent, fg_color='transparent')
        body.pack(fill='both', expand=True)
        ctk.CTkLabel(body, text='Record immediately after a capture, before changing another setting.\n'
                     'Use a warmed 60-second view or route; repeat A → B → A. Assess beauty and moving targets separately.',
                     justify='left', wraplength=800).pack(anchor='w', pady=4)
        self.fields = {key: self._entry(body, label) for key, label in
                       [('scene', 'Scene / location'), ('route', 'View / route'),
                        ('background_workload', 'Background apps'), ('driver_version', 'GPU driver'),
                        ('visual_notes', 'Visual quality notes'), ('visibility_notes', 'Target visibility notes')]}
        self.verified = ctk.CTkCheckBox(body, text='I verified the current settings in the running game menu')
        self.verified.pack(anchor='w', pady=5)
        self.overrides = ctk.CTkCheckBox(body, text='I verified the effective startup overrides, if present')
        self.overrides.pack(anchor='w', pady=5)
        self.generation = ctk.CTkCheckBox(body, text='Frame generation is disabled for this comparison')
        self.generation.pack(anchor='w', pady=5)
        bar = ctk.CTkFrame(body, fg_color='transparent')
        bar.pack(fill='x', pady=5)
        self._button(bar, 'Capture 60 seconds', lambda: self._guard(self.capture))
        self._button(bar, 'Import frame CSV & save run', lambda: self._guard(self.record_run))
        self.record_status = ctk.CTkLabel(body, text='Imports PresentMon v1 per-frame CSV. No game or system settings are changed.',
                                         wraplength=800, justify='left')
        self.record_status.pack(anchor='w', pady=4)

    def capture(self):
        script = Path(__file__).parent / 'tools/capture_performance_frames.ps1'
        tool = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'SynthScan/tools/PresentMon-2.6.0-x64.exe'
        if not tool.is_file():
            raise ValueError('The existing PresentMon 2.6 tool is unavailable. No software was downloaded or installed.')
        subprocess.Popen(['powershell.exe', '-NoProfile', '-File', str(script),
                          '-Seconds', '60', '-DelaySeconds', '10', '-Label', 'graphics-lab', '-Elevate'],
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.record_status.configure(text='Capture requested. Approve the Windows prompt if shown, then return to gameplay. '
                                         'After approval: 10-second preparation delay, then 60 seconds of recording. '
                                         'CSV/log files are in research/performance/runs. Import after completion; '
                                         'a request alone does not confirm a successful capture.')

    def record_run(self):
        values = {key: entry.get().strip() for key, entry in self.fields.items()}
        if any(not values[key] for key in ('scene', 'route', 'background_workload', 'driver_version')):
            raise ValueError('Fill scene, view/route, background apps and GPU driver so comparisons have controls.')
        source = filedialog.askopenfilename(parent=self, title='Select the game frame capture', filetypes=[('PresentMon CSV', '*.csv')])
        if not source:
            return
        if Path(source).stat().st_size > 50_000_000:
            raise ValueError('Choose a bounded capture smaller than 50 MB; long-session analysis belongs in the CLI.')
        frames = summarize_frame_csv(source)
        saved = snapshot()
        result = {'schema': 1, 'captured_at': utc_now(), **values, 'snapshot': saved,
                  'game_build': saved['build'].get('RequestedP4ChangeNum'), 'frames': frames,
                  'frame_csv': str(Path(source).resolve()), 'runtime_verified': bool(self.verified.get()),
                  'overrides_verified': bool(self.overrides.get()),
                  'frame_generation': False if self.generation.get() else None,
                  'settings_timestamp_note': 'Saved settings read at registration; user must verify they match the captured run.'}
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.json', initialdir=str(self.run_directory),
                                          initialfile='measured-run.json')
        if path:
            write_json(path, result)
            self.record_status.configure(text=f"Saved {Path(path).name}: {frames['average_fps']:.1f} FPS, "
                                              f"1% low {frames['one_percent_low_fps']:.1f}; p99 {frames['p99_ms']:.1f} ms.")

    def _build_compare(self, parent):
        bar = ctk.CTkFrame(parent, fg_color='transparent')
        bar.pack(fill='x')
        for key, label in [('A', 'Load baseline A'), ('B', 'Load variant B'), ('repeat', 'Load repeat A')]:
            self._button(bar, label, lambda key=key: self._guard(lambda: self.load_run(key)))
        self.loaded = ctk.CTkLabel(parent, text='No runs loaded', anchor='w', justify='left', wraplength=800)
        self.loaded.pack(fill='x', pady=6)
        self.setting = ctk.CTkOptionMenu(parent, values=[row[0] for row in CATALOG], width=350)
        self.setting.set('SysSpec_Shading')
        self.setting.pack(anchor='w', pady=5)
        bar = ctk.CTkFrame(parent, fg_color='transparent')
        bar.pack(fill='x')
        self._button(bar, 'Compare selected setting', lambda: self._guard(self.compare))
        self.results = ctk.CTkTextbox(parent, wrap='word', font=('Consolas', 13))
        self.results.pack(fill='both', expand=True, pady=6)
        self._set_text(self.results, 'Compare one setting with the same scene, route, background apps and driver.\n'
                       'Menu/loading frames and focus changes invalidate a gameplay comparison.\n'
                       '1% low means 1000 / average of the slowest 1% of frame intervals.\n'
                       'No automatic preset is selected from FPS alone.')

    def load_run(self, key):
        path = filedialog.askopenfilename(parent=self, initialdir=str(self.run_directory), filetypes=[('Measured run', '*.json')])
        if path:
            run = read_json(path)
            if not isinstance(run, dict) or not isinstance(run.get('snapshot'), dict) or not run.get('frames'):
                raise ValueError('Select a registered measured-run JSON, not a settings inventory or resource sample.')
            self.runs[key] = (path, run)
            self.loaded.configure(text='\n'.join(f'{key}: {Path(value[0]).name}' for key, value in self.runs.items()))

    def compare(self):
        if not {'A', 'B'}.issubset(self.runs):
            raise ValueError('Load baseline A and variant B first.')
        result = compare_runs(self.runs['A'][1], self.runs['B'][1], self.setting.get(),
                              self.runs['repeat'][1] if 'repeat' in self.runs else None)
        lines = [f"Evidence: {result['status']}", '']
        for key in ('A', 'B', 'repeat'):
            if key in self.runs:
                run = self.runs[key][1]
                f = run['frames']
                lines.extend([f"{key}: {f['average_fps']:.1f} FPS | 1% low {f['one_percent_low_fps']:.1f} | p99 {f['p99_ms']:.1f} ms",
                              f"  Quality: {run.get('visual_notes', 'Not assessed')}",
                              f"  Visibility: {run.get('visibility_notes', 'Not assessed')}"])
        for key, label in [('average_fps_change_pct', 'Average FPS change'), ('one_percent_low_change_pct', '1% low change'),
                           ('p99_ms_change_pct', 'p99 frame time change'), ('baseline_drift_pct', 'Baseline drift')]:
            if key in result:
                lines.append(f'{label}: {result[key]:+.2f}%')
        lines.extend(['', result['note']])
        if result['issues']:
            lines.extend(['', 'Do not attribute this difference to the setting yet:', *result['issues']])
        lines.extend(['', 'Saved setting differences:', json.dumps(result['differences'], indent=2)])
        self._set_text(self.results, '\n'.join(lines))

    def _guard(self, operation):
        try:
            operation()
        except (OSError, ValueError, KeyError, TypeError) as error:
            messagebox.showerror('Graphics Lab', str(error), parent=self)
