#include "SynthRoulette.h"
#include "SynthGlass.h"
#include "SynthPages.h"
#include "CraftingData.h"
#include "MiniJson.h"
#include <windowsx.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>

namespace SynthRoulette {
namespace {
using namespace Gdiplus;

constexpr float kPi = 3.14159265358979323846f;
constexpr UINT_PTR kTimerSpin = 1;
constexpr UINT_PTR kTimerWinGlow = 2;
constexpr int kBpPoolSizeMixed = 8;
constexpr int kBpPoolSizeSolo = 12;

HBRUSH bgBrush = CreateSolidBrush(RGB(15, 16, 19));
HWND window = nullptr;
float scale = 1.0f;
std::filesystem::path dataDir;
std::function<bool(int)> ownedQuery;
std::function<bool(int)> wantedQuery;
NavigateFn navigateCallback;

std::wstring wideUtf8(const char* s) {
    if (!s || !*s) return {};
    int needed = MultiByteToWideChar(CP_UTF8, 0, s, -1, nullptr, 0);
    if (needed <= 1) return {};
    std::wstring out(size_t(needed - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s, -1, out.data(), needed);
    return out;
}

Color scaleColor(Color c, int delta) {
    auto clampByte = [](int v) -> BYTE { return BYTE(std::clamp(v, 0, 255)); };
    return Color(c.GetA(), clampByte(int(c.GetR()) + delta),
                 clampByte(int(c.GetG()) + delta), clampByte(int(c.GetB()) + delta));
}

struct CategoryDef {
    std::string id;
    std::wstring label;
    Color color;
    bool enabled = true;
};

std::vector<CategoryDef> categories = {
    {"pvp",         L"PvP",         Color(255, 40, 108, 148), true},
    {"masochism",   L"Masochism",   Color(255, 114, 52, 116), true},
    {"mining",      L"Mining",      Color(255, 42, 112, 68),  true},
    {"trading",     L"Trading",     Color(255, 138, 102, 28), true},
    {"missions",    L"Missions",    Color(255, 44, 92, 146),  true},
    {"exploration", L"Exploration", Color(255, 44, 104, 108), true},
    {"social",      L"Social",      Color(255, 112, 58, 138), true},
    {"racing",      L"Racing",      Color(255, 140, 86, 26),  true},
    {"chaos",       L"Chaos",       Color(255, 140, 48, 54),  true},
    {"collection",  L"Collection",  Color(255, 32, 128, 106), true},
    {"blueprints",  L"Unlock BP",   Color(255, 24, 124, 142), true},
    {"ships",       L"Earn Ship",   Color(255, 138, 92, 30),  true},
};

struct FateEntry {
    std::wstring label;
    std::wstring wheelLabel;
    std::string catId;
    std::wstring category;
    std::wstring description;
    Color color;
    bool isBlueprint = false;
    bool isShip = false;
    bool isWanted = false;
    int blueprintIndex = -1;
    std::uint64_t shipCrc = 0;
    std::wstring shipName;
    std::string targetMaterial;
};

const std::vector<FateEntry> staticFates = {
    // PvP
    {L"BOUNTY HUNT", L"BOUNTY HUNT", "pvp", L"PvP", L"Grab a Crimson Pledge bounty and hunt down a named player. No mercy.", Color(255, 32, 92, 128)},
    {L"OPEN SEASON", L"OPEN SEASON", "pvp", L"PvP", L"Fly to the most populated shard and pick a fight with the first ship you see.", Color(255, 28, 72, 112)},
    {L"HULL SCRAPER", L"HULL SCRAPER", "pvp", L"PvP", L"Ram a ship. Any ship. Pedestrian or aggressor. Touch that hull.", Color(255, 112, 42, 44)},
    {L"ZERO-G BRAWL", L"ZERO-G BRAWL", "pvp", L"PvP", L"Land at GrimHEX, walk to the bar, start a melee brawl with the first person you see.", Color(255, 34, 98, 132)},
    {L"WANTED: YOU", L"WANTED: YOU", "pvp", L"PvP", L"Rack up a Crimestat 5 as fast as humanly possible. Speed run it.", Color(255, 118, 44, 46)},
    {L"PIRACY RUN", L"PIRACY RUN", "pvp", L"PvP", L"Intercept a hauler at a jump point and demand 50% cargo or delete them.", Color(255, 88, 42, 112)},
    {L"MURDER DERBY", L"MURDER DERBY", "pvp", L"PvP", L"Rented ships only at Delamar. Last one standing among willing participants.", Color(255, 108, 40, 44)},
    {L"TORPEDO THERAPY", L"TORPEDO", "pvp", L"PvP", L"Lock on a capital ship or station module with a torpedo. Release. Feel better.", Color(255, 30, 74, 116)},

    // Masochism
    {L"YEET FROM ORBIT", L"ORBIT YEET", "masochism", L"Masochism", L"Equip no EVA gear. Jump out of your ship at max altitude above Hurston. Survive.", Color(255, 76, 36, 84)},
    {L"FREEFALL YOLO", L"FREEFALL", "masochism", L"Masochism", L"Climb to the highest point on any moon. Jump off. No suit thrusters.", Color(255, 84, 38, 92)},
    {L"GLASS CANNON", L"GLASS CANNON", "masochism", L"Masochism", L"Fly a ship with no shields and no armor into a PvE encounter. Pure skill.", Color(255, 112, 42, 46)},
    {L"DEATHWISH RUN", L"DEATHWISH", "masochism", L"Masochism", L"Equip zero weapons. Enter a contested security zone. Talk your way out.", Color(255, 72, 34, 80)},
    {L"BALL CRUSHER", L"BAD TRADE", "masochism", L"Masochism", L"Take a catastrophically bad trade route. Buy high, sell lower. Lose aUEC on purpose.", Color(255, 106, 40, 46)},
    {L"PAIN TRADER", L"PAIN TRADER", "masochism", L"Masochism", L"Complete 10 cargo runs in a stock Aurora MR. No shortcuts.", Color(255, 96, 74, 24)},
    {L"CRIMESTAT DETOX", L"CS5 DETOX", "masochism", L"Masochism", L"Get yourself to Crimestat 5, then voluntarily turn yourself in and serve full time.", Color(255, 110, 42, 46)},
    {L"THE HARD WAY", L"NO QUANTUM", "masochism", L"Masochism", L"Travel between planetary zones using ONLY sub-cruising speed. No QD.", Color(255, 92, 70, 22)},

    // Mining
    {L"ORE MANIAC", L"ORE MANIAC", "mining", L"Mining", L"Mine a full 32 SCU of pure Quantanium solo in a single run.", Color(255, 36, 94, 54)},
    {L"DETONATION FUN", L"QUANT BOOM", "mining", L"Mining", L"Overcharge a Quantanium rock until it detonates. Ride the blast wave.", Color(255, 40, 102, 58)},
    {L"PROSPECTOR YOLO", L"VOLATILE ROCK", "mining", L"Mining", L"Solo mine the most volatile asteroid you find in the rings. Pray to the shard.", Color(255, 34, 88, 52)},
    {L"VACUUM CLAIM", L"CLAIM FLAG", "mining", L"Mining", L"Plant a claim flag in deep asteroid field. Defend it against anyone who shows up.", Color(255, 42, 104, 60)},
    {L"SCRAPER GRIND", L"HAND MINE", "mining", L"Mining", L"30 consecutive minutes of hand mining on foot. Multitool only, no vehicles.", Color(255, 36, 76, 76)},

    // Trading & Salvage
    {L"MAX HAUL", L"MAX HAUL", "trading", L"Trading", L"Fill the largest ship you own or can rent. 288+ SCU or bust.", Color(255, 98, 76, 22)},
    {L"BLIND TRADE", L"BLIND TRADE", "trading", L"Trading", L"Buy whatever commodity is highlighted first at the terminal. Sell it blind.", Color(255, 106, 82, 24)},
    {L"ILLEGAL GOODS", L"SMUGGLER", "trading", L"Trading", L"Smuggle contraband cargo directly through a security checkpoint.", Color(255, 92, 42, 114)},
    {L"JET FUEL HUSTLE", L"MICRO HAUL", "trading", L"Trading", L"Make 100k aUEC in a single session using only ships under 20 SCU.", Color(255, 96, 74, 22)},
    {L"SCRAP KING", L"SCRAP KING", "trading", L"Trading", L"Find a derelict hull in deep space. Manually strip every single panel off it.", Color(255, 38, 78, 80)},

    // Missions
    {L"HVT DELETION", L"HVT RUSH", "missions", L"Missions", L"Find a High Value Target bounty. Complete it with 10 minutes on the clock.", Color(255, 32, 92, 128)},
    {L"CARGO ESCORT", L"ESCORT", "missions", L"Missions", L"Guard a stranger's cargo hauler from jump to station. Zero aggression from you.", Color(255, 30, 74, 114)},
    {L"UGF STORM", L"UGF SOLO", "missions", L"Missions", L"Solo clear an Illegal Underground Bunker Facility. No squad backup.", Color(255, 112, 44, 46)},
    {L"CIPHER RUN", L"CIPHER RUN", "missions", L"Missions", L"Complete a data heist solo with no primary firearm: hack, grab, extract.", Color(255, 88, 42, 112)},
    {L"HOSPITAL DASH", L"MEDEVAC", "missions", L"Missions", L"Find an incapacitated player in global chat and medevac them to clinic.", Color(255, 38, 94, 56)},
    {L"9-TAILS HUNT", L"9-TAILS X3", "missions", L"Missions", L"Chain three 9-Tails Lockdown missions back-to-back without dying.", Color(255, 34, 96, 130)},
    {L"DERELICT SWEEP", L"WRECK SWEEP", "missions", L"Missions", L"Board a derelict space wreck. Clear every hostile NPC inside solo on foot.", Color(255, 38, 78, 78)},

    // Exploration
    {L"QUANTUM DRIFT", L"MOON DRIFT", "exploration", L"Exploration", L"Pick a random moon. Blind jump towards it. Walk wherever you set down.", Color(255, 34, 76, 116)},
    {L"LAGRANGE CAMP", L"LAGRANGE", "exploration", L"Exploration", L"Park at an unmonitored Lagrange point. Wait 15 mins for whatever comes.", Color(255, 38, 82, 82)},
    {L"DARKSIDE SURVEY", L"NIGHT SURVEY", "exploration", L"Exploration", L"Find the pitch-black night side of any planet. Land and explore 20 mins on foot.", Color(255, 76, 36, 82)},
    {L"RING WALK", L"RING EVA", "exploration", L"Exploration", L"Park ship inside planetary rings. EVA walk outside for 5+ minutes.", Color(255, 34, 78, 118)},
    {L"ALIEN RELIC", L"RELIC HUNT", "exploration", L"Exploration", L"Find and screenshot an alien ruin or cave formation. No guides allowed.", Color(255, 90, 42, 114)},
    {L"DEEP VOID", L"DEEP VOID", "exploration", L"Exploration", L"Quantum jump to the furthest empty void coordinate. Just sit there and chill.", Color(255, 74, 36, 80)},

    // Social
    {L"BAR CRAWL", L"BAR CRAWL", "social", L"Social", L"Hit every bar on GrimHEX, Lorville, and Area18 in one uninterrupted run.", Color(255, 92, 44, 116)},
    {L"TAXI LORD", L"TAXI LORD", "social", L"Social", L"Offer free transport in global chat. Give at least 5 rides without refusing.", Color(255, 38, 96, 56)},
    {L"GLADIATOR PIT", L"MELEE PIT", "social", L"Social", L"Organize a 4-man bare-knuckle melee duel tournament at GrimHEX.", Color(255, 114, 44, 46)},
    {L"PARADE MARCH", L"PARADE", "social", L"Social", L"Lead a convoy of 3+ friends through city limits. All ships, single file, slow.", Color(255, 42, 100, 64)},
    {L"HOSTAGE DEMAND", L"RANSOM RP", "social", L"Social", L"RP take an org buddy hostage. Demand 10,000 aUEC ransom from org chat.", Color(255, 90, 42, 112)},
    {L"STOWAWAY CREW", L"STOWAWAY", "social", L"Social", L"Sneak onto a stranger's multi-crew ship at a spaceport and see how long before they notice.", Color(255, 86, 46, 124)},

    // Racing
    {L"ATMOSPHERE RACE", L"ATMO RACE", "racing", L"Racing", L"Race from landing pad to landing pad in-atmo. No QD. Full boost.", Color(255, 110, 70, 24)},
    {L"CANYON SLASH", L"CANYON RUN", "racing", L"Racing", L"Pick a deep canyon on Daymar or Hurston. Fly through at max SCM and time yourself.", Color(255, 120, 76, 26)},
    {L"COFFEE CAN", L"SLOWEST SHIP", "racing", L"Racing", L"Challenge anyone in global chat to a race using the slowest ship you own.", Color(255, 100, 64, 22)},
    {L"LOW-FLY SKIM", L"LOW-FLY", "racing", L"Racing", L"Fly decoupled below 30m over moon terrain for 5 minutes straight without touching dirt.", Color(255, 116, 72, 24)},
    {L"BUGGY RALLY", L"STV RALLY", "racing", L"Racing", L"Drop STVs or Cyclones at a planetary outpost and race 5 km through rough terrain.", Color(255, 106, 68, 22)},

    // Chaos
    {L"MARKET DUMP", L"MARKET DUMP", "chaos", L"Chaos", L"Dump 1,000 units of any commodity on the lowest paying terminal. Tank it.", Color(255, 118, 42, 44)},
    {L"INSURE IT", L"INSURE IT", "chaos", L"Chaos", L"Crash your primary ship into an asteroid. Reclaim insurance. Repeat once.", Color(255, 114, 40, 44)},
    {L"GRAVITY TEST", L"GRAVITY TEST", "chaos", L"Chaos", L"Find the highest-gravity body. See how long you can sprint before blacking out.", Color(255, 36, 92, 126)},
    {L"DISTRESS AMBUSH", L"FAKE DISTRESS", "chaos", L"Chaos", L"Broadcast a suspicious distress beacon in chat. Set up a welcome party for whoever answers.", Color(255, 112, 40, 44)},
    {L"BUREAUCRAT", L"BUREAUCRAT", "chaos", L"Chaos", L"Stand in every queue/kiosk you find for 10 minutes. Inspect every terminal screen.", Color(255, 40, 80, 80)},
    {L"SPIN AGAIN", L"SPIN AGAIN", "chaos", L"Chaos", L"The wheel has spoken: spin again immediately. Double your task.", Color(255, 58, 58, 94)},
    {L"FREE PASS", L"FREE PASS", "chaos", L"Chaos", L"No task. You survived the wheel. Take 15 minutes of peace in the verse.", Color(255, 38, 96, 56)},

    // Collection (curated rare-item & scavenger party hunts; paired with dynamic Quality Material hunts)
    {L"VALAKKAR PEARL HUNT", L"VALAKKAR PEARL", "collection", L"Collection", L"Venture into Pyro's storm zones and collect an Irradiated Valakkar Pearl (Grade AA or AAA).", Color(255, 30, 112, 92)},
    {L"APEX VALAKKAR FANG", L"APEX FANG", "collection", L"Collection", L"Track and slay an Apex Valakkar (or raid a fresh kill) and extract an Irradiated Valakkar Fang (Apex).", Color(255, 28, 102, 86)},
    {L"YORMANDI TROPHY", L"YORMANDI PART", "collection", L"Collection", L"Hunt down a Yormandi and bring back a Yormandi Eye or Yormandi Tongue intact.", Color(255, 34, 118, 96)},
    {L"KOPION HORN RUN", L"KOPION HORNS", "collection", L"Collection", L"Clear a wilderness den or cave and collect 3 Tundra or Irradiated Kopion Horns without dying.", Color(255, 26, 98, 84)},
    {L"PLUSHIE CREW", L"PLUSHIE CREW", "collection", L"Collection", L"Visit planetary gift shops to collect 3 distinct plushies (Pico, Finley, Francis, Stormwal) for your dash.", Color(255, 36, 122, 100)},
    {L"COMP-BOARD HEIST", L"COMP-BOARD", "collection", L"Collection", L"Infiltrate Checkmate, Orbituary, or Ruin Station's Contested Zone and extract 1 Executive Hangar Comp-Board.", Color(255, 28, 106, 94)},
    {L"ASD DRIVE RECOVERY", L"ASD DRIVE", "collection", L"Collection", L"Run an Onyx / ASD facility and escape with an ASD Secure Drive in your backpack.", Color(255, 32, 114, 98)},
    {L"WIKELO FAVOR GRIND", L"WIKELO FAVOR", "collection", L"Collection", L"Gather rare curiosities or scrip and trade up to earn 1 fresh Wikelo Favor.", Color(255, 38, 126, 102)},
    {L"VANDUUL SCRAPPER", L"VANDUUL SCRAP", "collection", L"Collection", L"Find and extract a piece of Vanduul Plating or Vanduul Metal back to your home hangar.", Color(255, 26, 96, 82)},
    {L"PRISTINE MEDAL HUNT", L"PRISTINE MEDAL", "collection", L"Collection", L"Loot wrecks or outposts until you find any (Pristine) historic medal or Tevarin War Service Marker.", Color(255, 34, 116, 96)},
    {L"ZERO-TO-HERO ARMOR", L"LOOTED SET", "collection", L"Collection", L"Enter a bunker or outpost in a basic undersuit. Leave wearing a full matching looted armor set.", Color(255, 30, 108, 90)},
    {L"GALLEY SNACK RUN", L"SNACK RUN", "collection", L"Collection", L"Collect 5 distinct rare snacks or drinks (like Ermer Family Farms Ice Cream) from across the 'verse.", Color(255, 36, 120, 98)},
};

struct HistoryItem {
    FateEntry entry;
    std::wstring timeStr;
};

struct EarnableShipSpec {
    std::uint64_t crc = 0;
    std::wstring name;
    std::wstring company;
    std::wstring role;
    std::wstring channel;
    std::wstring channelLabel;
    long long priceAuec = 0;
    std::wstring dealerLabel;
    std::wstring recipe;
};

std::vector<FateEntry> sampledBlueprints;
std::vector<FateEntry> sampledCollections;
std::vector<FateEntry> sampledShips;
std::vector<EarnableShipSpec> unownedShipsPool;
std::unordered_set<std::uint64_t> ownedShipCrcs;
int missingObtainableCount = 0;
int missingShipsCount = 0;
int totalEnabledRawCount = 0;
std::vector<FateEntry> activeFates;
std::vector<HistoryItem> history;
int historyScroll = 0;

bool isSpinning = false;
float currentAngle = 0.0f;
float spinStartAngle = 0.0f;
float targetAngle = 0.0f;
float clackerKick = 0.0f;
int lastBoundaryTick = 0;
int lastLivePointerIndex = -1;
int selectedIndex = -1;
int totalSpins = 0;
ULONGLONG spinStartTime = 0;
ULONGLONG winGlowStart = 0;
float winGlowAlpha = 0.0f;
constexpr float kSpinDurationMs = 5000.0f;
constexpr float kWinGlowMs = 1300.0f;

struct HitZone {
    enum Kind { SpinBtn, CategoryToggle, CatAll, CatNone, ShuffleBps, ClearHistory, ResultCard, HistoryRow };
    Kind kind;
    int index = -1;
    RectF rect;
};

std::vector<HitZone> hitZones;
int hoverKind = -1;
int hoverIndex = -1;
bool trackingMouse = false;
RectF historyViewportRect;

bool categoryEnabled(const std::string& id) {
    for (const auto& c : categories) {
        if (c.id == id) return c.enabled;
    }
    return false;
}

int countStaticInCategory(const std::string& id) {
    int count = 0;
    for (const auto& f : staticFates) {
        if (f.catId == id) count++;
    }
    return count;
}

void savePrefs() {
    if (dataDir.empty()) return;
    std::error_code ec;
    std::filesystem::create_directories(dataDir, ec);
    std::ofstream out(dataDir / L"roulette_categories.txt", std::ios::trunc);
    if (!out) return;
    for (const auto& c : categories) {
        out << c.id << "=" << (c.enabled ? 1 : 0) << "\n";
    }
}

void loadPrefs() {
    if (dataDir.empty()) return;
    std::ifstream in(dataDir / L"roulette_categories.txt");
    if (!in) return;
    std::string line;
    while (std::getline(in, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string id = line.substr(0, eq);
        bool on = line.substr(eq + 1) != "0";
        for (auto& c : categories) {
            if (c.id == id) c.enabled = on;
        }
    }
}

std::wstring shortenWheelLabel(const std::wstring& full, const wchar_t* prefix = L"BP: ") {
    std::wstring s = std::wstring(prefix) + full;
    if (s.size() > 16) {
        s = s.substr(0, 14) + L"..";
    }
    return s;
}

std::wstring formatAuec(long long amount) {
    std::wstring digits = std::to_wstring(std::max(0LL, amount));
    std::wstring out;
    int count = 0;
    for (int i = int(digits.size()) - 1; i >= 0; i--) {
        if (count > 0 && count % 3 == 0) out.push_back(L',');
        out.push_back(digits[i]);
        count++;
    }
    std::reverse(out.begin(), out.end());
    return out + L" aUEC";
}

std::wstring formatBlueprintDescription(int bpIdx, bool isWanted) {
    const auto& bp = SCMiner::CRAFT_BLUEPRINTS[bpIdx];
    std::wstring desc;
    if (isWanted) desc += L"★ WANTED  ·  ";
    if (bp.type < SCMiner::CRAFT_TYPE_COUNT) {
        desc += wideUtf8(SCMiner::CRAFT_TYPES[bp.type]);
    }
    if (bp.size >= 0) {
        desc += L"  ·  Size " + std::to_wstring(bp.size);
    }
    if (bp.grade) {
        desc += L"  ·  Grade ";
        desc.push_back(wchar_t(bp.grade));
    }
    if (bp.srcCount > 0) {
        const auto& src = SCMiner::CRAFT_SOURCES[bp.srcFirst];
        desc += L"\nUnlock via: \"" + wideUtf8(src.title) + L"\"";
        std::wstring meta;
        if (src.faction && *src.faction) meta += wideUtf8(src.faction);
        if (src.system && *src.system) {
            if (!meta.empty()) meta += L" · ";
            meta += wideUtf8(src.system);
        }
        if (src.standing && *src.standing) {
            if (!meta.empty()) meta += L" · ";
            meta += wideUtf8(src.standing);
        }
        if (!meta.empty()) desc += L" (" + meta + L")";
        if (bp.srcCount > 1) {
            desc += L"  [+" + std::to_wstring(bp.srcCount - 1) + L" more contract" + (bp.srcCount > 2 ? L"s" : L"") + L"]";
        }
    }
    return desc;
}

void sampleMissingBlueprints() {
    sampledBlueprints.clear();
    missingObtainableCount = 0;

    std::vector<int> wantedMissing;
    std::vector<int> otherMissing;
    for (int b = 0; b < SCMiner::CRAFT_BLUEPRINT_COUNT; b++) {
        const auto& bp = SCMiner::CRAFT_BLUEPRINTS[b];
        if (bp.knownFromStart || bp.srcCount == 0) continue;
        if (ownedQuery && ownedQuery(b)) continue;
        missingObtainableCount++;
        if (wantedQuery && wantedQuery(b)) wantedMissing.push_back(b);
        else otherMissing.push_back(b);
    }

    int enabledNonBp = 0;
    for (const auto& c : categories) {
        if (c.id != "blueprints" && c.enabled) enabledNonBp++;
    }
    const int desired = (enabledNonBp == 0) ? kBpPoolSizeSolo : kBpPoolSizeMixed;

    std::random_device rd;
    std::mt19937 gen(rd() ^ unsigned(GetTickCount64()));
    std::shuffle(wantedMissing.begin(), wantedMissing.end(), gen);
    std::shuffle(otherMissing.begin(), otherMissing.end(), gen);

    std::vector<int> chosen;
    int maxWanted = std::min<int>(int(wantedMissing.size()), (enabledNonBp == 0) ? 5 : 3);
    for (int i = 0; i < maxWanted && int(chosen.size()) < desired; i++) {
        chosen.push_back(wantedMissing[i]);
    }
    for (int b : otherMissing) {
        if (int(chosen.size()) >= desired) break;
        chosen.push_back(b);
    }
    for (int i = maxWanted; i < int(wantedMissing.size()) && int(chosen.size()) < desired; i++) {
        chosen.push_back(wantedMissing[i]);
    }
    std::shuffle(chosen.begin(), chosen.end(), gen);

    const Color bpPalette[] = {
        Color(255, 22, 98, 126),
        Color(255, 28, 76, 122),
        Color(255, 20, 114, 114),
        Color(255, 34, 86, 134),
    };

    for (size_t i = 0; i < chosen.size(); i++) {
        int b = chosen[i];
        std::wstring bpName = wideUtf8(SCMiner::CRAFT_BLUEPRINTS[b].name);
        bool wanted = wantedQuery && wantedQuery(b);
        FateEntry entry;
        entry.label = L"UNLOCK: " + bpName;
        entry.wheelLabel = shortenWheelLabel(bpName);
        entry.catId = "blueprints";
        entry.category = L"Blueprint Unlock";
        entry.description = formatBlueprintDescription(b, wanted);
        entry.color = bpPalette[i % 4];
        entry.isBlueprint = true;
        entry.isWanted = wanted;
        entry.blueprintIndex = b;
        sampledBlueprints.push_back(std::move(entry));
    }
}

void refreshBlueprintsIfStale() {
    bool needsResample = sampledBlueprints.empty();
    if (!needsResample) {
        for (const auto& bp : sampledBlueprints) {
            if (ownedQuery && bp.blueprintIndex >= 0 && ownedQuery(bp.blueprintIndex)) {
                needsResample = true;
                break;
            }
        }
    }
    if (needsResample) {
        sampleMissingBlueprints();
    }
}

void sampleQualityCollections() {
    sampledCollections.clear();

    struct MatPick {
        const char* name;
        const wchar_t* shortName;
        int minAmount;
        int maxAmount;
        int minBand; // 0-based index into CraftMaterial::bands (3 = Band 4+, 4 = Band 5+, 5 = Band 6+)
        int maxBand;
    };
    static const MatPick picks[] = {
        {"Quantainium",     L"Quant",     3,  6,  4, 6},
        {"Savrilium",       L"Savrilium", 2,  4,  4, 6},
        {"Riccite",         L"Riccite",   3,  6,  4, 6},
        {"Stileron",        L"Stileron",  3,  6,  4, 6},
        {"Bexalite",        L"Bexalite",  6,  12, 4, 6},
        {"Taranite",        L"Taranite",  6,  12, 4, 6},
        {"Gold",            L"Gold",      8,  16, 4, 6},
        {"Laranite",        L"Laranite",  10, 20, 4, 6},
        {"Agricium",        L"Agricium",  10, 20, 4, 6},
        {"Lindinium",       L"Lindinium", 4,  8,  4, 6},
        {"Torite",          L"Torite",    6,  12, 4, 6},
        {"Ouratite",        L"Ouratite",  6,  10, 4, 6},
        {"Hadanite",        L"Hadanite",  10, 20, 4, 6},
        {"Feynmaline",      L"Feynmaline",6,  14, 4, 6},
        {"Janalite",        L"Janalite",  1,  2,  3, 5},
        {"Carinite",        L"Carinite",  6,  12, 3, 5},
        {"Saldynium (Ore)", L"Saldynium", 5,  10, 3, 5},
        {"Beradom",         L"Beradom",   8,  16, 4, 6},
        {"Glacosite",       L"Glacosite", 8,  16, 4, 6},
        {"Yormandi Eye",    L"Yormandi",  1,  1,  3, 5},
    };

    std::vector<int> indices(sizeof(picks) / sizeof(picks[0]));
    std::iota(indices.begin(), indices.end(), 0);
    std::random_device rd;
    std::mt19937 gen(rd() ^ unsigned(GetTickCount64() + 137));
    std::shuffle(indices.begin(), indices.end(), gen);

    const Color colPalette[] = {
        Color(255, 28, 120, 96),
        Color(255, 34, 108, 102),
        Color(255, 38, 128, 86),
        Color(255, 26, 112, 110),
    };

    constexpr int kQualityCount = 5;
    for (int k = 0; k < kQualityCount && k < int(indices.size()); k++) {
        const auto& pick = picks[indices[k]];
        int matIdx = SCMiner::materialIndex(pick.name);
        if (matIdx < 0) continue;
        const auto& mat = SCMiner::CRAFT_MATERIALS[matIdx];

        std::uniform_int_distribution<int> bandDist(pick.minBand, pick.maxBand);
        int band = bandDist(gen); // e.g., 4 means Band 5 (bands[3]+1 .. bands[4])
        int minQ = (band > 0 && mat.bands[band - 1] > 0) ? int(mat.bands[band - 1]) + 1 : 700;
        std::uniform_int_distribution<int> amtDist(pick.minAmount, pick.maxAmount);
        int amount = amtDist(gen);

        std::wstring matW = wideUtf8(mat.name);
        std::wstring unitW = mat.asUnits ? (amount == 1 ? L"unit" : L"units") : L"SCU";
        std::wstring qStr = L"Q" + std::to_wstring(minQ) + L"+";

        FateEntry entry;
        entry.label = L"COLLECT: " + qStr + L" " + matW;
        entry.wheelLabel = qStr + L" " + pick.shortName;
        if (entry.wheelLabel.size() > 16) entry.wheelLabel = entry.wheelLabel.substr(0, 14) + L"..";
        entry.catId = "collection";
        entry.category = L"Collection";
        entry.description = L"Mine or scavenge at least " + std::to_wstring(amount) + L" " + unitW +
                            L" of " + matW + L" at Quality " + std::to_wstring(minQ) +
                            L"+ (Band " + std::to_wstring(band + 1) + L"+) and bring it safely home.";
        entry.color = colPalette[k % 4];
        entry.targetMaterial = mat.name;
        sampledCollections.push_back(std::move(entry));
    }
}

bool readFileUtf8(const std::filesystem::path& p, std::string& out) {
    std::ifstream f(p, std::ios::binary);
    if (!f) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    out = ss.str();
    return !out.empty();
}

std::filesystem::path findBundledShipCatalog() {
    wchar_t exeBuf[MAX_PATH]{};
    GetModuleFileNameW(nullptr, exeBuf, MAX_PATH);
    std::filesystem::path cur = std::filesystem::path(exeBuf).parent_path();
    for (int depth = 0; depth < 4; depth++) {
        auto candidate = cur / L"data" / L"ship_catalog.json";
        if (std::filesystem::exists(candidate)) return candidate;
        if (!cur.has_parent_path() || cur.parent_path() == cur) break;
        cur = cur.parent_path();
    }
    return {};
}

void loadEarnableShipsFromKnickKnacks() {
    unownedShipsPool.clear();
    ownedShipCrcs.clear();

    auto parseCatalogEntries = [&](const SCMiner::JsonValue* shipsVal, bool trackOwned) {
        if (!shipsVal) return;
        for (const auto& item : shipsVal->items) {
            auto crc = std::uint64_t(std::llround(item.numberOr("crc", 0.0)));
            const auto* ownedVal = item.find("owned");
            if (trackOwned && ownedVal && ownedVal->boolean) {
                if (crc > 0) ownedShipCrcs.insert(crc);
                continue;
            }
            EarnableShipSpec sp;
            sp.crc = crc;
            sp.name = wideUtf8(item.textOr("name").c_str());
            if (sp.name.empty()) continue;
            sp.company = wideUtf8(item.textOr("company").c_str());
            sp.role = wideUtf8(item.textOr("role", "Ship").c_str());
            sp.channel = wideUtf8(item.textOr("channel", "dealership").c_str());
            sp.channelLabel = wideUtf8(item.textOr("channel_label", "In-Game Dealership").c_str());
            sp.priceAuec = std::llround(item.numberOr("price_auec", 0.0));
            sp.dealerLabel = wideUtf8(item.textOr("dealer_label").c_str());
            sp.recipe = wideUtf8(item.textOr("recipe").c_str());
            unownedShipsPool.push_back(std::move(sp));
        }
    };

    SCMiner::JsonValue root;
    std::string raw, why;
    bool loadedFromState = false;
    if (!dataDir.empty() && readFileUtf8(dataDir / L"knick_knacks_state.json", raw) &&
        SCMiner::parseJson(raw, root, why)) {
        if (const auto* shipsVal = root.find("ships")) {
            loadedFromState = true;
            parseCatalogEntries(shipsVal, true);
        }
    }

    if (!loadedFromState) {
        auto catPath = findBundledShipCatalog();
        if (!catPath.empty() && readFileUtf8(catPath, raw) && SCMiner::parseJson(raw, root, why)) {
            parseCatalogEntries(root.find("ships"), false);
        }
    }
    missingShipsCount = int(unownedShipsPool.size());
}

void sampleMissingShips() {
    loadEarnableShipsFromKnickKnacks();
    sampledShips.clear();
    if (unownedShipsPool.empty()) return;

    int enabledNonShip = 0;
    for (const auto& c : categories) {
        if (c.id != "ships" && c.enabled) enabledNonShip++;
    }
    const int desired = (enabledNonShip == 0) ? kBpPoolSizeSolo : kBpPoolSizeMixed;

    std::vector<size_t> idx(unownedShipsPool.size());
    std::iota(idx.begin(), idx.end(), 0);
    std::random_device rd;
    std::mt19937 gen(rd() ^ unsigned(GetTickCount64() + 313));
    std::shuffle(idx.begin(), idx.end(), gen);

    const Color shipPalette[] = {
        Color(255, 136, 84, 24),
        Color(255, 118, 72, 22),
        Color(255, 146, 98, 28),
        Color(255, 108, 66, 26),
    };

    const size_t take = std::min<size_t>(size_t(desired), idx.size());
    for (size_t k = 0; k < take; k++) {
        const auto& sp = unownedShipsPool[idx[k]];
        FateEntry entry;
        entry.label = L"EARN SHIP: " + sp.name;
        entry.wheelLabel = shortenWheelLabel(sp.name, L"SHIP: ");
        entry.catId = "ships";
        entry.category = L"Earn Unowned Ship";
        std::wstring desc;
        if (!sp.company.empty()) desc += sp.company + L"  ·  ";
        desc += sp.role.empty() ? L"Ship" : sp.role;
        desc += L"\n" + sp.channelLabel;
        if (sp.priceAuec > 0) desc += L"  ·  " + formatAuec(sp.priceAuec);
        if (!sp.dealerLabel.empty()) desc += L"  @  " + sp.dealerLabel;
        if (!sp.recipe.empty()) {
            std::wstring rec = sp.recipe;
            if (rec.size() > 140) rec = rec.substr(0, 137) + L"...";
            desc += L"\nTurn-in: " + rec;
        }
        entry.description = std::move(desc);
        entry.color = shipPalette[k % 4];
        entry.isShip = true;
        entry.shipCrc = sp.crc;
        entry.shipName = sp.name;
        sampledShips.push_back(std::move(entry));
    }
}

struct FateLinkInfo {
    std::string navKind;
    int bpIndex = -1;
    std::wstring target;
    std::wstring badgeLabel;
};

FateLinkInfo resolveFateLink(const FateEntry& entry) {
    if (entry.isBlueprint && entry.blueprintIndex >= 0) {
        return {"blueprint", entry.blueprintIndex, {}, L"Blueprint ↗"};
    }
    if (entry.isShip && !entry.shipName.empty()) {
        return {"ship_finder", -1, entry.shipName, L"Ship Finder ↗"};
    }
    if (entry.catId == "collection") {
        if (!entry.targetMaterial.empty()) {
            if (entry.targetMaterial == "Yormandi Eye") {
                return {"item_finder", -1, L"Yormandi", L"Item Finder ↗"};
            }
            return {"planner_ore", -1, wideUtf8(entry.targetMaterial.c_str()), L"Mining Tools ↗"};
        }
        if (entry.label == L"COMP-BOARD HEIST") return {"executive_hangar", -1, {}, L"Exec Hangar ↗"};
        if (entry.label == L"VALAKKAR PEARL HUNT") return {"item_finder", -1, L"Irradiated Valakkar Pearl", L"Item Finder ↗"};
        if (entry.label == L"APEX VALAKKAR FANG") return {"item_finder", -1, L"Irradiated Valakkar Fang", L"Item Finder ↗"};
        if (entry.label == L"YORMANDI TROPHY") return {"item_finder", -1, L"Yormandi", L"Item Finder ↗"};
        if (entry.label == L"KOPION HORN RUN") return {"item_finder", -1, L"Kopion Horn", L"Item Finder ↗"};
        if (entry.label == L"ASD DRIVE RECOVERY") return {"item_finder", -1, L"ASD Secure Drive", L"Item Finder ↗"};
        if (entry.label == L"WIKELO FAVOR GRIND") return {"item_finder", -1, L"Wikelo Favor", L"Item Finder ↗"};
        if (entry.label == L"VANDUUL SCRAPPER") return {"item_finder", -1, L"Vanduul", L"Item Finder ↗"};
        if (entry.label == L"PRISTINE MEDAL HUNT") return {"item_finder", -1, L"Pristine", L"Item Finder ↗"};
        return {"item_finder", -1, {}, L"Item Finder ↗"};
    }
    if (entry.catId == "mining") {
        if (entry.label == L"ORE MANIAC" || entry.label == L"DETONATION FUN") {
            return {"planner_ore", -1, L"Quantainium", L"Mining Tools ↗"};
        }
        return {"planner", -1, {}, L"Mining Tools ↗"};
    }
    if (entry.catId == "trading") return {"item_finder", -1, {}, L"Item Finder ↗"};
    if (entry.catId == "missions") return {"mission_log", -1, {}, L"Mission Log ↗"};
    if (entry.catId == "pvp" || entry.catId == "racing") return {"hud_piracy", -1, {}, L"Flight / Piracy ↗"};
    if (entry.catId == "exploration") return {"daylight", -1, {}, L"Day/Night ↗"};
    if (entry.catId == "social") return {"people", -1, {}, L"Citizens ↗"};
    return {};
}

void triggerFateLink(const FateEntry& entry) {
    if (!navigateCallback) return;
    auto link = resolveFateLink(entry);
    if (!link.navKind.empty()) {
        navigateCallback(link.navKind, link.bpIndex, link.target);
    }
}

void refreshShipsIfStale() {
    loadEarnableShipsFromKnickKnacks();
    bool needsResample = sampledShips.empty() && !unownedShipsPool.empty();
    if (!needsResample) {
        for (const auto& s : sampledShips) {
            if (s.shipCrc > 0 && ownedShipCrcs.count(s.shipCrc)) {
                needsResample = true;
                break;
            }
        }
    }
    if (needsResample) {
        sampleMissingShips();
    }
}

void rebuildActivePool(bool resetSelection) {
    activeFates.clear();
    totalEnabledRawCount = 0;

    std::random_device rd;
    std::mt19937 gen(rd() ^ unsigned(GetTickCount64() + 73));

    std::vector<std::vector<FateEntry>> buckets;
    for (const auto& c : categories) {
        if (!c.enabled) continue;
        std::vector<FateEntry> bucket;
        if (c.id == "blueprints") {
            for (const auto& f : sampledBlueprints) bucket.push_back(f);
        } else if (c.id == "ships") {
            for (const auto& f : sampledShips) bucket.push_back(f);
        } else {
            for (const auto& f : staticFates) {
                if (f.catId == c.id) bucket.push_back(f);
            }
            if (c.id == "collection") {
                for (const auto& f : sampledCollections) bucket.push_back(f);
            }
        }
        totalEnabledRawCount += int(bucket.size());
        if (!bucket.empty()) buckets.push_back(std::move(bucket));
    }

    // Keep the wheel uncluttered (<= 44 slices) when many categories are enabled,
    // while drawing random subsets from the full pool.
    if (totalEnabledRawCount > 48 && !buckets.empty()) {
        size_t capPerBucket = std::max<size_t>(3, 44 / buckets.size());
        for (auto& b : buckets) {
            if (b.size() > capPerBucket) {
                std::shuffle(b.begin(), b.end(), gen);
                b.resize(capPerBucket);
            }
        }
    }

    size_t maxLen = 0;
    for (const auto& b : buckets) maxLen = std::max(maxLen, b.size());
    for (size_t row = 0; row < maxLen; row++) {
        for (const auto& b : buckets) {
            if (row < b.size()) activeFates.push_back(b[row]);
        }
    }

    if (resetSelection || selectedIndex >= int(activeFates.size())) {
        selectedIndex = -1;
    }
}

int sliceAtPointer(float angle) {
    int n = int(activeFates.size());
    if (n <= 0) return -1;
    float sweep = 360.0f / float(n);
    float rel = std::fmod(-angle, 360.0f);
    if (rel < 0.0f) rel += 360.0f;
    int idx = int(rel / sweep);
    if (idx >= n) idx = n - 1;
    if (idx < 0) idx = 0;
    return idx;
}

void startSpin() {
    if (isSpinning || activeFates.empty()) return;

    // Resample if any shown blueprint or target ship became owned since last view
    if (categoryEnabled("blueprints")) {
        bool stale = false;
        for (const auto& f : activeFates) {
            if (f.isBlueprint && ownedQuery && ownedQuery(f.blueprintIndex)) {
                stale = true;
                break;
            }
        }
        if (stale) {
            sampleMissingBlueprints();
            rebuildActivePool(false);
        }
    }
    if (categoryEnabled("ships")) {
        loadEarnableShipsFromKnickKnacks();
        bool stale = false;
        for (const auto& f : activeFates) {
            if (f.isShip && f.shipCrc > 0 && ownedShipCrcs.count(f.shipCrc)) {
                stale = true;
                break;
            }
        }
        if (stale) {
            sampleMissingShips();
            rebuildActivePool(false);
        }
    }
    if (activeFates.empty()) return;

    isSpinning = true;
    winGlowAlpha = 0.0f;
    KillTimer(window, kTimerWinGlow);
    spinStartTime = GetTickCount64();

    std::random_device rd;
    std::mt19937 gen(rd() ^ unsigned(spinStartTime));
    std::uniform_int_distribution<size_t> distIdx(0, activeFates.size() - 1);
    selectedIndex = int(distIdx(gen));

    const float sweep = 360.0f / float(activeFates.size());
    // Slice i midpoint is at currentAngle + (i + 0.5) * sweep - 90.
    // Top pointer is at -90, so slice i centers under pointer when currentAngle = -(i + 0.5) * sweep.
    float dest = -(float(selectedIndex) + 0.5f) * sweep;
    // Allow close near-misses within [-0.38*sweep, +0.38*sweep] while staying cleanly inside the wedge
    std::uniform_real_distribution<float> jitter(-sweep * 0.38f, sweep * 0.38f);
    dest += jitter(gen);

    spinStartAngle = std::fmod(currentAngle, 360.0f);
    if (spinStartAngle < 0.0f) spinStartAngle += 360.0f;
    currentAngle = spinStartAngle;

    float destNorm = std::fmod(dest, 360.0f);
    if (destNorm < 0.0f) destNorm += 360.0f;

    float delta = std::fmod(destNorm - spinStartAngle, 360.0f);
    if (delta < 0.0f) delta += 360.0f;

    const float extraSpins = float(7 + (gen() % 5)) * 360.0f;
    targetAngle = spinStartAngle + extraSpins + delta;

    lastBoundaryTick = int(std::floor(currentAngle / sweep));
    clackerKick = 0.0f;
    lastLivePointerIndex = sliceAtPointer(currentAngle);

    SetTimer(window, kTimerSpin, 16, nullptr);
    InvalidateRect(window, nullptr, FALSE);
}

void finishSpin() {
    isSpinning = false;
    currentAngle = std::fmod(targetAngle, 360.0f);
    if (currentAngle < 0.0f) currentAngle += 360.0f;
    clackerKick = 0.0f;
    KillTimer(window, kTimerSpin);

    totalSpins++;
    selectedIndex = sliceAtPointer(currentAngle);

    if (selectedIndex >= 0 && selectedIndex < int(activeFates.size())) {
        std::time_t t = std::time(nullptr);
        std::tm local{};
        localtime_s(&local, &t);
        wchar_t buf[32]{};
        wcsftime(buf, 32, L"%H:%M:%S", &local);
        history.insert(history.begin(), {activeFates[selectedIndex], buf});
        if (history.size() > 30) history.pop_back();
        historyScroll = 0;
    }

    winGlowStart = GetTickCount64();
    winGlowAlpha = 1.0f;
    SetTimer(window, kTimerWinGlow, 28, nullptr);
    InvalidateRect(window, nullptr, FALSE);
}

void drawWheel(Graphics& g, float cx, float cy, float r) {
    // Outer ambient glow
    const float glowExtra = (isSpinning ? 28.0f : (winGlowAlpha > 0.0f ? 32.0f * winGlowAlpha : 16.0f)) * scale;
    GraphicsPath auraPath;
    auraPath.AddEllipse(cx - r - glowExtra, cy - r - glowExtra, (r + glowExtra) * 2, (r + glowExtra) * 2);
    PathGradientBrush auraBrush(&auraPath);
    Color centerGlow = winGlowAlpha > 0.0f
        ? Color(BYTE(48 + 44 * winGlowAlpha), 98, 204, 255)
        : (isSpinning ? Color(48, 98, 204, 255) : Color(26, 70, 125, 175));
    auraBrush.SetCenterColor(centerGlow);
    Color edgeGlow(0, 14, 18, 25);
    INT cnt = 1;
    auraBrush.SetSurroundColors(&edgeGlow, &cnt);
    g.FillPath(&auraBrush, &auraPath);

    const float bezelR = r + 13.0f * scale;
    // Metallic outer bezel
    LinearGradientBrush bezelBrush(PointF(cx, cy - bezelR), PointF(cx, cy + bezelR),
                                   Color(255, 36, 46, 62), Color(255, 16, 21, 30));
    g.FillEllipse(&bezelBrush, cx - bezelR, cy - bezelR, bezelR * 2, bezelR * 2);
    Pen bezelOuter(Color(200, 74, 94, 122), 1.6f * scale);
    g.DrawEllipse(&bezelOuter, cx - bezelR, cy - bezelR, bezelR * 2, bezelR * 2);
    Pen bezelInner(Color(180, 12, 16, 22), 2.0f * scale);
    g.DrawEllipse(&bezelInner, cx - r - 1.0f * scale, cy - r - 1.0f * scale, (r + 1.0f * scale) * 2, (r + 1.0f * scale) * 2);

    // 24 animated chase lights around the outer bezel
    constexpr int kBulbs = 24;
    const float bulbRingR = r + 6.5f * scale;
    const float bulbR = 2.4f * scale;
    ULONGLONG nowMs = GetTickCount64();
    int chasePhase = int(nowMs / 65) % kBulbs;
    for (int i = 0; i < kBulbs; i++) {
        float deg = float(i) * (360.0f / kBulbs) - 90.0f;
        float rad = deg * kPi / 180.0f;
        float bx = cx + bulbRingR * std::cos(rad);
        float by = cy + bulbRingR * std::sin(rad);

        bool lit = false;
        bool amber = false;
        if (winGlowAlpha > 0.0f) {
            lit = ((i + int(nowMs / 110)) % 2) == 0;
            amber = (i % 3 == 0);
        } else if (isSpinning) {
            int d = (i - chasePhase + kBulbs) % kBulbs;
            lit = (d % 4 == 0) || (d % 4 == 1);
            amber = (i == 0 || i == 1 || i == kBulbs - 1);
        } else {
            lit = (i % 4 == 0);
        }

        SolidBrush socket(Color(255, 10, 13, 19));
        g.FillEllipse(&socket, bx - bulbR - 0.8f * scale, by - bulbR - 0.8f * scale,
                      (bulbR + 0.8f * scale) * 2, (bulbR + 0.8f * scale) * 2);
        Color bulbCol = lit
            ? (amber ? Color(245, 251, 191, 36) : Color(235, 98, 204, 255))
            : Color(120, 48, 60, 78);
        SolidBrush bulbBrush(bulbCol);
        g.FillEllipse(&bulbBrush, bx - bulbR, by - bulbR, bulbR * 2, bulbR * 2);
    }

    if (activeFates.empty()) {
        SolidBrush emptyDisc(Color(255, 20, 25, 34));
        g.FillEllipse(&emptyDisc, cx - r, cy - r, r * 2, r * 2);
        Font fEmpty(L"Segoe UI", 12.0f * scale, FontStyleBold, UnitPixel);
        SolidBrush bEmpty(Color(255, 130, 145, 165));
        StringFormat sf;
        sf.SetAlignment(StringAlignmentCenter);
        sf.SetLineAlignment(StringAlignmentCenter);
        g.DrawString(L"Toggle at least one category\non the right to load the wheel.", -1, &fEmpty,
                     RectF(cx - r * 0.8f, cy - 30 * scale, r * 1.6f, 60 * scale), &sf, &bEmpty);
        return;
    }

    const int n = int(activeFates.size());
    const float sweep = 360.0f / float(n);
    const int activeIdx = (isSpinning || selectedIndex >= 0) ? sliceAtPointer(currentAngle) : -1;
    const float hub = std::clamp(r * 0.19f, 24.0f * scale, 35.0f * scale);
    const float bandInnerR = r * 0.84f;

    // Pie wedges with two-tone radial banding & active pointer highlight
    for (int i = 0; i < n; i++) {
        const auto& entry = activeFates[i];
        float start = currentAngle + float(i) * sweep - 90.0f;
        bool isHotSlice = (i == activeIdx);

        Color baseCol = entry.color;
        if (i % 2 == 1) baseCol = scaleColor(baseCol, -7);
        if (isHotSlice && (isSpinning || winGlowAlpha > 0.0f || selectedIndex == i)) {
            int boost = isSpinning ? 22 : int(16 + 26 * winGlowAlpha);
            baseCol = scaleColor(baseCol, boost);
        }

        // Outer band (brighter accent strip near rim)
        SolidBrush outerBrush(scaleColor(baseCol, 16));
        g.FillPie(&outerBrush, cx - r, cy - r, r * 2, r * 2, start, sweep);

        // Main inner wedge body
        SolidBrush innerBrush(baseCol);
        g.FillPie(&innerBrush, cx - bandInnerR, cy - bandInnerR, bandInnerR * 2, bandInnerR * 2, start, sweep);

        // Blueprint special outer highlight shimmer
        if (entry.isBlueprint) {
            Pen bpArc(Color(155, 98, 204, 255), 1.8f * scale);
            g.DrawArc(&bpArc, cx - r + 2.5f * scale, cy - r + 2.5f * scale,
                      (r - 2.5f * scale) * 2, (r - 2.5f * scale) * 2, start + 0.6f, std::max(0.5f, sweep - 1.2f));
        }

        // Crisp radial divider
        Pen edgePen(Color(215, 11, 14, 21), 1.3f * scale);
        g.DrawPie(&edgePen, cx - r, cy - r, r * 2, r * 2, start, sweep);

        // Active slice glow arc under pointer
        if (isHotSlice && (isSpinning || selectedIndex == i)) {
            Color arcCol = (entry.isBlueprint ? Color(245, 98, 204, 255) : Color(245, 251, 191, 36));
            Pen glowArc(arcCol, 3.0f * scale);
            g.DrawArc(&glowArc, cx - r + 1.5f * scale, cy - r + 1.5f * scale,
                      (r - 1.5f * scale) * 2, (r - 1.5f * scale) * 2, start, sweep);
        }
    }

    // Subtle inner depth shadow ring around the hub
    GraphicsPath shadowRing;
    shadowRing.AddEllipse(cx - hub - 14.0f * scale, cy - hub - 14.0f * scale,
                          (hub + 14.0f * scale) * 2, (hub + 14.0f * scale) * 2);
    Pen innerShadow(Color(95, 8, 10, 15), 10.0f * scale);
    g.DrawPath(&innerShadow, &shadowRing);

    // Radial wedge labels
    float rFactor = std::clamp(r / (165.0f * scale), 0.72f, 1.05f);
    float fontPx = ((n <= 10) ? 11.5f : (n <= 18) ? 10.0f : (n <= 28) ? 8.8f : (n <= 40) ? 7.8f : 7.0f) * rFactor;
    Font fSlice(L"Segoe UI", fontPx * scale, FontStyleBold, UnitPixel);
    StringFormat sfSlice;
    sfSlice.SetLineAlignment(StringAlignmentCenter);
    sfSlice.SetFormatFlags(StringFormatFlagsNoWrap);
    sfSlice.SetTrimming(StringTrimmingEllipsisCharacter);

    const float textStart = std::max(hub + 14.0f * scale, r * 0.36f);
    const float textEnd = r - 11.0f * scale;
    const float textSpan = std::max(24.0f * scale, textEnd - textStart);
    const float textH = std::max(14.0f * scale, fontPx * scale * 1.55f);

    for (int i = 0; i < n; i++) {
        const auto& entry = activeFates[i];
        float midDeg = currentAngle + (float(i) + 0.5f) * sweep - 90.0f;
        float midRad = midDeg * kPi / 180.0f;
        bool leftHalf = std::cos(midRad) < 0.0f;
        bool isHotSlice = (i == activeIdx);

        auto saved = g.Save();
        g.TranslateTransform(cx, cy);
        if (leftHalf) {
            g.RotateTransform(midDeg + 180.0f);
            sfSlice.SetAlignment(StringAlignmentNear);
            RectF box(-textEnd, -textH * 0.5f, textSpan, textH);
            Color txtCol = isHotSlice ? Color(255, 255, 255, 255)
                         : (entry.isBlueprint ? Color(245, 195, 240, 255)
                         : (entry.isShip ? Color(248, 252, 224, 152) : Color(230, 234, 240, 246)));
            SolidBrush shadowBrush(Color(160, 6, 8, 12));
            RectF shBox = box;
            shBox.X += 1.0f;
            shBox.Y += 1.0f;
            g.DrawString(entry.wheelLabel.c_str(), -1, &fSlice, shBox, &sfSlice, &shadowBrush);
            SolidBrush txtBrush(txtCol);
            g.DrawString(entry.wheelLabel.c_str(), -1, &fSlice, box, &sfSlice, &txtBrush);
        } else {
            g.RotateTransform(midDeg);
            sfSlice.SetAlignment(StringAlignmentFar);
            RectF box(textStart, -textH * 0.5f, textSpan, textH);
            Color txtCol = isHotSlice ? Color(255, 255, 255, 255)
                         : (entry.isBlueprint ? Color(245, 195, 240, 255)
                         : (entry.isShip ? Color(248, 252, 224, 152) : Color(230, 234, 240, 246)));
            SolidBrush shadowBrush(Color(160, 6, 8, 12));
            RectF shBox = box;
            shBox.X += 1.0f;
            shBox.Y += 1.0f;
            g.DrawString(entry.wheelLabel.c_str(), -1, &fSlice, shBox, &sfSlice, &shadowBrush);
            SolidBrush txtBrush(txtCol);
            g.DrawString(entry.wheelLabel.c_str(), -1, &fSlice, box, &sfSlice, &txtBrush);
        }
        g.Restore(saved);
    }

    // Rim pegs at every slice boundary
    const float pegR = (n > 36 ? 2.1f : 2.7f) * scale;
    const float pegRing = r - 2.0f * scale;
    for (int i = 0; i < n; i++) {
        float rad = (currentAngle + float(i) * sweep - 90.0f) * kPi / 180.0f;
        float px = cx + pegRing * std::cos(rad);
        float py = cy + pegRing * std::sin(rad);
        SolidBrush pegBack(Color(255, 12, 16, 22));
        g.FillEllipse(&pegBack, px - pegR - 0.8f * scale, py - pegR - 0.8f * scale,
                      (pegR + 0.8f * scale) * 2, (pegR + 0.8f * scale) * 2);
        SolidBrush pegTop(Color(255, 210, 224, 240));
        g.FillEllipse(&pegTop, px - pegR, py - pegR, pegR * 2, pegR * 2);
    }

    // Outer wheel rim
    Pen rimPen(Color(240, 92, 114, 142), 2.2f * scale);
    g.DrawEllipse(&rimPen, cx - r, cy - r, r * 2, r * 2);

    // Ornate center hub with rotating reticle ticks
    LinearGradientBrush hubBg(PointF(cx, cy - hub), PointF(cx, cy + hub),
                              Color(255, 24, 32, 44), Color(255, 11, 14, 20));
    g.FillEllipse(&hubBg, cx - hub, cy - hub, hub * 2, hub * 2);
    Pen hubOuter(isSpinning ? Color(255, 251, 191, 36) : Color(255, 98, 204, 255), 2.2f * scale);
    g.DrawEllipse(&hubOuter, cx - hub, cy - hub, hub * 2, hub * 2);
    Pen hubInner(Color(110, 98, 204, 255), 1.0f * scale);
    g.DrawEllipse(&hubInner, cx - hub * 0.72f, cy - hub * 0.72f, hub * 1.44f, hub * 1.44f);

    for (int k = 0; k < 8; k++) {
        float rad = (currentAngle * 1.5f + float(k) * 45.0f) * kPi / 180.0f;
        float x1 = cx + hub * 0.76f * std::cos(rad);
        float y1 = cy + hub * 0.76f * std::sin(rad);
        float x2 = cx + hub * 0.94f * std::cos(rad);
        float y2 = cy + hub * 0.94f * std::sin(rad);
        Pen tickP(Color(160, 148, 198, 220), 1.2f * scale);
        g.DrawLine(&tickP, x1, y1, x2, y2);
    }

    Font fHub(L"Bahnschrift", std::max(8.0f, hub * 0.34f), FontStyleBold, UnitPixel);
    SolidBrush bHub(isSpinning ? Color(255, 251, 191, 36) : Color(255, 98, 204, 255));
    StringFormat sfHub;
    sfHub.SetAlignment(StringAlignmentCenter);
    sfHub.SetLineAlignment(StringAlignmentCenter);
    const wchar_t* hubTxt = isSpinning ? L"SPIN" : (winGlowAlpha > 0.1f ? L"LOCK" : L"FATE");
    g.DrawString(hubTxt, -1, &fHub, RectF(cx - hub, cy - hub, hub * 2, hub * 2), &sfHub, &bHub);

    // Pivoted mechanical clacker / pointer at 12 o'clock
    float pivotX = cx;
    float pivotY = cy - r - 15.0f * scale;
    float deflectDeg = isSpinning ? (clackerKick * 24.0f) : 0.0f;

    auto savedPtr = g.Save();
    g.TranslateTransform(pivotX, pivotY);
    g.RotateTransform(deflectDeg);

    PointF pointerPoly[] = {
        PointF(-8.5f * scale, -3.0f * scale),
        PointF(8.5f * scale, -3.0f * scale),
        PointF(4.0f * scale, 10.0f * scale),
        PointF(0.0f, 21.0f * scale),
        PointF(-4.0f * scale, 10.0f * scale),
    };
    SolidBrush ptrShadow(Color(150, 0, 0, 0));
    g.TranslateTransform(1.5f * scale, 1.5f * scale);
    g.FillPolygon(&ptrShadow, pointerPoly, 5);
    g.TranslateTransform(-1.5f * scale, -1.5f * scale);

    LinearGradientBrush ptrFill(PointF(0, -3.0f * scale), PointF(0, 21.0f * scale),
                                Color(255, 253, 210, 74), Color(255, 217, 138, 12));
    g.FillPolygon(&ptrFill, pointerPoly, 5);
    Pen ptrEdge(Color(255, 255, 240, 175), 1.1f * scale);
    g.DrawPolygon(&ptrEdge, pointerPoly, 5);

    SolidBrush pinBody(Color(255, 24, 30, 42));
    g.FillEllipse(&pinBody, -4.0f * scale, -4.0f * scale, 8.0f * scale, 8.0f * scale);
    Pen pinRing(Color(255, 251, 191, 36), 1.4f * scale);
    g.DrawEllipse(&pinRing, -4.0f * scale, -4.0f * scale, 8.0f * scale, 8.0f * scale);
    g.Restore(savedPtr);
}

void paint(HDC dc) {
    RECT rc{};
    GetClientRect(window, &rc);
    int w = rc.right, h = rc.bottom;
    if (w <= 0 || h <= 0) return;

    hitZones.clear();

    Bitmap bmp(w, h, PixelFormat32bppPARGB);
    Graphics g(&bmp);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);

    g.Clear(Color(255, 15, 16, 19));
    SynthGlass::ambient(g, {0, 0, float(w), float(h)});

    const float pad = 14.0f * scale;
    const float leftW = std::clamp(float(w) * 0.47f, 340.0f * scale, 510.0f * scale);

    // =========================================================================
    // LEFT COLUMN: Wheel, Live Ticker, Spin Button, Result Card
    // =========================================================================
    RectF leftCard(pad, pad, leftW - pad, float(h) - pad * 2);
    SynthGlass::panel(g, leftCard, false, false, 12.0f * scale);

    const float lx = leftCard.X + 14.0f * scale;
    const float lw = leftCard.Width - 28.0f * scale;

    // Header row inside left card
    Font fTitle(L"Bahnschrift", 17.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bTitle(Color(255, 240, 246, 252));
    g.DrawString(L"FATE ROULETTE", -1, &fTitle, PointF(lx, leftCard.Y + 11.0f * scale), &bTitle);

    std::wstring spinsTxt = L"SPINS: " + std::to_wstring(totalSpins);
    RectF spinBadge(leftCard.GetRight() - 102.0f * scale, leftCard.Y + 11.0f * scale, 88.0f * scale, 22.0f * scale);
    SynthGlass::rounded(g, spinBadge, Color(200, 18, 25, 36), 6.0f * scale, Color(80, 251, 191, 36));
    Font fMono(L"Consolas", 10.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bAmber(Color(255, 251, 191, 36));
    StringFormat sfCenter;
    sfCenter.SetAlignment(StringAlignmentCenter);
    sfCenter.SetLineAlignment(StringAlignmentCenter);
    g.DrawString(spinsTxt.c_str(), -1, &fMono, spinBadge, &sfCenter, &bAmber);

    // Reserve vertical space for ticker + spin button + result card
    const float tickerH = 28.0f * scale;
    const float btnH = 42.0f * scale;
    const float resH = std::clamp(float(h) * 0.20f, 114.0f * scale, 154.0f * scale);
    const float bottomReserved = tickerH + 8.0f * scale + btnH + 10.0f * scale + resH + 14.0f * scale;
    const float wheelTop = leftCard.Y + 42.0f * scale;
    const float availWheelH = std::max(180.0f * scale, leftCard.GetBottom() - bottomReserved - wheelTop);
    const float wheelR = std::clamp(std::min((lw - 26.0f * scale) * 0.5f, (availWheelH - 34.0f * scale) * 0.5f),
                                    82.0f * scale, 184.0f * scale);
    const float wheelCx = leftCard.X + leftCard.Width * 0.5f;
    const float wheelCy = wheelTop + availWheelH * 0.5f + 4.0f * scale;

    drawWheel(g, wheelCx, wheelCy, wheelR);

    // Passing Ticker Pill
    const float tickerY = wheelTop + availWheelH + 2.0f * scale;
    RectF tickerRect(lx, tickerY, lw, tickerH);
    SynthGlass::rounded(g, tickerRect, Color(220, 13, 18, 26), 6.0f * scale,
                        isSpinning ? Color(140, 251, 191, 36) : Color(60, 148, 175, 205));

    int pointerIdx = activeFates.empty() ? -1 : sliceAtPointer(currentAngle);
    std::wstring tickerText;
    Color tickerColor(255, 148, 163, 184);
    if (activeFates.empty()) {
        tickerText = L"NO CATEGORIES SELECTED";
    } else if (isSpinning && pointerIdx >= 0) {
        const auto& cur = activeFates[pointerIdx];
        tickerText = L"►  [" + cur.category + L"]  " + cur.label;
        tickerColor = cur.isBlueprint ? Color(255, 118, 224, 255) : Color(255, 251, 191, 36);
    } else if (!isSpinning && selectedIndex >= 0 && selectedIndex < int(activeFates.size())) {
        const auto& cur = activeFates[selectedIndex];
        tickerText = L"★  LOCKED: " + cur.label;
        tickerColor = cur.isBlueprint ? Color(255, 98, 204, 255) : Color(255, 240, 248, 255);
    } else {
        tickerText = L"READY  ·  " + std::to_wstring(activeFates.size()) + L" FATES LOADED";
        tickerColor = Color(255, 161, 205, 208);
    }
    Font fTicker(L"Consolas", 10.5f * scale, FontStyleBold, UnitPixel);
    SolidBrush bTicker(tickerColor);
    StringFormat sfTicker;
    sfTicker.SetAlignment(StringAlignmentCenter);
    sfTicker.SetLineAlignment(StringAlignmentCenter);
    sfTicker.SetFormatFlags(StringFormatFlagsNoWrap);
    sfTicker.SetTrimming(StringTrimmingEllipsisCharacter);
    g.DrawString(tickerText.c_str(), -1, &fTicker,
                 RectF(tickerRect.X + 8.0f * scale, tickerRect.Y, tickerRect.Width - 16.0f * scale, tickerRect.Height),
                 &sfTicker, &bTicker);

    // Spin tension progress line at bottom of ticker
    if (isSpinning) {
        float t = std::min(float(GetTickCount64() - spinStartTime) / kSpinDurationMs, 1.0f);
        RectF barBg(tickerRect.X + 6.0f * scale, tickerRect.GetBottom() - 3.0f * scale,
                    tickerRect.Width - 12.0f * scale, 2.0f * scale);
        SolidBrush bBarBg(Color(90, 45, 58, 76));
        g.FillRectangle(&bBarBg, barBg);
        RectF barFg(barBg.X, barBg.Y, barBg.Width * t, barBg.Height);
        SolidBrush bBarFg(t > 0.65f ? Color(255, 251, 191, 36) : Color(255, 98, 204, 255));
        g.FillRectangle(&bBarFg, barFg);
    }

    // Spin Button
    const float btnY = tickerY + tickerH + 8.0f * scale;
    RectF btnRect(lx, btnY, lw, btnH);
    bool canSpin = !isSpinning && !activeFates.empty();
    bool btnHot = canSpin && hoverKind == HitZone::SpinBtn;
    SynthGlass::panel(g, btnRect, isSpinning, btnHot, 8.0f * scale);
    if (canSpin) {
        Pen accentEdge(btnHot ? Color(220, 98, 204, 255) : Color(130, 98, 204, 255), 1.3f * scale);
        GraphicsPath bp;
        SynthGlass::shape(bp, btnRect, 8.0f * scale);
        g.DrawPath(&accentEdge, &bp);
    }
    Font fBtn(L"Bahnschrift", 14.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bBtn(isSpinning ? Color(255, 251, 191, 36)
                  : (!activeFates.empty() ? Color(255, 244, 249, 255) : Color(255, 110, 122, 138)));
    const wchar_t* btnTxt = isSpinning ? L"SPINNING THE WHEEL..."
                          : (activeFates.empty() ? L"ENABLE A CATEGORY TO SPIN" : L"SPIN THE WHEEL");
    g.DrawString(btnTxt, -1, &fBtn, btnRect, &sfCenter, &bBtn);
    if (canSpin) hitZones.push_back({HitZone::SpinBtn, -1, btnRect});

    // Result Card
    const float resY = btnY + btnH + 10.0f * scale;
    const float actualResH = leftCard.GetBottom() - resY - 12.0f * scale;
    if (actualResH > 46.0f * scale) {
        RectF resRect(lx, resY, lw, actualResH);
        bool hasRes = selectedIndex >= 0 && selectedIndex < int(activeFates.size()) && !isSpinning;
        FateLinkInfo resLink = hasRes ? resolveFateLink(activeFates[selectedIndex]) : FateLinkInfo{};
        bool resClickable = hasRes && !resLink.navKind.empty();
        bool resHot = resClickable && hoverKind == HitZone::ResultCard;
        SynthGlass::panel(g, resRect, false, resHot, 8.0f * scale);

        if (hasRes) {
            const auto& fate = activeFates[selectedIndex];
            if (winGlowAlpha > 0.0f) {
                Pen winBorder(fate.isBlueprint
                                  ? Color(BYTE(190 * winGlowAlpha), 98, 204, 255)
                                  : Color(BYTE(190 * winGlowAlpha), 251, 191, 36),
                              2.0f * scale);
                GraphicsPath rp;
                SynthGlass::shape(rp, resRect, 8.0f * scale);
                g.DrawPath(&winBorder, &rp);
            }

            // Left accent strip
            SolidBrush resStrip(fate.color);
            g.FillRectangle(&resStrip, resRect.X, resRect.Y + 6.0f * scale, 4.0f * scale, resRect.Height - 12.0f * scale);

            Font fCat(L"Consolas", 10.0f * scale, FontStyleBold, UnitPixel);
            SolidBrush bCat(fate.isBlueprint ? Color(255, 98, 204, 255) : Color(255, 251, 191, 36));
            std::wstring catText = L"[ " + fate.category + L" ]";
            if (fate.isBlueprint && fate.isWanted) catText += L"  ·  ★ WANTED";
            g.DrawString(catText.c_str(), -1, &fCat, PointF(resRect.X + 14.0f * scale, resRect.Y + 9.0f * scale), &bCat);

            if (resClickable) {
                float badgeW = 96.0f * scale;
                RectF linkBadge(resRect.GetRight() - badgeW - 10.0f * scale, resRect.Y + 6.0f * scale, badgeW, 18.0f * scale);
                SynthGlass::rounded(g, linkBadge,
                                    resHot ? Color(220, 26, 48, 72) : Color(180, 16, 26, 38),
                                    4.0f * scale,
                                    resHot ? Color(180, 98, 204, 255) : Color(90, 98, 204, 255));
                Font fBadge(L"Segoe UI", 9.5f * scale, FontStyleBold, UnitPixel);
                SolidBrush bBadge(resHot ? Color(255, 224, 246, 255) : Color(255, 148, 224, 255));
                g.DrawString(resLink.badgeLabel.c_str(), -1, &fBadge, linkBadge, &sfCenter, &bBadge);
                hitZones.push_back({HitZone::ResultCard, selectedIndex, resRect});
            }

            Font fResTitle(L"Bahnschrift", 15.5f * scale, FontStyleBold, UnitPixel);
            SolidBrush bResTitle(Color(255, 248, 250, 252));
            RectF titleR(resRect.X + 14.0f * scale, resRect.Y + 26.0f * scale, resRect.Width - 26.0f * scale, 24.0f * scale);
            StringFormat sfTitle;
            sfTitle.SetFormatFlags(StringFormatFlagsNoWrap);
            sfTitle.SetTrimming(StringTrimmingEllipsisCharacter);
            g.DrawString(fate.label.c_str(), -1, &fResTitle, titleR, &sfTitle, &bResTitle);

            Font fDesc(L"Segoe UI", 11.0f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bDesc(Color(255, 174, 189, 206));
            RectF descRect(resRect.X + 14.0f * scale, resRect.Y + 52.0f * scale,
                           resRect.Width - 26.0f * scale, std::max(20.0f * scale, resRect.Height - 58.0f * scale));
            g.DrawString(fate.description.c_str(), -1, &fDesc, descRect, nullptr, &bDesc);
        } else {
            Font fPrompt(L"Segoe UI", 11.5f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bPrompt(Color(255, 142, 157, 173));
            const wchar_t* msg = isSpinning
                ? L"The wheel is spinning... watch the clacker slow."
                : L"Toggle your categories on the right, then spin to decide your fate.";
            g.DrawString(msg, -1, &fPrompt,
                         RectF(resRect.X + 14.0f * scale, resRect.Y + 8.0f * scale,
                               resRect.Width - 28.0f * scale, resRect.Height - 16.0f * scale),
                         &sfCenter, &bPrompt);
        }
    }

    // =========================================================================
    // RIGHT COLUMN: Category Toggles (top) + Spin History (bottom)
    // =========================================================================
    const float rightX = leftW + pad;
    const float rightW = float(w) - rightX - pad;

    // Top Panel: Category Toggles
    const float catCardH = 224.0f * scale;
    RectF catPanel(rightX, pad, rightW, catCardH);
    SynthGlass::panel(g, catPanel, false, false, 12.0f * scale);

    Font fHdr(L"Bahnschrift", 14.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bCyan(Color(255, 98, 204, 255));
    g.DrawString(L"CATEGORY POOL", -1, &fHdr, PointF(rightX + 14.0f * scale, pad + 12.0f * scale), &bCyan);

    Font fSub(L"Segoe UI", 10.5f * scale, FontStyleRegular, UnitPixel);
    SolidBrush bMuted(Color(255, 142, 157, 173));
    std::wstring poolMeta = (totalEnabledRawCount > int(activeFates.size()))
        ? (std::to_wstring(activeFates.size()) + L" on wheel (" + std::to_wstring(totalEnabledRawCount) + L" in pools)")
        : (std::to_wstring(activeFates.size()) + L" active slices");
    if (categoryEnabled("blueprints")) {
        poolMeta += L"  ·  " + std::to_wstring(missingObtainableCount) + L" unowned BPs";
    }
    if (categoryEnabled("ships")) {
        poolMeta += L"  ·  " + std::to_wstring(missingShipsCount) + L" unowned ships";
    }
    g.DrawString(poolMeta.c_str(), -1, &fSub, PointF(rightX + 14.0f * scale, pad + 31.0f * scale), &bMuted);

    // Quick action pills in Category Pool header: All / None / Shuffle
    const float pillH = 24.0f * scale;
    const float pillY = pad + 13.0f * scale;
    auto drawSmallPill = [&](float x, float pw, const wchar_t* text, HitZone::Kind kind, bool accent) {
        RectF r(x, pillY, pw, pillH);
        bool hot = !isSpinning && hoverKind == kind;
        SynthGlass::panel(g, r, false, hot, 6.0f * scale);
        if (accent) {
            Pen p(Color(110, 98, 204, 255), 1.0f);
            GraphicsPath gp;
            SynthGlass::shape(gp, r, 6.0f * scale);
            g.DrawPath(&p, &gp);
        }
        Font fp(L"Segoe UI", 10.0f * scale, FontStyleBold, UnitPixel);
        SolidBrush bp(isSpinning ? Color(255, 90, 102, 118)
                                 : (accent ? Color(255, 148, 224, 255) : Color(255, 220, 230, 240)));
        g.DrawString(text, -1, &fp, r, &sfCenter, &bp);
        if (!isSpinning) hitZones.push_back({kind, -1, r});
    };

    float rightEdge = rightX + rightW - 14.0f * scale;
    float shufW = 80.0f * scale;
    float noneW = 50.0f * scale;
    float allW = 42.0f * scale;
    if (!activeFates.empty() && (categoryEnabled("blueprints") || categoryEnabled("ships") || categoryEnabled("collection") || totalEnabledRawCount > int(activeFates.size()))) {
        drawSmallPill(rightEdge - shufW, shufW, L"Shuffle Pool", HitZone::ShuffleBps, true);
        rightEdge -= shufW + 6.0f * scale;
    }
    drawSmallPill(rightEdge - noneW, noneW, L"None", HitZone::CatNone, false);
    rightEdge -= noneW + 6.0f * scale;
    drawSmallPill(rightEdge - allW, allW, L"All", HitZone::CatAll, false);

    // 4x3 Uniform Grid of Category Toggle Cards
    const float gridX = rightX + 14.0f * scale;
    const float gridY = pad + 54.0f * scale;
    const float gridW = rightW - 28.0f * scale;
    const float gapX = 8.0f * scale;
    const float gapY = 6.0f * scale;
    const float cellW3 = (gridW - gapX * 2.0f) / 3.0f;
    const float cellH = (catCardH - (gridY - pad) - 12.0f * scale - gapY * 3.0f) / 4.0f;

    Font fCatLbl(L"Segoe UI", 11.2f * scale, FontStyleBold, UnitPixel);
    Font fCatCnt(L"Consolas", 9.5f * scale, FontStyleBold, UnitPixel);
    StringFormat sfLeft;
    sfLeft.SetAlignment(StringAlignmentNear);
    sfLeft.SetLineAlignment(StringAlignmentCenter);
    sfLeft.SetFormatFlags(StringFormatFlagsNoWrap);
    sfLeft.SetTrimming(StringTrimmingEllipsisCharacter);

    for (size_t i = 0; i < categories.size(); i++) {
        int col = int(i % 3);
        int row = int(i / 3);
        RectF cr(gridX + float(col) * (cellW3 + gapX), gridY + float(row) * (cellH + gapY), cellW3, cellH);
        const auto& cat = categories[i];
        bool hot = !isSpinning && hoverKind == HitZone::CategoryToggle && hoverIndex == int(i);

        if (cat.enabled) {
            SynthGlass::panel(g, cr, true, hot, 7.0f * scale);
            Color tint(42, cat.color.GetR(), cat.color.GetG(), cat.color.GetB());
            SynthGlass::rounded(g, cr, tint, 7.0f * scale, Color(115, cat.color.GetR() + 45, cat.color.GetG() + 45, cat.color.GetB() + 45));
        } else {
            SynthGlass::rounded(g, cr, hot ? Color(220, 30, 35, 44) : Color(195, 20, 24, 32), 7.0f * scale,
                                hot ? Color(90, 140, 155, 175) : Color(50, 110, 125, 145));
        }

        // Category color dot
        float dotR = 4.0f * scale;
        float dotX = cr.X + 10.0f * scale;
        float dotY = cr.Y + cr.Height * 0.5f;
        SolidBrush dotBrush(cat.enabled ? scaleColor(cat.color, 55) : Color(120, 90, 100, 115));
        g.FillEllipse(&dotBrush, dotX - dotR, dotY - dotR, dotR * 2, dotR * 2);

        // Count pill on right
        int itemCount = (cat.id == "blueprints") ? int(sampledBlueprints.size())
                      : (cat.id == "ships") ? int(sampledShips.size())
                      : (cat.id == "collection") ? (countStaticInCategory("collection") + int(sampledCollections.size()))
                      : countStaticInCategory(cat.id);
        std::wstring cntTxt = ((cat.id == "blueprints" && missingObtainableCount == 0) ||
                               (cat.id == "ships" && missingShipsCount == 0))
            ? L"0"
            : std::to_wstring(itemCount);
        float cntW = 24.0f * scale;
        RectF cntR(cr.GetRight() - cntW - 8.0f * scale, cr.Y + (cr.Height - 18.0f * scale) * 0.5f, cntW, 18.0f * scale);
        SynthGlass::rounded(g, cntR, cat.enabled ? Color(140, 12, 18, 26) : Color(110, 16, 19, 25), 4.0f * scale);
        SolidBrush bCnt(cat.enabled ? Color(255, 195, 224, 240) : Color(255, 96, 108, 124));
        g.DrawString(cntTxt.c_str(), -1, &fCatCnt, cntR, &sfCenter, &bCnt);

        // Category label
        RectF lblR(cr.X + 20.0f * scale, cr.Y, cntR.X - (cr.X + 22.0f * scale), cr.Height);
        SolidBrush bLbl(cat.enabled ? Color(255, 242, 247, 252) : Color(255, 116, 128, 145));
        g.DrawString(cat.label.c_str(), -1, &fCatLbl, lblR, &sfLeft, &bLbl);

        if (!isSpinning) hitZones.push_back({HitZone::CategoryToggle, int(i), cr});
    }

    // Bottom Panel: Spin History & Rolls
    const float histY = pad + catCardH + 10.0f * scale;
    const float histH = float(h) - histY - pad;
    RectF histPanel(rightX, histY, rightW, histH);
    SynthGlass::panel(g, histPanel, false, false, 12.0f * scale);

    g.DrawString(L"SPIN HISTORY & ROLLS", -1, &fHdr, PointF(rightX + 14.0f * scale, histY + 13.0f * scale), &bCyan);

    if (!history.empty()) {
        RectF clrR(rightX + rightW - 72.0f * scale, histY + 12.0f * scale, 58.0f * scale, 24.0f * scale);
        bool hot = hoverKind == HitZone::ClearHistory;
        SynthGlass::panel(g, clrR, false, hot, 6.0f * scale);
        Font fClr(L"Segoe UI", 10.0f * scale, FontStyleBold, UnitPixel);
        SolidBrush bClr(Color(255, 190, 202, 216));
        g.DrawString(L"Clear", -1, &fClr, clrR, &sfCenter, &bClr);
        hitZones.push_back({HitZone::ClearHistory, -1, clrR});
    }

    const float listTop = histY + 46.0f * scale;
    const float listH = std::max(40.0f * scale, histPanel.GetBottom() - listTop - 10.0f * scale);
    historyViewportRect = RectF(rightX + 12.0f * scale, listTop, rightW - 24.0f * scale, listH);

    if (history.empty()) {
        Font fEmpty(L"Segoe UI", 12.0f * scale, FontStyleRegular, UnitPixel);
        SolidBrush bEmpty(Color(255, 110, 122, 138));
        g.DrawString(L"No fates recorded yet. Spin the wheel to begin.", -1, &fEmpty, historyViewportRect, &sfCenter, &bEmpty);
    } else {
        const float rowH = 52.0f * scale;
        const float rowStep = rowH + 6.0f * scale;
        const int maxScroll = std::max(0, int(history.size()) * int(rowStep) - int(listH));
        historyScroll = std::clamp(historyScroll, 0, maxScroll);

        auto clipSave = g.Save();
        g.SetClip(historyViewportRect);

        Font fItem(L"Bahnschrift", 12.0f * scale, FontStyleBold, UnitPixel);
        Font fTime(L"Consolas", 9.5f * scale, FontStyleRegular, UnitPixel);
        Font fBadge(L"Segoe UI", 9.0f * scale, FontStyleBold, UnitPixel);
        Font fSub(L"Segoe UI", 10.0f * scale, FontStyleRegular, UnitPixel);
        StringFormat sfSub;
        sfSub.SetTrimming(StringTrimmingEllipsisCharacter);
        sfSub.SetFormatFlags(StringFormatFlagsNoWrap);

        float rowY = listTop - float(historyScroll);
        for (size_t i = 0; i < history.size(); i++) {
            const auto& item = history[i];
            if (rowY + rowH >= listTop - 4.0f && rowY <= historyViewportRect.GetBottom() + 4.0f) {
                RectF cardR(historyViewportRect.X, rowY, historyViewportRect.Width, rowH);
                auto link = resolveFateLink(item.entry);
                bool clickable = !link.navKind.empty();
                bool rowHot = clickable && hoverKind == HitZone::HistoryRow && hoverIndex == int(i);
                SynthGlass::panel(g, cardR, false, rowHot, 6.0f * scale);

                SolidBrush strip(item.entry.color);
                g.FillRectangle(&strip, cardR.X, cardR.Y + 4.0f * scale, 4.0f * scale, cardR.Height - 8.0f * scale);

                float rightPad = clickable ? 158.0f * scale : 76.0f * scale;
                RectF titleR(cardR.X + 12.0f * scale, cardR.Y + 6.0f * scale, cardR.Width - rightPad, 18.0f * scale);
                SolidBrush bItem(rowHot ? Color(255, 148, 224, 255) : Color(255, 238, 243, 248));
                g.DrawString(item.entry.label.c_str(), -1, &fItem, titleR, &sfSub, &bItem);

                if (clickable) {
                    float bw = 84.0f * scale;
                    RectF badgeR(cardR.GetRight() - 66.0f * scale - bw, cardR.Y + 5.0f * scale, bw, 17.0f * scale);
                    SynthGlass::rounded(g, badgeR,
                                        rowHot ? Color(220, 26, 48, 72) : Color(170, 15, 22, 32),
                                        4.0f * scale,
                                        rowHot ? Color(170, 98, 204, 255) : Color(75, 98, 204, 255));
                    SolidBrush bBadge(rowHot ? Color(255, 224, 246, 255) : Color(255, 138, 210, 242));
                    g.DrawString(link.badgeLabel.c_str(), -1, &fBadge, badgeR, &sfCenter, &bBadge);

                    RectF hitR = cardR;
                    if (hitR.Intersect(historyViewportRect) && hitR.Height > 8.0f) {
                        hitZones.push_back({HitZone::HistoryRow, int(i), hitR});
                    }
                }

                SolidBrush bTime(Color(255, 130, 144, 160));
                g.DrawString(item.timeStr.c_str(), -1, &fTime,
                             PointF(cardR.GetRight() - 60.0f * scale, cardR.Y + 8.0f * scale), &bTime);

                std::wstring sub = L"[" + item.entry.category + L"]  " + item.entry.description;
                for (wchar_t& ch : sub) {
                    if (ch == L'\n') ch = L' ';
                }
                RectF subR(cardR.X + 12.0f * scale, cardR.Y + 27.0f * scale, cardR.Width - 24.0f * scale, 16.0f * scale);
                SolidBrush bSub(item.entry.isBlueprint ? Color(255, 138, 206, 232) : Color(255, 152, 166, 184));
                g.DrawString(sub.c_str(), -1, &fSub, subR, &sfSub, &bSub);
            }
            rowY += rowStep;
        }
        g.Restore(clipSave);
    }

    Graphics screen(dc);
    screen.DrawImage(&bmp, 0, 0);
}

LRESULT CALLBACK proc(HWND hwnd, UINT msg, WPARAM w, LPARAM l) {
    if (msg == WM_PAINT) {
        PAINTSTRUCT ps{};
        HDC dc = BeginPaint(hwnd, &ps);
        paint(dc);
        EndPaint(hwnd, &ps);
        return 0;
    }
    if (msg == WM_PRINTCLIENT) {
        paint(reinterpret_cast<HDC>(w));
        return 0;
    }
    if (msg == WM_ERASEBKGND) {
        RECT r{};
        GetClientRect(hwnd, &r);
        FillRect(reinterpret_cast<HDC>(w), &r, bgBrush);
        return 1;
    }

    if (msg == WM_TIMER && w == kTimerSpin) {
        if (isSpinning) {
            ULONGLONG elapsed = GetTickCount64() - spinStartTime;
            float t = std::min(float(elapsed) / kSpinDurationMs, 1.0f);

            if (t >= 1.0f) {
                finishSpin();
            } else {
                // Phase 1 (0..0.04): quick -8 deg wind-up pullback
                // Phase 2 (0.04..1.0): explosive spin into long quintic slow-motion tail
                if (t < 0.04f) {
                    float pull = std::sin((t / 0.04f) * kPi);
                    currentAngle = spinStartAngle - 8.0f * pull;
                } else {
                    float u = (t - 0.04f) / 0.96f;
                    float eased = 1.0f - std::pow(1.0f - u, 4.8f);
                    currentAngle = spinStartAngle + (targetAngle - spinStartAngle) * eased;

                    if (!activeFates.empty()) {
                        float sweep = 360.0f / float(activeFates.size());
                        int tick = int(std::floor(currentAngle / sweep));
                        if (tick != lastBoundaryTick) {
                            lastBoundaryTick = tick;
                            clackerKick = 1.0f;
                        } else {
                            clackerKick *= 0.76f;
                        }
                    }
                }
                InvalidateRect(hwnd, nullptr, FALSE);
            }
        }
        return 0;
    }

    if (msg == WM_TIMER && w == kTimerWinGlow) {
        float elapsed = float(GetTickCount64() - winGlowStart);
        if (elapsed >= kWinGlowMs) {
            winGlowAlpha = 0.0f;
            KillTimer(hwnd, kTimerWinGlow);
        } else {
            float p = elapsed / kWinGlowMs;
            winGlowAlpha = (1.0f - p) * (0.65f + 0.35f * std::sin(p * 4.0f * kPi));
        }
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }

    if (msg == WM_MOUSEMOVE) {
        if (!trackingMouse) {
            TRACKMOUSEEVENT tme{sizeof(tme), TME_LEAVE, hwnd, 0};
            TrackMouseEvent(&tme);
            trackingMouse = true;
        }
        float mx = float(GET_X_LPARAM(l));
        float my = float(GET_Y_LPARAM(l));
        int nextKind = -1;
        int nextIndex = -1;
        for (const auto& hz : hitZones) {
            if (hz.rect.Contains(mx, my)) {
                nextKind = int(hz.kind);
                nextIndex = hz.index;
                break;
            }
        }
        if (nextKind != hoverKind || nextIndex != hoverIndex) {
            hoverKind = nextKind;
            hoverIndex = nextIndex;
            InvalidateRect(hwnd, nullptr, FALSE);
        }
        return 0;
    }

    if (msg == WM_MOUSELEAVE) {
        trackingMouse = false;
        if (hoverKind != -1 || hoverIndex != -1) {
            hoverKind = -1;
            hoverIndex = -1;
            InvalidateRect(hwnd, nullptr, FALSE);
        }
        return 0;
    }

    if (msg == WM_SETCURSOR && LOWORD(l) == HTCLIENT) {
        SetCursor(LoadCursor(nullptr, hoverKind != -1 ? IDC_HAND : IDC_ARROW));
        return TRUE;
    }

    if (msg == WM_LBUTTONDOWN) {
        SetFocus(hwnd);
        float mx = float(GET_X_LPARAM(l));
        float my = float(GET_Y_LPARAM(l));
        for (const auto& hz : hitZones) {
            if (!hz.rect.Contains(mx, my)) continue;
            if (hz.kind == HitZone::SpinBtn) {
                startSpin();
            } else if (hz.kind == HitZone::CategoryToggle && !isSpinning &&
                       hz.index >= 0 && hz.index < int(categories.size())) {
                categories[hz.index].enabled = !categories[hz.index].enabled;
                if (categoryEnabled("blueprints")) {
                    // Adjust solo vs mixed BP count cleanly
                    sampleMissingBlueprints();
                }
                if (categoryEnabled("ships")) {
                    // Adjust solo vs mixed unowned ship count cleanly
                    sampleMissingShips();
                }
                savePrefs();
                rebuildActivePool(true);
                InvalidateRect(hwnd, nullptr, FALSE);
            } else if (hz.kind == HitZone::CatAll && !isSpinning) {
                for (auto& c : categories) c.enabled = true;
                sampleMissingBlueprints();
                sampleMissingShips();
                savePrefs();
                rebuildActivePool(true);
                InvalidateRect(hwnd, nullptr, FALSE);
            } else if (hz.kind == HitZone::CatNone && !isSpinning) {
                for (auto& c : categories) c.enabled = false;
                savePrefs();
                rebuildActivePool(true);
                InvalidateRect(hwnd, nullptr, FALSE);
            } else if (hz.kind == HitZone::ShuffleBps && !isSpinning) {
                sampleMissingBlueprints();
                sampleQualityCollections();
                sampleMissingShips();
                rebuildActivePool(true);
                InvalidateRect(hwnd, nullptr, FALSE);
            } else if (hz.kind == HitZone::ClearHistory) {
                history.clear();
                historyScroll = 0;
                InvalidateRect(hwnd, nullptr, FALSE);
            } else if (hz.kind == HitZone::ResultCard && !isSpinning &&
                       selectedIndex >= 0 && selectedIndex < int(activeFates.size())) {
                triggerFateLink(activeFates[selectedIndex]);
            } else if (hz.kind == HitZone::HistoryRow &&
                       hz.index >= 0 && hz.index < int(history.size())) {
                triggerFateLink(history[hz.index].entry);
            }
            break;
        }
        return 0;
    }

    if (msg == WM_MOUSEWHEEL) {
        POINT pt{GET_X_LPARAM(l), GET_Y_LPARAM(l)};
        ScreenToClient(hwnd, &pt);
        if (historyViewportRect.Contains(float(pt.x), float(pt.y))) {
            int delta = GET_WHEEL_DELTA_WPARAM(w);
            historyScroll -= (delta / WHEEL_DELTA) * int(42.0f * scale);
            InvalidateRect(hwnd, nullptr, FALSE);
            return 0;
        }
    }

    if (msg == WM_KEYDOWN && (w == VK_SPACE || w == VK_RETURN)) {
        startSpin();
        return 0;
    }

    if (msg == WM_SIZE) {
        scale = std::max(0.7f, float(GetDpiForWindow(hwnd)) / 96.0f);
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }

    return DefWindowProcW(hwnd, msg, w, l);
}

} // namespace

void show(HWND parent, const std::filesystem::path& directory,
          std::function<bool(int)> isOwnedFn,
          std::function<bool(int)> isWantedFn,
          NavigateFn onNavigateFn) {
    dataDir = directory;
    if (isOwnedFn) ownedQuery = std::move(isOwnedFn);
    if (isWantedFn) wantedQuery = std::move(isWantedFn);
    if (onNavigateFn) navigateCallback = std::move(onNavigateFn);

    static bool prefsLoaded = false;
    if (!prefsLoaded) {
        loadPrefs();
        prefsLoaded = true;
    }
    refreshBlueprintsIfStale();
    refreshShipsIfStale();
    if (sampledCollections.empty()) sampleQualityCollections();
    rebuildActivePool(false);

    if (!window) {
        WNDCLASSW c{};
        c.hInstance = GetModuleHandleW(nullptr);
        c.lpszClassName = L"SynthScanRoulette";
        c.lpfnWndProc = proc;
        c.hbrBackground = bgBrush;
        c.hCursor = LoadCursor(nullptr, IDC_ARROW);
        RegisterClassW(&c);

        scale = std::max(0.7f, float(GetDpiForWindow(parent)) / 96.0f);
        window = CreateWindowExW(
            WS_EX_CONTROLPARENT,
            c.lpszClassName,
            L"Fate Roulette",
            WS_CHILD | WS_CLIPCHILDREN,
            0, 0, 900, 800,
            parent,
            nullptr,
            c.hInstance,
            nullptr
        );
    }

    SynthPages::mount(window);
    ShowWindow(window, SW_SHOW);
    InvalidateRect(window, nullptr, TRUE);
}

void close() {
    if (window) {
        KillTimer(window, kTimerSpin);
        KillTimer(window, kTimerWinGlow);
        DestroyWindow(window);
        window = nullptr;
    }
}

} // namespace SynthRoulette
