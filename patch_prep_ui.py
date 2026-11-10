"""Pre-patch and Release Candidate UI panel for SynthScan Settings.

Follows DESIGN.md standards:
- Deep navy/gunmetal surfaces, rounded cards, generous spacing, clear typography.
- Concise player-facing descriptions; technical details behind tooltips/notes.
- Safe asynchronous execution with thread-safe UI updates.
- Protects active game: clearly indicates when disk space or running processes require attention.
"""

from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from patch_prep import (
    backup_control_mappings,
    clear_shader_cache,
    deploy_ptu_to_live,
    get_patch_status,
    seed_ptu_from_live,
)

# Visual styling constants consistent with SynthScan theme
SC_BG_CARD = '#1e222a'
SC_BG_CARD_ALT = '#262b35'
SC_BG_PANEL = '#181b22'
SC_BORDER_DIM = '#2c323e'
SC_BORDER_CYAN = '#566275'
SC_TEXT_BRIGHT = '#f8fafc'
SC_TEXT_CYAN = '#d0d7e2'
SC_TEXT_AMBER = '#62ccff'
SC_TEXT_GREEN = '#48bb78'
SC_TEXT_RED = '#e05260'
SC_TEXT_MUTED = '#7e889b'
FONT_TECH = 'Bahnschrift'
FONT_MONO = 'Consolas'


