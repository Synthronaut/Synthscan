#pragma once
#include "MiningLocations.h"
#include "MiningHardware.h"
#include <map>
#include <string>
#include <vector>
#include <algorithm>
namespace SCMiner {
struct MiningTripStop {std::string location,system;std::vector<std::string> materials;double weight=0;};
inline std::vector<MiningTripStop> miningTripStops(const std::vector<std::string>& targets,const std::string& system,
    const std::vector<OreLocation>& locations=ORE_LOCATIONS){
    std::map<std::string,MiningTripStop> stops;
    for(const auto& row:locations){
        if(row.family!=MiningFamily::Ship||(system!="ALL"&&system!=row.system)||row.chance<=0)continue;
        for(const auto& target:targets){
            bool found=target==row.mineral;
            if(!found)for(int i=0;i<ROCK_PART_COUNT;++i){const auto& part=ROCK_PARTS[i];if(row.mineral==std::string(part.rock)&&target==part.ore&&part.most>0){found=true;break;}}
            if(!found)continue;
            auto& stop=stops[std::string(row.system)+"/"+row.location];stop.location=row.location;stop.system=row.system;
            if(std::find(stop.materials.begin(),stop.materials.end(),target)==stop.materials.end())stop.materials.push_back(target);
            stop.weight=std::max(stop.weight,row.chance);
        }
    }
    std::vector<MiningTripStop> out;for(auto& pair:stops)out.push_back(std::move(pair.second));
    std::sort(out.begin(),out.end(),[](const auto& a,const auto& b){if(a.materials.size()!=b.materials.size())return a.materials.size()>b.materials.size();if(a.weight!=b.weight)return a.weight>b.weight;return a.system==b.system?a.location<b.location:a.system<b.system;});
    return out;
}
}
