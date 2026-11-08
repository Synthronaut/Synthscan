#include "RockContents.h"

#include "DevSwitch.h"
#include "LoadoutReader.h"
#include "MiningHardware.h"
#include "HandMiningReference.h"
#include "ScanPanel.h"
#include "TextLineReader.h"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <functional>
#include <iostream>
#include <map>

namespace SCMiner {

namespace {

// Where the list is looked for, at size 1, from the labels' left edge and the
// MASS label's top. Every seat sets the same table - the share, the name
// beginning 58 right of where the share does, the quality ending 214 right
// of it, the lines 18.5 to 19.7 apart - but not at the same place: the
// Prospector's, the Golem's and the MOLE's own seat begin it at the labels'
// edge with the first line's middle 170 to 174 down, while a MOLE turret's
// panel leans, and its list begins 8 to 12 LEFT of the labels and a little
// further left with every line. So the table is found, not assumed: the
// column most lines begin at, the column most of them end at, and the lean
// between the lines. Its words are then cut where the table has them - a
// share never reaches 0.24 of the way across and a name begins at 0.274 -
// and not by the gaps in the lettering, which the ground behind a
// see-through HUD fills in at will (on Daymar's sand a ridge can run into
// a figure, a pole into a share).
constexpr double REGION_LEFT = -26.0;
constexpr double REGION_RIGHT = 236.0;
constexpr double REGION_TOP = 146.0;      // through the composition bar, which ends by 153
constexpr double REGION_BOTTOM = 300.0;   // six lines and some room
constexpr double LIST_FROM = 158.0;       // no line's middle is higher than this: the bar's ticks are, at 146
constexpr double FIRST_BY = 186.0;        // the first line's middle is no lower than this
constexpr double SHARE_FROM = -20.0;      // where the shares may begin, from the labels' edge
constexpr double SHARE_BY = 8.0;
constexpr double TABLE_LEAST = 190.0;     // from where a share begins to where a quality ends
constexpr double TABLE_MOST = 228.0;
constexpr double PITCH_LEAST = 15.5;      // from one line's middle to the next
constexpr double PITCH_MOST = 23.0;
constexpr double SAME_COLUMN = 3.0;       // how far a line's edge may stand off the column
constexpr double LEAN_MOST = 0.15;        // sideways per line of height
constexpr double SHARE_ENDS = 0.257;      // of the table's width: between the widest share and the names
constexpr double NAME_BEGINS = 0.262;
constexpr double QUALITY_BEGINS = 0.85;   // three numerals' room before the table's end, and clear of a turret's INERT MATERIALS
constexpr double QUALITY_HOLDS = 0.135;   // of the table's width: what three numerals take at its end
constexpr double NUMERAL_GAP = 6.5;       // the most room between two numerals: a 1 stands narrow in a numeral's width
constexpr double SAME_TONE = 0.22;        // how far a quality's colour may be off its share's, each channel as its part of the three: 0.05 to 0.15 measured, 0.35 and more for ice and rock

bool sameName(const char* a, const std::string& b) {
    if (std::strlen(a) != b.size()) return false;
    for (size_t i = 0; i < b.size(); i++) {
        if (std::tolower((unsigned char)a[i]) != std::tolower((unsigned char)b[i])) return false;
    }
    return true;
}

const OreBands* bandsOf(const std::string& ore) {
    for (const auto& b : HAND_MINING_BANDS) if (sameName(b.ore, ore)) return &b;
    for (int b = 0; b < ORE_BANDS_COUNT; b++) {
        if (sameName(ORE_BANDS[b].ore, ore)) return &ORE_BANDS[b];
    }
    return nullptr;
}

// Which of an ore's eight values a quality is, -1 for none of them
int bandOf(const std::string& ore, int quality) {
    const OreBands* bands = bandsOf(ore);
    if (!bands) return -1;
    for (int k = 0; k < 8; k++) {
        if (bands->bands[k] == quality) return k;
    }
    return -1;
}

// The numerals of a line the reader gave, with a full stop where it wrote
// one: a reader of words puts O for 0, I or l for 1, S for 5, B for 8 - and
// has a full-width stop and comma in its alphabet besides
std::string numerals(std::string text) {
    for (const auto& [wide, plain] : {std::pair<const char*, char>{"\xEF\xBC\x8C", ','},
                                      std::pair<const char*, char>{"\xEF\xBC\x8E", '.'},
                                      std::pair<const char*, char>{"\xEF\xBC\x85", '%'}}) {
        for (size_t at; (at = text.find(wide)) != std::string::npos;) text.replace(at, std::strlen(wide), 1, plain);
    }
    std::string out;
    for (unsigned char c : text) {
        if (c >= '0' && c <= '9') out += (char)c;
        else if (c == 'O' || c == 'o' || c == 'D' || c == 'Q') out += '0';
        else if (c == 'I' || c == 'l' || c == '|' || c == 'i') out += '1';
        else if (c == 'Z' || c == 'z') out += '2';
        else if (c == 'S' || c == 's') out += '5';
        else if (c == 'B') out += '8';
        else if (c == '.' || c == ',') out += '.';
        else if (c == '%') out += '%';
    }
    return out;
}

// Whether a line's name is the inert rest's: INERT MATERIALS, with a letter
// or two of it lost to the ground behind - "?DNERT MATEUAUS" and "?THERT
// MATERUAUS" over an ice asteroid. No ore has NERT or MATER in its name.
bool saysInert(const std::string& name) {
    std::string letters;
    for (char c : name) {
        const char up = (char)std::toupper((unsigned char)c);
        if (up >= 'A' && up <= 'Z') letters += up;
    }
    return letters.find("NERT") != std::string::npos || letters.find("MATER") != std::string::npos || letters=="IMERT";
}

// The shares are cut off after the second place, not rounded: measured
// lists add up to 99.97 to 99.99, never to 100.00 or over. So a list of n
// lines that is the whole rock adds up to between 100 less n hundredths
// and 100.
bool sumIsTheRock(double sum, size_t lines) {
    return sum > 100.0 - 0.01 * (double)lines - 0.006 && sum < 100.006;
}

}  // namespace

bool parseShare(const std::string& text, float& percent) {
    const std::string seen = numerals(text);
    std::string digits;
    int stop = -1;
    for (char c : seen) {
        if (c == '%') break;
        if (c == '.') {
            if (stop < 0 && !digits.empty()) stop = (int)digits.size();
            continue;
        }
        digits += c;
    }
    // Always to two places, "0.01%" to "100.00%": the last two numerals are
    // the hundredths, with the stop read or lost. One read elsewhere - a
    // numeral lost behind it - is no share.
    if (digits.size() < 3 || digits.size() > 5) return false;
    const int whole = (int)digits.size() - 2;
    if (stop >= 0 && stop != whole) return false;
    const double value = std::atoi(digits.substr(0, (size_t)whole).c_str()) + std::atoi(digits.substr((size_t)whole).c_str()) / 100.0;
    if (value <= 0.0 || value > 100.0) return false;
    percent = (float)value;
    return true;
}

bool parseQuality(const std::string& text, int& quality) {
    std::string seen = numerals(text);
    // An isolated quality can acquire punctuation from the ground beside it.
    // Strip only outer stops; a decimal inside the numeral remains invalid.
    while(!seen.empty()&&seen.front()=='.')seen.erase(seen.begin());
    while(!seen.empty()&&seen.back()=='.')seen.pop_back();
    if (seen.empty() || seen.size() > 4) return false;
    for (char c : seen) {
        if (c < '0' || c > '9') return false;
    }
    const int value = std::atoi(seen.c_str());
    if (value > 1000) return false;
    quality = value;
    return true;
}

bool qualityOfOre(const std::string& ore, int quality) {
    return bandOf(ore, quality) >= 0;
}

bool nameContentsByRock(const std::string& rockOre, RockContents& contents) {
    std::vector<const RockPart*> parts;
    for (int i = 0; i < ROCK_PART_COUNT; i++) {
        if (sameName(ROCK_PARTS[i].rock, rockOre)) parts.push_back(&ROCK_PARTS[i]);
    }
    if (parts.empty() || contents.parts.empty()) return false;
    // A line is the ore whose value its quality is - of the ores a rock of
    // this kind holds, and within what that part of it can come to. The
    // panel does not keep the files' order - a Hephaestanite rock can list
    // Silicon first, a Bexalite rock Gold before Borase - and a piece broken
    // off a rock holds whatever share of a part fell to it: all Iron at 325,
    // or a seventh Iron at 664 and the rest inert. So neither the order nor
    // the share says which line is what; the quality does, wherever the
    // rock's ores share no value - all but two kinds: Hephaestanite and
    // Quartz, each the other's side ore, both begin at 330, and their lists
    // are read by name. The line without a quality is the inert rest.
    std::vector<std::string> named(contents.parts.size());
    int rests = 0;
    for (size_t i = 0; i < contents.parts.size(); i++) {
        const RockPartRead& line = contents.parts[i];
        if (line.inert || line.quality == 0) {
            rests++;
            continue;
        }
        for (const RockPart* part : parts) {
            const int band = bandOf(part->ore, line.quality);
            if (band < 0 || band > topQualityBand(part->qualityScale)) continue;
            if (!named[i].empty() && !sameName(part->ore, named[i])) return false;   // two ores have that value
            named[i] = part->ore;
        }
        if (named[i].empty()) return false;
    }
    if (rests > 1) return false;
    for (size_t i = 0; i < contents.parts.size(); i++) {
        contents.parts[i].ore = named[i];
        contents.parts[i].inert = named[i].empty();
    }
    return true;
}

bool contentsFitRock(const std::string& rockOre, const RockContents& contents) {
    std::vector<const RockPart*> parts;
    for (int i = 0; i < ROCK_PART_COUNT; i++) {
        if (sameName(ROCK_PARTS[i].rock, rockOre)) parts.push_back(&ROCK_PARTS[i]);
    }
    // Ore by ore, of the ores the rock is built of: its lines' bands, the
    // highest first, against what its parts can come to, the furthest first.
    // A line too many, or one above its part's reach, and they are not this
    // rock's.
    for (const RockPart* part : parts) {
        std::vector<int> reach, bands;
        for (const RockPart* other : parts) {
            if (sameName(other->ore, part->ore)) reach.push_back(topQualityBand(other->qualityScale));
        }
        for (const RockPartRead& line : contents.parts) {
            if (!line.inert && sameName(part->ore, line.ore)) bands.push_back(bandOf(line.ore, line.quality));
        }
        if (bands.size() > reach.size()) return false;
        std::sort(reach.rbegin(), reach.rend());
        std::sort(bands.rbegin(), bands.rend());
        for (size_t i = 0; i < bands.size(); i++) {
            if (bands[i] > reach[i]) return false;
        }
    }
    return true;
}

bool contentsPieceQuotesReady(const RockContents& contents) {
    bool any=false;
    for(const auto& p:contents.parts)if(!p.inert){
        bool gem=false;for(const auto& b:HAND_MINING_BANDS)if(p.ore==b.ore)gem=true;
        if(!gem||bandOf(p.ore,p.quality)<0)return false;
        if(!contents.whole && (snapOreName(p.nameText)!=p.ore || numerals(p.qualityText)!=std::to_string(p.quality)))return false;
        any=true;
    }
    return any;
}

bool contentsHold(RockContents& contents) {
    double sum = 0;
    bool named = !contents.parts.empty();
    for (const RockPartRead& part : contents.parts) {
        sum += part.percent;
        if (part.inert) {
            if (part.quality != 0) named = false;
        } else if (part.ore.empty() || bandOf(part.ore, part.quality) < 0) {
            named = false;
        }
    }
    contents.sum = (float)sum;
    contents.whole = named && sumIsTheRock(sum, contents.parts.size());
    return contents.whole;
}

bool contentsEstimateReady(const RockContents& contents) {
    if(contents.whole)return true;
    if(!contents.partial)return false;
    double sum=0;bool inert=false;
    if(contents.parts.size()<2)return false;
    for(const auto& part:contents.parts) {
        if(!std::isfinite(part.percent)||part.percent<=0||part.percent>100)return false;
        sum+=part.percent;
        if(part.inert){if(inert||part.quality!=0)return false;inert=true;}
        else if(part.ore.empty()||bandOf(part.ore,part.quality)<0)return false;
    }
    // Never silently call this a whole rock: the HUD labels the coverage
    // and the price excludes any unread remainder. Large OCR disagreements
    // or missing rows still wait for another view.
    return inert&&sum>=99.8&&sum<100.006;
}

cv::Rect rockContentsRegion(const ScanPanel& panel, const cv::Size& frame) {
    if (panel.labels.x < 0 || panel.labelScale <= 0) return cv::Rect();
    const double u = panel.labelScale;
    const cv::Rect wanted(cv::Point((int)std::lround(panel.labels.x + REGION_LEFT * u), (int)std::lround(panel.labels.y + REGION_TOP * u)),
                          cv::Point((int)std::lround(panel.labels.x + REGION_RIGHT * u), (int)std::lround(panel.labels.y + REGION_BOTTOM * u)));
    return wanted & cv::Rect(0, 0, frame.width, frame.height);
}

namespace {

// One reading of the list: the lines found in `ink`, the lettering of the
// region as white on black, and read off the picture itself. `edge` is the
// labels' left edge in the region.
bool readList(const cv::Mat& frame, const cv::Rect& region, const cv::Mat& ink, double u, int edge,
              const std::string& rockOre, TextLineReader& lines, RockContents& out, const std::string& dumpAs,
              bool qualityRows=false,bool pieceOnly=false) {
    out = RockContents();
    auto done = [&](bool ok, const std::string& why) {
        if (!why.empty()) out.note = why;
        return ok;
    };
    const cv::Rect picture(0, 0, frame.cols, frame.rows);
    const char* dump = dumpAs.empty() ? nullptr : dumpAs.c_str();
    cv::Mat drawn;
    if (dump) {
        cv::imwrite(std::string(dump) + "_region.png", frame(region));
        cv::imwrite(std::string(dump) + "_ink.png", ink);
        drawn = frame(region).clone();
    }

    // The letters, and the rows they stand in: a letter joins the row its
    // middle falls in, and a row is never taller than a bracket
    cv::Mat labels, stats, centres;
    const int count = cv::connectedComponentsWithStats(ink, labels, stats, centres, 8, CV_32S);
    std::vector<cv::Rect> letters;
    for (int i = 1; i < count; i++) {
        const cv::Rect r(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
                         stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
        if (r.height < 5 * u || r.height > 17 * u) continue;
        if (stats.at<int>(i, cv::CC_STAT_AREA) < 4) continue;
        if (r.width <= 20 * u) {
            letters.push_back(r);
            continue;
        }
        // Numerals run together: the panel sways with the pilot's head, and at a
        // scale of 0.95 "05%" can come out as one piece 20 px wide and "70%" as
        // one of 28. Such a piece is cut where it is thinnest, about a numeral's
        // width apart; wider than a word it is no lettering at all.
        if (r.width > 90 * u) continue;
        const int n = (std::max)(2, (int)std::lround(r.width / (0.62 * r.height)));
        std::vector<int> column((size_t)r.width, 0);
        for (int y = r.y; y < r.y + r.height; y++) {
            const int* row = labels.ptr<int>(y);
            for (int x = r.x; x < r.x + r.width; x++) column[(size_t)(x - r.x)] += row[x] == i ? 1 : 0;
        }
        int from = 0;
        for (int k = 1; k < n; k++) {
            const int guess = k * r.width / n, reach = (std::max)(1, r.width / n / 3);
            int cut = guess;
            for (int x = (std::max)(from + 2, guess - reach); x <= (std::min)(r.width - 2, guess + reach); x++) {
                if (column[(size_t)x] < column[(size_t)cut]) cut = x;
            }
            if (cut <= from + 1) continue;
            letters.push_back(cv::Rect(r.x + from, r.y, cut - from, r.height));
            from = cut;
        }
        letters.push_back(cv::Rect(r.x + from, r.y, r.width - from, r.height));
    }
    struct Row {
        int top, bottom;
        std::vector<cv::Rect> parts;
    };
    std::vector<Row> rows;
    std::sort(letters.begin(), letters.end(), [](const cv::Rect& a, const cv::Rect& b) {
        return a.y * 2 + a.height < b.y * 2 + b.height;
    });
    for (const cv::Rect& p : letters) {
        const int middle = p.y + p.height / 2;
        Row* into = nullptr;
        for (Row& r : rows) {
            if (middle >= r.top && middle <= r.bottom) into = &r;
        }
        if (!into) {
            rows.push_back({p.y, p.y + p.height - 1, {}});
            into = &rows.back();
        }
        into->parts.push_back(p);
        const int top = (std::min)(into->top, p.y), bottom = (std::max)(into->bottom, p.y + p.height - 1);
        if (bottom - top + 1 <= 17 * u) {
            into->top = top;
            into->bottom = bottom;
        }
    }
    std::sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) { return a.top < b.top; });

