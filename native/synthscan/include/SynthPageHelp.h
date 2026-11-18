#pragma once
#include <windows.h>
#include <gdiplus.h>
#include <algorithm>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

namespace SynthPageHelp {

struct PageHelp {
    const char* page;
    const wchar_t* title;
    const wchar_t* summary;
    std::vector<const wchar_t*> tips;
};

inline const std::vector<PageHelp>& catalog() {
    static const std::vector<PageHelp> entries = {
        {
            "directory",
            L"Item & Ship Finder",
            L"Search ships, components, weapons, blueprints, and Wikelo barter items in one place. Selecting an entry loads UEX shop prices, ship hardpoints & DPS, or Wikelo turn-in tasks.",
            {
                L"Click the Name, Type, or Category headers to sort results; set Type to \"Favorites\" to see your starred items.",
                L"UEX shop prices are color-coded: green marks the lowest listed price, and red shows how much higher other shops are.",
                L"Wikelo items break down exact Favor counts, ways to earn Favors, required elevator items, and unlock missions."
            }
        },
        {
            "people",
            L"Citizens",
            L"See players on your current shard, manage your party, apply custom color tags, and read or translate live in-game chat channels.",
            {
                L"Shift-click rows to multi-select players, then stage them in bulk for party invites, friend requests, or color tags.",
                L"Right-click any player in the roster, party list, or chat feed for quick invite, friend, or tagging actions. Chat & invites run over CIG services (no game focus required).",
                L"In Party, click \"Share All Contracts\" to share every active contract with your party at once, or toggle \"Auto-share (9:30–10:30)\" for randomized interval re-sharing.",
                L"Enable \"Live translate\" in Chat to translate incoming foreign / [zh] messages into English, and turn on \"Join alerts\" to watch for tagged players on your shard."
            }
        },
        {
            "mission_log",
            L"Mission & Wallet Log",
            L"Tracks completed, failed, and abandoned contracts alongside measured reputation gains and aUEC wallet changes across play sessions.",
            {
                L"Click any row (or \"Evidence\") to inspect exact balance windows, split payout comparisons, and source observations; click the same row again to collapse.",
                L"Reclassify \"Unclassified\" wallet changes (repairs, cargo trades, transfers, store buys) in the Evidence pane—or right-click rows in fallback mode—to keep session totals accurate.",
                L"Export filtered history anytime as CSV, raw JSON, or a readable HTML report."
            }
        },
        {
            "servers",
            L"Server History",
            L"Logs every Star Citizen shard you join with join/leave timestamps, region, shard ID, session duration, and repeat visit counts.",
            {
                L"Use \"Name current shard\" to attach a custom label (e.g. \"Org Cargo\" or \"Clean Pyro\") so you recognize the server if you land on it again.",
                L"Set a \"Current shard cooldown\" in minutes or save notes on any past visit to remember shard conditions.",
                L"Filter by region, date range (YYYY-MM-DD), or text query, and export your visit log to CSV or JSON."
            }
        },
        {
            "blueprints",
            L"Blueprint Library",
            L"Browse crafting recipes, auto-sync owned blueprints from your CIG account & logs, star ★ Wanted targets, and build multi-item crafting lists.",
            {
                L"Start typing anywhere on the blueprint list to search immediately. Click ★ on any recipe (or inside Grind Planner) to prioritize it under Wanted.",
                L"Inside a recipe, drag the Quality slider (or click preset quality marks) to preview how material quality boosts item stats.",
                L"Right-click any material (in the filter bar or inside a recipe) to highlight it Cyan (wanted) or Red (skip) in Star Citizen's in-game text (restart game to apply).",
                L"Use \"Add to list\" and the trolley icon to build a combined crafting cart, or open Grind Planner (uses live CIG reputation) to see exact missions & rep needed."
            }
        },
        {
            "planner",
            L"Mining Tools",
            L"Find where to mine Ship, ROC, and Hand ores across Stanton, Pyro, and Nyx, check UEX ore prices, highlight target ores in-game, and keep your Mining Diary below.",
            {
                L"Right-click any ore or material to mark it Cyan (target) or Red (avoid) in Star Citizen's in-game text (restart the game to apply).",
                L"Left-click a moon or belt inside an ore's breakdown to flip the view and see everything mineable at that location, or click \"UEX market\" for player listings.",
                L"Toggle the watch icon on an ore to add or remove it from your Mining HUD \"Looking for\" watchlist.",
                L"Scroll down for Mining Diary: Ctrl-click two or more scan rows and press \"Merge scans\" to combine partial rock reads, or export a local-only PNG/text share card."
            }
        },
        {
            "refinery",
            L"Refinery",
            L"Compare refinery yields, fees, and processing times across Stanton, Pyro, and Nyx stations, and monitor active refinery work orders and collected stock.",
            {
                L"Click an ore to add it to your simulated hold, then use +/- or click the SCU number directly to type an exact decimal amount.",
                L"Scroll the mouse wheel over the station list to browse more refineries, and use Up/Down/Enter/Esc on the Refining Method dropdown.",
                L"Green values indicate station yield bonuses; red values indicate penalties. Press Esc once to clear your selected hold before closing.",
                L"Switch to \"Work orders\" for live countdown timers on active terminal jobs, and \"Collected stock\" to review confirmed pickups."
            }
        },
        {
            "executive_hangar",
            L"Executive Hangar",
            L"Live PYAM / Executive Hangar cycle countdown, 5-power-cell status dial, and personal Comp Board (1-7) inventory tracker across Checkmate, Orbituary, and Ruin Station.",
            {
                L"Type directly into any board's count box and press Enter to save immediately, or use -/+ steppers and \"Save counts\".",
                L"Use \"+ full set\" to add one of every board (1-7), \"Use full set\" when claiming a hangar to subtract one of each, and \"Undo set\" if clicked by mistake.",
                L"Click \"Open Hangars HUD\" to pop out the compact overlay timer in-game, or \"Refresh timing\" to fetch the latest community-synced schedule."
            }
        },
        {
            "hud_piracy",
            L"Flight / Piracy",
            L"Flight logs your ship sorties, helm hours, quantum jumps, and combat survival; Piracy provides QT Snare geometry, 3D GPS spline checks, stakeout timing, and loot splitting.",
            {
                L"Switch between the \"Flight\" and \"Piracy\" sub-tabs at the top, and use \"Share Flight Card\" to copy a formatted summary of your sorties.",
                L"In Piracy's QT Snare Planner, type /showlocation in game chat and paste the coordinates into \"Verify My Position\" (Origin, Dest, Ship)—no r_DisplayInfo needed.",
                L"Use the Crew Cut Splitter to calculate payouts with custom Snare/Mantis lead bonuses and fence fees, and watch Jurisdiction & Snare Watch alerts."
            }
        },
        {
            "daylight",
            L"Day/Night Forecast",
            L"Predict sunrise, sunset, remaining daylight, and local solar time for any planet, moon, or outpost across Stanton, Pyro, and Nyx—right now or at your ETA.",
            {
                L"Switch Arrival between \"Now\", \"+Minutes\" (travel ETA), or \"Custom\" date/time to check if a landing zone will be sunlit when you arrive.",
                L"Use the Verse search box to jump straight to any outpost, cave, or bunker without browsing system dropdowns.",
                L"Click \"Calibrate\" to log an unobstructed sunrise or sunset you saw in-game (within 7 days) to sync forecasts to your shard, and \"Copy Forecast\" to share with crew."
            }
        },
        {
            "acceptance",
            L"Automations",
            L"Optional background helpers that auto-accept shared contracts, party invites, or friend requests, hide global chat on join, and configure startup r_DisplayInfo.",
            {
                L"Every toggle saves immediately. Keep Star Citizen focused so incoming-request accept keypresses are not blocked by open menus.",
                L"\"Hide global chat after joining (F12)\" presses F12 once after loading finishes—keep your in-game chat toggle bound to F12.",
                L"\"Startup telemetry overlay\" writes r_DisplayInfo (1-3) to user.cfg so Star Citizen loads it automatically on your next game boot."
            }
        },
        {
            "roulette",
            L"Fate Roulette",
            L"Spin the wheel for a randomized Star Citizen challenge, rare-item or quality-ore collection hunt, unowned earnable ship goal, or missing obtainable blueprint.",
            {
                L"Toggle any category cards on or off to customize the wheel pool; your selections save automatically.",
                L"Enable Earn Ship to roll unowned ships you can earn in-game (dealership aUEC, Wikelo Emporium, or PYAM Executive Hangar), Collection for quality-material hunts, or Unlock BP for missing blueprints. Use Shuffle anytime to draw a fresh pool.",
                L"Click the locked Result Card or any entry in Spin History & Rolls to jump straight to that blueprint in the Blueprint Library, ship/item in the Item & Ship Finder, or ore in Mining Tools."
            }
        },
        {
            "settings",
            L"Settings",
            L"Configure auto-launch with the RSI Launcher, automatic mining scans, HUD visibility, Snare Watch alerts, custom hotkeys, privacy controls, and optional modules.",
            {
                L"Many helper features—such as the automatic contract acceptor, party/friend auto-accept, and automatic global chat disabler (F12)—only work while Star Citizen is the active, focused window. If you are alt-tabbed or clicked onto another monitor when they activate, they will not trigger.",
                L"Click \"HUD keyboard / mouse shortcuts\" to bind spare keys (such as F23 / F24 for Logitech G502 X G8/G7 buttons) to toggle or cycle HUD tabs.",
                L"\"Privacy & capture\" lets you pause screen reading anytime, auto-pause when alt-tabbed, inspect the game-only frame, or toggle CIG account features.",
                L"On Home, use \"Patch status\" and \"Text settings\" at the bottom to manage SynthStrings (custom in-game blueprint tags and ore colors)."
            }
        },
        {
            "privacy",
            L"Privacy & Capture",
            L"Control local-only Star Citizen window capture, pause screen reading at any time, inspect the exact captured frame, and manage game-account permissions.",
            {
                L"Capture reads only the verified StarCitizen.exe window locally on your PC—never the desktop—and pauses automatically when unfocused if enabled.",
                L"\"Preview game capture\" stays in memory only and clears as soon as you leave this page unless you explicitly click Save."
            }
        },
        {
            "buyer_alerts",
            L"Buyer Alerts",
            L"Monitor UEX player marketplace demand for items and ores you want to sell so you can spot active buyers quickly.",
            {
                L"Select an item from the market catalog to watch buyer listings and inspect matching offers."
            }
        },
        {
            "bookmarks",
            L"Rock Bookmarks",
            L"Field-test tool to save your ship's exact coordinates at a rock or point of interest using /showlocation, and export or import bookmark JSON files.",
            {
                L"Select the planetary body, arm a bookmark, and type /showlocation in game chat to record your parked ship's coordinates.",
                L"For a stationary check, stay parked for at least 30 seconds after arming before typing /showlocation."
            }
        },
        {
            "knick_knacks",
            L"Knick-Knacks",
            L"Find spare, unequipped items across all station inventories, Persistent Hangars, and crates, or inspect permanent RSI Hangar & account-attributed items without launching the game.",
            {
                L"Spare Storage hides items mounted on your ships, equipped on your character, and auto-generated medical respawn/prison starter gear.",
                L"Use the Crafted tab to isolate crafted weapons, armor, and mining lasers, and click any material or crafted row to expand exact quality tiers and SCU amounts.",
                L"Switch to Account Hangar (RSI) for permanent pledges, or Ships & Fleet to compare earned in-game ships, pledged ships, and unowned earnable ships (dealership aUEC, Wikelo, Exec Hangar)."
            }
        }
    };
    return entries;
}

inline const PageHelp* find(const std::string& page) {
    if (page == "home" || page.empty()) return nullptr;
    for (const auto& entry : catalog()) {
        if (page == entry.page) return &entry;
    }
    return nullptr;
}

inline std::unique_ptr<Gdiplus::Font> makeHeadingFont(float sizePx) {
    Gdiplus::FontFamily bahn(L"Bahnschrift");
    if (bahn.IsAvailable()) {
        return std::make_unique<Gdiplus::Font>(&bahn, sizePx, Gdiplus::FontStyleBold, Gdiplus::UnitPixel);
    }
    return std::make_unique<Gdiplus::Font>(L"Segoe UI", sizePx, Gdiplus::FontStyleBold, Gdiplus::UnitPixel);
}

struct TooltipMetrics {
    int width = 0;
    int height = 0;
    float padX = 0;
    float padY = 0;
    float titleH = 0;
    float summaryH = 0;
    float sectionLabelH = 0;
    std::vector<float> tipHeights;
};

inline TooltipMetrics measureTooltip(Gdiplus::Graphics& g, const PageHelp& help, float scale, int maxWidthPx) {
    TooltipMetrics m;
    const float logicalW = std::clamp(float(maxWidthPx) / scale, 320.f, 460.f);
    m.width = int(logicalW * scale);
    m.padX = 18.f * scale;
    m.padY = 16.f * scale;
    const float textW = float(m.width) - m.padX * 2.f - 8.f * scale;

    auto titleFont = makeHeadingFont(15.5f * scale);
    Gdiplus::Font bodyFont(L"Segoe UI", 12.f * scale, Gdiplus::FontStyleRegular, Gdiplus::UnitPixel);
    Gdiplus::Font sectionFont(L"Segoe UI", 10.f * scale, Gdiplus::FontStyleBold, Gdiplus::UnitPixel);

    Gdiplus::StringFormat wrapFmt;
    wrapFmt.SetTrimming(Gdiplus::StringTrimmingNone);

    auto measure = [&](const wchar_t* text, Gdiplus::Font& font, float availW) {
        Gdiplus::RectF bounds;
        g.MeasureString(text, -1, &font, Gdiplus::RectF(0, 0, availW, 2000.f), &wrapFmt, &bounds);
        return std::ceil(bounds.Height);
    };

    m.titleH = std::max(22.f * scale, measure(help.title, *titleFont, textW - 88.f * scale));
    m.summaryH = measure(help.summary, bodyFont, textW);
    m.sectionLabelH = measure(L"TIPS & HIDDEN DETAILS", sectionFont, textW);

    const float bulletTextW = textW - 14.f * scale;
    float tipsTotal = 0.f;
    for (const auto* tip : help.tips) {
        float h = measure(tip, bodyFont, bulletTextW);
        m.tipHeights.push_back(h);
        tipsTotal += h + 6.f * scale;
    }
    if (!help.tips.empty()) tipsTotal -= 6.f * scale;

    const float totalH =
        4.f * scale +               // shadow top inset
        m.padY +                    // top padding
        m.titleH + 6.f * scale +    // title + gap
        m.summaryH + 12.f * scale + // summary + gap
        1.f * scale + 10.f * scale +// divider + gap
        m.sectionLabelH + 7.f * scale + // section label + gap
        tipsTotal +
        m.padY +                    // bottom padding
        8.f * scale;                // shadow bottom inset

    m.height = int(std::ceil(totalH));
    return m;
}

inline void paintTooltipCard(Gdiplus::Graphics& g, const PageHelp& help, const TooltipMetrics& m, float scale) {
    g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
    g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);

