"""Pure game-log display labels; no screen or image dependencies."""
import re

REGION_MAP = {
    "use1": "US-EAST",
    "use2": "US-EAST",
    "usw1": "US-WEST",
    "usw2": "US-WEST",
    "usc1": "US-CENTRAL",
    "euw1": "EU-WEST",
    "euw2": "EU-WEST",
    "euc1": "EU-CENTRAL",
    "apse1": "ASIA-SE",
    "apse2": "AUS-SYD",
    "apne1": "ASIA-NE",
    "ape1": "ASIA-EAST",
}

LOCATION_FRIENDLY_MAP = {
    "RR ARC LEO": "BAIJINI POINT (ARCCORP)",
    "RR HUR LEO": "EVERUS HARBOR (HURSTON)",
    "RR CRU LEO": "SERAPHIM (CRUSADER)",
    "RR MIC LEO": "PORT TRESSLER (MICROTECH)",
    "RR HUR L1": "HUR-L1 GREEN GLADE",
    "RR HUR L2": "HUR-L2 FAITHFUL DREAM",
    "RR HUR L3": "HUR-L3 THUNDERING EXPRESS",
    "RR HUR L4": "HUR-L4 MELODIC FIELDS",
    "RR HUR L5": "HUR-L5 HIGH COURSE",
    "RR CRU L1": "CRU-L1 AMBITIOUS DREAM",
    "RR CRU L4": "CRU-L4 SHALLOW FIELDS",
    "RR CRU L5": "CRU-L5 BEAUTIFUL GLEN",
    "RR ARC L1": "ARC-L1 WIDE FOREST",
    "RR ARC L2": "ARC-L2 LIVELY PATHWAY",
    "RR ARC L3": "ARC-L3 MODERN EXPRESS",
    "RR ARC L4": "ARC-L4 FAINT GLEN",
    "RR ARC L5": "ARC-L5 YELLOW CORE",
    "RR MIC L1": "MIC-L1 SHALLOW FRONTIER",
    "RR MIC L2": "MIC-L2 LONG FOREST",
    "RR MIC L3": "MIC-L3 ENDLESS ODYSSEY",
    "RR MIC L4": "MIC-L4 RED CROSSROADS",
    "RR MIC L5": "MIC-L5 MODERN ICARUS",
    "STANTON 1": "HURSTON",
    "STANTON 1A": "ARIEL",
    "STANTON 1B": "ABERDEEN",
    "STANTON 1C": "MAGDA",
    "STANTON 1D": "ITA",
    "STANTON 2": "CRUSADER",
    "STANTON 2A": "CELLIN",
    "STANTON 2B": "DAYMAR",
    "STANTON 2C": "YELA",
    "STANTON 3": "ARCCORP",
    "STANTON 3A": "LYRIA",
    "STANTON 3B": "WALA",
    "STANTON 4": "MICROTECH",
    "STANTON 4A": "CALLIOPE",
    "STANTON 4B": "CLIO",
    "STANTON 4C": "EUTERPE",
    "GRIM HEX": "GRIM HEX",
    "GRIMHEX": "GRIM HEX",
    "CELLIN": "CELLIN",
    "DAYMAR": "DAYMAR",
    "YELA": "YELA",
    "HURSTON": "HURSTON",
    "ARIEL": "ARIEL",
    "ABERDEEN": "ABERDEEN",
    "MAGDA": "MAGDA",
    "ITA": "ITA",
    "CRUSADER": "CRUSADER",
    "ARCCORP": "ARCCORP",
    "LYRIA": "LYRIA",
    "WALA": "WALA",
    "MICROTECH": "MICROTECH",
    "CALLIOPE": "CALLIOPE",
    "CLIO": "CLIO",
    "EUTERPE": "EUTERPE",
    "PYRO": "PYRO",
    "SERAPHIM": "SERAPHIM",
    "BAIJINI": "BAIJINI POINT",
    "EVERUS": "EVERUS HARBOR",
    "TRESSLER": "PORT TRESSLER",
    # Jump point stations & Gateways
    "RR JP STANTONPYRO": "PYRO GATEWAY",
    "RR JP PYROSTANTON": "STANTON GATEWAY",
    "RR JP STANTONMAGNUS": "MAGNUS GATEWAY",
    "RR JP STANTONTERRA": "TERRA GATEWAY",
    "RR JP PYRONYX": "NYX GATEWAY",
    "RR_JP_STANTONPYRO": "PYRO GATEWAY",
    "RR_JP_PYROSTANTON": "STANTON GATEWAY",
    "RR_JP_STANTONMAGNUS": "MAGNUS GATEWAY",
    "RR_JP_STANTONTERRA": "TERRA GATEWAY",
    "RR_JP_PYRONYX": "NYX GATEWAY",

    # Pyro Stations & Rest Stops (mined directly from global.ini)
    "RR_P3_LEO": "ORBITUARY",
    "RR_P3": "ORBITUARY",
    "RRP3_LEO": "ORBITUARY",
    "RRP3 LEO": "ORBITUARY",
    "RR P3 LEO": "ORBITUARY",
    "RS_INT_P3LEO": "ORBITUARY",
    "ORBITUARY": "ORBITUARY",
    "848868938": "ORBITUARY",

    "RR_P2_L4": "CHECKMATE",
    "RS_INT_P2L4": "CHECKMATE",
    "CHECKMATE": "CHECKMATE",

    "RR_P3_L1": "STARLIGHT SERVICE STATION",
    "RS_INT_P3L1": "STARLIGHT SERVICE STATION",
    "STARLIGHT": "STARLIGHT SERVICE STATION",

    "RR_P3_L3": "PATCH CITY",
    "RS_INT_P3L3": "PATCH CITY",
    "PATCH CITY": "PATCH CITY",

    "RR_P5_L2": "GASLIGHT",
    "RS_INT_P5L2": "GASLIGHT",
    "GASLIGHT": "GASLIGHT",

    "RR_P5_L4": "ROD'S FUEL 'N SUPPLIES",
    "RS_INT_P5L4": "ROD'S FUEL 'N SUPPLIES",
    "ROD'S FUEL": "ROD'S FUEL 'N SUPPLIES",

    "RR_P5_L5": "RAT'S NEST",
    "RS_INT_P5L5": "RAT'S NEST",
    "RAT'S NEST": "RAT'S NEST",

    "RR_P6": "RUIN STATION",
    "RR_P6_LEO": "RUIN STATION",
    "RS_INT_P6LEO": "RUIN STATION",
    "RUIN STATION": "RUIN STATION",

    "RR_P6_L3": "ENDGAME",
    "RS_INT_P6L3": "ENDGAME",
    "ENDGAME": "ENDGAME",

    "RR_P6_L4": "DUDLEY & DAUGHTERS",
    "RS_INT_P6L4": "DUDLEY & DAUGHTERS",

    "RR_P6_L5": "MEGUMI REFUELING",
    "RS_INT_P6L5": "MEGUMI REFUELING",

    # Stanton Orbital Transfer Stations (mined directly from global.ini)
    "STANTON1_TRANSFER": "EVERUS HARBOR",
    "EVERUS HARBOR": "EVERUS HARBOR",
    "EVERUS": "EVERUS HARBOR",

    "STANTON2_TRANSFER": "SERAPHIM STATION",
    "STANTON2_TRANSFER_SERAPHIM": "SERAPHIM STATION",
    "SERAPHIM STATION": "SERAPHIM STATION",
    "SERAPHIM": "SERAPHIM STATION",
    "3781743795": "SERAPHIM STATION",

    "STANTON3_TRANSFER": "BAIJINI POINT",
    "BAIJINI POINT": "BAIJINI POINT",
    "BAIJINI": "BAIJINI POINT",

    "STANTON4_TRANSFER": "PORT TRESSLER",
    "PORT TRESSLER": "PORT TRESSLER",
    "TRESSLER": "PORT TRESSLER",

    "THECOLLECTORASTEROID": "THE COLLECTOR",
    "THECOLLECTORASTEROID_STANTON": "THE COLLECTOR",
    "PYRO GATEWAY": "PYRO GATEWAY",
    "STANTON GATEWAY": "STANTON GATEWAY",
    "MAGNUS GATEWAY": "MAGNUS GATEWAY",
    "TERRA GATEWAY": "TERRA GATEWAY",
    "NYX GATEWAY": "NYX GATEWAY",
    "1547955914": "PYRO GATEWAY",
}

