// Settled native readings are diary encounters, never inferred cargo or sales.
#include "SynthScanShell.h"
#include "SynthJson.h"
#include "ScanPanel.h"
#include "RockContents.h"
#include "AppPaths.h"
#include <chrono>
namespace SynthScan {
namespace {
std::string encounter,material,lastSystem,lastPlace,lastShip;
double anchor=0,lastSeen=0,lastWritten=0;
Json parts;
bool active=false;
unsigned sequence=0;
double settingsAt=0;bool enabled=true;
}
void endMiningRock(){active=false;}
void observeMiningRock(const SCMiner::RockStats& rock,const SCMiner::RockContents* contents,
                       const std::string& system,const std::string& place,const std::string& ship,int version){
    if(activityMode()){active=false;return;}
    if(!std::isfinite(rock.mass)||rock.mass<=0)return;
    const double now=std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    if(now-settingsAt>2){enabled=flag(read(SCMiner::AppPaths::data()/L"diary_settings.json"),"auto_log",true);settingsAt=now;}
    if(!enabled){active=false;return;}
    const bool changed=!active||now-lastSeen>30||std::fabs(rock.mass-anchor)>std::max(1.0,anchor*.01)||
        (!material.empty()&&!rock.ore.empty()&&material!=rock.ore)||
        (!lastSystem.empty()&&!system.empty()&&system!=lastSystem)||
        (!lastPlace.empty()&&!place.empty()&&place!=lastPlace)||(!lastShip.empty()&&!ship.empty()&&ship!=lastShip);
    if(changed){encounter="rock-"+std::to_string(static_cast<long long>(now*1000))+"-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(++sequence);anchor=rock.mass;parts=arr();lastWritten=0;material.clear();}
    active=true;lastSeen=now;lastSystem=system;lastPlace=place;lastShip=ship;if(!rock.ore.empty())material=rock.ore;
    bool composition=contents&&contents->whole;
    if(composition){parts=arr();for(const auto& p:contents->parts)parts.items.push_back(obj({{"material",str(p.ore)},{"percent",num(p.percent)},{"quality",num(p.quality)},{"inert",boolean(p.inert)}}));}
    if(now-lastWritten<2&&!composition)return;
    std::string patch=version>0?std::to_string(version/10000)+"."+std::to_string(version/100%100)+"."+std::to_string(version%100):"";
    Json value=obj({{"id",str(encounter)},{"at",num(now)},{"settled",boolean(true)},{"mass_kg",num(rock.mass)},
        {"material",str(material)},{"system",str(system)},{"location",str(place)},{"ship",str(ship)},{"patch",str(patch)},
        {"composition_complete",boolean(!parts.items.empty())},{"parts",parts}});
    std::error_code error;auto folder=SCMiner::AppPaths::data()/L"diary_inbox";std::filesystem::create_directories(folder,error);
    if(!error&&write(folder/std::filesystem::u8path(encounter+".json"),value))lastWritten=now;
}
}
