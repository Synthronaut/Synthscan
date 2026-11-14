"""
SynthScan // FATE ROULETTE
Integrated in-app tab page for SynthScan MFD viewport.
Decide your destiny in the 'verse.
"""

import math
import random
import time
import tkinter as tk
import customtkinter as ctk
from dataclasses import dataclass
from typing import Optional

# Palette
BG, CARD, CARD_ALT, HEADER, BORDER_DIM, BORDER_MED = (
    '#181b22', '#1e222a', '#262b35', '#14171d', '#2c323e', '#3f4756'
)
TEXT_BRIGHT, TEXT_CYAN, TEXT_AMBER, TEXT_MUTED, TEXT_FAINT = (
    '#f8fafc', '#62ccff', '#fbbf24', '#7e889b', '#4a5363'
)

FONT_TECH = "Bahnschrift"
FONT_MONO = "Consolas"

@dataclass
class RouletteEntry:
    label: str
    description: str
    category: str
    color: str
    icon: str

FATE_ENTRIES: list[RouletteEntry] = [
    # PvP
    RouletteEntry("BOUNTY HUNT", "Grab a Crimson Pledge bounty and hunt down a named player. No mercy.", "PvP", "#1a4f6b", "⊕"),
    RouletteEntry("OPEN SEASON", "Fly to the most populated shard and pick a fight with the first ship you see.", "PvP", "#1a3a5c", "⚔"),
    RouletteEntry("HULL SCRAPER", "Ram a ship. Any ship. Pedestrian or aggressor. Touch that hull.", "PvP", "#5c2222", "💥"),
    RouletteEntry("ZERO-G BRAWL", "Land at GrimHEX, walk to the bar, start a melee fight with the first person you see.", "PvP", "#1a4f6b", "👊"),
    RouletteEntry("WANTED: YOU", "Rack up a Crimestat 5 as fast as humanly possible. Speed run it.", "PvP", "#5c2222", "🔴"),
    RouletteEntry("PIRACY RUN", "Intercept a hauler at a jump point and demand 50% of their cargo or they get deleted.", "PvP", "#4b2060", "☠"),
    RouletteEntry("MURDER DERBY", "Rented ships only. Delamar. Last one standing among willing participants.", "PvP", "#5c2222", "🏁"),
    RouletteEntry("TORPEDO THERAPY", "Lock on a capital ship or station module with a torpedo. Release. Feel better.", "PvP", "#1a3a5c", "🚀"),

    # Masochism
    RouletteEntry("YEET FROM ORBIT", "Equip no EVA gear. Jump out of your ship at max altitude above Hurston. Survive.", "Masochism", "#3a1a3a", "🌌"),
    RouletteEntry("FREEFALL YOLO", "Climb to the highest point on any moon. Jump. No suit jets.", "Masochism", "#3a1a3a", "🪂"),
    RouletteEntry("GLASS CANNON", "Fly a ship with no shields, no armor, into a PvE encounter. Skill only.", "Masochism", "#5c2222", "💀"),
    RouletteEntry("DEATHWISH RUN", "Equip no weapons. Enter a contested security zone. Try to talk your way out.", "Masochism", "#3a1a3a", "🤡"),
    RouletteEntry("BALL CRUSHER", "Take the most catastrophically bad trade route possible. Buy high, sell lower. Lose aUEC on purpose.", "Masochism", "#5c2222", "💸"),
    RouletteEntry("PAIN TRADER", "Complete 10 cargo runs in an Aurora MR. No other ship. No shortcuts.", "Masochism", "#4a3a0d", "😭"),
    RouletteEntry("CRIMESTAT DETOX", "Get yourself to Crimestat 5, then voluntarily turn yourself in and serve full time.", "Masochism", "#5c2222", "🔒"),
    RouletteEntry("THE HARD WAY", "Travel from Stanton to Pyro using ONLY sub-cruising speed. No QT allowed.", "Masochism", "#4a3a0d", "🐢"),

    # Mining
    RouletteEntry("ORE MANIAC", "Mine a full 32 SCU of pure Quantanium. Single session. No co-op. Good luck.", "Mining", "#1f4a2b", "⛏"),
    RouletteEntry("DETONATION FUN", "Overcharge a Quantanium rock until it explodes. Ride the shockwave and survive.", "Mining", "#1f4a2b", "💣"),
    RouletteEntry("PROSPECTOR YOLO", "Solo mine the most volatile rock you can find in the rings. Pray to the shard gods.", "Mining", "#1f4a2b", "🪨"),
    RouletteEntry("VACUUM CLAIM", "Plant a mining claim flag in deep asteroid field. Defend it from anyone who shows up.", "Mining", "#1f4a2b", "🚩"),
    RouletteEntry("SCRAPER GRIND", "30 consecutive minutes of hand mining on foot. No ships. Just you and the multitool.", "Mining", "#1f3a3a", "🔧"),

    # Trading
    RouletteEntry("MAX HAUL", "Fill the largest ship you can rent/own. 288 SCU or die trying.", "Trading", "#4a3a0d", "📦"),
    RouletteEntry("BLIND TRADE", "Buy whatever commodity is highlighted first at the nearest terminal. Sell it blind.", "Trading", "#4a3a0d", "🎲"),
    RouletteEntry("ILLEGAL GOODS", "Pick up illegal cargo and smuggle it past a security checkpoint.", "Trading", "#4b2060", "🕵"),
    RouletteEntry("JET FUEL HUSTLE", "Make 100k aUEC in a single session using only ships under 20 SCU.", "Trading", "#4a3a0d", "💰"),
    RouletteEntry("SCRAP KING", "Find a derelict ship. Salvage every panel off it manually. All of it.", "Trading", "#1f3a3a", "♻"),

    # Missions
    RouletteEntry("HVT DELETION", "Find a High Value Target bounty. Complete it with 10 minutes on the clock.", "Missions", "#1a4f6b", "🎯"),
    RouletteEntry("CARGO ESCORT", "Guard another player's hauler ship from jumppoint to delivery. No PvP initiated by you.", "Missions", "#1a3a5c", "🛡"),
    RouletteEntry("UGF STORM", "Solo clear an Illegal Underground Facility. No backup.", "Missions", "#5c2222", "🏚"),
    RouletteEntry("CIPHER RUN", "Complete a data heist mission solo with no gun: hack, extract, escape.", "Missions", "#4b2060", "💻"),
    RouletteEntry("HOSPITAL DASH", "Find an injured player and medevac them to the nearest hospital. Fast.", "Missions", "#1f4a2b", "🏥"),
    RouletteEntry("9-TAILS HUNT", "Chain three 9-Tails Lockdown missions back-to-back. No respawns allowed.", "Missions", "#1a4f6b", "🔗"),
    RouletteEntry("DERELICT SWEEP", "Find a derelict ship in space. Clear every NPC inside. Solo FPS.", "Missions", "#1f3a3a", "👻"),

    # Exploration
    RouletteEntry("QUANTUM DRIFT", "Pick a random moon. Quantum to it with no destination. Walk wherever you land.", "Exploration", "#1a3a5c", "🌙"),
    RouletteEntry("LAGRANGE CAMP", "Set up camp at a Lagrange point. Wait until something happens. No time limit.", "Exploration", "#1f3a3a", "⛺"),
    RouletteEntry("DARKSIDE SURVEY", "Find the night side of any planet. Land in the dark. Explore on foot 20 mins.", "Exploration", "#3a1a3a", "🌑"),
    RouletteEntry("RING WALK", "Park in a planetary ring. EVA walk for 5+ minutes among the rocks.", "Exploration", "#1a3a5c", "💫"),
    RouletteEntry("ALIEN RELIC HUNT", "Find and photograph an alien ruin or artifact. No wiki allowed.", "Exploration", "#4b2060", "🛸"),
    RouletteEntry("DEEP SPACE FLOAT", "Quantum to the furthest possible point from any station. Just... sit there.", "Exploration", "#3a1a3a", "🔭"),

    # Social
    RouletteEntry("BAR CRAWL", "Hit every bar at GrimHEX, Lorville and Area18 in one session. Sit at each.", "Social", "#4b2060", "🍺"),
    RouletteEntry("TAXI LORD", "Offer free taxi rides to strangers in global chat. 5 trips minimum.", "Social", "#1f4a2b", "🚕"),
    RouletteEntry("GLADIATOR PIT", "Host an improvised duel tournament. Any weapons. First to organize 4 people wins.", "Social", "#5c2222", "🏟"),
    RouletteEntry("PARADE MARCH", "Lead a convoy of 3+ friends through city limits. All ships, single file, slow.", "Social", "#1f4a2b", "🎺"),
    RouletteEntry("HOSTAGE DEMAND", "Take a friend 'hostage' in-RP. Demand another friend pay 10,000 aUEC ransom. Must be paid.", "Social", "#4b2060", "🤑"),

    # Racing
    RouletteEntry("ATMOSPHERE RACE", "Race from landing pad to landing pad in-atmo. No QD. Speed only.", "Racing", "#4a3a0d", "🏎"),
    RouletteEntry("CANYON SLASH", "Pick a canyon on any planet. Fly through at full speed. Time yourself.", "Racing", "#4a3a0d", "🌊"),
    RouletteEntry("COFFEE CAN", "Race using the slowest ship on the server. Win against literally anything else.", "Racing", "#4a3a0d", "🐌"),

    # Chaos
    RouletteEntry("MARKET CRASH", "Dump 1,000 units of any commodity at the worst possible terminal. Tank your own profits.", "Chaos", "#5c2222", "📉"),
    RouletteEntry("INSURE IT", "Intentionally destroy your own ship. Collect insurance. Buy it again. Repeat.", "Chaos", "#5c2222", "🔥"),
    RouletteEntry("GRAVITY TEST", "Find the highest-gravity body. See how long you can run before collapsing.", "Chaos", "#1a4f6b", "🌍"),
    RouletteEntry("DISTRESS AMBUSH", "Broadcast a fake distress call in chat. Set up an ambush for whoever shows up.", "Chaos", "#5c2222", "📡"),
    RouletteEntry("EMPTY WALLET", "Spend all your liquid aUEC on the most useless items you can find. Zero balance required.", "Chaos", "#5c2222", "💳"),
    RouletteEntry("BUREAUCRAT", "Spend 10 minutes standing at every queue/kiosk you can find. Talk to every NPC terminal.", "Chaos", "#1f3a3a", "🏛"),
    RouletteEntry("SPIN AGAIN", "The wheel has spoken: spin it again. Twice the fate, twice the suffering.", "Chaos", "#2a2a40", "🔄"),
    RouletteEntry("DOUBLE DOWN", "Whatever your last fate was — do it again. But harder. Add self-imposed difficulty.", "Chaos", "#2a2a40", "×2"),
    RouletteEntry("FREE DAY", "No task. Do whatever you want. The wheel gifts you freedom. Probably a glitch.", "Chaos", "#1f4a2b", "✓"),
]

