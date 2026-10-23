"""Task-oriented entry to extracted items, resources, and blueprint workflows."""
import customtkinter as ctk
from crafting_catalog import get_catalog
from game_library import ArtworkImages, get_game_library

BG, CARD, TEXT, MUTED, GOLD = '#181b22', '#1e222a', '#f8fafc', '#929eb1', '#d99b43'


def label(parent, text, size=13, color=TEXT):
    widget = ctk.CTkLabel(parent, text=text, font=('Bahnschrift', size), text_color=color,
                          anchor='w', justify='left', wraplength=480)
    widget.pack(fill='x', padx=14, pady=6)
    widget.bind('<Configure>', lambda e: widget.configure(wraplength=max(120, e.width-4)))
    return widget


class GameLibraryPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG)
        self.pack(fill='both', expand=True)
        self.app, self.library = app, get_game_library()
        self.images = ArtworkImages(self.library)
        self.page, self.selected_id, self.pending_refresh = 0, None, None
        self.mode = ctk.CTkSegmentedButton(self, values=['Items', 'Materials', 'Blueprints'], command=self.set_mode)
        self.mode.pack(anchor='w', pady=(0, 10))
        self.reference = ctk.CTkFrame(self, fg_color=BG)
        label(self.reference, 'Game library', 26)
        provenance = self.library.data['provenance']
        self.note = label(self.reference, f"{len(self.library.entries):,} named records · {provenance.get('with_static_artwork', 0):,} with extracted icons", color=MUTED)
        if self.library.error:
            label(self.reference, 'Game library unavailable. Run Refresh_Game_Reference.bat in the SynthScan folder, then restart the app. Your saved blueprints and inventory are separate.', 13, GOLD)
        if not self.library.matches_installation:
            label(self.reference, 'Saved reference: current game build differs or is unavailable.', 12, GOLD)
        label(self.reference, 'Client records can include internal and unreleased variants. Listed here does not mean obtainable in the current universe.', 12, MUTED)
        self.search = ctk.CTkEntry(self.reference, placeholder_text='Find an item, material, manufacturer or description…', height=36)
        self.search.pack(fill='x', padx=14, pady=8)
        self.search.bind('<KeyRelease>', self.schedule_refresh)
        filters = ctk.CTkFrame(self.reference, fg_color='transparent')
        filters.pack(fill='x', padx=14, pady=6)
        self.category = ctk.CTkOptionMenu(filters, values=['All']+sorted({e['category'] for e in self.library.entries}),
                                         width=210, command=lambda _: self.refresh(True))
        self.category.pack(side='left', padx=(0, 10))
        self.art_only = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(filters, text='With icons', variable=self.art_only, command=lambda: self.refresh(True)).pack(side='left')
        ctk.CTkButton(filters, text='Clear', width=70, command=self.clear).pack(side='right')
        self.internal = ctk.BooleanVar(value=False)
        self.internal_toggle = ctk.CTkCheckBox(self.reference, text='Include internal fixtures & character parts', variable=self.internal,
                                              command=lambda: self.refresh(True))
        self.internal_toggle.pack(anchor='w', padx=14, pady=3)
        body = ctk.CTkFrame(self.reference, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=14, pady=8)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=2, minsize=270)
        body.grid_columnconfigure(1, weight=3, minsize=360)
        self.results = ctk.CTkScrollableFrame(body, fg_color=CARD)
        self.results.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.details = ctk.CTkScrollableFrame(body, fg_color=CARD)
        self.details.grid(row=0, column=1, sticky='nsew')
        pager = ctk.CTkFrame(self.reference, fg_color='transparent')
        pager.pack(fill='x', padx=14, pady=8)
        self.previous = ctk.CTkButton(pager, text='Previous', width=90, command=lambda: self.change_page(-1))
        self.previous.pack(side='left')
        self.count = label(pager, '', 12, MUTED)
        self.count.pack_forget()
        self.count.pack(side='left', padx=12)
        self.next = ctk.CTkButton(pager, text='Next', width=90, command=lambda: self.change_page(1))
        self.next.pack(side='left')
        self.blueprint_host = ctk.CTkFrame(self, fg_color=BG)
        self.set_mode('Items')

    def set_mode(self, mode):
        self.mode.set(mode)
        self.reference.pack_forget()
        self.blueprint_host.pack_forget()
        if mode == 'Blueprints':
            if not hasattr(self.app, 'blueprint_page'):
                from blueprint_library_ui import BlueprintLibraryPage
                self.app.blueprint_page = BlueprintLibraryPage(self.blueprint_host, self.app)
                self.app.blueprint_page.add_candidates(list(self.app.fabricator_pending.values()))
            self.blueprint_host.pack(fill='both', expand=True)
        else:
            self.category.set('All')
            categories = sorted({e['category'] for e in self.library.entries if e['kind']==('Material' if mode=='Materials' else 'Item')})
            self.category.configure(values=['All']+categories)
            self.reference.pack(fill='both', expand=True)
            self.refresh(True)

    def clear(self):
        self.search.delete(0, 'end')
        self.category.set('All')
        self.art_only.set(False)
        self.internal.set(False)
        self.refresh(True)

    def schedule_refresh(self, event=None):
        if self.pending_refresh:
            self.after_cancel(self.pending_refresh)
        self.pending_refresh = self.after(200, lambda: self.refresh(True))

    def change_page(self, delta):
        self.page += delta
        self.refresh()
        self.results._parent_canvas.yview_moveto(0)

    def refresh(self, reset=False):
        self.pending_refresh = None
        if reset:
            self.page = 0
        rows = self.library.query(self.search.get(), kind='Material' if self.mode.get()=='Materials' else 'Item',
                                  category=self.category.get(), artwork_only=self.art_only.get(), include_internal=self.internal.get())
        self.page = max(0, min(self.page, (len(rows)-1)//40))
        for child in self.results.winfo_children():
            child.destroy()
        current = next((r for r in rows if r['id']==self.selected_id), None)
        start = self.page*40
        for entry in rows[start:start+40]:
            image = self.images.get(entry, 46)
            ctk.CTkButton(self.results, text=entry['name']+'\n'+entry['type'], image=image, compound='left',
                          anchor='w', height=64, font=('Bahnschrift', 13), text_color=TEXT,
                          fg_color='#354155' if entry['id']==self.selected_id else '#262b35',
                          hover_color='#354155', command=lambda e=entry: self.select(e)).pack(fill='x', padx=3, pady=3)
        self.count.configure(text=f'{len(rows):,} results · {self.page+1} / {max(1,(len(rows)+39)//40)}')
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if start+40<len(rows) else 'disabled')
        for child in self.details.winfo_children():
            child.destroy()
        if rows:
            self.detail(current or rows[start])
        else:
            label(self.details, 'No matching records. Try a broader search.', 18)

    def select(self, entry):
        self.selected_id = entry['id']
        self.refresh()
        self.details._parent_canvas.yview_moveto(0)

    def detail(self, entry):
        self.selected_id = entry['id']
        image = self.images.get(entry, 160)
        if image:
            ctk.CTkLabel(self.details, text='', image=image).pack(anchor='w', padx=14, pady=12)
        else:
            label(self.details, '3D thumbnail not rendered yet' if entry.get('thumbnail_entity') or entry.get('has_geometry') else 'No extracted image for this record', 12, MUTED)
        label(self.details, entry['name'], 25)
        bits = [entry['type'], entry.get('manufacturer')]
        if entry.get('size') is not None:
            bits.append(f"Size {entry['size']}")
        if entry.get('grade') is not None:
            bits.append(f"Grade {entry['grade']}")
        label(self.details, ' · '.join(str(b) for b in bits if b), color=GOLD)
        label(self.details, entry.get('description') or 'No localized description in this record.')
        catalog = get_catalog()
        recipes = [bp for bp in catalog.items if bp.get('item_id')==entry['id']]
        uses = [bp for bp in catalog.items if any(s['material']==entry['name'] for s in bp['slots'])] if entry['kind']=='Material' else []
        if entry['kind']=='Material':
            from mining_planner import get_mining_planner
            name = get_mining_planner().resolve_material(entry['name'])
            if name:
                ctk.CTkButton(self.details, text='Find mining locations & secondaries →', command=lambda: self.app.open_material_picker([name])).pack(fill='x', padx=14, pady=8)
            if entry.get('refined_id'):
                refined = self.library.resolve(entry['refined_id'])
                if refined:
                    label(self.details, 'Refines into: '+refined['name'], color=GOLD)
            label(self.details, f'Used in {len(uses):,} catalogued recipes', 16)
        if recipes:
            label(self.details, 'Crafting & blueprint unlocks', 16)
        for bp in (recipes+uses)[:30]:
            ctk.CTkButton(self.details, text=bp['name']+' →', anchor='w', fg_color='#303847',
                          command=lambda b=bp: self.open_blueprint(b)).pack(fill='x', padx=14, pady=3)
        if len(uses)>30:
            label(self.details, 'First 30 shown. Search this material in Blueprints for all recipes.', 12, MUTED)
        if entry.get('inventory_micro_scu') is not None:
            label(self.details, f"Configured inventory volume: {entry['inventory_micro_scu']/1000000:g} SCU", 12, MUTED)
        label(self.details, 'Record details', 14, GOLD)
        label(self.details, entry['tag']+'\n'+entry['id'], 11, MUTED)
        label(self.details, 'Source: installed game records and CIG artwork. Shared/generic game icons are retained as supplied.', 11, MUTED)

    def open_blueprint(self, bp):
        self.set_mode('Blueprints')
        page = self.app.blueprint_page
        page.clear_filters()
        page.search.insert(0, bp['name'])
        page.selected_id = bp['id']
        page.refresh(reset=True)


class HomePage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG)
        self.pack(fill='both', expand=True)
        label(self, 'What are you planning today?', 28)
        label(self, 'Explore the game library, choose a crafting goal, or plan your next haul.', 15, MUTED)
        cards = [
            ('Arrange your HUD', 'Preview session details and mining results. Adjust position, size and opacity.', lambda: app.switch_page('hud')),
            ('Explore the library', 'Search equipment, materials and game descriptions, with extracted artwork.', lambda: app.open_library('Items')),
            ('Build something', 'Find a blueprint, check its unlock source, materials and quality effects.', lambda: app.open_library('Blueprints')),
            ('Plan a mining trip', 'Compare locations, quality scales and ores found in the same rocks.', lambda: app.switch_page('mining_planner')),
            ('Check materials & refinery orders', 'Review scanned orders and your local material ledger.', lambda: app.switch_page('refinery')),
        ]
        for title, description, command in cards:
            card = ctk.CTkFrame(self, fg_color=CARD)
            card.pack(fill='x', padx=14, pady=8)
            ctk.CTkButton(card, text=title+' →', anchor='w', font=('Bahnschrift', 18), fg_color='transparent',
                          text_color=TEXT, command=command).pack(fill='x', padx=14, pady=(12, 0))
            label(card, description, 13, MUTED)
        library = get_game_library()
        provenance = library.data['provenance']
        label(self, f"Local reference · {len(library.entries):,} named game records · {len(get_catalog().items):,} blueprint entries", 13, GOLD)
        label(self, f"Build {provenance.get('build', {}).get('RequestedP4ChangeNum', 'not extracted')} · {provenance.get('with_static_artwork', 0):,} records with static game icons. 3D thumbnails are still being developed.", 12, MUTED)
