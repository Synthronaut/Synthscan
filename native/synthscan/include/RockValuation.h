#pragma once
#include "RockContents.h"
#include <map>
#include <string>
#include <vector>
#include <tuple>

namespace SCMiner {
struct MarketQuote {
    bool known=false, limited=false;
    double price=0, listings=0;
    int qualityMin=0,qualityMax=0;
    long long reported=0;
    std::string unit;
    double low=0,high=0;
    bool historyOnly=false;
};
struct RockPartValue {
    std::string material;
    int quality=0;
    double refinedScu=0,pricePerScu=0,value=0,listings=0;
    double lowPerScu=0,highPerScu=0;
};
// Whole-rock potential at 100% collection, excluding inert. Never confirmed cargo.
struct RockValue {
    bool scanned = false, rawKnown = false, refinedKnown = false, feesKnown = false;
    double raw = 0, refined = 0, fees = 0, player = 0, playerCoverage = 0;
    int refinery = -1, method = 2;
    long long rawReported = 0, refinedReported = 0, playerReported = 0;
    std::string rawTerminal, refinedTerminal;
    bool playerLimited=false;
    std::vector<RockPartValue> playerParts;
    double playerLow=0,playerHigh=0;
    bool playerHistoryOnly=false;
};

class RockPriceBook {
public:
    bool read(const std::string& commodities, const std::string& terminals,
              const std::string& raw, const std::string& refined, const std::string& market,
              long long now, const std::string& version, std::string& why);
    RockValue estimate(double scu, const RockContents& contents, const std::string& system,
                       int method, long long now) const;
    // Matching quality-band buy averages; per-piece quotes never use SCU conversions.
    MarketQuote playerQuote(const std::string& item,int quality,const std::string& unit,long long now) const;
    MarketQuote marketRange(const std::string& item,int quality,const std::string& unit,long long now) const;
    bool addHistory(const std::string& json,long long now);
    static std::string material(std::string name);
    static int qualityTier(int quality);
private:
    struct Quote { double price = 0; long long at = 0; };
    struct Terminal { std::string name, system; std::map<std::string, Quote> prices; };
    std::map<int, Terminal> raw_, refined_;
    struct Market { double weighted = 0, samples = 0; long long at = 0; int item=0;bool ambiguous=false; };
    std::map<std::pair<std::string,int>, Market> market_;
    std::map<std::pair<std::string,int>, Market> pieces_;
    struct RangeSample {double price=0,weight=1;long long at=0;int quality=0,item=0;bool historical=false;};
    using RangeKey=std::tuple<std::string,std::string,int>;
    std::map<RangeKey,std::vector<RangeSample>> rangeAverages_;
    // One latest snapshot per listing, regardless of daily repeats/price edits.
    std::map<std::pair<int,long long>,std::pair<RangeKey,RangeSample>> history_;
    std::map<int,std::string> refinedItems_;
    std::string version_;
};
}
