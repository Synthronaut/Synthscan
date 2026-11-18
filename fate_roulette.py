"""
SynthScan // FATE ROULETTE
Integrated in-app tab page for SynthScan MFD viewport.
Decide your destiny in the 'verse.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import time
import tkinter as tk
import customtkinter as ctk
from typing import Optional

from crafting_catalog import get_catalog

# Palette (aligned with DESIGN.md deep navy & cyan/amber accents)
BG, CARD, CARD_ALT, HEADER, BORDER_DIM, BORDER_MED = (
    '#0f1013', '#161b24', '#1d2430', '#12161e', '#283242', '#3d4c63'
)
TEXT_BRIGHT, TEXT_CYAN, TEXT_AMBER, TEXT_MUTED, TEXT_FAINT = (
    '#f0f6fc', '#62ccff', '#fbbf24', '#8e9dad', '#526073'
)

FONT_TECH = "Bahnschrift"
FONT_BODY = "Segoe UI"
FONT_MONO = "Consolas"


def _hex_shift(hex_col: str, delta: int) -> str:
    h = hex_col.lstrip('#')
    if len(h) != 6:
        return hex_col
    r = max(0, min(255, int(h[0:2], 16) + delta))
    g = max(0, min(255, int(h[2:4], 16) + delta))
    b = max(0, min(255, int(h[4:6], 16) + delta))
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class RouletteEntry:
    label: str
    description: str
    category: str
    color: str
    icon: str = ""
    wheel_label: str = ""
    is_blueprint: bool = False
    is_wanted: bool = False
    bp_name: str = ""

    def __post_init__(self):
        if not self.wheel_label:
            self.wheel_label = self.label[:18]


CATEGORY_ORDER = [
    ("PvP", "#286c94"),
    ("Masochism", "#723474"),
    ("Mining", "#2a7044"),
    ("Trading", "#8a661c"),
    ("Missions", "#2c5c92"),
    ("Exploration", "#2c686c"),
    ("Social", "#703a8a"),
    ("Racing", "#8c561a"),
    ("Chaos", "#8c3036"),
    ("Collection", "#20806a"),
    ("Blueprint Unlock", "#187c8e"),
]

# Verified 4.10 quality-band thresholds (Band 1..8 upper bounds) from CraftingData.h
_QUALITY_MATERIALS = [
    ("Quantainium", "Quant", False, 3, 6, 4, 6, (344, 514, 669, 762, 852, 901, 974, 1000)),
    ("Savrilium", "Savrilium", False, 2, 4, 4, 6, (322, 580, 636, 776, 878, 905, 967, 1000)),
    ("Riccite", "Riccite", False, 3, 6, 4, 6, (325, 525, 671, 743, 870, 942, 965, 1000)),
    ("Stileron", "Stileron", False, 3, 6, 4, 6, (330, 517, 681, 747, 874, 947, 972, 1000)),
    ("Bexalite", "Bexalite", False, 6, 12, 4, 6, (302, 597, 632, 756, 875, 941, 959, 1000)),
    ("Taranite", "Taranite", False, 6, 12, 4, 6, (310, 525, 646, 718, 853, 925, 957, 1000)),
    ("Gold", "Gold", False, 8, 16, 4, 6, (264, 553, 644, 786, 864, 916, 959, 1000)),
    ("Laranite", "Laranite", False, 10, 20, 4, 6, (298, 510, 698, 707, 858, 910, 975, 1000)),
    ("Agricium", "Agricium", False, 10, 20, 4, 6, (346, 588, 667, 796, 852, 943, 971, 1000)),
    ("Lindinium", "Lindinium", False, 4, 8, 4, 6, (305, 585, 618, 729, 853, 930, 954, 1000)),
    ("Torite", "Torite", False, 6, 12, 4, 6, (262, 528, 661, 785, 873, 944, 951, 1000)),
    ("Ouratite", "Ouratite", False, 6, 10, 4, 6, (310, 523, 647, 779, 860, 912, 960, 1000)),
    ("Hadanite", "Hadanite", True, 10, 20, 4, 6, (274, 526, 665, 762, 867, 916, 959, 1000)),
    ("Feynmaline", "Feynmaline", True, 6, 14, 4, 6, (371, 561, 682, 769, 880, 906, 965, 1000)),
    ("Janalite", "Janalite", True, 1, 2, 3, 5, (269, 596, 632, 732, 898, 926, 964, 1000)),
    ("Carinite", "Carinite", True, 6, 12, 3, 5, (273, 554, 647, 716, 880, 909, 959, 1000)),
    ("Saldynium (Ore)", "Saldynium", True, 5, 10, 3, 5, (301, 575, 674, 757, 861, 938, 955, 1000)),
    ("Beradom", "Beradom", True, 8, 16, 4, 6, (287, 578, 656, 723, 881, 937, 969, 1000)),
    ("Glacosite", "Glacosite", True, 8, 16, 4, 6, (360, 567, 678, 724, 857, 916, 972, 1000)),
    ("Yormandi Eye", "Yormandi", True, 1, 1, 3, 5, (391, 515, 663, 794, 807, 938, 978, 1000)),
]

FATE_ENTRIES: list[RouletteEntry] = [
    # PvP
    RouletteEntry("BOUNTY HUNT", "Grab a Crimson Pledge bounty and hunt down a named player. No mercy.", "PvP", "#205c80", wheel_label="BOUNTY HUNT"),
    RouletteEntry("OPEN SEASON", "Fly to the most populated shard and pick a fight with the first ship you see.", "PvP", "#1c4870", wheel_label="OPEN SEASON"),
    RouletteEntry("HULL SCRAPER", "Ram a ship. Any ship. Pedestrian or aggressor. Touch that hull.", "PvP", "#702a2c", wheel_label="HULL SCRAPER"),
    RouletteEntry("ZERO-G BRAWL", "Land at GrimHEX, walk to the bar, start a melee fight with the first person you see.", "PvP", "#226284", wheel_label="ZERO-G BRAWL"),
    RouletteEntry("WANTED: YOU", "Rack up a Crimestat 5 as fast as humanly possible. Speed run it.", "PvP", "#762c2e", wheel_label="WANTED: YOU"),
    RouletteEntry("PIRACY RUN", "Intercept a hauler at a jump point and demand 50% of their cargo or they get deleted.", "PvP", "#582a70", wheel_label="PIRACY RUN"),
    RouletteEntry("MURDER DERBY", "Rented ships only. Delamar. Last one standing among willing participants.", "PvP", "#6c282c", wheel_label="MURDER DERBY"),
    RouletteEntry("TORPEDO THERAPY", "Lock on a capital ship or station module with a torpedo. Release. Feel better.", "PvP", "#1e4a74", wheel_label="TORPEDO"),

    # Masochism
    RouletteEntry("YEET FROM ORBIT", "Equip no EVA gear. Jump out of your ship at max altitude above Hurston. Survive.", "Masochism", "#4c2454", wheel_label="ORBIT YEET"),
    RouletteEntry("FREEFALL YOLO", "Climb to the highest point on any moon. Jump. No suit jets.", "Masochism", "#54265c", wheel_label="FREEFALL"),
    RouletteEntry("GLASS CANNON", "Fly a ship with no shields, no armor, into a PvE encounter. Skill only.", "Masochism", "#702a2e", wheel_label="GLASS CANNON"),
    RouletteEntry("DEATHWISH RUN", "Equip no weapons. Enter a contested security zone. Try to talk your way out.", "Masochism", "#482250", wheel_label="DEATHWISH"),
    RouletteEntry("BALL CRUSHER", "Take the most catastrophically bad trade route possible. Buy high, sell lower. Lose aUEC on purpose.", "Masochism", "#6a282e", wheel_label="BAD TRADE"),
    RouletteEntry("PAIN TRADER", "Complete 10 cargo runs in an Aurora MR. No other ship. No shortcuts.", "Masochism", "#604a18", wheel_label="PAIN TRADER"),
    RouletteEntry("CRIMESTAT DETOX", "Get yourself to Crimestat 5, then voluntarily turn yourself in and serve full time.", "Masochism", "#6e2a2e", wheel_label="CS5 DETOX"),
    RouletteEntry("THE HARD WAY", "Travel between planetary zones using ONLY sub-cruising speed. No QT allowed.", "Masochism", "#5c4616", wheel_label="NO QUANTUM"),

    # Mining
    RouletteEntry("ORE MANIAC", "Mine a full 32 SCU of pure Quantanium. Single session. No co-op. Good luck.", "Mining", "#245e36", wheel_label="ORE MANIAC"),
    RouletteEntry("DETONATION FUN", "Overcharge a Quantanium rock until it explodes. Ride the shockwave and survive.", "Mining", "#28663a", wheel_label="QUANT BOOM"),
    RouletteEntry("PROSPECTOR YOLO", "Solo mine the most volatile rock you can find in the rings. Pray to the shard gods.", "Mining", "#225834", wheel_label="VOLATILE ROCK"),
    RouletteEntry("VACUUM CLAIM", "Plant a mining claim flag in deep asteroid field. Defend it from anyone who shows up.", "Mining", "#2a683c", wheel_label="CLAIM FLAG"),
    RouletteEntry("SCRAPER GRIND", "30 consecutive minutes of hand mining on foot. No ships. Just you and the multitool.", "Mining", "#244c4c", wheel_label="HAND MINE"),

    # Trading
    RouletteEntry("MAX HAUL", "Fill the largest ship you can rent/own. 288 SCU or die trying.", "Trading", "#624c16", wheel_label="MAX HAUL"),
    RouletteEntry("BLIND TRADE", "Buy whatever commodity is highlighted first at the nearest terminal. Sell it blind.", "Trading", "#6a5218", wheel_label="BLIND TRADE"),
    RouletteEntry("ILLEGAL GOODS", "Pick up illegal cargo and smuggle it past a security checkpoint.", "Trading", "#5c2a72", wheel_label="SMUGGLER"),
    RouletteEntry("JET FUEL HUSTLE", "Make 100k aUEC in a single session using only ships under 20 SCU.", "Trading", "#604a16", wheel_label="MICRO HAUL"),
    RouletteEntry("SCRAP KING", "Find a derelict ship. Salvage every panel off it manually. All of it.", "Trading", "#264e50", wheel_label="SCRAP KING"),

    # Missions
    RouletteEntry("HVT DELETION", "Find a High Value Target bounty. Complete it with 10 minutes on the clock.", "Missions", "#205c80", wheel_label="HVT RUSH"),
    RouletteEntry("CARGO ESCORT", "Guard another player's hauler ship from jumppoint to delivery. No PvP initiated by you.", "Missions", "#1e4a72", wheel_label="ESCORT"),
    RouletteEntry("UGF STORM", "Solo clear an Illegal Underground Facility. No backup.", "Missions", "#702c2e", wheel_label="UGF SOLO"),
    RouletteEntry("CIPHER RUN", "Complete a data heist mission solo with no gun: hack, extract, escape.", "Missions", "#582a70", wheel_label="CIPHER RUN"),
    RouletteEntry("HOSPITAL DASH", "Find an injured player and medevac them to the nearest hospital. Fast.", "Missions", "#265e38", wheel_label="MEDEVAC"),
    RouletteEntry("9-TAILS HUNT", "Chain three 9-Tails Lockdown missions back-to-back. No respawns allowed.", "Missions", "#226082", wheel_label="9-TAILS X3"),
    RouletteEntry("DERELICT SWEEP", "Find a derelict ship in space. Clear every NPC inside. Solo FPS.", "Missions", "#264e4e", wheel_label="WRECK SWEEP"),

    # Exploration
    RouletteEntry("QUANTUM DRIFT", "Pick a random moon. Quantum to it with no destination. Walk wherever you land.", "Exploration", "#224c74", wheel_label="MOON DRIFT"),
    RouletteEntry("LAGRANGE CAMP", "Set up camp at a Lagrange point. Wait until something happens. No time limit.", "Exploration", "#265252", wheel_label="LAGRANGE"),
    RouletteEntry("DARKSIDE SURVEY", "Find the night side of any planet. Land in the dark. Explore on foot 20 mins.", "Exploration", "#4c2452", wheel_label="NIGHT SURVEY"),
    RouletteEntry("RING WALK", "Park in a planetary ring. EVA walk for 5+ minutes among the rocks.", "Exploration", "#224e76", wheel_label="RING EVA"),
    RouletteEntry("ALIEN RELIC HUNT", "Find and photograph an alien ruin or artifact. No wiki allowed.", "Exploration", "#5a2a72", wheel_label="RELIC HUNT"),
    RouletteEntry("DEEP SPACE FLOAT", "Quantum to the furthest possible point from any station. Just... sit there.", "Exploration", "#4a2450", wheel_label="DEEP VOID"),

    # Social
    RouletteEntry("BAR CRAWL", "Hit every bar at GrimHEX, Lorville and Area18 in one session. Sit at each.", "Social", "#5c2c74", wheel_label="BAR CRAWL"),
    RouletteEntry("TAXI LORD", "Offer free taxi rides to strangers in global chat. 5 trips minimum.", "Social", "#266038", wheel_label="TAXI LORD"),
    RouletteEntry("GLADIATOR PIT", "Host an improvised duel tournament. Any weapons. First to organize 4 people wins.", "Social", "#722c2e", wheel_label="MELEE PIT"),
    RouletteEntry("PARADE MARCH", "Lead a convoy of 3+ friends through city limits. All ships, single file, slow.", "Social", "#2a6440", wheel_label="PARADE"),
    RouletteEntry("HOSTAGE DEMAND", "Take a friend 'hostage' in-RP. Demand another friend pay 10,000 aUEC ransom. Must be paid.", "Social", "#5a2a70", wheel_label="RANSOM RP"),

    # Racing
    RouletteEntry("ATMOSPHERE RACE", "Race from landing pad to landing pad in-atmo. No QD. Speed only.", "Racing", "#6e4618", wheel_label="ATMO RACE"),
    RouletteEntry("CANYON SLASH", "Pick a canyon on any planet. Fly through at full speed. Time yourself.", "Racing", "#784c1a", wheel_label="CANYON RUN"),
    RouletteEntry("COFFEE CAN", "Race using the slowest ship on the server. Win against literally anything else.", "Racing", "#644016", wheel_label="SLOWEST SHIP"),

    # Chaos
    RouletteEntry("MARKET CRASH", "Dump 1,000 units of any commodity at the worst possible terminal. Tank your own profits.", "Chaos", "#762a2c", wheel_label="MARKET CRASH"),
    RouletteEntry("INSURE IT", "Intentionally destroy your own ship. Collect insurance. Buy it again. Repeat.", "Chaos", "#72282c", wheel_label="INSURE IT"),
    RouletteEntry("GRAVITY TEST", "Find the highest-gravity body. See how long you can run before collapsing.", "Chaos", "#245c7e", wheel_label="GRAVITY TEST"),
    RouletteEntry("DISTRESS AMBUSH", "Broadcast a fake distress call in chat. Set up an ambush for whoever shows up.", "Chaos", "#70282c", wheel_label="FAKE DISTRESS"),
    RouletteEntry("EMPTY WALLET", "Spend all your liquid aUEC on the most useless items you can find. Zero balance required.", "Chaos", "#6e282e", wheel_label="EMPTY WALLET"),
    RouletteEntry("BUREAUCRAT", "Spend 10 minutes standing at every queue/kiosk you can find. Talk to every NPC terminal.", "Chaos", "#285050", wheel_label="BUREAUCRAT"),
    RouletteEntry("SPIN AGAIN", "The wheel has spoken: spin it again. Twice the fate, twice the suffering.", "Chaos", "#3a3a5e", wheel_label="SPIN AGAIN"),
    RouletteEntry("DOUBLE DOWN", "Whatever your last fate was — do it again. But harder. Add self-imposed difficulty.", "Chaos", "#424268", wheel_label="DOUBLE DOWN"),
    RouletteEntry("FREE DAY", "No task. Do whatever you want. The wheel gifts you freedom. Probably a glitch.", "Chaos", "#266038", wheel_label="FREE DAY"),

    # Collection (curated rare-item & scavenger party hunts; paired with dynamic Quality Material hunts)
    RouletteEntry("VALAKKAR PEARL HUNT", "Venture into Pyro's storm zones and collect an Irradiated Valakkar Pearl (Grade AA or AAA).", "Collection", "#1e705c", wheel_label="VALAKKAR PEARL"),
    RouletteEntry("APEX VALAKKAR FANG", "Track and slay an Apex Valakkar (or raid a fresh kill) and extract an Irradiated Valakkar Fang (Apex).", "Collection", "#1c6656", wheel_label="APEX FANG"),
    RouletteEntry("YORMANDI TROPHY", "Hunt down a Yormandi and bring back a Yormandi Eye or Yormandi Tongue intact.", "Collection", "#227660", wheel_label="YORMANDI PART"),
    RouletteEntry("KOPION HORN RUN", "Clear a wilderness den or cave and collect 3 Tundra or Irradiated Kopion Horns without dying.", "Collection", "#1a6254", wheel_label="KOPION HORNS"),
    RouletteEntry("PLUSHIE CREW", "Visit planetary gift shops to collect 3 distinct plushies (Pico, Finley, Francis, Stormwal) for your dash.", "Collection", "#247a64", wheel_label="PLUSHIE CREW"),
    RouletteEntry("COMP-BOARD HEIST", "Infiltrate Checkmate, Orbituary, or Ruin Station's Contested Zone and extract 1 Executive Hangar Comp-Board.", "Collection", "#1c6a5e", wheel_label="COMP-BOARD"),
    RouletteEntry("ASD DRIVE RECOVERY", "Run an Onyx / ASD facility and escape with an ASD Secure Drive in your backpack.", "Collection", "#207262", wheel_label="ASD DRIVE"),
    RouletteEntry("WIKELO FAVOR GRIND", "Gather rare curiosities or scrip and trade up to earn 1 fresh Wikelo Favor.", "Collection", "#267e66", wheel_label="WIKELO FAVOR"),
    RouletteEntry("VANDUUL SCRAPPER", "Find and extract a piece of Vanduul Plating or Vanduul Metal back to your home hangar.", "Collection", "#1a6052", wheel_label="VANDUUL SCRAP"),
    RouletteEntry("PRISTINE MEDAL HUNT", "Loot wrecks or outposts until you find any (Pristine) historic medal or Tevarin War Service Marker.", "Collection", "#227460", wheel_label="PRISTINE MEDAL"),
    RouletteEntry("ZERO-TO-HERO ARMOR", "Enter a bunker or outpost in a basic undersuit. Leave wearing a full matching looted armor set.", "Collection", "#1e6c5a", wheel_label="LOOTED SET"),
    RouletteEntry("GALLEY SNACK RUN", "Collect 5 distinct rare snacks or drinks (like Ermer Family Farms Ice Cream) from across the 'verse.", "Collection", "#247862", wheel_label="SNACK RUN"),
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
    _SPIN_DURATION = 5.0
    _WIN_GLOW_DURATION = 1.3
    _SPIN_FPS = 60
    _HISTORY_MAX = 30
    _BP_POOL_MIXED = 8
    _BP_POOL_SOLO = 12

    def __init__(self, parent, app, prefs_path: Optional[Path] = None):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.pack(fill='both', expand=True)
        self.app = app
        self._prefs_path = prefs_path

        self.history: list[SpinRecord] = []
        self._spin_active = False
        self._spin_seed = 0
        self._spin_target_idx = 0
        self._current_angle = 0.0
        self._spin_start_angle = 0.0
        self._final_angle = 0.0
        self._total_rotation = 0.0
        self._spin_start = 0.0
        self._last_boundary_tick = 0
        self._clacker_kick = 0.0
        self._win_glow_start = 0.0
        self._win_glow_alpha = 0.0
        self._total_spins = 0
        self._selected_idx = -1

        self._enabled_cats: dict[str, bool] = {name: True for name, _ in CATEGORY_ORDER}
        self._load_prefs()

        self._sampled_bps: list[RouletteEntry] = []
        self._sampled_collections: list[RouletteEntry] = []
        self._missing_bp_count = 0
        self._total_raw_count = 0
        self._entries: list[RouletteEntry] = []
        self._cat_widgets: dict[str, dict] = {}
        self._history_cards: list[ctk.CTkFrame] = []

        self._sample_missing_blueprints()
        self._sample_quality_collections()
        self._rebuild_active_entries(reset_selection=True)
        self._build_ui()
        self._refresh_category_cards()
        self._draw_wheel(self._current_angle)

    def _prefs_file(self) -> Optional[Path]:
        if self._prefs_path is not None:
            return self._prefs_path
        try:
            from installation import PROFILE
            return PROFILE / "roulette_categories.json"
        except Exception:
            return None

    def _load_prefs(self):
        path = self._prefs_file()
        if not path or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                for name, _ in CATEGORY_ORDER:
                    if name in raw:
                        self._enabled_cats[name] = bool(raw[name])
        except Exception:
            pass

    def _save_prefs(self):
        path = self._prefs_file()
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._enabled_cats, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _get_missing_obtainable_blueprints(self) -> list[dict]:
        bp_mgr = getattr(self.app, "bp_manager", None)
        if bp_mgr is None:
            return []
        try:
            rows = bp_mgr.get_blueprints(status_filter="MISSING")
        except Exception:
            return []
        return [
            r for r in rows
            if not r.get("known_from_start") and r.get("sources")
        ]

    def _format_bp_description(self, bp: dict) -> str:
        parts = []
        if bp.get("is_favorite"):
            parts.append("★ WANTED")
        if bp.get("type"):
            parts.append(str(bp["type"]))
        if bp.get("size") not in (None, -1, ""):
            parts.append(f"Size {bp['size']}")
        if bp.get("grade"):
            parts.append(f"Grade {bp['grade']}")
        head = "  ·  ".join(parts)

        try:
            sources = get_catalog().sources(bp)
        except Exception:
            sources = []
        if sources:
            src = sources[0]
            meta = [str(src[k]) for k in ("faction", "system", "standing") if src.get(k)]
            meta_txt = f" ({' · '.join(meta)})" if meta else ""
            unlock_line = f'Unlock via: "{src.get("title", "Contract")}"{meta_txt}'
            if len(sources) > 1:
                more = len(sources) - 1
                unlock_line += f"  [+{more} more contract{'s' if more != 1 else ''}]"
            return f"{head}\n{unlock_line}" if head else unlock_line
        return head or "Obtainable blueprint missing from your library."

    def _sample_missing_blueprints(self):
        missing = self._get_missing_obtainable_blueprints()
        self._missing_bp_count = len(missing)
        self._sampled_bps.clear()
        if not missing:
            return

        non_bp_on = sum(1 for name, _ in CATEGORY_ORDER if name != "Blueprint Unlock" and self._enabled_cats.get(name, True))
        desired = self._BP_POOL_SOLO if non_bp_on == 0 else self._BP_POOL_MIXED

        favs = [b for b in missing if b.get("is_favorite")]
        others = [b for b in missing if not b.get("is_favorite")]
        random.shuffle(favs)
        random.shuffle(others)

        max_fav = min(len(favs), 5 if non_bp_on == 0 else 3)
        chosen = favs[:max_fav] + others[: max(0, desired - max_fav)]
        if len(chosen) < desired:
            chosen.extend(favs[max_fav: max_fav + (desired - len(chosen))])
        random.shuffle(chosen)

        bp_colors = ["#16627e", "#1c4c7a", "#147272", "#225686"]
        for i, bp in enumerate(chosen):
            name = bp.get("name", "Unknown Blueprint")
            short = f"BP: {name}"
            if len(short) > 20:
                short = short[:18] + ".."
            self._sampled_bps.append(
                RouletteEntry(
                    label=f"UNLOCK: {name}",
                    description=self._format_bp_description(bp),
                    category="Blueprint Unlock",
                    color=bp_colors[i % len(bp_colors)],
                    wheel_label=short,
                    is_blueprint=True,
                    is_wanted=bool(bp.get("is_favorite")),
                    bp_name=name,
                )
            )

    def _sample_quality_collections(self):
        self._sampled_collections.clear()
        picks = random.sample(_QUALITY_MATERIALS, k=min(5, len(_QUALITY_MATERIALS)))
        col_palette = ["#1c7860", "#226c66", "#268056", "#1a706e"]
        for i, (mat_name, short_name, as_units, min_amt, max_amt, min_band, max_band, bands) in enumerate(picks):
            band = random.randint(min_band, max_band)
            min_q = bands[band - 1] + 1 if band > 0 else 700
            amount = random.randint(min_amt, max_amt)
            unit = ("unit" if amount == 1 else "units") if as_units else "SCU"
            q_str = f"Q{min_q}+"
            wheel_lbl = f"{q_str} {short_name}"
            if len(wheel_lbl) > 16:
                wheel_lbl = wheel_lbl[:14] + ".."
            self._sampled_collections.append(
                RouletteEntry(
                    label=f"COLLECT: {q_str} {mat_name}",
                    description=(
                        f"Mine or scavenge at least {amount} {unit} of {mat_name} "
                        f"at Quality {min_q}+ (Band {band + 1}+) and bring it safely home."
                    ),
                    category="Collection",
                    color=col_palette[i % len(col_palette)],
                    wheel_label=wheel_lbl,
                )
            )

    def _rebuild_active_entries(self, reset_selection: bool = False):
        buckets: list[list[RouletteEntry]] = []
        raw_total = 0
        for cat_name, _ in CATEGORY_ORDER:
            if not self._enabled_cats.get(cat_name, True):
                continue
            if cat_name == "Blueprint Unlock":
                bucket = list(self._sampled_bps)
            else:
                bucket = [e for e in FATE_ENTRIES if e.category == cat_name]
                if cat_name == "Collection":
                    bucket.extend(self._sampled_collections)
            raw_total += len(bucket)
            if bucket:
                buckets.append(bucket)

        self._total_raw_count = raw_total
        if raw_total > 48 and buckets:
            cap = max(3, 44 // len(buckets))
            capped: list[list[RouletteEntry]] = []
            for b in buckets:
                if len(b) > cap:
                    b = random.sample(b, cap)
                capped.append(b)
            buckets = capped

        interleaved: list[RouletteEntry] = []
        max_len = max((len(b) for b in buckets), default=0)
        for idx in range(max_len):
            for b in buckets:
                if idx < len(b):
                    interleaved.append(b[idx])
        self._entries = interleaved
        if reset_selection or self._selected_idx >= len(self._entries):
            self._selected_idx = -1

    def _slice_at_pointer(self, angle: float) -> int:
        n = len(self._entries)
        if n <= 0:
            return -1
        sweep = 360.0 / n
        rel = (-angle) % 360.0
        idx = int(rel / sweep)
        return max(0, min(n - 1, idx))

    def _build_ui(self):
        # Top banner
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
            text="Toggle your active categories, spin the wheel, and follow where fate lands.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
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
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0, minsize=430)
        body.grid_columnconfigure(1, weight=1)

        # LEFT: Wheel, Ticker, Spin Button, Result Card
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORDER_DIM)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        canvas_outer = ctk.CTkFrame(left, fg_color="#0a0d12", corner_radius=8, border_width=1, border_color=BORDER_DIM)
        canvas_outer.pack(padx=14, pady=(14, 6), fill="x")

        self._canvas = tk.Canvas(
            canvas_outer,
            width=396,
            height=388,
            bg="#0a0d12",
            highlightthickness=0
        )
        self._canvas.pack(padx=4, pady=4)

        # Live passing-slice ticker bar
        ticker_box = ctk.CTkFrame(left, fg_color="#0d121a", corner_radius=6, border_width=1, border_color=BORDER_DIM)
        ticker_box.pack(fill="x", padx=14, pady=(0, 8))

        self._lbl_ticker = ctk.CTkLabel(
            ticker_box,
            text=f"READY  ·  {len(self._entries)} FATES LOADED",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color="#a1cdd0",
            height=26
        )
        self._lbl_ticker.pack(fill="x", padx=10, pady=(2, 0))

        self._spin_progress = ctk.CTkProgressBar(
            ticker_box,
            height=3,
            corner_radius=1,
            fg_color="#18202c",
            progress_color=TEXT_CYAN
        )
        self._spin_progress.set(0.0)
        self._spin_progress.pack(fill="x", padx=6, pady=(0, 3))

        # Spin button
        self._btn_spin = ctk.CTkButton(
            left,
            text="SPIN THE WHEEL",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            height=44,
            fg_color="#194b66",
            hover_color="#226284",
            border_color=TEXT_CYAN,
            border_width=1,
            text_color=TEXT_BRIGHT,
            corner_radius=6,
            command=self._start_spin
        )
        self._btn_spin.pack(fill="x", padx=14, pady=(0, 10))

        # Result card
        result_card = ctk.CTkFrame(left, fg_color=CARD_ALT, corner_radius=8, border_width=1, border_color=BORDER_DIM)
        result_card.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._lbl_result_cat = ctk.CTkLabel(
            result_card,
            text="[ AWAITING DESTINY ]",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
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
            wraplength=375,
            justify="left"
        )
        self._lbl_result_name.pack(fill="x", padx=12, pady=(2, 0))

        self._lbl_result_desc = ctk.CTkLabel(
            result_card,
            text="Toggle your categories on the right, then spin to decide your fate.",
            font=ctk.CTkFont(family=FONT_BODY, size=11),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=375,
            justify="left"
        )
        self._lbl_result_desc.pack(fill="x", padx=12, pady=(4, 10))

        # RIGHT: Category Toggles + History
        right_col = ctk.CTkFrame(body, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew")
        right_col.grid_rowconfigure(1, weight=1)
        right_col.grid_columnconfigure(0, weight=1)

        # Category Toggles Panel
        cat_panel = ctk.CTkFrame(right_col, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORDER_DIM)
        cat_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        cat_hdr = ctk.CTkFrame(cat_panel, fg_color="transparent")
        cat_hdr.pack(fill="x", padx=14, pady=(10, 4))

        cat_title_col = ctk.CTkFrame(cat_hdr, fg_color="transparent")
        cat_title_col.pack(side="left")

        ctk.CTkLabel(
            cat_title_col,
            text="CATEGORY POOL",
            font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"),
            text_color=TEXT_CYAN,
            anchor="w"
        ).pack(anchor="w")

        self._lbl_pool_meta = ctk.CTkLabel(
            cat_title_col,
            text="",
            font=ctk.CTkFont(family=FONT_BODY, size=11),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        self._lbl_pool_meta.pack(anchor="w")

        cat_actions = ctk.CTkFrame(cat_hdr, fg_color="transparent")
        cat_actions.pack(side="right", anchor="n")

        self._btn_shuffle_bps = ctk.CTkButton(
            cat_actions,
            text="Shuffle Pool",
            width=86,
            height=26,
            fg_color="#16384a",
            hover_color="#1f4d66",
            border_color="#4fa3c7",
            border_width=1,
            text_color="#bce9ff",
            font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"),
            corner_radius=5,
            command=self._shuffle_blueprints
        )
        self._btn_shuffle_bps.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            cat_actions,
            text="All",
            width=42,
            height=26,
            fg_color=CARD_ALT,
            hover_color="#2a3545",
            border_color=BORDER_MED,
            border_width=1,
            text_color=TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"),
            corner_radius=5,
            command=self._enable_all_cats
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            cat_actions,
            text="None",
            width=50,
            height=26,
            fg_color=CARD_ALT,
            hover_color="#2a3545",
            border_color=BORDER_MED,
            border_width=1,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"),
            corner_radius=5,
            command=self._disable_all_cats
        ).pack(side="left")

        cat_grid = ctk.CTkFrame(cat_panel, fg_color="transparent")
        cat_grid.pack(fill="x", padx=12, pady=(4, 12))
        for col in range(2):
            cat_grid.grid_columnconfigure(col, weight=1, uniform="catcol")

        for idx, (cat_name, cat_color) in enumerate(CATEGORY_ORDER):
            r = idx // 2
            c = idx % 2
            card = ctk.CTkFrame(
                cat_grid,
                fg_color=CARD_ALT,
                corner_radius=6,
                border_width=1,
                border_color=BORDER_MED,
                cursor="hand2"
            )
            card.grid(row=r, column=c, sticky="ew", padx=4, pady=3)

            dot = ctk.CTkFrame(card, width=8, height=8, corner_radius=4, fg_color=cat_color)
            dot.pack(side="left", padx=(10, 8), pady=10)

            lbl = ctk.CTkLabel(
                card,
                text=cat_name,
                font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
                text_color=TEXT_BRIGHT,
                anchor="w"
            )
            lbl.pack(side="left", fill="x", expand=True)

            badge = ctk.CTkLabel(
                card,
                text="0",
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                text_color=TEXT_CYAN,
                fg_color="#11161f",
                corner_radius=4,
                width=28,
                height=20
            )
            badge.pack(side="right", padx=(6, 8), pady=6)

            for w in (card, dot, lbl, badge):
                w.bind("<Button-1>", lambda e, name=cat_name: self._toggle_category(name))

            self._cat_widgets[cat_name] = {
                "card": card,
                "dot": dot,
                "lbl": lbl,
                "badge": badge,
                "color": cat_color,
            }

        # History Panel
        right = ctk.CTkFrame(right_col, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORDER_DIM)
        right.grid(row=1, column=0, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        rh = ctk.CTkFrame(right, fg_color=HEADER, corner_radius=0, height=42, border_width=1, border_color=BORDER_DIM)
        rh.grid(row=0, column=0, sticky="ew")
        rh.grid_propagate(False)

        ctk.CTkLabel(
            rh,
            text="SPIN HISTORY & ROLLS",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=TEXT_CYAN,
            anchor="w"
        ).pack(side="left", padx=14, pady=8)

        ctk.CTkButton(
            rh,
            text="Clear",
            width=56,
            height=24,
            fg_color=CARD_ALT,
            hover_color="#2a3545",
            border_color=BORDER_MED,
            border_width=1,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_BODY, size=10, weight="bold"),
            corner_radius=5,
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
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_FAINT,
            justify="center"
        )
        self._lbl_history_empty.pack(pady=60)

    def _refresh_category_cards(self):
        for cat_name, wdict in self._cat_widgets.items():
            on = self._enabled_cats.get(cat_name, True)
            cat_col = wdict["color"]
            if cat_name == "Blueprint Unlock":
                cnt = len(self._sampled_bps)
            elif cat_name == "Collection":
                cnt = sum(1 for e in FATE_ENTRIES if e.category == "Collection") + len(self._sampled_collections)
            else:
                cnt = sum(1 for e in FATE_ENTRIES if e.category == cat_name)

            if on:
                wdict["card"].configure(
                    fg_color="#1d2838",
                    border_color=_hex_shift(cat_col, 45)
                )
                wdict["dot"].configure(fg_color=_hex_shift(cat_col, 55))
                wdict["lbl"].configure(text_color=TEXT_BRIGHT)
                wdict["badge"].configure(
                    text=str(cnt),
                    text_color="#c3e6fa",
                    fg_color="#111722"
                )
            else:
                wdict["card"].configure(
                    fg_color="#141820",
                    border_color="#28303d"
                )
                wdict["dot"].configure(fg_color="#475366")
                wdict["lbl"].configure(text_color="#6e7c91")
                wdict["badge"].configure(
                    text=str(cnt),
                    text_color="#5d6a7d",
                    fg_color="#10141c"
                )

        if self._total_raw_count > len(self._entries):
            meta = f"{len(self._entries)} on wheel ({self._total_raw_count} in pools)"
        else:
            meta = f"{len(self._entries)} active slices"
        if self._enabled_cats.get("Blueprint Unlock", True):
            meta += f"  ·  {self._missing_bp_count} unowned obtainable BPs"
        self._lbl_pool_meta.configure(text=meta)

        can_shuffle = bool(
            self._entries and (
                (self._enabled_cats.get("Blueprint Unlock", True) and self._missing_bp_count > 0)
                or self._enabled_cats.get("Collection", True)
                or self._total_raw_count > len(self._entries)
            )
        )
        if can_shuffle:
            self._btn_shuffle_bps.configure(state="normal")
        else:
            self._btn_shuffle_bps.configure(state="disabled")

        if not self._spin_active:
            if not self._entries:
                self._btn_spin.configure(state="disabled", text="ENABLE A CATEGORY TO SPIN")
                self._lbl_ticker.configure(text="NO CATEGORIES SELECTED", text_color=TEXT_MUTED)
            else:
                self._btn_spin.configure(state="normal", text="SPIN THE WHEEL")
                self._lbl_ticker.configure(
                    text=f"READY  ·  {len(self._entries)} FATES LOADED",
                    text_color="#a1cdd0"
                )

    def _toggle_category(self, name: str):
        if self._spin_active:
            return
        self._enabled_cats[name] = not self._enabled_cats.get(name, True)
        if self._enabled_cats.get("Blueprint Unlock", True):
            self._sample_missing_blueprints()
        self._save_prefs()
        self._rebuild_active_entries(reset_selection=True)
        self._refresh_category_cards()
        self._draw_wheel(self._current_angle)

    def _enable_all_cats(self):
        if self._spin_active:
            return
        for name, _ in CATEGORY_ORDER:
            self._enabled_cats[name] = True
        self._sample_missing_blueprints()
        self._save_prefs()
        self._rebuild_active_entries(reset_selection=True)
        self._refresh_category_cards()
        self._draw_wheel(self._current_angle)

    def _disable_all_cats(self):
        if self._spin_active:
            return
        for name, _ in CATEGORY_ORDER:
            self._enabled_cats[name] = False
        self._save_prefs()
        self._rebuild_active_entries(reset_selection=True)
        self._refresh_category_cards()
        self._draw_wheel(self._current_angle)

    def _shuffle_blueprints(self):
        if self._spin_active:
            return
        self._sample_missing_blueprints()
        self._sample_quality_collections()
        self._rebuild_active_entries(reset_selection=True)
        self._refresh_category_cards()
        self._draw_wheel(self._current_angle)

    def _draw_wheel(self, angle_offset: float):
        c = self._canvas
        c.delete("all")
        cx, cy, r = 198, 200, 166
        bezel_r = r + 13

        # Outer machined bezel
        c.create_oval(
            cx - bezel_r, cy - bezel_r, cx + bezel_r, cy + bezel_r,
            fill="#161d29", outline="#4a5d7a", width=2
        )
        c.create_oval(
            cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2,
            fill="#0b0f15", outline="#10151f", width=2
        )

        # 24 perimeter chase lights
        bulbs = 24
        bulb_ring = r + 7
        now_ms = int(time.monotonic() * 1000)
        chase = (now_ms // 65) % bulbs
        for i in range(bulbs):
            rad = math.radians(i * (360.0 / bulbs) - 90.0)
            bx = cx + bulb_ring * math.cos(rad)
            by = cy + bulb_ring * math.sin(rad)
            if self._win_glow_alpha > 0.0:
                lit = ((i + (now_ms // 110)) % 2) == 0
                amber = (i % 3 == 0)
            elif self._spin_active:
                d = (i - chase) % bulbs
                lit = (d % 4 == 0) or (d % 4 == 1)
                amber = (i in (0, 1, bulbs - 1))
            else:
                lit = (i % 4 == 0)
                amber = False
            c.create_oval(bx - 3, by - 3, bx + 3, by + 3, fill="#0a0d12", outline="")
            bcol = (TEXT_AMBER if amber else TEXT_CYAN) if lit else "#2f3b4d"
            c.create_oval(bx - 2.2, by - 2.2, bx + 2.2, by + 2.2, fill=bcol, outline="")

        entries = self._entries
        if not entries:
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#141922", outline="#324054", width=1.5)
            c.create_text(
                cx, cy,
                text="Toggle at least one category\non the right to load the wheel.",
                fill=TEXT_MUTED, font=(FONT_BODY, 11, "bold"), justify="center"
            )
            return

        n = len(entries)
        sweep = 360.0 / n
        active_idx = self._slice_at_pointer(angle_offset) if (self._spin_active or self._selected_idx >= 0) else -1
        hub = max(24.0, min(34.0, r * 0.19))
        band_r = r * 0.84

        # Wedges (CW convention from 3 o'clock -> tk_start = -(cw_start + sweep))
        for i, entry in enumerate(entries):
            cw_start = angle_offset + i * sweep - 90.0
            tk_start = -(cw_start + sweep)
            is_hot = (i == active_idx)
            col = entry.color if i % 2 == 0 else _hex_shift(entry.color, -8)
            if is_hot and (self._spin_active or self._win_glow_alpha > 0.0 or self._selected_idx == i):
                col = _hex_shift(col, 24)

            c.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=tk_start, extent=sweep,
                fill=_hex_shift(col, 16), outline="#0b0e15", width=1.2, style="pieslice"
            )
            c.create_arc(
                cx - band_r, cy - band_r, cx + band_r, cy + band_r,
                start=tk_start, extent=sweep,
                fill=col, outline="#0b0e15", width=1.0, style="pieslice"
            )
            if entry.is_blueprint:
                c.create_arc(
                    cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2,
                    start=tk_start + 0.5, extent=max(0.5, sweep - 1.0),
                    outline=TEXT_CYAN, width=1.6, style="arc"
                )
            if is_hot and (self._spin_active or self._selected_idx == i):
                c.create_arc(
                    cx - r + 1.5, cy - r + 1.5, cx + r - 1.5, cy + r - 1.5,
                    start=tk_start, extent=sweep,
                    outline=TEXT_CYAN if entry.is_blueprint else TEXT_AMBER, width=3.0, style="arc"
                )

        # Radial labels
        font_pt = 10 if n <= 12 else (9 if n <= 22 else (8 if n <= 36 else 7))
        text_start = max(hub + 14.0, r * 0.36)
        ir = (text_start + (r - 11.0)) * 0.5
        for i, entry in enumerate(entries):
            cw_mid = angle_offset + (i + 0.5) * sweep - 90.0
            mid_rad = math.radians(cw_mid)
            tx = cx + ir * math.cos(mid_rad)
            ty = cy + ir * math.sin(mid_rad)
            # Keep text right-side-up on the left hemisphere
            left_half = math.cos(mid_rad) < 0.0
            tk_angle = (-cw_mid + 180.0) if left_half else (-cw_mid)
            is_hot = (i == active_idx)
            txt_col = "#ffffff" if is_hot else ("#c3f0ff" if entry.is_blueprint else "#e6ecf4")
            c.create_text(
                tx, ty,
                text=entry.wheel_label,
                fill=txt_col,
                font=(FONT_BODY, font_pt, "bold"),
                angle=tk_angle,
                anchor="center"
            )

        # Boundary pegs
        peg_r = 2.0 if n > 36 else 2.6
        peg_ring = r - 2.0
        for i in range(n):
            rad = math.radians(angle_offset + i * sweep - 90.0)
            px = cx + peg_ring * math.cos(rad)
            py = cy + peg_ring * math.sin(rad)
            c.create_oval(px - peg_r - 0.8, py - peg_r - 0.8, px + peg_r + 0.8, py + peg_r + 0.8, fill="#0c1016", outline="")
            c.create_oval(px - peg_r, py - peg_r, px + peg_r, py + peg_r, fill="#d2e0f0", outline="")

        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#5c728e", width=2.2)

        # Machined center hub
        c.create_oval(
            cx - hub, cy - hub, cx + hub, cy + hub,
            fill="#0e131b",
            outline=TEXT_AMBER if self._spin_active else TEXT_CYAN,
            width=2.2
        )
        c.create_oval(
            cx - hub * 0.72, cy - hub * 0.72, cx + hub * 0.72, cy + hub * 0.72,
            outline="#385b70", width=1.0
        )
        for k in range(8):
            rad = math.radians(angle_offset * 1.5 + k * 45.0)
            c.create_line(
                cx + hub * 0.76 * math.cos(rad), cy + hub * 0.76 * math.sin(rad),
                cx + hub * 0.94 * math.cos(rad), cy + hub * 0.94 * math.sin(rad),
                fill="#7eb6d4", width=1.2
            )
        hub_txt = "SPIN" if self._spin_active else ("LOCK" if self._win_glow_alpha > 0.1 else "FATE")
        c.create_text(
            cx, cy, text=hub_txt,
            fill=TEXT_AMBER if self._spin_active else TEXT_CYAN,
            font=(FONT_TECH, 9, "bold")
        )

        # Pivoted mechanical clacker at 12 o'clock
        piv_x, piv_y = cx, cy - r - 14.0
        deflect_rad = math.radians(self._clacker_kick * 24.0) if self._spin_active else 0.0
        pts_local = [(-8.0, -3.0), (8.0, -3.0), (4.0, 10.0), (0.0, 20.0), (-4.0, 10.0)]
        cos_d, sin_d = math.cos(deflect_rad), math.sin(deflect_rad)
        pts = []
        for lx, ly in pts_local:
            rx = piv_x + lx * cos_d - ly * sin_d
            ry = piv_y + lx * sin_d + ly * cos_d
            pts.extend((rx, ry))
        c.create_polygon(*pts, fill=TEXT_AMBER, outline="#fff0af", width=1.1)
        c.create_oval(piv_x - 4, piv_y - 4, piv_x + 4, piv_y + 4, fill="#181e2a", outline=TEXT_AMBER, width=1.4)

    def _start_spin(self):
        if self._spin_active or not self._entries:
            return
        if self._enabled_cats.get("Blueprint Unlock", True):
            self._sample_missing_blueprints()
            self._rebuild_active_entries(reset_selection=False)
            self._refresh_category_cards()
        if not self._entries:
            return

        self._spin_active = True
        self._win_glow_alpha = 0.0
        self._btn_spin.configure(state="disabled", text="SPINNING...")
        self._lbl_result_cat.configure(text="[ CALCULATING FATE... ]", text_color=TEXT_MUTED)
        self._lbl_result_name.configure(text="—", text_color=TEXT_MUTED)
        self._lbl_result_desc.configure(text="The wheel is spinning... watch the clacker slow.", text_color=TEXT_MUTED)

        self._spin_seed = random.randint(0, 999_999)
        rng = random.Random(self._spin_seed)
        self._spin_target_idx = rng.randint(0, len(self._entries) - 1)

        n = len(self._entries)
        sweep = 360.0 / n
        dest = -(self._spin_target_idx + 0.5) * sweep + rng.uniform(-sweep * 0.38, sweep * 0.38)

        self._spin_start_angle = self._current_angle % 360.0
        dest_norm = dest % 360.0
        delta = (dest_norm - self._spin_start_angle) % 360.0
        extra_spins = rng.randint(7, 11) * 360.0
        self._total_rotation = extra_spins + delta
        self._final_angle = self._spin_start_angle + self._total_rotation
        self._spin_start = time.monotonic()

        self._last_boundary_tick = math.floor(self._spin_start_angle / sweep)
        self._clacker_kick = 0.0
        self._animate_spin()

    def _animate_spin(self):
        elapsed = time.monotonic() - self._spin_start
        t = min(elapsed / self._SPIN_DURATION, 1.0)
        self._spin_progress.set(t)

        if t < 1.0:
            if t < 0.04:
                pull = math.sin((t / 0.04) * math.pi)
                angle_now = self._spin_start_angle - 8.0 * pull
            else:
                u = (t - 0.04) / 0.96
                eased = 1.0 - (1.0 - u) ** 4.8
                angle_now = self._spin_start_angle + self._total_rotation * eased
                if self._entries:
                    sweep = 360.0 / len(self._entries)
                    tick = math.floor(angle_now / sweep)
                    if tick != self._last_boundary_tick:
                        self._last_boundary_tick = tick
                        self._clacker_kick = 1.0
                    else:
                        self._clacker_kick *= 0.76

            self._current_angle = angle_now
            ptr_idx = self._slice_at_pointer(angle_now)
            if 0 <= ptr_idx < len(self._entries):
                cur = self._entries[ptr_idx]
                self._lbl_ticker.configure(
                    text=f"►  [{cur.category.upper()}]  {cur.label}",
                    text_color=TEXT_CYAN if cur.is_blueprint else TEXT_AMBER
                )
            self._draw_wheel(angle_now)
            delay = max(1, int(1000 / self._SPIN_FPS))
            self.after(delay, self._animate_spin)
        else:
            self._current_angle = self._final_angle % 360.0
            self._clacker_kick = 0.0
            self._spin_progress.set(1.0)
            self._on_spin_complete()

    def _on_spin_complete(self):
        self._spin_active = False
        self._total_spins += 1
        self._lbl_spin_count.configure(text=f"TOTAL SPINS: {self._total_spins}")

        self._selected_idx = self._slice_at_pointer(self._current_angle)
        entry = self._entries[self._selected_idx]
        record = SpinRecord(timestamp=time.time(), entry=entry, seed=self._spin_seed)
        self.history.insert(0, record)
        if len(self.history) > self._HISTORY_MAX:
            self.history = self.history[:self._HISTORY_MAX]

        badge = f"[ {entry.category.upper()} ]"
        if entry.is_blueprint and entry.is_wanted:
            badge += "  ·  ★ WANTED"
        self._lbl_result_cat.configure(
            text=badge,
            text_color=TEXT_CYAN if entry.is_blueprint else TEXT_AMBER
        )
        self._lbl_result_name.configure(text=entry.label, text_color=TEXT_BRIGHT)
        self._lbl_result_desc.configure(
            text=entry.description,
            text_color="#bce9ff" if entry.is_blueprint else "#b4c2d4"
        )
        self._lbl_ticker.configure(
            text=f"★  LOCKED: {entry.label}",
            text_color=TEXT_CYAN if entry.is_blueprint else TEXT_BRIGHT
        )

        self._btn_spin.configure(state="normal", text="SPIN THE WHEEL")
        self._win_glow_start = time.monotonic()
        self._win_glow_alpha = 1.0
        self._animate_win_glow()
        self._refresh_history()

    def _animate_win_glow(self):
        elapsed = time.monotonic() - self._win_glow_start
        if elapsed >= self._WIN_GLOW_DURATION or self._spin_active:
            self._win_glow_alpha = 0.0
            self._spin_progress.set(0.0)
            self._draw_wheel(self._current_angle)
            return
        p = elapsed / self._WIN_GLOW_DURATION
        self._win_glow_alpha = (1.0 - p) * (0.65 + 0.35 * math.sin(p * 4.0 * math.pi))
        self._draw_wheel(self._current_angle)
        self.after(28, self._animate_win_glow)

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
                corner_radius=6,
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
                text=entry.label,
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
                text=entry.description.replace("\n", " · "),
                font=ctk.CTkFont(family=FONT_BODY, size=10),
                text_color="#8acde8" if entry.is_blueprint else TEXT_MUTED,
                anchor="w",
                wraplength=400,
                justify="left"
            ).pack(fill="x")

            pill = ctk.CTkFrame(card, fg_color=HEADER, corner_radius=4)
            pill.pack(side="right", padx=8, pady=8)
            ctk.CTkLabel(
                pill,
                text=entry.category.upper(),
                font=ctk.CTkFont(family=FONT_MONO, size=8, weight="bold"),
                text_color=TEXT_CYAN if entry.is_blueprint else TEXT_MUTED
            ).pack(padx=6, pady=2)

            self._history_cards.append(card)

    def _clear_history(self):
        self.history.clear()
        self._refresh_history()
