#include "SynthRoulette.h"
#include "SynthGlass.h"
#include "SynthPages.h"
#include <windowsx.h>
#include <vector>
#include <string>
#include <random>
#include <cmath>
#include <ctime>

namespace SynthRoulette {
namespace {
using namespace Gdiplus;

HWND window = nullptr;
HFONT fontTitle = nullptr;
HFONT fontBtn = nullptr;
float scale = 1.0f;

struct FateEntry {
    std::wstring label;
    std::wstring category;
    std::wstring description;
    Color color;
};

const std::vector<FateEntry> fates = {
    // PvP
    {L"BOUNTY HUNT", L"PvP", L"Grab a Crimson Pledge bounty and hunt down a named player. No mercy.", Color(255, 26, 79, 107)},
    {L"OPEN SEASON", L"PvP", L"Fly to the most populated shard and pick a fight with the first ship you see.", Color(255, 26, 58, 92)},
    {L"HULL SCRAPER", L"PvP", L"Ram a ship. Any ship. Pedestrian or aggressor. Touch that hull.", Color(255, 92, 34, 34)},
    {L"ZERO-G BRAWL", L"PvP", L"Land at GrimHEX, walk to the bar, start a melee brawl with the first person you see.", Color(255, 26, 79, 107)},
    {L"WANTED: YOU", L"PvP", L"Rack up a Crimestat 5 as fast as humanly possible. Speed run it.", Color(255, 92, 34, 34)},
    {L"PIRACY RUN", L"PvP", L"Intercept a hauler at a jump point and demand 50% cargo or delete them.", Color(255, 75, 32, 96)},
    {L"MURDER DERBY", L"PvP", L"Rented ships only at Delamar. Last one standing among willing participants.", Color(255, 92, 34, 34)},
    {L"TORPEDO THERAPY", L"PvP", L"Lock on a capital ship or station module with a torpedo. Release. Feel better.", Color(255, 26, 58, 92)},

    // Masochism
    {L"YEET FROM ORBIT", L"Masochism", L"Equip no EVA gear. Jump out of your ship at max altitude above Hurston. Survive.", Color(255, 58, 26, 58)},
    {L"FREEFALL YOLO", L"Masochism", L"Climb to the highest point on any moon. Jump off. No suit thrusters.", Color(255, 58, 26, 58)},
    {L"GLASS CANNON", L"Masochism", L"Fly a ship with no shields and no armor into a PvE encounter. Pure skill.", Color(255, 92, 34, 34)},
    {L"DEATHWISH RUN", L"Masochism", L"Equip zero weapons. Enter a contested security zone. Talk your way out.", Color(255, 58, 26, 58)},
    {L"BALL CRUSHER", L"Masochism", L"Take a catastrophically bad trade route. Buy high, sell lower. Lose aUEC on purpose.", Color(255, 92, 34, 34)},
    {L"PAIN TRADER", L"Masochism", L"Complete 10 cargo runs in a stock Aurora MR. No shortcuts.", Color(255, 74, 58, 13)},
    {L"CRIMESTAT DETOX", L"Masochism", L"Get yourself to Crimestat 5, then voluntarily turn yourself in and serve full time.", Color(255, 92, 34, 34)},
    {L"THE HARD WAY", L"Masochism", L"Travel between planetary systems using ONLY sub-cruising speed. No QD.", Color(255, 74, 58, 13)},

    // Mining
    {L"ORE MANIAC", L"Mining", L"Mine a full 32 SCU of pure Quantanium solo in a single run.", Color(255, 31, 74, 43)},
    {L"DETONATION FUN", L"Mining", L"Overcharge a Quantanium rock until it detonates. Ride the blast wave.", Color(255, 31, 74, 43)},
    {L"PROSPECTOR YOLO", L"Mining", L"Solo mine the most volatile asteroid you find in the rings. Pray to the shard.", Color(255, 31, 74, 43)},
    {L"VACUUM CLAIM", L"Mining", L"Plant a claim flag in deep asteroid field. Defend it against anyone who shows up.", Color(255, 31, 74, 43)},
    {L"SCRAPER GRIND", L"Mining", L"30 consecutive minutes of hand mining on foot. Multitool only, no vehicles.", Color(255, 31, 58, 58)},

    // Trading & Salvage
    {L"MAX HAUL", L"Trading", L"Fill the largest ship you own or can rent. 288+ SCU or bust.", Color(255, 74, 58, 13)},
    {L"BLIND TRADE", L"Trading", L"Buy whatever commodity is highlighted first at the terminal. Sell it blind.", Color(255, 74, 58, 13)},
    {L"ILLEGAL GOODS", L"Trading", L"Smuggle contraband cargo directly through a security checkpoint.", Color(255, 75, 32, 96)},
    {L"JET FUEL HUSTLE", L"Trading", L"Make 100k aUEC in a single session using only ships under 20 SCU.", Color(255, 74, 58, 13)},
    {L"SCRAP KING", L"Trading", L"Find a derelict hull in deep space. Manually strip every single panel off it.", Color(255, 31, 58, 58)},

    // Missions
    {L"HVT DELETION", L"Missions", L"Find a High Value Target bounty. Complete it with 10 minutes on the clock.", Color(255, 26, 79, 107)},
    {L"CARGO ESCORT", L"Missions", L"Guard a stranger's cargo hauler from jump to station. Zero aggression from you.", Color(255, 26, 58, 92)},
    {L"UGF STORM", L"Missions", L"Solo clear an Illegal Underground Bunker Facility. No squad backup.", Color(255, 92, 34, 34)},
    {L"CIPHER RUN", L"Missions", L"Complete a data heist solo with no primary firearm: hack, grab, extract.", Color(255, 75, 32, 96)},
    {L"HOSPITAL DASH", L"Missions", L"Find an incapacitated player in global chat and medevac them to clinic.", Color(255, 31, 74, 43)},
    {L"9-TAILS HUNT", L"Missions", L"Chain three 9-Tails Lockdown missions back-to-back without dying.", Color(255, 26, 79, 107)},
    {L"DERELICT SWEEP", L"Missions", L"Board a derelict space wreck. Clear every hostile NPC inside solo on foot.", Color(255, 31, 58, 58)},

    // Exploration
    {L"QUANTUM DRIFT", L"Exploration", L"Pick a random moon. Blind jump towards it. Walk wherever you set down.", Color(255, 26, 58, 92)},
    {L"LAGRANGE CAMP", L"Exploration", L"Park at an unmonitored Lagrange point. Wait 15 mins for whatever comes.", Color(255, 31, 58, 58)},
    {L"DARKSIDE SURVEY", L"Exploration", L"Find the pitch-black night side of any planet. Land and explore 20 mins on foot.", Color(255, 58, 26, 58)},
    {L"RING WALK", L"Exploration", L"Park ship inside planetary rings. EVA walk outside for 5+ minutes.", Color(255, 26, 58, 92)},
    {L"ALIEN RELIC", L"Exploration", L"Find and screenshot an alien ruin or cave formation. No guides allowed.", Color(255, 75, 32, 96)},
    {L"DEEP VOID", L"Exploration", L"Quantum jump to the furthest empty void coordinate. Just sit there and chill.", Color(255, 58, 26, 58)},

    // Social & Chaos
    {L"BAR CRAWL", L"Social", L"Hit every bar on GrimHEX, Lorville, and Area18 in one uninterrupted run.", Color(255, 75, 32, 96)},
    {L"TAXI LORD", L"Social", L"Offer free transport in global chat. Give at least 5 rides without refusing.", Color(255, 31, 74, 43)},
    {L"GLADIATOR PIT", L"Social", L"Organize a 4-man bare-knuckle melee duel tournament at GrimHEX.", Color(255, 92, 34, 34)},
    {L"HOSTAGE DEMAND", L"Social", L"RP take an org buddy hostage. Demand 10,000 aUEC ransom from org chat.", Color(255, 75, 32, 96)},
    {L"MARKET DUMP", L"Chaos", L"Dump 1,000 units of any commodity on the lowest paying terminal. Tank it.", Color(255, 92, 34, 34)},
    {L"INSURE IT", L"Chaos", L"Crash your primary ship into an asteroid. Reclaim insurance. Repeat once.", Color(255, 92, 34, 34)},
    {L"SPIN AGAIN", L"Chaos", L"The wheel has spoken: spin again immediately. Double your task.", Color(255, 42, 42, 64)},
    {L"FREE PASS", L"Chaos", L"No task. You survived the wheel. Take 15 minutes of peace in the verse.", Color(255, 31, 74, 43)}
};

struct HistoryItem {
    FateEntry entry;
    std::wstring timeStr;
};

std::vector<HistoryItem> history;

// Spinning state
bool isSpinning = false;
float currentAngle = 0.0f;
float targetAngle = 0.0f;
float spinVelocity = 0.0f;
int selectedIndex = -1;
ULONGLONG spinStartTime = 0;

void startSpin() {
    if (isSpinning || fates.empty()) return;
    isSpinning = true;
    spinStartTime = GetTickCount64();

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<size_t> distIdx(0, fates.size() - 1);
    selectedIndex = int(distIdx(gen));

    // Calculate rotation to land on selectedIndex
    float sweep = 360.0f / fates.size();
    float dest = (90.0f - (selectedIndex + 0.5f) * sweep);
    std::uniform_real_distribution<float> jitter(-sweep * 0.35f, sweep * 0.35f);
    dest += jitter(gen);

    float extraSpins = float(8 + (gen() % 6)) * 360.0f;
    float currentNorm = std::fmod(currentAngle, 360.0f);
    if (currentNorm < 0) currentNorm += 360.0f;
    float delta = std::fmod(dest - currentNorm, 360.0f);
    if (delta < 0) delta += 360.0f;

    targetAngle = currentAngle + extraSpins + delta;
    SetTimer(window, 1, 16, nullptr);
}

void finishSpin() {
    isSpinning = false;
    currentAngle = std::fmod(targetAngle, 360.0f);
    KillTimer(window, 1);

    if (selectedIndex >= 0 && selectedIndex < int(fates.size())) {
        std::time_t t = std::time(nullptr);
        std::tm local{};
        localtime_s(&local, &t);
        wchar_t buf[32];
        wcsftime(buf, 32, L"%H:%M:%S", &local);
        history.insert(history.begin(), {fates[selectedIndex], buf});
        if (history.size() > 20) history.pop_back();
    }

    InvalidateRect(window, nullptr, FALSE);
}

void drawWheel(Graphics& g, float cx, float cy, float r) {
    if (fates.empty()) return;
    int n = int(fates.size());
    float sweep = 360.0f / n;

    for (int i = 0; i < n; i++) {
        float start = currentAngle + i * sweep - 90.0f;
        SolidBrush fillBrush(fates[i].color);
        g.FillPie(&fillBrush, cx - r, cy - r, r * 2, r * 2, start, sweep);

        Pen edgePen(Color(180, 15, 18, 25), 1.2f);
        g.DrawPie(&edgePen, cx - r, cy - r, r * 2, r * 2, start, sweep);
    }

    // Outer ring
    Pen rim(Color(255, 86, 98, 117), 2.5f);
    g.DrawEllipse(&rim, cx - r, cy - r, r * 2, r * 2);

    // Center Hub
    float hub = 32.0f * scale;
    SolidBrush hubBg(Color(255, 14, 18, 25));
    g.FillEllipse(&hubBg, cx - hub, cy - hub, hub * 2, hub * 2);
    Pen hubEdge(Color(255, 98, 204, 255), 2.0f);
    g.DrawEllipse(&hubEdge, cx - hub, cy - hub, hub * 2, hub * 2);

    Font fHub(L"Segoe UI", 9.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bHub(Color(255, 98, 204, 255));
    StringFormat sf;
    sf.SetAlignment(StringAlignmentCenter);
    sf.SetLineAlignment(StringAlignmentCenter);
    g.DrawString(L"FATE", -1, &fHub, RectF(cx - hub, cy - hub, hub * 2, hub * 2), &sf, &bHub);

    // Pointer at top (12 o'clock)
    PointF arrow[] = {
        PointF(cx - 8.0f * scale, cy - r - 12.0f * scale),
        PointF(cx + 8.0f * scale, cy - r - 12.0f * scale),
        PointF(cx, cy - r + 3.0f * scale)
    };
    SolidBrush arrowBrush(Color(255, 251, 191, 36));
    g.FillPolygon(&arrowBrush, arrow, 3);
    Pen arrowEdge(Color(255, 196, 143, 16), 1.0f);
    g.DrawPolygon(&arrowEdge, arrow, 3);
}

void paint(HDC dc) {
    RECT rc{};
    GetClientRect(window, &rc);
    int w = rc.right, h = rc.bottom;
    if (w <= 0 || h <= 0) return;

    Bitmap bmp(w, h, PixelFormat32bppPARGB);
    Graphics g(&bmp);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);

    // Background
    SolidBrush bgBrush(Color(255, 14, 18, 25));
    g.FillRectangle(&bgBrush, 0, 0, w, h);

    // Left Column: Roulette Wheel & Control Panel
    float leftW = std::min(460.0f * scale, float(w) * 0.48f);
    float pad = 16.0f * scale;

    // Wheel card
    SynthGlass::panel(g, RectF(pad, pad, leftW - pad, h - pad * 2), false, false, 12);

    float wheelSize = std::min((leftW - pad * 3) / 2.0f, 170.0f * scale);
    float wheelCx = pad + (leftW - pad) / 2.0f;
    float wheelCy = pad + wheelSize + 24.0f * scale;

    drawWheel(g, wheelCx, wheelCy, wheelSize);

    // Spin Button
    float btnY = wheelCy + wheelSize + 22.0f * scale;
    float btnW = leftW - pad * 3;
    float btnH = 46.0f * scale;
    RectF btnRect(pad + pad / 2, btnY, btnW, btnH);

    SynthGlass::panel(g, btnRect, isSpinning, !isSpinning, 8);
    Font fBtn(L"Segoe UI", 12.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bBtn(isSpinning ? Color(255, 150, 160, 175) : Color(255, 240, 248, 255));
    StringFormat sfBtn;
    sfBtn.SetAlignment(StringAlignmentCenter);
    sfBtn.SetLineAlignment(StringAlignmentCenter);
    g.DrawString(isSpinning ? L"SPINNING..." : L"[ SPIN THE WHEEL ]", -1, &fBtn, btnRect, &sfBtn, &bBtn);

    // Result Card
    float resY = btnY + btnH + 12.0f * scale;
    float resH = (h - pad) - resY - 8.0f * scale;
    if (resH > 40.0f * scale) {
        RectF resRect(pad + pad / 2, resY, btnW, resH);
        SynthGlass::panel(g, resRect, false, false, 8);

        if (selectedIndex >= 0 && selectedIndex < int(fates.size())) {
            const auto& fate = fates[selectedIndex];
            Font fCat(L"Consolas", 10.0f * scale, FontStyleBold, UnitPixel);
            SolidBrush bCat(Color(255, 251, 191, 36));
            std::wstring catText = L"// FATE: [" + fate.category + L"]";
            g.DrawString(catText.c_str(), -1, &fCat, PointF(resRect.X + 12, resRect.Y + 10), &bCat);

            Font fTitle(L"Segoe UI", 15.0f * scale, FontStyleBold, UnitPixel);
            SolidBrush bTitle(Color(255, 248, 250, 252));
            g.DrawString(fate.label.c_str(), -1, &fTitle, PointF(resRect.X + 12, resRect.Y + 28 * scale), &bTitle);

            Font fDesc(L"Segoe UI", 11.0f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bDesc(Color(255, 142, 157, 173));
            RectF descRect(resRect.X + 12, resRect.Y + 54 * scale, resRect.Width - 24, resRect.Height - 60 * scale);
            g.DrawString(fate.description.c_str(), -1, &fDesc, descRect, nullptr, &bDesc);
        } else {
            Font fPrompt(L"Segoe UI", 12.0f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bPrompt(Color(255, 142, 157, 173));
            StringFormat sfPrompt;
            sfPrompt.SetAlignment(StringAlignmentCenter);
            sfPrompt.SetLineAlignment(StringAlignmentCenter);
            g.DrawString(L"Press Spin to receive your destiny in the verse.", -1, &fPrompt, resRect, &sfPrompt, &bPrompt);
        }
    }

    // Right Column: History Ledger
    float rightX = leftW + pad;
    float rightW = w - rightX - pad;
    SynthGlass::panel(g, RectF(rightX, pad, rightW, h - pad * 2), false, false, 12);

    Font fHdr(L"Segoe UI", 13.0f * scale, FontStyleBold, UnitPixel);
    SolidBrush bHdr(Color(255, 98, 204, 255));
    g.DrawString(L"SPIN HISTORY & ROLLS", -1, &fHdr, PointF(rightX + 16, pad + 14), &bHdr);

    float rowY = pad + 44.0f * scale;
    float rowH = 46.0f * scale;

    if (history.empty()) {
        Font fEmpty(L"Segoe UI", 12.0f * scale, FontStyleRegular, UnitPixel);
        SolidBrush bEmpty(Color(255, 90, 100, 115));
        g.DrawString(L"No fates recorded yet. Spin the wheel to begin.", -1, &fEmpty, PointF(rightX + 16, rowY + 20), &bEmpty);
    } else {
        for (const auto& item : history) {
            if (rowY + rowH > h - pad - 10) break;

            RectF cardR(rightX + 14, rowY, rightW - 28, rowH);
            SynthGlass::panel(g, cardR, false, false, 6);

            // Left colored strip
            SolidBrush strip(item.entry.color);
            g.FillRectangle(&strip, cardR.X, cardR.Y, 4.0f * scale, cardR.Height);

            // Fate title
            Font fItem(L"Segoe UI", 11.5f * scale, FontStyleBold, UnitPixel);
            SolidBrush bItem(Color(255, 238, 239, 241));
            g.DrawString(item.entry.label.c_str(), -1, &fItem, PointF(cardR.X + 14, cardR.Y + 6), &bItem);

            // Timestamp
            Font fTime(L"Consolas", 9.0f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bTime(Color(255, 120, 130, 145));
            g.DrawString(item.timeStr.c_str(), -1, &fTime, PointF(cardR.GetRight() - 65 * scale, cardR.Y + 8), &bTime);

            // Category tag & excerpt
            Font fSub(L"Segoe UI", 9.5f * scale, FontStyleRegular, UnitPixel);
            SolidBrush bSub(Color(255, 150, 160, 175));
            std::wstring sub = L"[" + item.entry.category + L"] " + item.entry.description;
            RectF subR(cardR.X + 14, cardR.Y + 24 * scale, cardR.Width - 28, 16 * scale);
            StringFormat sfSub;
            sfSub.SetTrimming(StringTrimmingEllipsisCharacter);
            sfSub.SetFormatFlags(StringFormatFlagsNoWrap);
            g.DrawString(sub.c_str(), -1, &fSub, subR, &sfSub, &bSub);

            rowY += rowH + 6.0f * scale;
        }
    }

    Graphics screen(dc);
    screen.DrawImage(&bmp, 0, 0);
}

LRESULT CALLBACK proc(HWND hwnd, UINT msg, WPARAM w, LPARAM l) {
    if (msg == WM_PAINT) {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        paint(dc);
        EndPaint(hwnd, &ps);
        return 0;
    }
    if (msg == WM_ERASEBKGND) return 1;

    if (msg == WM_TIMER && w == 1) {
        if (isSpinning) {
            ULONGLONG elapsed = GetTickCount64() - spinStartTime;
            float duration = 3800.0f; // ms
            float t = std::min(float(elapsed) / duration, 1.0f);
            float eased = 1.0f - std::pow(1.0f - t, 4.0f);

            float totalDelta = targetAngle - currentAngle;
            // interpolate angle
            float currentShow = currentAngle + (targetAngle - currentAngle) * eased;
            if (t >= 1.0f) {
                finishSpin();
            } else {
                currentAngle = currentShow;
                InvalidateRect(hwnd, nullptr, FALSE);
            }
        }
        return 0;
    }

    if (msg == WM_LBUTTONDOWN) {
        int x = GET_X_LPARAM(l), y = GET_Y_LPARAM(l);
        RECT rc{};
        GetClientRect(hwnd, &rc);
        float leftW = std::min(460.0f * scale, float(rc.right) * 0.48f);
        float pad = 16.0f * scale;
        float wheelSize = std::min((leftW - pad * 3) / 2.0f, 170.0f * scale);
        float wheelCy = pad + wheelSize + 24.0f * scale;
        float btnY = wheelCy + wheelSize + 22.0f * scale;
        float btnW = leftW - pad * 3;
        float btnH = 46.0f * scale;

        if (x >= pad + pad / 2 && x <= pad + pad / 2 + btnW &&
            y >= btnY && y <= btnY + btnH) {
            startSpin();
        }
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

void show(HWND parent, const std::filesystem::path& directory) {
    if (!window) {
        WNDCLASSW c{};
        c.hInstance = GetModuleHandleW(nullptr);
        c.lpszClassName = L"SynthScanRoulette";
        c.lpfnWndProc = proc;
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
        KillTimer(window, 1);
        DestroyWindow(window);
        window = nullptr;
    }
}

} // namespace SynthRoulette