    // The column most rows have a letter's edge at - the left edge where the
    // shares begin, the right edge where the qualities end. A row has a say
    // with every letter it has between `from` and `to`; rock and sky put a
    // letter anywhere, but not in the same place line after line. Of two
    // columns as many rows stand at, the outer is the table's: the shares'
    // second numerals line up as well as their first. Not every row has a
    // say, though: over an ice asteroid the ground makes rows of its own,
    // enough to outvote a short list. So where the shares begin is said by
    // rows that begin like a share - three letters at the least within a
    // share's width - and where the qualities end by the rows that do begin
    // there, with a letter that ends like a quality: as tall as the share's
    // numerals and of their colour - every seat sets the two in one ink, and
    // the names in another - and a numeral wide or a numeral's gap after the
    // letter before it. Ice right of the list can put a letter beside every
    // line, further out than the qualities, and widen the table. Not level
    // with the share, though: the panel sways with the pilot's head, and a
    // line's end can stand five pixels under its beginning.
    struct Column {
        int at = -1;                           // -1: none
        std::vector<std::pair<int, int>> has;  // row, and that row's own edge there
    };
    const int same = (std::max)(2, (int)std::lround(SAME_COLUMN * u));
    auto columnOf = [&](bool leftEdges, double from, double to, const std::function<bool(size_t, int)>& hasSay) {
        Column best;
        std::vector<int> edges;
        for (size_t r = 0; r < rows.size(); r++) {
            for (const cv::Rect& p : rows[r].parts) {
                const int e = leftEdges ? p.x : p.x + p.width;
                if (e >= from && e <= to && hasSay(r, e)) edges.push_back(e);
            }
        }
        std::sort(edges.begin(), edges.end());
        if (!leftEdges) std::reverse(edges.begin(), edges.end());
        for (int at : edges) {
            Column column;
            column.at = at;
            for (size_t r = 0; r < rows.size(); r++) {
                int nearest = -1;
                for (const cv::Rect& p : rows[r].parts) {
                    const int e = leftEdges ? p.x : p.x + p.width;
                    if (std::abs(e - at) > same || !hasSay(r, e)) continue;
                    if (nearest < 0 || std::abs(e - at) < std::abs(nearest - at)) nearest = e;
                }
                if (nearest >= 0) column.has.push_back({(int)r, nearest});
            }
            if (column.has.size() > best.has.size()) best = column;   // (the outermost first, so it wins a tie)
        }
        return best;
    };
    const Column begins = columnOf(true, edge + SHARE_FROM * u, edge + SHARE_BY * u, [&](size_t r, int from) {
        int letters = 0;
        for (const cv::Rect& p : rows[r].parts) {
            if (p.x >= from && p.x + p.width / 2.0 <= from + SHARE_ENDS * TABLE_LEAST * u) letters++;
        }
        return letters >= 3;
    });
    if (begins.at < 0) return done(false, "no lines under the bar");
    // (the share's numerals in each of those rows: how tall the middle one is, and their colour)
    const cv::Mat regionPicture = frame(region);
    auto toneOf = [&](const cv::Rect& box) {
        const cv::Scalar mean = cv::mean(regionPicture(box), ink(box));
        const double all = mean[0] + mean[1] + mean[2];
        return all > 0 ? cv::Vec3d(mean[0] / all, mean[1] / all, mean[2] / all) : cv::Vec3d(0, 0, 0);
    };
    struct Share {
        int tall = 0;
        cv::Vec3d tone;
    };
    std::map<int, Share> shareOfRow;
    for (const auto& [row, from] : begins.has) {
        std::vector<int> tall;
        cv::Rect box;
        for (const cv::Rect& p : rows[(size_t)row].parts) {
            if (p.x >= from && p.x + p.width / 2.0 <= from + SHARE_ENDS * TABLE_LEAST * u) {
                tall.push_back(p.height);
                box = tall.size() == 1 ? p : (box | p);
            }
        }
        if (tall.empty()) continue;
        std::sort(tall.begin(), tall.end());
        shareOfRow[row] = {tall[tall.size() / 2], toneOf(box)};
    }
    const int asTall = (std::max)(2, (int)std::lround(2 * u));
    if (dump) {
        for (const auto& [row, share] : shareOfRow) {
            for (const cv::Rect& p : rows[(size_t)row].parts) {
                const int end = p.x + p.width;
                if (end < begins.at + TABLE_LEAST * u - 30 * u || end > begins.at + TABLE_MOST * u) continue;
                const cv::Vec3d tone = toneOf(p);
                std::cerr << "row " << row << " share tall " << share.tall << " tone " << share.tone << " | piece ends "
                          << (end - edge) / u << " tall " << p.height << " wide " << p.width << " tone off "
                          << std::abs(tone[0] - share.tone[0]) + std::abs(tone[1] - share.tone[1]) + std::abs(tone[2] - share.tone[2])
                          << std::endl;
            }
        }
    }
    const Column ends = columnOf(false, begins.at + TABLE_LEAST * u, begins.at + TABLE_MOST * u, [&](size_t r, int end) {
        const auto share = shareOfRow.find((int)r);
        if (share == shareOfRow.end()) return false;
        for (const cv::Rect& p : rows[r].parts) {
            if (p.x + p.width != end || std::abs(p.height - share->second.tall) > asTall) continue;
            const cv::Vec3d tone = toneOf(p);
            const cv::Vec3d& wanted = share->second.tone;
            if (std::abs(tone[0] - wanted[0]) + std::abs(tone[1] - wanted[1]) + std::abs(tone[2] - wanted[2]) > SAME_TONE) continue;
            if (p.width >= 4.5 * u) return true;
            for (const cv::Rect& q : rows[r].parts) {
                const int gap = p.x - (q.x + q.width);
                if (&q != &p && gap >= 0 && gap <= NUMERAL_GAP * u) return true;
            }
        }
        return false;
    });
    if (ends.at < 0) return done(false, "no qualities beside the lines");
    auto middleOf = [&](int r) { return (rows[(size_t)r].top + rows[(size_t)r].bottom) / 2.0; };
    // The lean: how far the lines' beginnings move sideways from one line to
    // the next, by the straight line through them - with three at the least,
    // and no steeper than a turret's panel leans
    double lean = 0;
    if (begins.has.size() >= 3) {
        double sy = 0, sx = 0, syy = 0, sxy = 0;
        for (const auto& [r, x] : begins.has) {
            const double y = middleOf(r);
            sy += y;
            sx += x;
            syy += y * y;
            sxy += x * y;
        }
        const double n = (double)begins.has.size(), spread = n * syy - sy * sy;
        if (spread > 1) lean = (std::max)(-LEAN_MOST, (std::min)(LEAN_MOST, (n * sxy - sx * sy) / spread));
    }
    auto standsAt = [&](const Column& column) {
        // where the column stands at the region's top, by the middle one of its rows
        std::vector<double> at;
        for (const auto& [r, x] : column.has) at.push_back(x - lean * middleOf(r));
        std::sort(at.begin(), at.end());
        return at[at.size() / 2];
    };
    const double beginsAt = standsAt(begins), endsAt = standsAt(ends);
    const double width = endsAt - beginsAt;
    if (width < TABLE_LEAST * u || width > TABLE_MOST * u) return done(false, "no table between the columns");
    const std::string table = "; table " + std::to_string((int)std::lround((beginsAt - edge) / u)) + " to " +
                              std::to_string((int)std::lround((endsAt - edge) / u)) + " by " +
                              std::to_string((int)begins.has.size()) + " and " + std::to_string((int)ends.has.size()) +
                              " rows, lean " + std::to_string((int)std::lround(lean * 100)) + " %";