    auto shape = [](Gdiplus::GraphicsPath& p, Gdiplus::RectF r, float radius) {
        float d = std::min(radius * 2.f, std::min(r.Width, r.Height));
        if (d <= 0.f) return;
        p.AddArc(r.X, r.Y, d, d, 180.f, 90.f);
        p.AddArc(r.GetRight() - d, r.Y, d, d, 270.f, 90.f);
        p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0.f, 90.f);
        p.AddArc(r.X, r.GetBottom() - d, d, d, 90.f, 90.f);
        p.CloseFigure();
    };

    // Soft outer shadow layers (requires per-pixel alpha layered target)
    for (int s = 0; s < 2; ++s) {
        float inset = float(s) * 2.f * scale;
        Gdiplus::RectF sr(inset, inset + 2.f * scale, float(m.width) - inset * 2.f, float(m.height) - inset * 2.f - 2.f * scale);
        Gdiplus::GraphicsPath sp;
        shape(sp, sr, (14.f - s * 1.5f) * scale);
        Gdiplus::SolidBrush sb(Gdiplus::Color(s == 0 ? 48 : 80, 4, 6, 10));
        g.FillPath(&sb, &sp);
    }

    const Gdiplus::RectF card(4.f * scale, 2.f * scale, float(m.width) - 8.f * scale, float(m.height) - 10.f * scale);
    Gdiplus::GraphicsPath cp;
    shape(cp, card, 12.f * scale);
    Gdiplus::LinearGradientBrush bg(
        Gdiplus::PointF(card.X, card.Y),
        Gdiplus::PointF(card.X, card.GetBottom() + 1.f),
        Gdiplus::Color(248, 22, 28, 39),
        Gdiplus::Color(248, 15, 19, 27));
    g.FillPath(&bg, &cp);

    Gdiplus::Pen border(Gdiplus::Color(145, 98, 204, 255), std::max(1.f, 1.f * scale));
    g.DrawPath(&border, &cp);
    Gdiplus::Pen sheen(Gdiplus::Color(42, 255, 255, 255), std::max(1.f, 1.f * scale));
    g.DrawLine(&sheen, card.X + 12.f * scale, card.Y + 1.f, card.GetRight() - 12.f * scale, card.Y + 1.f);

    const float x = card.X + m.padX;
    const float textW = card.Width - m.padX * 2.f;
    float y = card.Y + m.padY;

    auto titleFont = makeHeadingFont(15.5f * scale);
    Gdiplus::Font badgeFont(L"Segoe UI", 9.5f * scale, Gdiplus::FontStyleBold, Gdiplus::UnitPixel);
    Gdiplus::Font bodyFont(L"Segoe UI", 12.f * scale, Gdiplus::FontStyleRegular, Gdiplus::UnitPixel);
    Gdiplus::Font sectionFont(L"Segoe UI", 10.f * scale, Gdiplus::FontStyleBold, Gdiplus::UnitPixel);

    Gdiplus::SolidBrush inkBrush(Gdiplus::Color(255, 238, 241, 246));
    Gdiplus::SolidBrush mutedBrush(Gdiplus::Color(255, 186, 196, 210));
    Gdiplus::SolidBrush accentBrush(Gdiplus::Color(255, 98, 204, 255));

    Gdiplus::StringFormat wrapFmt;
    wrapFmt.SetTrimming(Gdiplus::StringTrimmingNone);

    // Header + small "GUIDE" pill
    g.DrawString(help.title, -1, titleFont.get(), Gdiplus::RectF(x, y, textW - 82.f * scale, m.titleH + 2.f * scale), &wrapFmt, &inkBrush);
    {
        Gdiplus::RectF pill(card.GetRight() - m.padX - 72.f * scale, y + 1.f * scale, 72.f * scale, 20.f * scale);
        Gdiplus::GraphicsPath pp;
        shape(pp, pill, 6.f * scale);
        Gdiplus::SolidBrush pb(Gdiplus::Color(34, 98, 204, 255));
        g.FillPath(&pb, &pp);
        Gdiplus::Pen ppen(Gdiplus::Color(85, 98, 204, 255), 1.f);
        g.DrawPath(&ppen, &pp);
        Gdiplus::StringFormat centerFmt;
        centerFmt.SetAlignment(Gdiplus::StringAlignmentCenter);
        centerFmt.SetLineAlignment(Gdiplus::StringAlignmentCenter);
        g.DrawString(L"PAGE GUIDE", -1, &badgeFont, pill, &centerFmt, &accentBrush);
    }

    y += m.titleH + 6.f * scale;
    g.DrawString(help.summary, -1, &bodyFont, Gdiplus::RectF(x, y, textW, m.summaryH + 2.f * scale), &wrapFmt, &mutedBrush);
    y += m.summaryH + 12.f * scale;

    Gdiplus::Pen rule(Gdiplus::Color(42, 174, 193, 219), std::max(1.f, 1.f * scale));
    g.DrawLine(&rule, x, y, x + textW, y);
    y += 1.f * scale + 10.f * scale;

    g.DrawString(L"TIPS & HIDDEN DETAILS", -1, &sectionFont, Gdiplus::RectF(x, y, textW, m.sectionLabelH + 2.f * scale), &wrapFmt, &accentBrush);
    y += m.sectionLabelH + 7.f * scale;

    const float bulletTextW = textW - 14.f * scale;
    for (size_t i = 0; i < help.tips.size(); ++i) {
        const float th = m.tipHeights[i];
        // Crisp cyan dot aligned with first line cap-center
        const float dotR = 2.4f * scale;
        g.FillEllipse(&accentBrush, x + 2.f * scale, y + 6.5f * scale, dotR * 2.f, dotR * 2.f);
        g.DrawString(help.tips[i], -1, &bodyFont, Gdiplus::RectF(x + 14.f * scale, y, bulletTextW, th + 2.f * scale), &wrapFmt, &inkBrush);
        y += th + 6.f * scale;
    }
}

} // namespace SynthPageHelp
