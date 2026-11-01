#include "RockValuation.h"
#include "MiniJson.h"
#include "RefineryData.h"
#include "RefiningData.h"
#include <algorithm>
#include <cmath>
#include <cctype>
#include <limits>

namespace SCMiner {
namespace {
double number(const JsonValue& row, const char* key) {
    const auto* v = row.find(key);
    if (!v) return 0;
    if (v->kind == JsonValue::Kind::Number) return v->number;
    if (v->kind == JsonValue::Kind::String) {
        char* end = nullptr; double n = std::strtod(v->text.c_str(), &end);
        if (end && end != v->text.c_str() && !*end) return n;
    }
    return 0;
}
bool fresh(long long at, long long now, long long age) { return at > 0 && at <= now + 300 && now - at <= age; }
bool rows(const std::string& text, JsonValue& value) {
    std::string why;
    if (!parseJson(text, value, why) || value.textOr("status") != "ok") return false;
    const auto* data = value.find("data"); return data && data->kind == JsonValue::Kind::Array;
}
}

std::string RockPriceBook::material(std::string name) {
    for (char& c : name) c = (char)std::tolower((unsigned char)c);
    for (const std::string suffix : {" (raw)", " (ore)"})
        if (name.size() > suffix.size() && name.compare(name.size()-suffix.size(),suffix.size(),suffix)==0)
            name.resize(name.size()-suffix.size());
    if (name.rfind("raw ",0)==0) name.erase(0,4);
    if (name == "aluminium") name = "aluminum";
    if (name == "quantanium") name = "quantainium"; // the game's/UEX's historical spelling
    return name;
}

int RockPriceBook::qualityTier(int quality) {
    if (quality < 1 || quality > 1000) return 0;
    if (quality < 500) return 1;
    if (quality < 600) return 2;
    if (quality < 700) return 3;
    if (quality < 800) return 4;
    if (quality < 900) return 5;
    if (quality < 950) return 6;
    return 7;
}

bool RockPriceBook::read(const std::string& commodities, const std::string& terminals,
                         const std::string& raw, const std::string& refined, const std::string& market,
                         long long now, const std::string& version, std::string& why) {
    raw_.clear(); refined_.clear(); market_.clear();
    JsonValue cs, ts;
    if (!rows(commodities,cs) || !rows(terminals,ts)) { why="Commodity/terminal definitions unavailable"; return false; }
    std::map<int,std::string> rawIds, refinedIds;
    for (const auto& c : cs.find("data")->items) {
        if (number(c,"is_available_live") != 1) continue;
        const int id=(int)number(c,"id");
        auto name=material(c.textOr("name"));
        if (number(c,"is_raw")==1) rawIds[id]=name;
        else refinedIds[id]=name;
    }
    std::map<int,Terminal> locations;
    for (const auto& t : ts.find("data")->items) {
        if (number(t,"is_available_live") != 1) continue;
        locations[(int)number(t,"id")] = {t.textOr("name"),t.textOr("star_system_name"),{}};
    }
    auto prices=[&](const std::string& text,const std::map<int,std::string>& ids,std::map<int,Terminal>& out) {
        JsonValue data; if (!rows(text,data)) return;
        for (const auto& r : data.find("data")->items) {
            const int id=(int)number(r,"id_commodity"), terminal=(int)number(r,"id_terminal");
            auto c=ids.find(id); auto t=locations.find(terminal);
            double price=number(r,"price_sell"); // what the player receives, not what they pay
            long long at=(long long)number(r,"date_modified");
            if (c==ids.end() || t==locations.end() || !std::isfinite(price) || price<=0 ||
                number(r,"status_sell")>=7 || number(r,"quality")>0 || !fresh(at,now,30ll*86400)) continue;
            auto& location=out[terminal];location.name=t->second.name;location.system=t->second.system;
            auto& old=location.prices[c->second];
            if (at>=old.at) old={price,at};
        }
    };
    prices(raw,rawIds,raw_);prices(refined,refinedIds,refined_);
    JsonValue averages;
    if (rows(market,averages) && !version.empty()) for (const auto& r : averages.find("data")->items) {
        if (r.textOr("operation")!="buy" || r.textOr("currency")!="UEC" || r.textOr("game_version")!=version) continue;
        const auto unit=r.textOr("unit"); if (unit!="scu" && unit!="cscu") continue;
        int tier=(int)number(r,"quality_tier"); double samples=number(r,"listings_count"), price=number(r,"price_avg");
        long long at=(long long)number(r,"date_modified");
        if (tier<1 || tier>7 || !std::isfinite(price) || !std::isfinite(samples) || samples<=0 || price<=0 ||
            !fresh(at,now,48ll*3600)) continue; // count=0 is a historical fallback, not a current offer
        // Raw ads are a different product. Only refined commodity identities.
        const auto name=material(r.textOr("item_name"));
        bool known=false;
        for (const auto& c : cs.find("data")->items)
            if (number(c,"is_raw")==0 && number(c,"id_item")==number(r,"id_item") && material(c.textOr("name"))==name) known=true;
        if (!known) continue;
        auto& m=market_[{name,tier}];m.weighted+=price*(unit=="cscu"?100:1)*samples;m.samples+=samples;
        m.at=m.at?std::min(m.at,at):at;
    }
    if (raw_.empty() && refined_.empty()) {why="No recent terminal buyback quotes available";return false;}
    why.clear();return true;
}

RockValue RockPriceBook::estimate(double scu, const RockContents& contents, const std::string& system,
                                  int method, long long now) const {
    RockValue out;out.method=method;
    if (!contentsEstimateReady(contents) || !std::isfinite(scu) || scu<=0 || method<0 || method>=REFINING_METHOD_COUNT) return out;
    std::map<std::string,double> amounts;
    double sum=0;
    for (const auto& part : contents.parts) {
        if (!std::isfinite(part.percent) || part.percent<0 || part.percent>100) return out;
        sum+=part.percent;
        if (!part.inert && part.percent>0) {
            if (part.ore.empty() || qualityTier(part.quality)==0) return out;
            amounts[material(part.ore)]+=scu*part.percent/100;
        }
    }
    if (sum<99 || sum>100.1 || amounts.empty()) return out;
    out.scanned=true;
    auto sale=[&](const std::map<int,Terminal>& terminals,const std::map<std::string,double>& volumes,
                  double& total,std::string& place,long long& reported) {
        bool found=false,local=false;
        for (const auto& t : terminals) {
            double value=0;long long oldest=0;bool complete=true;
            for (const auto& a : volumes) {
                auto q=t.second.prices.find(a.first);
                if(q==t.second.prices.end() || !fresh(q->second.at,now,30ll*86400)) {complete=false;break;}
                value+=q->second.price*a.second;oldest=oldest?std::min(oldest,q->second.at):q->second.at;
            }
            const bool here=!system.empty() && material(t.second.system)==material(system);
            if (complete && (!found || (here&&!local) || (here==local && value>total))) {
                found=true;local=here;total=value;reported=oldest;
                place=t.second.name+(t.second.system.empty()?"":" / "+t.second.system);
            }
        }
        return found;
    };
    out.rawKnown=sale(raw_,amounts,out.raw,out.rawTerminal,out.rawReported);
    bool hasLocal=false;
    for (const auto& station : REFINERIES) if (material(station.system)==material(system)) hasLocal=true;
    double best=-std::numeric_limits<double>::infinity();
    for (int s=0;s<REFINERY_COUNT;s++) {
        if (hasLocal && material(REFINERIES[s].system)!=material(system)) continue;
        std::map<std::string,double> outputs;double fees=0;bool complete=true,valid=true;
        for (const auto& a : amounts) {
            int ore=-1;
            for (int i=0;i<REFINERY_MATERIAL_COUNT;i++) if (material(REFINERY_MATERIALS[i])==a.first) ore=i;
            if (ore<0) {valid=false;break;}
            const auto r=refine(float(a.second*100),s,ore,method);
            outputs[a.first]=r.yield/100;fees+=r.cost;complete=complete&&r.complete;
        }
        if(!valid)continue;
        double gross=0;std::string terminal;long long reported=0;
        bool quoted=sale(refined_,outputs,gross,terminal,reported);
        // Player buyers remain useful even when NPC prices are missing.
        if (!quoted && out.refinery<0) {out.refinery=s;out.fees=fees;out.feesKnown=complete;}
        // Select on gross output: fees are not known at every station, and
        // comparing unknown fees as zero would invent a profitable route.
        if (!quoted || gross<=best) continue;
        best=gross;out.refinedKnown=true;out.refined=gross;out.fees=fees;out.feesKnown=complete;
        out.refinery=s;out.refinedTerminal=terminal;out.refinedReported=reported;
    }
    // Player estimate uses the same refinery/method and active buy-side
    // quality-band averages. Partial coverage is explicit, never a whole-rock total.
    if (out.refinery>=0) {
        double all=0,priced=0;
        for (const auto& part : contents.parts) {
            if(part.inert||part.percent<=0)continue;
            const auto name=material(part.ore);int ore=-1;
            for(int i=0;i<REFINERY_MATERIAL_COUNT;i++)if(material(REFINERY_MATERIALS[i])==name)ore=i;
            if(ore<0)continue;
            double volume=refine(float(scu*part.percent),out.refinery,ore,method).yield/100;all+=volume;
            auto m=market_.find({name,qualityTier(part.quality)});
            if(m==market_.end()||m->second.samples<3||!fresh(m->second.at,now,48ll*3600))continue;
            out.player+=volume*m->second.weighted/m->second.samples;priced+=volume;
            out.playerReported=out.playerReported?std::min(out.playerReported,m->second.at):m->second.at;
        }
        out.playerCoverage=all>0?priced/all:0;
    }
    return out;
}
}