    // The lines: every stretch of the picture in which the shares' column
    // has lettering. Not the rows of letters above - at 1080 lines the glow
    // runs a share's numerals into one piece, too wide for a letter, and a
    // line whose numerals do not stand apart is a line all the same (the Tin
    // rock of tests/scanpanel: one line of its four was found by letters).
    struct Entry {
        int top = 0, bottom = 0;     // of the share's lettering, in the region
        double from = 0, to = 0;     // where the line begins and ends
        double qualityFrom = 0;      // where its quality begins
    };
    std::vector<Entry> entries;
    std::vector<int> inked((size_t)ink.rows, 0);
    for (int y = 0; y < ink.rows; y++) {
        const int x0 = (std::max)(0, (int)std::lround(beginsAt + lean * y));
        const int x1 = (std::min)(ink.cols, (int)std::lround(beginsAt + lean * y + SHARE_ENDS * width));
        if (x1 > x0) inked[(size_t)y] = cv::countNonZero(ink.row(y).colRange(x0, x1));
    }
    const int inkLeast = (std::max)(3, (int)std::lround(4 * u));
    if(qualityRows) {
        // Flight R-ALT/VSI text can merge several percentage rows while the
        // right-hand quality numerals remain clear. Use their baselines as a
        // second geometric proposal, then read every original share/name/
        // quality and apply the same game-value and whole-rock sum checks.
        for(int y=0;y<ink.rows;y++) {
            const int right=std::clamp((int)std::lround(endsAt+lean*y+2*u),0,ink.cols);
            const int left=std::clamp((int)std::lround(endsAt+lean*y-QUALITY_HOLDS*width),0,ink.cols);
            inked[(size_t)y]=right>left&&cv::countNonZero(ink.row(y).colRange(left,right))>0?inkLeast:0;
        }
    }
    for (int y = 0; y < ink.rows; y++) {
        if (inked[(size_t)y] < inkLeast) continue;
        int end = y;
        while (end + 1 < ink.rows && inked[(size_t)end + 1] >= inkLeast) end++;
        Entry entry;
        entry.top = y;
        entry.bottom = end + 1;
        y = end;
        const int tall = entry.bottom - entry.top;
        const double middle = (entry.top + entry.bottom) / 2.0;
        if (tall < 6 * u || tall > 16 * u) continue;
        if (middle < (LIST_FROM - REGION_TOP) * u) continue;   // the composition bar's own row of ticks
        entry.from = beginsAt + lean * middle;
        entry.to = endsAt + lean * middle;
        // Where its letters do stand apart, the line's own edges are taken
        // for the column's, and its quality is the word it ends with: from
        // the letter that ends it leftwards while they stand a numeral
        // apart. Where the ground has run into the numerals there is no
        // such letter, and the quality is looked for where three numerals
        // would stand - a turret sets its names wider than the other seats,
        // and INERT MATERIALS ends where a fourth would begin.
        std::vector<cv::Rect> across;
        for (size_t r = 0; r < rows.size(); r++) {
            const double m = middleOf((int)r);
            if (m < entry.top || m > entry.bottom) continue;
            across.insert(across.end(), rows[r].parts.begin(), rows[r].parts.end());
            for (const auto& [has, x] : begins.has) {
                if (has == (int)r) entry.from = x;
            }
            for (const auto& [has, x] : ends.has) {
                if (has == (int)r) entry.to = x;
            }
        }
        std::sort(across.begin(), across.end(), [](const cv::Rect& a, const cv::Rect& b) { return a.x < b.x; });
        int last = -1;
        for (size_t i = 0; i < across.size(); i++) {
            if (std::abs(across[i].x + across[i].width - entry.to) <= same) last = (int)i;
        }
        entry.qualityFrom = entry.from + QUALITY_BEGINS * width;
        if (last >= 0) {
            // three numerals' room, and a fourth before them for the 1000 a
            // rock's best part can come to
            auto joins = [&](int i) {
                return i > 0 && across[(size_t)i].x - (across[(size_t)i - 1].x + across[(size_t)i - 1].width) <= NUMERAL_GAP * u;
            };
            int first = last;
            while (joins(first) && across[(size_t)first - 1].x + across[(size_t)first - 1].width / 2.0 >= entry.to - QUALITY_HOLDS * width) first--;
            if (last - first == 2 && joins(first) && across[(size_t)first - 1].x >= entry.from + 0.78 * width) first--;
            entry.qualityFrom = across[(size_t)first].x - 3 * u;
        }
        entries.push_back(entry);
    }
    std::sort(entries.begin(), entries.end(), [](const Entry& a, const Entry& b) { return a.top < b.top; });

