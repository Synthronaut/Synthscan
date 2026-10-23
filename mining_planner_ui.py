"""Material picker with location ranking and separate same-rock compositions."""
import customtkinter as ctk
from mining_planner import get_mining_planner
from crafting_catalog import get_catalog
from game_library import ArtworkImages

BG, CARD, TEXT, MUTED, GOLD = '#181b22', '#1e222a', '#f8fafc', '#929eb1', '#d99b43'


class MiningPlannerPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.pack(fill='both', expand=True)
        self.app, self.planner = app, get_mining_planner()
        self.images = ArtworkImages()
        self.selected = None
        self.label(self, 'MATERIAL PICKER', 24, bold=True)
        version = self.planner.data['provenance']['build']['RequestedP4ChangeNum']
        source_label = 'Local game data' if self.planner.matches_installation else 'Saved reference · current installation differs or is unavailable'
        self.label(self, f'{source_label} · LIVE {version}', color=MUTED if self.planner.matches_installation else GOLD)
        filters = ctk.CTkFrame(self, fg_color=CARD)
        filters.pack(fill='x', pady=8)
        row = ctk.CTkFrame(filters, fg_color='transparent')
        row.pack(fill='x', padx=12, pady=10)
        self.target = ctk.CTkComboBox(row, values=self.planner.materials, width=170, command=lambda _: self.refresh())
        self.target.pack(side='left', padx=(0, 8))
        self.additional = ctk.CTkEntry(row, placeholder_text='Also need (comma separated)', width=245)
        self.additional.pack(side='left', padx=(0, 8))
        self.additional.bind('<Return>', lambda _: self.refresh())
        ctk.CTkButton(row, text='Find locations', width=120, command=self.refresh).pack(side='left')
        row2 = ctk.CTkFrame(filters, fg_color='transparent')
        row2.pack(fill='x', padx=12, pady=(0, 10))
        self.system = self.menu(row2, ['All', 'Stanton', 'Pyro', 'Nyx'], 115)
        self.family = self.menu(row2, ['Ship', 'ROC', 'FPS', 'All'], 100)
        self.mode = self.menu(row2, ['Primary ores', 'Include secondaries'], 155)
        row3 = ctk.CTkFrame(filters, fg_color='transparent')
        row3.pack(fill='x', padx=12, pady=(0, 10))
        self.quality = self.menu(row3, ['All quality scales', 'Full quality scale'], 160)
        self.sort = self.menu(row3, ['Primary prevalence', 'Configured material upper bound'], 220)
        self.note = self.label(self, 'Preset weights compare configured deposits within an equipment family. They are not a live spawn rate or guaranteed haul.', 12, MUTED)
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True, pady=8)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=2, minsize=270)
        body.grid_columnconfigure(1, weight=3, minsize=400)
        self.results = ctk.CTkScrollableFrame(body, fg_color=CARD)
        self.results.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.detail = ctk.CTkScrollableFrame(body, fg_color=CARD)
        self.detail.grid(row=0, column=1, sticky='nsew')
        self.refresh()

    def menu(self, parent, values, width):
        menu = ctk.CTkOptionMenu(parent, values=values, width=width, command=lambda _: self.refresh(), fg_color='#303847')
        menu.pack(side='left', padx=(0, 6))
        return menu

    def label(self, parent, text, size=13, color=TEXT, bold=False):
        widget = ctk.CTkLabel(parent, text=text, font=('Bahnschrift', size, 'bold' if bold else 'normal'),
                              text_color=color, anchor='w', justify='left', wraplength=480)
        widget.pack(fill='x', padx=12, pady=5)
        widget.bind('<Configure>', lambda e: widget.configure(wraplength=max(100, e.width-4)))
        return widget

    def set_targets(self, names):
        resolved = [self.planner.resolve_material(n) for n in names]
        resolved = list(dict.fromkeys(n for n in resolved if n))
        if not resolved:
            self.note.configure(text='No mining source is present for those ingredients in the local dataset.')
            return
        self.target.set(resolved[0])
        self.additional.delete(0, 'end')
        self.additional.insert(0, ', '.join(resolved[1:]))
        self.mode.set('Include secondaries')
        self.refresh()

    def refresh(self):
        targets = [self.target.get()] + [s.strip() for s in self.additional.get().split(',') if s.strip()]
        unknown = [t for t in targets if self.planner.resolve_material(t) is None]
        if unknown:
            self.note.configure(text='Unknown material: ' + ', '.join(unknown))
            return
        candidates = self.planner.candidates(targets, system=self.system.get(), family=self.family.get(),
                    primary_only=self.mode.get()=='Primary ores', min_quality_scale=1 if self.quality.get()=='Full quality scale' else 0,
                    sort=self.sort.get())
        for child in self.results.winfo_children():
            child.destroy()
        self.note.configure(text=f'{len(candidates)} location/equipment matches. All requested materials must occur in that location; they may be in different rocks. Weights are conditional preset comparisons, not live spawn rates.')
        current = None
        for candidate in candidates:
            location = candidate['location']
            key = location['id'] + candidate['family']
            if key == self.selected:
                current = candidate
            summary = '\n'.join(f"{t}: {m['primary_share']:.1%} primary" for t,m in candidate['matches'].items())
            ctk.CTkButton(self.results, text=f"{location['name']}\n{location['system']} · {candidate['family']}\n{summary}", anchor='w',
                          height=max(72, 48+18*len(candidate['matches'])), fg_color='#354155' if key==self.selected else '#262b35', hover_color='#354155',
                          font=('Bahnschrift', 13), command=lambda c=candidate: self.select(c)).pack(fill='x', padx=4, pady=4)
        if candidates:
            self.show_detail(current or candidates[0])
        else:
            for child in self.detail.winfo_children():
                child.destroy()
            self.label(self.detail, 'No matching locations. Try including secondaries or removing an additional ingredient.', 16)

    def select(self, candidate):
        self.selected = candidate['location']['id'] + candidate['family']
        self.show_detail(candidate)
        self.detail._parent_canvas.yview_moveto(0)

    def show_detail(self, candidate):
        for child in self.detail.winfo_children():
            child.destroy()
        location = candidate['location']
        self.label(self.detail, location['name'], 24, bold=True)
        self.label(self.detail, f"{location['system']} · {location['kind']} · {candidate['family']} mining", color=MUTED)
        if location.get('curated_alias'):
            self.label(self.detail, location['curated_alias']['note'], 12, GOLD)
        for target, match in candidate['matches'].items():
            image = self.images.material(target, 54)
            if image:
                ctk.CTkLabel(self.detail, text='', image=image).pack(anchor='w', padx=12, pady=5)
            self.label(self.detail, target, 17, GOLD, True)
            self.label(self.detail, f"Primary-ore preset weight: {match['primary_share']:.2%}\nPresets that can contain it: {match['containing_share']:.2%}\nConfigured material fraction upper bound: {match['maximum_material_weight']:.2%}", 12)
        self.label(self.detail, 'TARGET ROCKS & THEIR SECONDARIES', 12, GOLD, True)
        self.label(self.detail, 'Rows below belong to the same rock composition. Repeated ore names are separate quality-scaled portions; their ranges are not expected values.', 12, MUTED)
        for comp in self.planner.relevant_compositions(candidate):
            card = ctk.CTkFrame(self.detail, fg_color='#262b35')
            card.pack(fill='x', padx=12, pady=6)
            self.label(card, f"{comp['name']} · {comp['weight']:.2%} preset weight", 15, bold=True)
            for part in comp['parts']:
                role = 'primary' if part['material']==comp['primary'] else 'secondary'
                self.label(card, f"{part['material']} · {part['min_percent']:g}–{part['max_percent']:g}% · quality scale ×{part['quality_scale']:g} · {role}", 12)
                if part['probability'] != 1:
                    self.label(card, f"Configured inclusion probability: {part['probability']:g}. Sampling mechanics are not independently verified.", 11, MUTED)
        self.label(self.detail, 'CRAFTING USES', 12, GOLD, True)
        catalog = get_catalog()
        for target in candidate['requested']:
            uses = [b for b in catalog.items if any(self.planner.resolve_material(s['material'])==target for s in b['slots'])]
            self.label(self.detail, f"{target}: used by {len(uses)} catalog entries", 13)
            ctk.CTkButton(self.detail, text=f'Find blueprints using {target} →', fg_color='#303847',
                          command=lambda t=target: self.open_library(t)).pack(fill='x', padx=12, pady=5)
        self.label(self.detail, 'Numerical source: local Game2.dcb. Location labels: SCMDB. Internal/unlocated presets are excluded from the default route list. Travel time, live depletion, extraction losses and ship capability are not part of this ranking.', 11, MUTED)

    def open_library(self, material):
        self.app.switch_page('blueprints')
        page = self.app.blueprint_page
        page.clear_filters()
        page.search.insert(0, material)
        page.refresh(reset=True)