@dataclass
class SpinRecord:
    timestamp: float
    entry: RouletteEntry
    seed: int


class FateRoulettePage(ctk.CTkFrame):
    """
    In-app tab page inside the main SynthScan MFD viewport.
    """
    _SPIN_DURATION = 4.0
    _SPIN_FPS = 60
    _HISTORY_MAX = 30

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.pack(fill='both', expand=True)
        self.app = app

        self.history: list[SpinRecord] = []
        self._spin_active = False
        self._spin_seed = 0
        self._spin_target_idx = 0
        self._current_angle = 0.0
        self._final_angle = 0.0
        self._total_rotation = 0.0
        self._spin_start = 0.0
        self._total_spins = 0
        self._filter_category: Optional[str] = None
        self._entries = FATE_ENTRIES[:]
        self._history_cards: list[ctk.CTkFrame] = []

        self._build_ui()
        self._draw_wheel(self._current_angle)

    def _build_ui(self):
        # Top banner/title
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(12, 6))

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="FATE ROULETTE",
            font=ctk.CTkFont(family=FONT_TECH, size=24, weight="bold"),
            text_color=TEXT_BRIGHT,
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Every activity in the 'verse. Decide your fate. No excuses.",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=TEXT_MUTED,
            anchor="w"
        ).pack(anchor="w")

        self._lbl_spin_count = ctk.CTkLabel(
            top_bar,
            text="TOTAL SPINS: 0",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=TEXT_AMBER
        )
        self._lbl_spin_count.pack(side="right", padx=8)

        # Main 2-column body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(6, 12))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0, minsize=420)
        body.grid_columnconfigure(1, weight=1)

        # LEFT: Wheel & controls
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6, border_width=1, border_color=BORDER_DIM)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)

        # Wheel canvas container
        canvas_outer = ctk.CTkFrame(left, fg_color="#0a0c10", corner_radius=6, border_width=1, border_color=BORDER_DIM)
        canvas_outer.pack(padx=14, pady=(14, 4), fill="x")

        self._canvas = tk.Canvas(
            canvas_outer,
            width=380,
            height=360,
            bg="#0a0c10",
            highlightthickness=0
        )
        self._canvas.pack(padx=4, pady=4)

        # Filter & Fate Count Row
        frow = ctk.CTkFrame(left, fg_color="transparent")
        frow.pack(fill="x", padx=14, pady=(6, 4))

        ctk.CTkLabel(
            frow,
            text="CATEGORY:",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        cats = ["ALL"] + sorted(set(e.category for e in FATE_ENTRIES))
        self._filter_var = tk.StringVar(value="ALL")
        ctk.CTkOptionMenu(
            frow,
            values=cats,
            variable=self._filter_var,
            width=140,
            height=28,
            fg_color=CARD_ALT,
            button_color=BORDER_MED,
            button_hover_color="#4a5570",
            dropdown_fg_color=HEADER,
            dropdown_hover_color="#2a303c",
            text_color=TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            command=self._on_filter_change
        ).pack(side="left")

        self._lbl_entry_count = ctk.CTkLabel(
            frow,
            text=f"{len(self._entries)} fates available",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=TEXT_FAINT
        )
        self._lbl_entry_count.pack(side="right")

        # SPIN BUTTON
        self._btn_spin = ctk.CTkButton(
            left,
            text="⬡   SPIN THE WHEEL   ⬡",
            font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"),
            height=46,
            fg_color="#1a4f6b",
            hover_color="#236080",
            border_color=TEXT_CYAN,
            border_width=1,
            text_color=TEXT_BRIGHT,
            corner_radius=4,
            command=self._start_spin
        )
        self._btn_spin.pack(fill="x", padx=14, pady=(6, 8))

        # Result display card
        result_card = ctk.CTkFrame(left, fg_color=CARD_ALT, corner_radius=6, border_width=1, border_color=BORDER_DIM)
        result_card.pack(fill="x", padx=14, pady=(0, 14))

        self._lbl_result_cat = ctk.CTkLabel(
            result_card,
            text="AWAITING DESTINY",
            font=ctk.CTkFont(family=FONT_MONO, size=9, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        self._lbl_result_cat.pack(fill="x", padx=12, pady=(10, 0))

        self._lbl_result_name = ctk.CTkLabel(
            result_card,
            text="—",
            font=ctk.CTkFont(family=FONT_TECH, size=16, weight="bold"),
            text_color=TEXT_BRIGHT,
            anchor="w",
            wraplength=360,
            justify="left"
        )
        self._lbl_result_name.pack(fill="x", padx=12, pady=(2, 0))

        self._lbl_result_desc = ctk.CTkLabel(
            result_card,
            text="Hit spin. Whatever it says, you have to do.",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=360,
            justify="left"
        )
        self._lbl_result_desc.pack(fill="x", padx=12, pady=(4, 12))

        # RIGHT: History
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6, border_width=1, border_color=BORDER_DIM)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        rh = ctk.CTkFrame(right, fg_color=HEADER, corner_radius=0, height=44, border_width=1, border_color=BORDER_DIM)
        rh.grid(row=0, column=0, sticky="ew")
        rh.grid_propagate(False)

        ctk.CTkLabel(
            rh,
            text="// FATE RECORD & HISTORY",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            text_color=TEXT_CYAN,
            anchor="w"
        ).pack(side="left", padx=14, pady=10)

        ctk.CTkButton(
            rh,
            text="CLEAR",
            width=58,
            height=26,
            fg_color=CARD,
            hover_color="#2a303c",
            border_color=BORDER_MED,
            border_width=1,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_MONO, size=9, weight="bold"),
            corner_radius=4,
            command=self._clear_history
        ).pack(side="right", padx=10, pady=8)

        self._history_scroll = ctk.CTkScrollableFrame(
            right,
            fg_color=BG,
            corner_radius=0,
            scrollbar_button_color=BORDER_MED,
            scrollbar_button_hover_color="#4a5570"
        )
        self._history_scroll.grid(row=1, column=0, sticky="nsew")

        self._lbl_history_empty = ctk.CTkLabel(
            self._history_scroll,
            text="No fates rolled yet.\nSpin the wheel to test your resolve.",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=TEXT_FAINT,
            justify="center"
        )
        self._lbl_history_empty.pack(pady=60)

    def _on_filter_change(self, val: str):
        if val == "ALL":
            self._entries = FATE_ENTRIES[:]
            self._filter_category = None
        else:
            self._entries = [e for e in FATE_ENTRIES if e.category == val]
            self._filter_category = val
        count = len(self._entries)
        self._lbl_entry_count.configure(text=f"{count} fate{'s' if count != 1 else ''} available")
        self._draw_wheel(self._current_angle)

    def _draw_wheel(self, angle_offset: float):
        c = self._canvas
        c.delete("all")
        entries = self._entries
        if not entries:
            c.create_text(190, 180, text="No fates in this category", fill=TEXT_MUTED, font=(FONT_MONO, 11))
            return

        cx, cy, r = 190, 180, 160
        n = len(entries)
        sweep = 360.0 / n

        for i, entry in enumerate(entries):
            start_deg = angle_offset + i * sweep - 90.0
            c.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=start_deg, extent=sweep,
                fill=entry.color, outline="#09090f", width=1.4,
                style="pieslice"
            )
            mid_rad = math.radians(start_deg + sweep / 2)
            ir = r * 0.68
            tx = cx + ir * math.cos(mid_rad)
            ty = cy + ir * math.sin(mid_rad)
            c.create_text(
                tx, ty,
                text=entry.icon,
                fill=TEXT_BRIGHT,
                font=(FONT_TECH, max(7, min(12, int(220 / n))), "bold"),
                anchor="center"
            )

        # Outer rim
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#566275", width=2.5)

        # Center Hub
        hub = 28
        c.create_oval(cx - hub, cy - hub, cx + hub, cy + hub, fill="#0a0c10", outline=TEXT_CYAN, width=2)
        c.create_text(cx, cy, text="FATE", fill=TEXT_CYAN, font=(FONT_MONO, 7, "bold"))

        # Tick marks
        for i in range(n):
            tick_rad = math.radians(angle_offset + i * sweep - 90.0)
            x1 = cx + (r - 7) * math.cos(tick_rad)
            y1 = cy + (r - 7) * math.sin(tick_rad)
            x2 = cx + (r + 3) * math.cos(tick_rad)
            y2 = cy + (r + 3) * math.sin(tick_rad)
            c.create_line(x1, y1, x2, y2, fill="#566275", width=1.2)

        # Pointer at top (12 o'clock)
        px, py = cx, cy - r - 6
        c.create_polygon(
            px - 7, py - 12,
            px + 7, py - 12,
            px, py + 2,
            fill=TEXT_AMBER, outline="#c48f10", width=1
        )

    def _start_spin(self):
        if self._spin_active or not self._entries:
            return
        self._spin_active = True
        self._btn_spin.configure(state="disabled", text="SPINNING...")
        self._lbl_result_cat.configure(text="CALCULATING FATE...", text_color=TEXT_MUTED)
        self._lbl_result_name.configure(text="—", text_color=TEXT_MUTED)
        self._lbl_result_desc.configure(text="")

        self._spin_seed = random.randint(0, 999_999)
        rng = random.Random(self._spin_seed)
        self._spin_target_idx = rng.randint(0, len(self._entries) - 1)

        n = len(self._entries)
        sweep = 360.0 / n
        mid_offset = (90.0 - (self._spin_target_idx + 0.5) * sweep) % 360.0
        jitter = rng.uniform(-sweep * 0.35, sweep * 0.35)
        target_angle = (mid_offset + jitter) % 360.0

        extra_spins = rng.randint(6, 12) * 360.0
        current = self._current_angle % 360.0
        delta = (target_angle - current) % 360.0
        self._total_rotation = extra_spins + delta
        self._spin_start = time.monotonic()
        self._final_angle = self._current_angle + self._total_rotation

        self._animate_spin()

    def _animate_spin(self):
        elapsed = time.monotonic() - self._spin_start
        t = min(elapsed / self._SPIN_DURATION, 1.0)
        eased = 1.0 - (1.0 - t) ** 4

        angle_now = (self._final_angle - self._total_rotation * (1.0 - eased)) % 360.0
        self._draw_wheel(angle_now)

        if t < 1.0:
            delay = max(1, int(1000 / self._SPIN_FPS))
            self.after(delay, self._animate_spin)
        else:
            self._current_angle = self._final_angle % 360.0
            self._on_spin_complete()

    def _on_spin_complete(self):
        self._spin_active = False
        self._total_spins += 1
        self._lbl_spin_count.configure(text=f"TOTAL SPINS: {self._total_spins}")

        entry = self._entries[self._spin_target_idx]
        record = SpinRecord(timestamp=time.time(), entry=entry, seed=self._spin_seed)
        self.history.insert(0, record)
        if len(self.history) > self._HISTORY_MAX:
            self.history = self.history[:self._HISTORY_MAX]

        self._lbl_result_cat.configure(
            text=f"[ {entry.category.upper()} ]",
            text_color=TEXT_AMBER
        )
        self._lbl_result_name.configure(text=entry.label, text_color=TEXT_BRIGHT)
        self._lbl_result_desc.configure(text=entry.description, text_color=TEXT_CYAN)

        self._btn_spin.configure(state="normal", text="⬡   SPIN THE WHEEL   ⬡")
        self._refresh_history()

    def _refresh_history(self):
        for card in self._history_cards:
            card.destroy()
        self._history_cards.clear()

        if not self.history:
            self._lbl_history_empty.pack(pady=60)
            return

        self._lbl_history_empty.pack_forget()

        for i, record in enumerate(self.history):
            entry = record.entry
            ts = time.strftime("%H:%M:%S", time.localtime(record.timestamp))

            card = ctk.CTkFrame(
                self._history_scroll,
                fg_color=CARD if i % 2 == 0 else CARD_ALT,
                corner_radius=4,
                border_width=1,
                border_color=BORDER_DIM
            )
            card.pack(fill="x", padx=8, pady=3)

            ctk.CTkFrame(card, width=4, corner_radius=0, fg_color=entry.color).pack(side="left", fill="y", padx=(0, 8))

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, pady=6)

            top_row = ctk.CTkFrame(content, fg_color="transparent")
            top_row.pack(fill="x")

            ctk.CTkLabel(
                top_row,
                text=f"{entry.icon}  {entry.label}",
                font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
                text_color=TEXT_BRIGHT,
                anchor="w"
            ).pack(side="left")

            ctk.CTkLabel(
                top_row,
                text=ts,
                font=ctk.CTkFont(family=FONT_MONO, size=9),
                text_color=TEXT_FAINT,
                anchor="e"
            ).pack(side="right", padx=(0, 8))

            ctk.CTkLabel(
                content,
                text=entry.description,
                font=ctk.CTkFont(family=FONT_MONO, size=10),
                text_color=TEXT_MUTED,
                anchor="w",
                wraplength=400,
                justify="left"
            ).pack(fill="x")

            pill = ctk.CTkFrame(card, fg_color=HEADER, corner_radius=3)
            pill.pack(side="right", padx=8, pady=8)
            ctk.CTkLabel(
                pill,
                text=entry.category.upper(),
                font=ctk.CTkFont(family=FONT_MONO, size=8, weight="bold"),
                text_color=TEXT_MUTED
            ).pack(padx=6, pady=2)

            self._history_cards.append(card)

    def _clear_history(self):
        self.history.clear()
        self._refresh_history()