    // A word as the reader wants it: a letter's room either side and a few
    // pixels above and below - a line, not ink shaved to its edge
    const int pad = (std::max)(3, (int)std::lround(5 * u));
    const int lift = (std::max)(2, (int)std::lround(3 * u));
    auto cropOf = [&](const Entry& entry, double from, double to) {
        return cv::Rect(cv::Point(region.x + (int)std::lround(from), region.y + entry.top - lift),
                        cv::Point(region.x + (int)std::lround(to), region.y + entry.bottom + lift)) & picture;
    };
    auto shareOf = [&](const Entry& e) { return cropOf(e, e.from - pad, e.from + SHARE_ENDS * width); };
    auto nameOf = [&](const Entry& e) { return cropOf(e, e.from + NAME_BEGINS * width, e.qualityFrom - u); };
    auto qualityOf = [&](const Entry& e) { return cropOf(e, e.qualityFrom, e.to + pad); };
    if(pieceOnly){
        for(const auto& e:entries){
            if((e.top+e.bottom)*.5>(FIRST_BY-REGION_TOP)*u)break;
            const auto qbox=qualityOf(e),nbox=nameOf(e);
            if(qbox.width<8*u||nbox.width<20*u)continue;
            const auto q=lines.read(frame(qbox));int quality=0;
            if(q.mean<.92||!parseQuality(q.text,quality)||bandOf(rockOre,quality)<0)continue;
            const auto name=lines.read(frame(nbox));
            if(name.mean<.85||snapOreName(name.text)!=rockOre)continue;
            RockPartRead part;part.ore=rockOre;part.quality=quality;
            part.nameText=name.text;part.qualityText=q.text;out.parts.push_back(part);
            return done(true,"fast gem name/quality; composition not measured");
        }
        return done(false,"gem row not confirmed");
    }
    // The lines, from the first that begins with a share, one under the
    // other, until the rock is accounted for or something else follows -
    // the Golem has LOCK, TARG and AUTO a line's pitch under its list
    std::vector<const Entry*> list;
    bool read = true;
    double sum = 0;
    int cut = 0;
    for (const Entry& entry : entries) {
        const int middle = (entry.top + entry.bottom) / 2;
        if (list.empty()) {
            if (middle > (FIRST_BY - REGION_TOP) * u) break;
        } else {
            const int step = middle - (list.back()->top + list.back()->bottom) / 2;
            if (step < PITCH_LEAST * u) continue;
            if (step > PITCH_MOST * u) break;
        }
        RockPartRead part;
        const cv::Rect share = shareOf(entry), quality = qualityOf(entry);
        if (share.width < 20 * u || quality.width < 8 * u) continue;
        part.shareText = lines.read(frame(share)).text;
        if (dump) {
            cv::imwrite(std::string(dump) + "_share" + std::to_string(cut) + ".png", frame(share));
            cv::imwrite(std::string(dump) + "_quality" + std::to_string(cut) + ".png", frame(quality));
            cv::imwrite(std::string(dump) + "_name" + std::to_string(cut) + ".png", frame(nameOf(entry)));
            cv::rectangle(drawn, share - region.tl(), cv::Scalar(0, 255, 0));
            cv::rectangle(drawn, nameOf(entry) - region.tl(), cv::Scalar(255, 160, 0));
            cv::rectangle(drawn, quality - region.tl(), cv::Scalar(0, 0, 255));
            cut++;
        }
        if (!parseShare(part.shareText, part.percent)) {
            // Yellow flight text over an orange percent sign can make it
            // read as 94. A monochrome read often separates those strokes.
            cv::Mat green;cv::extractChannel(frame(share),green,1);
            const auto retry=lines.read(green);
            if(retry.mean>=0.80&&parseShare(retry.text,part.percent))part.shareText=retry.text;
            else {if (list.empty()) continue;break;}
        }
        // The quality: three or four numerals, one of the ore's values - no
        // ore's is under 262. Anything else is the inert rest's 0 or a quality
        // that did not read, and the 0 itself does not say which: a dotted zero
        // on its own comes back from the reader as 0, as @, as an 8 or as a
        // Chinese character, and so does the one numeral left of a 917 the
        // ground has swallowed the rest of. The line's name says it: INERT
        // MATERIALS, in every seat.
        part.qualityText = lines.read(frame(quality)).text;
        int value = 0;
        if (parseQuality(part.qualityText, value) && value >= 100) {
            part.quality = value;
        } else {
            const cv::Rect name = nameOf(entry);
            if (name.width >= 20 * u) part.nameText = lines.read(frame(name)).text;
            if (saysInert(part.nameText)) {
                part.quality = 0;
                part.inert = true;
            } else {
                part.quality = -1;
                read = false;
            }
        }
        out.parts.push_back(part);
        list.push_back(&entry);
        sum += part.percent;
        if (sumIsTheRock(sum, list.size()) || sum > 100.006 || list.size() == 7) break;
    }
    if (dump) cv::imwrite(std::string(dump) + "_words.png", drawn);
    if (list.empty()) return done(false, "no lines under the bar" + table);
    if (!read) {
        contentsHold(out);
        out.whole = false;
        return done(false, "a quality did not read" + table);
    }
    // A terrain stroke just left of a share can become an extra leading
    // numeral (5.75% -> 15.75%). Ask slightly inset/monochrome crops for
    // alternatives only when the literal total fails. Accept a correction
    // only if exactly ONE distinct combination accounts for the whole rock;
    // no percentage is manufactured or normalized from the missing total.
    if(!sumIsTheRock(sum,out.parts.size())&&list.size()==out.parts.size()) {
        using Alternative=std::pair<float,std::string>;
        std::vector<std::vector<Alternative>> options;
        for(size_t i=0;i<list.size();i++) {
            std::vector<Alternative> values={{out.parts[i].percent,out.parts[i].shareText}};
            auto box=shareOf(*list[i]);
            for(int inset:{(int)std::lround(4*u),(int)std::lround(8*u)}) {
                auto cut=box;cut.x+=inset;cut.width-=inset;
                if(cut.width<16)continue;
                auto reading=lines.read(frame(cut));float value=0;
                if(reading.mean<0.80||!parseShare(reading.text,value))continue;
                bool duplicate=false;for(const auto& v:values)if(std::abs(v.first-value)<.001)duplicate=true;
                if(!duplicate)values.push_back({value,reading.text});
            }
            options.push_back(values);
        }
        std::vector<size_t> choice(options.size()),winner;int solutions=0;
        std::function<void(size_t,double)> solve=[&](size_t row,double total) {
            if(solutions>1||total>100.006)return;
            if(row==options.size()){if(sumIsTheRock(total,options.size())){solutions++;winner=choice;}return;}
            for(size_t k=0;k<options[row].size();k++){choice[row]=k;solve(row+1,total+options[row][k].first);}
        };
        solve(0,0);
        if(solutions==1)for(size_t i=0;i<winner.size();i++) {
            out.parts[i].percent=options[i][winner[i]].first;out.parts[i].shareText=options[i][winner[i]].second;
        }
    }
    // The names: by the rock's kind where that fits, else read. Either way
    // the lines have to be a rock's of that kind - see contentsFitRock.
    auto holds = [&]() {
        const bool complete=contentsHold(out);
        out.partial=!complete;
        if(out.partial&&!contentsEstimateReady(out))out.partial=false;
        if (rockOre.empty() || contentsFitRock(rockOre, out)) return complete;
        out.whole = false;out.partial=false;
        return false;
    };
    if (!rockOre.empty() && nameContentsByRock(rockOre, out)) {
        return done(holds(), "named by the rock's kind" + table);
    }
    for (size_t i = 0; i < list.size(); i++) {
        RockPartRead& part = out.parts[i];
        if (part.inert) continue;
        const cv::Rect name = nameOf(*list[i]);
        if (name.width < 20 * u) continue;
        part.nameText = lines.read(frame(name)).text;
        // (a line with a quality that calls itself inert is no line of the list)
        if (!saysInert(part.nameText)) part.ore = snapOreName(part.nameText);
        if(part.ore.empty()&&!part.inert&&name.width>70*u) {
            // SynthStrings' short aliases need only the first word's room;
            // flight instruments in the otherwise empty name cell are noise.
            const auto shortName=lines.read(frame(cv::Rect(name.x,name.y,(int)std::lround(65*u),name.height)));
            if(shortName.mean>=0.75) {
                const auto ore=snapOreName(shortName.text);
                if(qualityOfOre(ore,part.quality)){part.ore=ore;part.nameText=shortName.text;}
            }
        }
    }
    // A unique quality in the extracted game table is another independent
    // material identity, even when a flight instrument covers its name.
    // Shared qualities (notably 1000) cannot supply a name.
    for(auto& part:out.parts)if(!part.inert&&part.ore.empty()&&part.quality>0) {
        std::string unique;int matches=0;
        for(int b=0;b<ORE_BANDS_COUNT;b++)if(bandOf(ORE_BANDS[b].ore,part.quality)>=0){unique=ORE_BANDS[b].ore;matches++;}
        for(const auto& b:HAND_MINING_BANDS)if(bandOf(b.ore,part.quality)>=0){unique=b.ore;matches++;}
        if(matches==1)part.ore=unique;
    }
    // Resolve a shared quality only when every matching game-defined rock
    // composition agrees. Known OCR names are constraints, not overwritten.
    std::vector<std::string> agreed(out.parts.size());int matchingKinds=0;
    std::vector<std::string> tried;
    for(int k=0;k<ROCK_PART_COUNT;k++) {
        const std::string kind=ROCK_PARTS[k].rock;
        if(std::find(tried.begin(),tried.end(),kind)!=tried.end())continue;
        tried.push_back(kind);RockContents candidate=out;
        if(!nameContentsByRock(kind,candidate)||!contentsFitRock(kind,candidate))continue;
        bool matches=true;
        for(size_t i=0;i<out.parts.size();i++)if(!out.parts[i].ore.empty()&&out.parts[i].ore!=candidate.parts[i].ore)matches=false;
        if(!matches)continue;
        for(size_t i=0;i<out.parts.size();i++) {
            if(matchingKinds==0)agreed[i]=candidate.parts[i].ore;
            else if(agreed[i]!=candidate.parts[i].ore)agreed[i].clear();
        }
        matchingKinds++;
    }
    if(matchingKinds)for(size_t i=0;i<out.parts.size();i++)if(out.parts[i].ore.empty()&&!out.parts[i].inert)out.parts[i].ore=agreed[i];
    return done(holds(), "names read" + table);
}

}  // namespace

