"""Blueprint library: compact browse pane and a detailed, sourced recipe view."""
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import ImageGrab

from crafting_catalog import get_catalog, material_coverage, quality_factor
from refinery_db import load_inventory
from screen_readers import read_image, fabricator_candidates
from game_library import ArtworkImages

BG, CARD, EDGE = '#181b22', '#1e222a', '#2c323e'
TEXT, MUTED, ACCENT, GOLD, GREEN = '#f8fafc', '#929eb1', '#b9cbe1', '#d99b43', '#48bb78'


class BlueprintLibraryPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app, self.catalog = app, get_catalog()
        self.images = ArtworkImages()
        self.selected_id = None
        self.page = 0
        self.pending = {}
        self._debounce = None
        self.pack(fill='both', expand=True)
        title = ctk.CTkFrame(self, fg_color='transparent')
        title.pack(fill='x', pady=(2, 12))
        ctk.CTkLabel(title, text='BLUEPRINT LIBRARY', font=('Bahnschrift', 23, 'bold'), text_color=TEXT).pack(side='left')
        self.stats = ctk.CTkLabel(title, text='', text_color=MUTED)
        self.stats.pack(side='right')
        actions = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        actions.pack(fill='x', pady=(0, 10))
        self.scan_button = ctk.CTkButton(actions, text='Scan fabricator', width=138, command=self.capture)
        self.scan_button.pack(side='left', padx=10, pady=10)
        ctk.CTkButton(actions, text='Open screenshot', width=135, command=self.open_image).pack(side='left', padx=4)
        ctk.CTkButton(actions, text='Paste image', width=100, command=self.paste).pack(side='left', padx=4)
        self.review_button = ctk.CTkButton(actions, text='Review scans (0)', width=145, command=self.review)
        self.review_button.pack(side='left', padx=4)
        ctk.CTkButton(actions, text='Read game logs', width=130, command=app.on_scan_blueprint_logs).pack(side='right', padx=10)
        self.notice = ctk.CTkLabel(self, text='Scan while browsing your fabricator. Review ownership before importing; existing records are preserved.',
                                   text_color=MUTED, anchor='w')
        self.notice.pack(fill='x', pady=(0, 8))
        if app.bp_manager.load_errors:
            self.notice.configure(text='A saved library file could not be read. Imports are blocked to preserve that file.', text_color=GOLD)
        self.search = ctk.CTkEntry(self, placeholder_text='Search items, materials, stats, missions or factions…', height=36)
        self.search.pack(fill='x', pady=(0, 8))
        self.search.bind('<KeyRelease>', self.schedule_refresh)
        filters = ctk.CTkFrame(self, fg_color='transparent')
        filters.pack(fill='x', pady=(0, 10))
        self.category = self._menu(filters, ['All'] + sorted({b['category'] for b in self.catalog.items}), 170)
        self.item_type = self._menu(filters, ['All'] + sorted({b['type'] for b in self.catalog.items}), 158)
        self.status = self._menu(filters, ['All items', 'With unlock sources', 'Available', 'Not recorded', 'Favorites'], 140)
        self.group = self._menu(filters, ['Category', 'Type', 'Manufacturer', 'Primary material'], 145)
        ctk.CTkButton(filters, text='Clear', width=65, command=self.clear_filters).pack(side='right')
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True)
        body.grid_columnconfigure(0, weight=2, minsize=290)
        body.grid_columnconfigure(1, weight=3, minsize=390)
        body.grid_rowconfigure(0, weight=1)
        self.browse = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=8)
        self.browse.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.detail = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=8)
        self.detail.grid(row=0, column=1, sticky='nsew')
        pager = ctk.CTkFrame(self, fg_color='transparent')
        pager.pack(fill='x', pady=(8, 0))
        self.prev = ctk.CTkButton(pager, text='Previous', width=90, command=lambda: self.change_page(-1))
        self.prev.pack(side='left')
        self.count = ctk.CTkLabel(pager, text='', text_color=MUTED)
        self.count.pack(side='left', padx=12)
        self.next = ctk.CTkButton(pager, text='Next', width=90, command=lambda: self.change_page(1))
        self.next.pack(side='left')
        ctk.CTkButton(pager, text='Library tools', width=100, fg_color='#303847', command=self.tools).pack(side='right', padx=(12, 0))
        ctk.CTkLabel(pager, text='SC 4.10.2 · Game data & reference catalog', text_color=MUTED).pack(side='right')
        self.refresh()

    def _menu(self, parent, values, width):
        menu = ctk.CTkOptionMenu(parent, values=values, width=width, fg_color='#303847',
                                  command=lambda _: self.refresh(reset=True))
        menu.pack(side='left', padx=(0, 7))
        return menu

    def schedule_refresh(self, event=None):
        if self._debounce:
            self.after_cancel(self._debounce)
        self._debounce = self.after(180, lambda: self.refresh(reset=True))

    def clear_filters(self):
        self.search.delete(0, 'end')
        self.category.set('All')
        self.item_type.set('All')
        self.status.set('All items')
        self.group.set('Category')
        self.refresh(reset=True)

    def change_page(self, amount):
        self.page += amount
        self.refresh()
        self.browse._parent_canvas.yview_moveto(0)

    def refresh(self, reset=False):
        self._debounce = None
        if reset:
            self.page = 0
        status = {'All items': 'ALL', 'With unlock sources': 'ALL', 'Available': 'OWNED', 'Not recorded': 'MISSING', 'Favorites': 'FAVORITES'}[self.status.get()]
        manager = self.app.bp_manager
        self.rows = self.catalog.library(manager.blueprints.copy(), manager.favorites.copy(), search=self.search.get(),
                                         category=self.category.get(), item_type=self.item_type.get(),
                                         status=status, group=self.group.get())
        if self.status.get() == 'With unlock sources':
            self.rows = [b for b in self.rows if b['sources'] or b['is_unlocked']]
        stats = manager.get_stats()
        self.stats.configure(text=f"{stats['total_owned']:,} available  /  {stats['total_catalog']:,} catalogued")
        self.page = max(0, min(self.page, (len(self.rows)-1)//40))
        current = next((r for r in self.rows if r['id'] == self.selected_id), None)
        if current is None and self.rows:
            current = self.rows[self.page * 40]
            self.selected_id = current['id']
        for child in self.browse.winfo_children():
            child.destroy()
        start = self.page * 40
        last_group = None
        for bp in self.rows[start:start+40]:
            if bp['group'] != last_group:
                self.label(self.browse, bp['group'].upper(), 11, GOLD, (12, 4), bold=True)
                last_group = bp['group']
            subtitle = bp['type']
            if bp.get('size') is not None:
                subtitle += f"  ·  S{bp['size']}"
            if bp.get('grade'):
                subtitle += f"  ·  Grade {bp['grade']}"
            badge = '✓ ' if bp['is_unlocked'] else '○ '
            if bp['is_favorite']:
                badge += '★ '
            ctk.CTkButton(self.browse, text=badge + bp['name'] + '\n' + subtitle, anchor='w',
                          image=self.images.blueprint(bp, 42), compound='left',
                          height=56, corner_radius=5, font=('Bahnschrift', 13),
                          fg_color='#354155' if bp['id'] == self.selected_id else '#262b35',
                          hover_color='#354155', text_color=TEXT,
                          command=lambda b=bp: self.select(b)).pack(fill='x', padx=3, pady=3)
        self.count.configure(text=f"{len(self.rows):,} results  ·  Page {self.page+1} of {max(1, (len(self.rows)+39)//40)}")
        self.prev.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if start+40 < len(self.rows) else 'disabled')
        if current is None:
            self.selected_id = None
        if self.rows:
            self.show_detail(current or self.rows[start])
        else:
            for child in self.detail.winfo_children():
                child.destroy()
            self.label(self.detail, 'No matching blueprints. Try fewer filters.', 15)

    def label(self, parent, text, size=13, color=TEXT, pady=(4, 4), bold=False):
        widget = ctk.CTkLabel(parent, text=text, font=('Bahnschrift', size, 'bold' if bold else 'normal'),
                              text_color=color, anchor='w', justify='left', wraplength=460)
        widget.pack(fill='x', padx=14, pady=pady)
        # Keep paragraphs readable as the detail pane changes size.
        widget.bind('<Configure>', lambda event: widget.configure(wraplength=max(120, event.width-4)))
        return widget

    def select(self, bp):
        self.selected_id = bp['id']
        self.refresh()
        self.detail._parent_canvas.yview_moveto(0)

    def show_detail(self, bp):
        self.selected_id = bp['id']
        for child in self.detail.winfo_children():
            child.destroy()
        image = self.images.blueprint(bp, 144)
        if image:
            ctk.CTkLabel(self.detail, text='', image=image).pack(anchor='w', padx=14, pady=(14, 0))
        self.label(self.detail, bp['name'], 24, pady=(18, 5), bold=True)
        metadata = [bp['type'], bp.get('manufacturer'), bp.get('item_class')]
        if bp.get('size') is not None:
            metadata.append(f"Size {bp['size']}")
        if bp.get('grade'):
            metadata.append(f"Grade {bp['grade']}")
        self.label(self.detail, '  ·  '.join(str(v) for v in metadata if v), color=MUTED)
        self.label(self.detail, bp['ownership_source'], color=GREEN if bp['is_unlocked'] else MUTED)
        if bp.get('native_verified'):
            version = self.catalog.data['native_provenance']['build']['RequestedP4ChangeNum']
            self.label(self.detail, f'Recipe inputs verified against your installed game · build {version}', 12, GREEN)
        elif bp.get('slots'):
            self.label(self.detail, 'Reference recipe · local verification is incomplete for this entry', 12, GOLD)
        if bp.get('description'):
            self.label(self.detail, bp['description'], 13, MUTED)
        buttons = ctk.CTkFrame(self.detail, fg_color='transparent')
        buttons.pack(fill='x', padx=14, pady=8)
        ctk.CTkButton(buttons, text='★ Saved' if bp['is_favorite'] else '☆ Save', width=100,
                      command=lambda: self.favorite(bp)).pack(side='left', padx=(0, 8))
        if not bp['is_unlocked']:
            ctk.CTkButton(buttons, text='Mark owned', width=120, command=lambda: self.mark_owned(bp)).pack(side='left')
        elif not bp.get('known_from_start'):
            ctk.CTkButton(buttons, text='Clear ownership record', width=165, fg_color='#303847', command=lambda: self.clear_owned(bp)).pack(side='left')
        if bp['slots']:
            ctk.CTkButton(self.detail, text='Plan a mining trip for these ingredients →', fg_color='#303847',
                          command=lambda: self.app.open_material_picker([s['material'] for s in bp['slots']])).pack(fill='x', padx=14, pady=8)
        if bp.get('seconds'):
            self.label(self.detail, f"Fabrication time  {int(bp['seconds']//60)}m {bp['seconds']%60:02g}s", color=MUTED)
        self.label(self.detail, 'MATERIALS & QUALITY EFFECTS', 12, GOLD, (18, 6), True)
        self.label(self.detail, 'Preview applies one quality to every slot and shows recipe factors, not absolute item stats. Coverage uses your local vault; check location at the fabricator.', 12, MUTED)
        preview = ctk.CTkFrame(self.detail, fg_color='#262b35')
        preview.pack(fill='x', padx=14, pady=6)
        qlabel = self.label(preview, 'Preview quality 1000', color=ACCENT)
        effects_labels = []
        def update_quality(value):
            q = int(value)
            qlabel.configure(text=f'Preview quality {q}')
            for label, slot in effects_labels:
                label.configure(text=self.effect_text(slot, q))
        ctk.CTkSlider(preview, from_=1, to=1000, number_of_steps=999, command=update_quality).pack(fill='x', padx=14, pady=10)
        preview.winfo_children()[-1].set(1000)
        for slot in material_coverage(bp, load_inventory()):
            card = ctk.CTkFrame(self.detail, fg_color='#262b35', corner_radius=6)
            card.pack(fill='x', padx=14, pady=5)
            image = self.images.material(slot['material'], 42)
            if image:
                ctk.CTkLabel(card, text='', image=image).pack(anchor='w', padx=14, pady=(8, 0))
            self.label(card, f"{slot['name']}  ·  {slot['material']}", 14, bold=True)
            self.label(card, f"{slot['amount']:g} {slot['unit']}  ·  Minimum quality {slot['min_quality']}", color=ACCENT)
            text = f"Local qualifying stock: {slot['available']:g} / {slot['amount']:g} {slot['unit']}"
            if slot['unit'] == 'units':
                text = 'Unit-count stock is not tracked in the SCU vault.'
            self.label(card, text, 12, GREEN if not slot['missing'] else MUTED)
            if slot['unit'] == 'SCU':
                stock = [(o['station'], p) for o in self.app.refinery_orders.snapshot()
                         if o['status'] == 'completed' and not o.get('collected_at')
                         for p in o['parts'] if p['material'] == slot['material']]
                for station, part in stock:
                    self.label(card, f"At {station}: {part['scu']:g} SCU · Q{part['quality']} · awaiting collection", 12, ACCENT)
            effect_label = self.label(card, self.effect_text(slot, 1000), 12)
            effects_labels.append((effect_label, slot))
            material = self.catalog.materials.get(slot['material'], {})
            bands = material.get('quality_bands', [])
            if bands:
                self.label(card, 'Mined qualities: ' + ' · '.join(map(str, bands)), 11, MUTED)
            ctk.CTkButton(card, text='Where to mine this material →', fg_color='transparent', anchor='w',
                          text_color=ACCENT, command=lambda m=slot['material']: self.app.open_material_picker([m])).pack(fill='x', padx=8, pady=(0, 6))
        if not bp['slots']:
            self.label(self.detail, 'No sourced recipe is available for this legacy record. Generic costs have been removed.', color=MUTED)
        self.label(self.detail, 'HOW TO UNLOCK', 12, GOLD, (20, 6), True)
        if bp.get('known_from_start'):
            self.label(self.detail, 'Available from the start in the source game build.', color=GREEN)
        missions = self.catalog.sources(bp)
        if not missions and not bp.get('known_from_start'):
            self.label(self.detail, 'No unlock mission is listed in this dataset. This does not establish that the item is obtainable in the current patch.', color=MUTED)
        for mission in missions:
            card = ctk.CTkFrame(self.detail, fg_color='#262b35', corner_radius=6)
            card.pack(fill='x', padx=14, pady=5)
            self.label(card, mission['title'], 15, bold=True)
            self.label(card, '  ·  '.join(v for v in (mission['faction'], mission['system']) if v), color=ACCENT)
            self.label(card, f"Required rank: {mission['standing'] or 'Not specified'}  ·  Cooldown: {mission['cooldown']} min", 12, MUTED)
            self.label(card, f"Reward roll: {mission['chance']}% for a pool of {mission['pool_size']} blueprints. This is not an individual blueprint drop rate.", 12, MUTED)
            if mission['illegal']:
                self.label(card, 'Illegal contract', 12, GOLD)
            if mission['once_only']:
                self.label(card, 'Once-only contract', 12, GOLD)
            ctk.CTkButton(card, text='Mission briefing & reward pool', fg_color='transparent', anchor='w',
                          command=lambda m=mission: self.show_mission(m)).pack(fill='x', padx=8, pady=5)
        self.label(self.detail, 'Verified recipes use your installed game records. Other recipes and mission annotations use the reference catalog (4.10.2). Reference stat curves are labelled where local decoding was incomplete. Source credits are in Library tools.', 11, MUTED, (20, 14))

    @staticmethod
    def effect_text(slot, quality):
        if quality < slot['min_quality']:
            return 'This quality is below the recipe requirement.'
        if not slot['effects']:
            return 'No stat effect is listed for this slot.'
        rows = []
        for effect in slot['effects']:
            factor = quality_factor(effect, quality)
            if factor is None:
                rows.append(effect['stat'] + ': curve not decoded')
                continue
            text = f"{effect['stat']}: ×{factor:.4f}"
            if effect['better'] in ('higher', 'lower'):
                text += f" ({effect['better']} is better)"
            if effect.get('local_decode_unknown'):
                text += ' · reference curve'
            rows.append(text)
        return '\n'.join(rows)

    def text_dialog(self, title, text):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry('730x580')
        textbox = ctk.CTkTextbox(dialog, wrap='word', font=('Bahnschrift', 14))
        textbox.pack(fill='both', expand=True, padx=18, pady=18)
        textbox.insert('1.0', text)
        textbox.configure(state='disabled')
        return dialog

    def show_locations(self, material):
        rows = material.get('locations', [])
        text = '\n\n'.join(f"{r['system']} / {r['location']}  ·  {r['family']} mining\n{r['note']}".strip() for r in rows)
        self.text_dialog(material.get('name', 'Material') + ' — locations',
                         (text or 'No mining location is listed in this dataset.') + '\n\nSource: imported location reference, game build 4.10.0. Use Mining planner for the current local presets. Source credits are in Library tools.')

    def show_mission(self, mission):
        details = f"{mission['title']}\n{mission['faction']}\n{mission['system']}\n\n{mission['briefing']}\n\n"
        details += f"Time limit: {mission['minutes']} min (0 = unspecified)\nCompletion cooldown: {mission['cooldown']} min\nAbandon cooldown: {mission['abandon_cooldown']} min (-1 = never again)\n"
        details += f"Reputation reward: {mission['reputation'] or 'Not specified'}\nRisk: {mission['risk_text'] or 'Not specified'}\n\nReward pool:\n"
        details += '\n'.join(mission['reward_pool']) or 'Not named'
        self.text_dialog(mission['title'], details)

    def tools(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title('Blueprint library tools')
        dialog.geometry('560x350')
        ctk.CTkButton(dialog, text='Third-party licenses & data sources', command=self.show_sources).pack(padx=20,pady=8,fill='x')
        self.label(dialog, 'Localization tools', 22, bold=True)
        self.label(dialog, 'These existing tools write or restore the game’s localization file. The catalog and screen reader work independently of localization changes.', color=MUTED)
        ctk.CTkButton(dialog, text='Sync SynthStrings to global.ini', command=self.app.on_sync_synthstrings_click).pack(padx=20, pady=8, fill='x')
        self.app.btn_restore_ini = ctk.CTkButton(dialog, text='Restore original localization', command=self.app.on_restore_synthstrings)
        self.app.btn_restore_ini.pack(padx=20, pady=8, fill='x')
        ctk.CTkButton(dialog, text='Verify patch & adapt localization', command=self.app.on_force_patch_check).pack(padx=20, pady=8, fill='x')

    def show_sources(self):
        from pathlib import Path
        self.text_dialog('Licenses & data sources', (Path(__file__).parent/'LICENSES.md').read_text(encoding='utf-8'))

    def favorite(self, bp):
        self.app.bp_manager.toggle_favorite(bp['name'] if self.catalog.resolve(bp['name']) or bp['id'].startswith('legacy:') else 'catalog:' + bp['id'])
        self.refresh()

    def mark_owned(self, bp):
        self.app.bp_manager.unlock_batch([bp], source='Manual ownership confirmation')
        self.refresh()

    def clear_owned(self, bp):
        self.app.bp_manager.remove_blueprint('catalog:' + bp['id'] if not self.catalog.resolve(bp['name']) and not bp['id'].startswith('legacy:') else bp['name'])
        self.refresh()

    def open_image(self):
        path = filedialog.askopenfilename(parent=self, title='Fabricator screenshot', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp')])
        if path:
            self.analyze(path)

    def paste(self):
        image = ImageGrab.grabclipboard()
        if hasattr(image, 'convert'):
            self.analyze(image)
        else:
            self.notice.configure(text='Copy a fabricator screenshot to the clipboard first.')

    def capture(self):
        # Reuse the existing monitor choice without typing or changing game state.
        same_monitor = self.app._detect_current_ui_monitor() == self.app.cfg.get('game_monitor', 1)
        if same_monitor:
            self.app.root.withdraw()
            self.after(180, lambda: self.capture_now(True))
        else:
            self.capture_now(False)

    def capture_now(self, restore):
        try:
            image = self.app.detector.grab_full_game_monitor_pil()
        except Exception as exc:
            self.notice.configure(text='Screen capture failed: ' + str(exc))
            return
        finally:
            if restore:
                self.app.root.deiconify()
        self.analyze(image)

    def analyze(self, image):
        self.scan_button.configure(state='disabled')
        self.notice.configure(text='Reading fabricator screenshot…')
        def worker():
            try:
                candidates, error = fabricator_candidates(read_image(image)), None
            except Exception as exc:
                candidates, error = [], str(exc)
            # The main UI event pump owns all Tk calls.
            self.app.ui_events.put(('fabricator_scan', (candidates, error), None))
        threading.Thread(target=worker, daemon=True).start()

    def scan_finished(self, candidates, error=None):
        self.scan_button.configure(state='normal')
        if error:
            self.notice.configure(text='Scan failed: ' + error)
            return
        self.app.fabricator_inbox.add(candidates)
        self.add_candidates(candidates)
        self.notice.configure(text=f'{len(candidates)} exact item names read. Review the list and select the blueprints you own.' if candidates else 'No exact catalog names read. Keep the fabricator title and full item names visible; partial names are rejected.')

    def add_candidates(self, candidates):
        for candidate in candidates:
            self.pending[candidate['id']] = candidate
        self.review_button.configure(text=f'Review scans ({len(self.pending)})')

    def review(self):
        if not self.pending:
            self.notice.configure(text='Scan a fabricator screen or open a screenshot to collect candidates.')
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title('Review fabricator scan')
        dialog.geometry('690x620')
        self.label(dialog, 'Select the blueprints you own', 22, bold=True)
        self.label(dialog, 'Visible names can include locked entries. Nothing is imported until you select it. Scans accumulate as you browse.', color=MUTED)
        choices = {}
        selection = ctk.CTkFrame(dialog, fg_color='transparent')
        selection.pack(fill='x', padx=15, pady=4)
        ctk.CTkButton(selection, text='Select all', width=110, command=lambda: [v.set(True) for v in choices.values()]).pack(side='left', padx=5)
        ctk.CTkButton(selection, text='Select none', width=110, command=lambda: [v.set(False) for v in choices.values()]).pack(side='left', padx=5)
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill='both', expand=True, padx=15, pady=10)
        for candidate in sorted(self.pending.values(), key=lambda c: c['name']):
            var = tk.BooleanVar(master=dialog, value=False)
            choices[candidate['id']] = var
            ctk.CTkCheckBox(scroll, text=f"{candidate['name']}  ·  OCR {candidate['confidence']:.0%}", variable=var).pack(anchor='w', padx=10, pady=9)
        def save():
            chosen = [self.pending[key] for key, var in choices.items() if var.get()]
            try:
                added = self.app.bp_manager.unlock_batch(chosen, source='Fabricator scan — user confirmed')
            except Exception as exc:
                self.notice.configure(text='Import failed; scan candidates retained: ' + str(exc))
                return
            self.app.fabricator_inbox.remove([key for key, var in choices.items() if var.get()])
            for key, var in choices.items():
                if var.get():
                    self.pending.pop(key, None)
            self.review_button.configure(text=f'Review scans ({len(self.pending)})')
            self.notice.configure(text=f'{added} new owned blueprints imported. Existing ownership and favorites were preserved.')
            dialog.destroy()
            self.refresh()
        ctk.CTkButton(dialog, text='Import selected ownership', command=save).pack(pady=(0, 15))
