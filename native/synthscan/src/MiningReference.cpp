#include "MiningReference.h"
#include "MiningHardware.h"
#include "AppPaths.h"
#include "SynthJson.h"
#include <array>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <set>

namespace SCMiner {
namespace {
using namespace SynthScan;
bool numeric(const Json& row,const char* key,float& destination,float low=-10000,float high=10000){
    auto value=row.find(key);if(!value||value->kind!=Json::Kind::Number||!std::isfinite(value->number)||value->number<low||value->number>high)return false;
    destination=float(value->number);return true;
}
bool apply(const Json& value){
    const auto& lasers=field(value,"lasers").items;const auto& modules=field(value,"modules").items;const auto& gadgets=field(value,"gadgets").items;
    if(lasers.size()!=MINING_LASER_COUNT||modules.size()!=MINING_MODULE_COUNT||gadgets.size()!=MINING_GADGET_COUNT)return false;
    std::array<MiningLaser,MINING_LASER_COUNT> nextLasers;std::copy(std::begin(MINING_LASERS),std::end(MINING_LASERS),nextLasers.begin());
    std::array<MiningModule,MINING_MODULE_COUNT> nextModules;std::copy(std::begin(MINING_MODULES),std::end(MINING_MODULES),nextModules.begin());
    std::array<MiningGadget,MINING_GADGET_COUNT> nextGadgets;std::copy(std::begin(MINING_GADGETS),std::end(MINING_GADGETS),nextGadgets.begin());
    std::set<std::string> seen;
    for(const auto& row:lasers){
        auto id=row.textOr("id");if(!seen.insert(id).second)return false;
        auto found=std::find_if(nextLasers.begin(),nextLasers.end(),[&](const MiningLaser& item){return id==item.id;});if(found==nextLasers.end())return false;
        auto& item=*found;float slots=0;
        if(!numeric(row,"fracture",item.fracture,0,1e8f)||!numeric(row,"extraction",item.extraction,0,1e8f)||!numeric(row,"fullRange",item.fullRange,0,1e6f)||!numeric(row,"zeroRange",item.zeroRange,0,1e6f)||
           !numeric(row,"window",item.window)||!numeric(row,"rate",item.rate)||!numeric(row,"resistance",item.resistance)||!numeric(row,"instability",item.instability)||!numeric(row,"filter",item.filter)||
           !numeric(row,"throttleMin",item.throttleMin,0,1)||!numeric(row,"slots",slots,0,3)||slots!=std::floor(slots)||item.zeroRange<=item.fullRange)return false;
        item.slots=int8_t(slots);
    }
    seen.clear();
    for(const auto& row:modules){
        auto id=row.textOr("id");if(!seen.insert(id).second)return false;
        auto found=std::find_if(nextModules.begin(),nextModules.end(),[&](const MiningModule& item){return id==item.id;});if(found==nextModules.end())return false;
        auto& item=*found;
        if(!numeric(row,"power",item.power,0,100)||!numeric(row,"window",item.window)||!numeric(row,"rate",item.rate)||!numeric(row,"resistance",item.resistance)||!numeric(row,"instability",item.instability)||
           !numeric(row,"filter",item.filter)||!numeric(row,"shatter",item.shatter)||!numeric(row,"danger",item.danger)||!numeric(row,"extraction",item.extraction))return false;
    }
    seen.clear();
    for(const auto& row:gadgets){
        auto id=row.textOr("id");if(!seen.insert(id).second)return false;
        auto found=std::find_if(nextGadgets.begin(),nextGadgets.end(),[&](const MiningGadget& item){return id==item.id;});if(found==nextGadgets.end())return false;
        auto& item=*found;
        if(!numeric(row,"instability",item.instability)||!numeric(row,"window",item.window)||!numeric(row,"rate",item.rate)||!numeric(row,"resistance",item.resistance)||!numeric(row,"cluster",item.cluster))return false;
    }
    std::copy(nextLasers.begin(),nextLasers.end(),std::begin(MINING_LASERS));std::copy(nextModules.begin(),nextModules.end(),std::begin(MINING_MODULES));std::copy(nextGadgets.begin(),nextGadgets.end(),std::begin(MINING_GADGETS));
    return true;
}
}
void refreshMiningReference(const std::filesystem::path& game){
    using namespace SynthScan;
    static auto checked=std::chrono::steady_clock::time_point{};auto now=std::chrono::steady_clock::now();
    if(now-checked<std::chrono::seconds(2))return;checked=now;
    static std::string appliedRevision,appliedBuild,lastStatus;
    auto value=read(AppPaths::data()/"mining_reference.json");auto build=field(read(game/"build_manifest.id"),"Data").textOr("BuildId");
    std::string status="bundled",detail="Using bundled mining hardware; waiting for a verified reference import.";
    if(!value.textOr("revision").empty()){
        if(build.empty()||build!=value.textOr("build_id")){status="version mismatch";detail="Imported hardware does not match the installed game build. It was not applied.";}
        else if(value.numberOr("schema")!=1){status="unsupported";detail="Reference schema is unsupported; retaining the last working hardware.";}
        else if(value.textOr("revision")==appliedRevision&&build==appliedBuild){status="applied";detail="SCMDB "+value.textOr("version")+" · numeric hardware generation is active.";}
        else if(apply(value)){appliedRevision=value.textOr("revision");appliedBuild=build;status="applied";detail="SCMDB "+value.textOr("version")+" · numeric hardware generation is active.";}
        else{status="rejected";detail="Reference validation failed; retaining the last working hardware.";}
    }
    std::string key=status+detail+appliedRevision;
    if(key!=lastStatus){
        lastStatus=key;write(AppPaths::data()/"mining_reference_status.json",obj({{"status",str(status)},{"detail",str(detail)},{"revision",str(appliedRevision)},{"build_id",str(appliedBuild)},{"owner_pid",num(GetCurrentProcessId())}}));
    }
}
bool miningReferenceSelfTest(){
    using namespace SynthScan;
    std::array<MiningLaser,MINING_LASER_COUNT> original;std::copy(std::begin(MINING_LASERS),std::end(MINING_LASERS),original.begin());
    auto value=obj();auto lasers=arr(),modules=arr(),gadgets=arr();
    for(const auto& item:MINING_LASERS)lasers.items.push_back(obj({{"id",str(item.id)},{"fracture",num(item.fracture+1)},{"extraction",num(item.extraction)},{"fullRange",num(item.fullRange)},{"zeroRange",num(item.zeroRange)},
        {"window",num(item.window)},{"rate",num(item.rate)},{"resistance",num(item.resistance)},{"instability",num(item.instability)},{"filter",num(item.filter)},{"slots",num(item.slots)},{"throttleMin",num(item.throttleMin)}}));
    for(const auto& item:MINING_MODULES)modules.items.push_back(obj({{"id",str(item.id)},{"power",num(item.power)},{"window",num(item.window)},{"rate",num(item.rate)},{"resistance",num(item.resistance)},
        {"instability",num(item.instability)},{"filter",num(item.filter)},{"shatter",num(item.shatter)},{"danger",num(item.danger)},{"extraction",num(item.extraction)}}));
    for(const auto& item:MINING_GADGETS)gadgets.items.push_back(obj({{"id",str(item.id)},{"instability",num(item.instability)},{"window",num(item.window)},{"rate",num(item.rate)},{"resistance",num(item.resistance)},{"cluster",num(item.cluster)}}));
    value=obj({{"lasers",lasers},{"modules",modules},{"gadgets",gadgets}});const MiningLaser* held=&MINING_LASERS[0];
    bool valid=apply(value)&&held==&MINING_LASERS[0]&&held->fracture==original[0].fracture+1;
    auto broken=value;broken.members[1].second.items.clear();valid=valid&&!apply(broken)&&held->fracture==original[0].fracture+1;
    std::copy(original.begin(),original.end(),std::begin(MINING_LASERS));return valid;
}
}