bool readRockPieceQuote(const cv::Mat& frame,ScanPanel& panel,TextLineReader& lines,RockContents& out){
    out=RockContents();if(frame.empty()||panel.labels.x<0||panel.labelScale<=0||!lines.ready())return false;
    auto rows=panelFigureLines(panel,frame.size());if(rows.empty()||rows[0].empty())return false;
    auto header=rows[0];const int margin=(int)std::lround(18*panel.labelScale);
    header.x-=margin;header.y-=(int)std::lround(2*panel.labelScale);
    header.width=(int)std::lround(135*panel.labelScale);header.height+=(int)std::lround(7*panel.labelScale);
    header&=cv::Rect(0,0,frame.cols,frame.rows);if(header.empty())return false;
    const auto title=lines.read(frame(header));if(title.mean<.85)return false;
    const auto name=snapOreName(title.text);panel.stats.ore=name;
    bool gem=false;for(const auto& b:HAND_MINING_BANDS)if(name==b.ore)gem=true;
    if(!gem)return false;
    const auto region=rockContentsRegion(panel,frame.size());if(region.empty())return false;
    const auto started=std::chrono::steady_clock::now();
    const auto ink=hudLetteringInk(frame(region),panel.labelScale);
    bool ok=readList(frame,region,ink,panel.labelScale,panel.labels.x-region.x,name,lines,out,"",false,true);
    if(!ok)ok=readList(frame,region,ink,panel.labelScale,panel.labels.x-region.x,name,lines,out,"",true,true);
    out.ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
    return ok&&contentsPieceQuotesReady(out);
}

