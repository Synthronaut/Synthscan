#pragma once
#include "RockContents.h"
#include <map>
#include <string>
#include <vector>

namespace SCMiner {
// Whole-rock potential at 100% collection, excluding inert. Never confirmed cargo.
struct RockValue {
    bool scanned = false, rawKnown = false, refinedKnown = false, feesKnown = false;
    double raw = 0, refined = 0, fees = 0, player = 0, playerCoverage = 0;
    int refinery = -1, method = 2;
    long long rawReported = 0, refinedReported = 0, playerReported = 0;
    std::string rawTerminal, refinedTerminal;
};

class RockPriceBook {
public:
    bool read(const std::string& commodities, const std::string& terminals,
              const std::string& raw, const std::string& refined, const std::string& market,
              long long now, const std::string& version, std::string& why);
    RockValue estimate(double scu, const RockContents& contents, const std::string& system,
                       int method, long long now) const;
    static std::string material(std::string name);
    static int qualityTier(int quality);
private:
    struct Quote { double price = 0; long long at = 0; };
    struct Terminal { std::string name, system; std::map<std::string, Quote> prices; };
    std::map<int, Terminal> raw_, refined_;
    struct Market { double weighted = 0, samples = 0; long long at = 0; };
    std::map<std::pair<std::string,int>, Market> market_;
};
}