def translate_region(raw_reg: str) -> str:
    if not raw_reg:
        return "UNKNOWN"
    clean = raw_reg.lower().strip()
    clean = clean.replace("u5", "us").replace("ap5", "aps").replace("10", "1b")
    for prefix, friendly in REGION_MAP.items():
        if clean.startswith(prefix):
            return f"{friendly} ({clean.upper()})"
    if clean.startswith("us"):
        return f"US ({clean.upper()})"
    if clean.startswith("eu"):
        return f"EU ({clean.upper()})"
    return clean.upper()

def translate_location(raw_loc: str, raw_planet: str = "") -> str:
    explicit = {
        "STANTON1_LORVILLE": "LORVILLE (HURSTON)",
        "STANTON3_AREA18": "AREA18 (ARCCORP)",
        "STANTON4_NEWBABBAGE": "NEW BABBAGE (MICROTECH)",
        "STANTON2_ORISON": "ORISON (CRUSADER)",
    }
    direct = (raw_loc or "").strip().upper()
    if direct in explicit:
        return explicit[direct]
    sorted_map = sorted(LOCATION_FRIENDLY_MAP.items(), key=lambda item: len(item[0]), reverse=True)

    candidate = (raw_loc or "").strip()
    if candidate:
        norm = re.sub(r'[^A-Za-z0-9_\-\s]', ' ', candidate).upper()
        norm = re.sub(r'\s+', ' ', norm).strip()
        norm = norm.replace("LE0", "LEO")
        # Log location names vary between spaces and underscores. Never resolve
        # numeric inventory IDs through the old hardcoded station guesses.
        if norm.isdigit():
            return "UNKNOWN"
        for k, v in sorted_map:
            if k.replace("_", " ") in norm.replace("_", " "):
                return v
        if len(norm) >= 3:
            return norm[:28]

    if raw_planet:
        p = raw_planet.upper().replace("00C", "OOC").replace("5TANTON", "STANTON")
        p = re.sub(r'OOC[\s_]*', '', p)
        p = p.replace("_", " ").strip()
        for k, v in sorted_map:
            if k in p:
                return v
        parts = [tok for tok in p.split() if tok not in ("STANTON", "OOC", "LOAD", "COMPLETE")]
        if parts:
            return " ".join(parts)[-26:]
    return "DEEP SPACE"