bool readRockContents(const cv::Mat& frame, const ScanPanel& panel, const std::string& rockOre,
                      TextLineReader& lines, RockContents& out) {
    out = RockContents();
    const auto started = std::chrono::steady_clock::now();
    auto done = [&](bool ok) {
        out.ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
        return ok;
    };
    if (frame.empty() || panel.labels.x < 0 || panel.labelScale <= 0) {
        out.note = "no label column";
        return done(false);
    }
    const double u = panel.labelScale;
    const cv::Rect region = rockContentsRegion(panel, frame.size());
    if (region.width < 215 * u || region.height < 40 * u) {
        out.note = "the list is off the picture";
        return done(false);
    }
    const int edge = panel.labels.x - region.x;
    const char* dump = DEV_ENV("SCMINER_CONTENTS_DUMP");
    if (readList(frame, region, hudLetteringInk(frame(region), u), u, edge, rockOre, lines, out, dump ? dump : "")) {
        return done(true);
    }
    // Over snow the lettering is the darker of the two: a turret's orange
    // shares measure 219/146/113 where they are most themselves, on a ground
    // of 200/198/204 - a shade over it in red, well under it in green and
    // blue - and what stands out of the ground finds only a few strokes of
    // them. So a list that did not come out whole is looked for once more
    // in what stands out of the picture's negative: the shares and the
    // qualities, which is all the table is found by. The words are read off
    // the picture as it is either way.
    cv::Mat negative;
    cv::bitwise_not(frame(region), negative);
    RockContents dark;
    if (readList(frame, region, hudLetteringInk(negative, u), u, edge, rockOre, lines, dark,
                 dump ? std::string(dump) + "_dark" : std::string())) {
        out = dark;
        out.note += "; dark on bright";
        return done(true);
    }
    for(bool inverted:{false,true}) {
        RockContents byQuality;
        const auto geometry=inverted?hudLetteringInk(negative,u):hudLetteringInk(frame(region),u);
        const bool complete=readList(frame,region,geometry,u,edge,rockOre,lines,byQuality,
            dump?std::string(dump)+(inverted?"_quality_dark":"_quality"):std::string(),true);
        if(complete||contentsEstimateReady(byQuality)) {
            out=std::move(byQuality);out.note+="; quality-column rows";
            return done(complete);
        }
    }
    if (out.parts.empty() && !dark.parts.empty()) {
        out = dark;
        out.note += "; dark on bright";
    }
    return done(false);
}

}  // namespace SCMiner
