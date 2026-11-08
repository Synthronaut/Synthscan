#include "RockValuation.h"
#include "MiniJson.h"
#include "RefineryData.h"
#include "RefiningData.h"
#include <algorithm>
#include <cmath>
#include <cctype>
#include <limits>
#include <set>

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
std::string itemKey(std::string name){
    for(char& c:name)c=(char)std::tolower((unsigned char)c);
    // Preserve item forms: raw, ore and pure pieces are different products.
    return name;
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
    raw_.clear(); refined_.clear(); market_.clear();pieces_.clear();
    rangeAverages_.clear();history_.clear();refinedItems_.clear();version_=version;
    JsonValue cs, ts;
    const bool haveCommodities=rows(commodities,cs),haveTerminals=rows(terminals,ts);
    std::map<int,std::string> rawIds, refinedIds;
    if(haveCommodities)for (const auto& c : cs.find("data")->items) {
        if (number(c,"is_available_live") != 1) continue;
        const int id=(int)number(c,"id");
        auto name=material(c.textOr("name"));
        if (number(c,"is_raw")==1) rawIds[id]=name;
        else {refinedIds[id]=name;const int item=(int)number(c,"id_item");if(item>0)refinedItems_[item]=name;}
    }
    std::map<int,Terminal> locations;
    if(haveTerminals)for (const auto& t : ts.find("data")->items) {
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
    // Gems can be flagged is_raw but sold at normal commodity terminals.
    std::map<int,std::string> gemIds;
    if(haveCommodities)for(const auto& c:cs.find("data")->items)
        if(number(c,"is_available_live")==1&&number(c,"is_mineral")==1)gemIds[(int)number(c,"id")]=material(c.textOr("name"));
    prices(refined,gemIds,raw_);
    JsonValue averages;
    if (rows(market,averages) && !version.empty()) for (const auto& r : averages.find("data")->items) {
        const auto operation=r.textOr("operation");
        if ((operation!="buy"&&operation!="sell") || r.textOr("currency")!="UEC" || r.textOr("game_version")!=version) continue;
        const auto unit=r.textOr("unit"); if (unit!="scu" && unit!="cscu" && unit!="unit") continue;
        int tier=(int)number(r,"quality_tier"); double samples=number(r,"listings_count"), price=number(r,"price_avg");
        long long at=(long long)number(r,"date_modified");
        if (tier<1 || tier>7 || !std::isfinite(price) || !std::isfinite(samples) || samples<=0 || price<=0 ||
            !fresh(at,now,48ll*3600)) continue; // count=0 is a historical fallback, not a current offer
        const int item=(int)number(r,"id_item");
        if(item<=0||std::floor(samples)!=samples)continue;
        const auto rangeName=unit=="unit"?itemKey(r.textOr("item_name")):material(r.textOr("item_name"));
        if(unit=="unit"||(refinedItems_.count(item)&&refinedItems_[item]==rangeName))
            rangeAverages_[{rangeName,unit=="unit"?"unit":"scu",tier}].push_back({price*(unit=="cscu"?100:1),std::min(5.0,samples),at,0,item,false});
        if(operation!="buy")continue;
        auto add=[&](Market& m,double p){
            if(m.item&&m.item!=item)m.ambiguous=true;
            m.item=item;m.weighted+=p*samples;m.samples+=samples;
            m.at=m.at?std::min(m.at,at):at;
        };
        if(unit=="unit"){
            const auto name=itemKey(r.textOr("item_name"));
            if(!name.empty())add(pieces_[{name,tier}],price);
            continue;
        }
        // Raw ads are a different product. Only refined commodity identities.
        const auto name=material(r.textOr("item_name"));
        bool known=false;
        if(haveCommodities)for (const auto& c : cs.find("data")->items)
            if (number(c,"is_raw")==0 && number(c,"id_item")==number(r,"id_item") && material(c.textOr("name"))==name) known=true;
        if (!known) continue;
        add(market_[{name,tier}],price*(unit=="cscu"?100:1));
    }
    if (raw_.empty() && refined_.empty() && market_.empty() && pieces_.empty()&&rangeAverages_.empty()) {why="No recent terminal or market prices available";return false;}
    why.clear();return true;
}

MarketQuote RockPriceBook::playerQuote(const std::string& item,int quality,const std::string& unit,long long now)const{
    MarketQuote out;out.unit=unit;
    const int tier=qualityTier(quality);if(!tier||(unit!="unit"&&unit!="scu"))return out;
    const auto& table=unit=="unit"?pieces_:market_;
    auto found=table.find({unit=="unit"?itemKey(item):material(item),tier});
    if(found==table.end())return out;
    const auto& quote=found->second;
    if(quote.ambiguous||quote.samples<=0||!fresh(quote.at,now,48ll*3600))return out;
    out.known=true;out.price=quote.weighted/quote.samples;out.listings=quote.samples;
    out.limited=quote.samples<3;out.reported=quote.at;
    static const int lower[]={0,1,500,600,700,800,900,950},upper[]={0,499,599,699,799,899,949,1000};
    out.qualityMin=lower[tier];out.qualityMax=upper[tier];return out;
}

bool RockPriceBook::addHistory(const std::string& json,long long now){
    JsonValue data;if(version_.empty()||!rows(json,data))return false;
    bool added=false;
    for(const auto& r:data.find("data")->items){
        const auto operation=r.textOr("operation"),unit=r.textOr("unit");
        if((operation!="buy"&&operation!="sell")||r.textOr("currency")!="UEC"||r.textOr("game_version")!=version_||
            (unit!="unit"&&unit!="scu"&&unit!="cscu"))continue;
        const double price=number(r,"price"),quality=number(r,"quality");
        const int tier=(int)number(r,"quality_tier"),item=(int)number(r,"id_item");
        const auto listing=(long long)number(r,"id_listing"),at=(long long)number(r,"date_added");
        if(!std::isfinite(price)||price<=0||!std::isfinite(quality)||std::floor(quality)!=quality||
            !qualityTier((int)quality)||qualityTier((int)quality)!=tier||item<=0||listing<=0||!fresh(at,now,30ll*86400))continue;
        const auto name=unit=="unit"?itemKey(r.textOr("item_name")):material(r.textOr("item_name"));
        if(name.empty()||(unit!="unit"&&(!refinedItems_.count(item)||refinedItems_[item]!=name)))continue;
        const auto removed=(long long)number(r,"date_removed");
        if(removed<0||removed>now+300)continue;
        auto& old=history_[{item,listing}];
        if(at>=old.second.at){
            old={{name,unit=="unit"?"unit":"scu",tier},{price*(unit=="cscu"?100:1),1,at,(int)quality,item,removed>0}};
            added=true;
        }
    }
    return added;
}

MarketQuote RockPriceBook::marketRange(const std::string& item,int quality,const std::string& unit,long long now)const{
    MarketQuote out;out.unit=unit;const int tier=qualityTier(quality);
    if(!tier||(unit!="unit"&&unit!="scu"))return out;
    const RangeKey key={unit=="unit"?itemKey(item):material(item),unit,tier};
    std::vector<RangeSample> samples;
    for(const auto& h:history_)if(h.second.first==key&&fresh(h.second.second.at,now,30ll*86400))samples.push_back(h.second.second);
    // A history response repeats current ads. Use the deduplicated snapshots
    // instead of counting both them and their aggregate a second time.
    const bool snapshots=!samples.empty();
    if(!snapshots){auto a=rangeAverages_.find(key);if(a!=rangeAverages_.end())
        for(const auto& s:a->second)if(fresh(s.at,now,48ll*3600))samples.push_back(s);}
    if(samples.empty())return out;
    std::set<int> identities;for(const auto& s:samples)identities.insert(s.item);
    if(identities.size()!=1)return out;
    if(snapshots){
        std::vector<RangeSample> exact,recent;
        for(const auto& s:samples)if(s.quality==quality)exact.push_back(s);
        if(exact.size()>=2)samples=std::move(exact);
        for(const auto& s:samples)if(fresh(s.at,now,7ll*86400))recent.push_back(s);
        if(recent.size()>=3)samples=std::move(recent);
    }
    std::sort(samples.begin(),samples.end(),[](const auto& a,const auto& b){return a.price<b.price;});
    double total=0;out.historyOnly=true;int exactQuality=quality;
    for(auto& s:samples){
        // Recent observations contribute most; closed/removed ads remain a
        // useful price reference without claiming a verified sale.
        if(snapshots)s.weight=std::pow(.5,double(std::max(0ll,now-s.at))/(7*86400))*(s.historical?.5:1);
        total+=s.weight;out.historyOnly=out.historyOnly&&s.historical;
        out.reported=std::max(out.reported,s.at);if(s.quality!=quality)exactQuality=0;
    }
    auto percentile=[&](double q){double at=0;for(const auto& s:samples){at+=s.weight;if(at>=q*total)return s.price;}return samples.back().price;};
    out.known=true;out.price=percentile(.5);out.listings=snapshots?(double)samples.size():total;
    out.low=samples.size()<5?samples.front().price:percentile(.2);
    out.high=samples.size()<5?samples.back().price:percentile(.8);
    out.limited=out.listings<3||out.historyOnly||now-out.reported>7ll*86400;
    static const int lo[]={0,1,500,600,700,800,900,950},hi[]={0,499,599,699,799,899,949,1000};
    out.qualityMin=exactQuality?quality:lo[tier];out.qualityMax=exactQuality?quality:hi[tier];
    return out;
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
            if (part.ore.empty()) return out;
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
            const auto quote=marketRange(name,part.quality,"scu",now);
            if(!quote.known)continue;
            const double value=volume*quote.price;
            out.player+=value;priced+=volume;out.playerLimited=out.playerLimited||quote.limited;
            out.playerHistoryOnly=out.playerParts.empty()?quote.historyOnly:(out.playerHistoryOnly&&quote.historyOnly);
            out.playerLow+=volume*quote.low;out.playerHigh+=volume*quote.high;
            out.playerParts.push_back({part.ore,part.quality,volume,quote.price,value,quote.listings,quote.low,quote.high});
            out.playerReported=out.playerReported?std::min(out.playerReported,quote.reported):quote.reported;
        }
        out.playerCoverage=all>0?priced/all:0;
    }
    return out;
}
}