class PatchPrepCard(ctk.CTkFrame):
    """Integrated Settings card for automated Star Citizen pre-patch prep & Release Candidate staging."""

    def __init__(self, parent, on_status_change=None):
        super().__init__(
            parent,
            fg_color=SC_BG_CARD,
            corner_radius=4,
            border_width=1,
            border_color=SC_BORDER_DIM,
        )
        self.pack(fill='x', pady=(0, 10))
        self.on_status_change = on_status_change
        self._is_busy = False

        self._build_header()
        self._build_status_strip()
        self._build_action_cards()
        self._build_progress_bar()

        # Initial background status load
        self.after(200, self.refresh_status)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color='transparent')
        hdr.pack(fill='x', padx=14, pady=(12, 4))

        ctk.CTkLabel(
            hdr,
            text='// PATCH PREPARATION & RELEASE CANDIDATE STAGING',
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight='bold'),
            text_color=SC_TEXT_CYAN,
        ).pack(side='left')

        self.btn_refresh = ctk.CTkButton(
            hdr,
            text='[ REFRESH STATUS ]',
            command=self.refresh_status,
            fg_color=SC_BG_CARD_ALT,
            hover_color='#343c4a',
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight='bold'),
            height=24,
            width=120,
        )
        self.btn_refresh.pack(side='right')

        ctk.CTkLabel(
            self,
            text='Stage upcoming patch builds from PTU test servers without interrupting your active game. '
                 'Back up controls and purge stale shader cache with one click.',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED,
            wraplength=800,
            justify='left',
        ).pack(anchor='w', padx=14, pady=(0, 8))

    def _build_status_strip(self):
        strip = ctk.CTkFrame(self, fg_color=SC_BG_PANEL, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        strip.pack(fill='x', padx=14, pady=(0, 10))

        # Channel versions
        col1 = ctk.CTkFrame(strip, fg_color='transparent')
        col1.pack(side='left', fill='y', padx=12, pady=8)
        self.lbl_live_version = ctk.CTkLabel(
            col1,
            text='LIVE: Detecting...',
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight='bold'),
            text_color=SC_TEXT_BRIGHT,
            anchor='w',
        )
        self.lbl_live_version.pack(anchor='w')
        self.lbl_ptu_version = ctk.CTkLabel(
            col1,
            text='PTU: Detecting...',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED,
            anchor='w',
        )
        self.lbl_ptu_version.pack(anchor='w')

        # Storage & Space
        col2 = ctk.CTkFrame(strip, fg_color='transparent')
        col2.pack(side='left', fill='y', padx=16, pady=8)
        self.lbl_drive_space = ctk.CTkLabel(
            col2,
            text='Drive Space: Checking...',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_CYAN,
            anchor='w',
        )
        self.lbl_drive_space.pack(anchor='w')
        self.lbl_rc_status = ctk.CTkLabel(
            col2,
            text='Release Candidate: Checking...',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_AMBER,
            anchor='w',
        )
        self.lbl_rc_status.pack(anchor='w')

        # Controls & Shaders
        col3 = ctk.CTkFrame(strip, fg_color='transparent')
        col3.pack(side='left', fill='y', padx=16, pady=8)
        self.lbl_controls_info = ctk.CTkLabel(
            col3,
            text='Controls: Checking...',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_BRIGHT,
            anchor='w',
        )
        self.lbl_controls_info.pack(anchor='w')
        self.lbl_shaders_info = ctk.CTkLabel(
            col3,
            text='Shader Cache: Checking...',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED,
            anchor='w',
        )
        self.lbl_shaders_info.pack(anchor='w')

        # Running process warning badge
        self.lbl_proc_warning = ctk.CTkLabel(
            strip,
            text='',
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight='bold'),
            text_color=SC_TEXT_AMBER,
            anchor='e',
        )
        self.lbl_proc_warning.pack(side='right', padx=14, pady=8)

    def _build_action_cards(self):
        grid = ctk.CTkFrame(self, fg_color='transparent')
        grid.pack(fill='x', padx=14, pady=(0, 10))

        # CARD 1: Deploy PTU to LIVE (Fast Patch Day Swap)
        card1 = ctk.CTkFrame(grid, fg_color=SC_BG_CARD_ALT, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        card1.pack(side='left', fill='both', expand=True, padx=(0, 6))

        ctk.CTkLabel(
            card1,
            text='FAST PATCH DAY DEPLOY',
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight='bold'),
            text_color=SC_TEXT_GREEN,
            anchor='w',
        ).pack(anchor='w', padx=12, pady=(10, 2))

        ctk.CTkLabel(
            card1,
            text='Promotes tested PTU Release Candidate to LIVE in seconds. Backs up control mappings and purges stale shaders.',
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=SC_TEXT_MUTED,
            wraplength=250,
            justify='left',
            anchor='w',
        ).pack(anchor='w', padx=12, pady=(0, 8))

        self.btn_deploy = ctk.CTkButton(
            card1,
            text='[ DEPLOY PTU TO LIVE ]',
            command=self._on_deploy_clicked,
            fg_color='#18231c',
            hover_color='#223227',
            border_width=1,
            border_color='#2f573c',
            text_color='#48bb78',
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight='bold'),
            height=30,
        )
        self.btn_deploy.pack(fill='x', padx=12, pady=(4, 10))

        # CARD 2: Seed PTU from LIVE (Pre-load Test Server)
        card2 = ctk.CTkFrame(grid, fg_color=SC_BG_CARD_ALT, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        card2.pack(side='left', fill='both', expand=True, padx=3)

        ctk.CTkLabel(
            card2,
            text='PRE-LOAD PTU FROM LIVE',
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight='bold'),
            text_color=SC_TEXT_CYAN,
            anchor='w',
        ).pack(anchor='w', padx=12, pady=(10, 2))

        self.lbl_clone_desc = ctk.CTkLabel(
            card2,
            text='Clones current files to PTU so you only download tiny delta updates. Your LIVE game remains 100% playable.',
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=SC_TEXT_MUTED,
            wraplength=250,
            justify='left',
            anchor='w',
        )
        self.lbl_clone_desc.pack(anchor='w', padx=12, pady=(0, 8))

        self.btn_seed = ctk.CTkButton(
            card2,
            text='[ SEED PTU FROM LIVE ]',
            command=self._on_seed_clicked,
            fg_color='#1d2430',
            hover_color='#283243',
            border_width=1,
            border_color='#3c4b64',
            text_color=SC_TEXT_CYAN,
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight='bold'),
            height=30,
        )
        self.btn_seed.pack(fill='x', padx=12, pady=(4, 10))

        # CARD 3: Maintenance (Shaders, Controls & Characters)
        card3 = ctk.CTkFrame(grid, fg_color=SC_BG_CARD_ALT, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        card3.pack(side='left', fill='both', expand=True, padx=(6, 0))

        ctk.CTkLabel(
            card3,
            text='PROFILE & SHADER CLEANER',
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight='bold'),
            text_color=SC_TEXT_AMBER,
            anchor='w',
        ).pack(anchor='w', padx=12, pady=(10, 2))

        ctk.CTkLabel(
            card3,
            text='Backs up keybinds, character appearances (.chf) and settings, and purges compiled shaders to stop stutters.',
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=SC_TEXT_MUTED,
            wraplength=250,
            justify='left',
            anchor='w',
        ).pack(anchor='w', padx=12, pady=(0, 8))

        self.btn_clean = ctk.CTkButton(
            card3,
            text='[ BACKUP PROFILE & PURGE SHADERS ]',
            command=self._on_clean_clicked,
            fg_color='#252621',
            hover_color='#36382c',
            border_width=1,
            border_color='#5c5737',
            text_color='#d8c168',
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight='bold'),
            height=30,
        )
        self.btn_clean.pack(fill='x', padx=12, pady=(4, 10))

    def _build_progress_bar(self):
        self.prog_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.prog_frame.pack(fill='x', padx=14, pady=(0, 8))

        self.lbl_progress = ctk.CTkLabel(
            self.prog_frame,
            text='',
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_CYAN,
            anchor='w',
        )
        self.lbl_progress.pack(fill='x')

        self.progress_bar = ctk.CTkProgressBar(
            self.prog_frame,
            progress_color=SC_TEXT_AMBER,
            fg_color=SC_BG_PANEL,
            height=6,
        )
        self.progress_bar.set(0)
        # Hidden when not active
        self.progress_bar.pack_forget()

    def refresh_status(self):
        """Asynchronously updates game installation and release candidate metrics."""
        def worker():
            try:
                status = get_patch_status()
            except Exception as e:
                status = {'error': str(e)}
            self.after(0, lambda: self._apply_status(status))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_status(self, status: dict):
        if 'error' in status:
            self.lbl_live_version.configure(text=f"Status error: {status['error']}", text_color=SC_TEXT_RED)
            return

        live = status['live']
        ptu = status['ptu']
        space = status['drive_space']
        procs = status['processes']
        shaders = status['shader_cache']
        backup = status['latest_controls_backup']

        # LIVE version
        if live['exists']:
            self.lbl_live_version.configure(
                text=f"LIVE: {live['version']} ({live['branch']})",
                text_color=SC_TEXT_BRIGHT,
            )
        else:
            self.lbl_live_version.configure(text='LIVE: Not Detected', text_color=SC_TEXT_RED)

        # PTU version
        if ptu['exists']:
            self.lbl_ptu_version.configure(
                text=f"PTU: {ptu['version']} ({ptu['p4k_size_gb']} GB)",
                text_color=SC_TEXT_GREEN if status['rc_detected'] else SC_TEXT_CYAN,
            )
        else:
            self.lbl_ptu_version.configure(text='PTU: Not Installed', text_color=SC_TEXT_MUTED)

        # Drive Space
        self.lbl_drive_space.configure(
            text=f"SSD Space: {space['free_gb']} GB free / {space['total_gb']} GB",
            text_color=SC_TEXT_CYAN if space['free_gb'] >= 100 else SC_TEXT_AMBER,
        )

        # Release Candidate status
        self.lbl_rc_status.configure(
            text=f"Status: {status['rc_status_text']}",
            text_color=SC_TEXT_GREEN if status['rc_detected'] else SC_TEXT_MUTED,
        )

        # Controls, Characters & Shaders
        backup_chars = backup.get('character_count', 0) if backup else 0
        live_chars = live.get('character_count', 0)
        char_desc = f"{live_chars} .chf found" if live_chars else "no .chf"
        backup_text = backup['timestamp'] if backup else 'None yet'
        self.lbl_controls_info.configure(
            text=f"Profile: Keybinds {'OK' if live['has_controls'] else 'Missing'} · Characters: {char_desc} (Backup: {backup_text})",
            text_color=SC_TEXT_BRIGHT if live['has_controls'] else SC_TEXT_MUTED,
        )
        self.lbl_shaders_info.configure(
            text=f"Shader Cache: {shaders['file_count']} files ({shaders['size_mb']} MB)",
            text_color=SC_TEXT_AMBER if shaders['file_count'] > 0 else SC_TEXT_MUTED,
        )

        # Running process alert
        if procs['game_running']:
            self.lbl_proc_warning.configure(text='Star Citizen Running (Close to Deploy)')
            self.btn_deploy.configure(state='disabled')
            self.btn_seed.configure(state='disabled')
        elif procs['launcher_running']:
            self.lbl_proc_warning.configure(text='RSI Launcher Open (Close to Deploy)')
            self.btn_deploy.configure(state='disabled')
            self.btn_seed.configure(state='disabled')
        else:
            self.lbl_proc_warning.configure(text='Ready (Game & Launcher Closed)')
            self.btn_deploy.configure(state='normal' if ptu['has_p4k'] else 'disabled')
            self.btn_seed.configure(state='normal' if status['can_clone'] else 'disabled')

        # Clone button helper text if space is tight
        if not status['can_clone'] and live['has_p4k']:
            self.lbl_clone_desc.configure(
                text=f"Needs {status['needed_for_clone_gb']} GB free SSD to keep both versions simultaneously (Drive has {space['free_gb']} GB). Wait for patch day swap.",
                text_color='#d99b43',
            )
        else:
            self.lbl_clone_desc.configure(
                text='Clones current files to PTU so you only download tiny delta updates. Your LIVE game remains 100% playable.',
                text_color=SC_TEXT_MUTED,
            )

    def _set_busy(self, busy: bool, message: str = ''):
        self._is_busy = busy
        self.lbl_progress.configure(text=message)
        if busy:
            self.progress_bar.pack(fill='x', pady=(4, 0))
            self.btn_refresh.configure(state='disabled')
            self.btn_deploy.configure(state='disabled')
            self.btn_seed.configure(state='disabled')
            self.btn_clean.configure(state='disabled')
        else:
            self.progress_bar.pack_forget()
            self.btn_refresh.configure(state='normal')
            self.btn_clean.configure(state='normal')
            self.refresh_status()

    def _on_deploy_clicked(self):
        confirm = messagebox.askyesno(
            'Confirm Patch Deployment',
            'This will promote your tested PTU Release Candidate to LIVE.\n\n'
            '• Control mappings (actionmaps.xml) will be backed up and restored automatically.\n'
            '• Compiled shader caches will be purged to prevent visual glitches.\n'
            '• Swap completes instantly (0 seconds copy time).\n\n'
            'Proceed with deployment?',
            parent=self.winfo_toplevel(),
        )
        if not confirm:
            return

        self._set_busy(True, 'Deploying PTU Release Candidate to LIVE...')
        self.progress_bar.set(0.1)

        def worker():
            try:
                def prog(msg, frac):
                    self.after(0, lambda m=msg, f=frac: (self.lbl_progress.configure(text=m), self.progress_bar.set(f)))

                res = deploy_ptu_to_live(progress_callback=prog)
                self.after(0, lambda: self._on_operation_done(True, res['message']))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_operation_done(False, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_seed_clicked(self):
        confirm = messagebox.askyesno(
            'Confirm PTU Pre-Load',
            'This will clone your LIVE game files into PTU.\n\n'
            '• Your LIVE game will remain 100% playable.\n'
            '• Open the RSI Launcher after this finishes to download only the test delta.\n\n'
            'Start cloning?',
            parent=self.winfo_toplevel(),
        )
        if not confirm:
            return

        self._set_busy(True, 'Seeding PTU from LIVE...')
        self.progress_bar.set(0.05)

        def worker():
            try:
                def prog(msg, frac):
                    self.after(0, lambda m=msg, f=frac: (self.lbl_progress.configure(text=m), self.progress_bar.set(f)))

                res = seed_ptu_from_live(progress_callback=prog)
                self.after(0, lambda: self._on_operation_done(True, res['message']))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_operation_done(False, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_clean_clicked(self):
        self._set_busy(True, 'Backing up controls and purging shaders...')
        self.progress_bar.set(0.3)

        def worker():
            try:
                b_res = backup_control_mappings()
                s_res = clear_shader_cache()
                char_msg = f"{b_res.get('character_count', 0)} character appearance(s)" if b_res.get('character_count') else "settings"
                msg = f"Keybinds and {char_msg} saved to AppData. Purged {s_res['deleted_files']} shader cache files ({s_res['freed_mb']} MB freed)."
                self.after(0, lambda: self._on_operation_done(True, msg))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_operation_done(False, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_operation_done(self, success: bool, message: str):
        self._set_busy(False, message)
        if success:
            messagebox.showinfo('SynthScan Patch Prep', message, parent=self.winfo_toplevel())
        else:
            messagebox.showerror('SynthScan Patch Prep', f'Operation stopped: {message}', parent=self.winfo_toplevel())
