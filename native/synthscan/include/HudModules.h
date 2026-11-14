#pragma once
#include "SynthJson.h"
#include <vector>
namespace SynthScan::HudModules {
inline bool installed(const Json& release,const std::string& name,bool screenReading){
    if(name=="notes")return false;
    if(name.empty())return true;
    if(name=="mining_recognition"&&!screenReading)return false;
    const auto* modules=release.find("modules");
    if(!modules)return true;
    if(modules->kind!=Json::Kind::Array)return false;
    for(const auto& row:modules->items)if(row.kind==Json::Kind::String&&row.text==name)return true;
    return false;
}
inline const char* featureForAction(const std::string& action){
    if(action=="blueprints")return "blueprints";
    if(action=="directory"||action=="buyer_alerts"||action=="hud_finder")return "item_finder";
    if(action=="people")return "people";
    if(action=="mission_log"||action=="hud_missions")return "missions";
    if(action=="servers")return "server_history";
    if(action=="planner"||action=="diary"||action=="refinery"||action=="bookmarks"||action=="dismiss_refinery")return "mining_tools";
    if(action=="executive_hangar"||action=="hud_hangars")return "hangars";
    if(action=="hud_piracy")return "piracy";
    if(action=="daylight")return "daylight";
    if(action=="acceptance")return "acceptance";
    if(action=="roulette"||action=="fate_roulette")return ""; // always available
    if(action=="hud_mining"||action=="mining")return "mining_recognition";
    if(action=="strings_settings"||action=="strings_details")return "synthstrings";
    return "";
}
inline bool actionAvailable(const Json& release,const std::string& action,bool screenReading){
    if(action=="notes")return false;
    return installed(release,featureForAction(action),screenReading)&&
        (std::string(featureForAction(action))!="mining_recognition"||installed(release,"mining_tools",screenReading));
}
inline const char* module(int mode){
    static const char* names[]={"mining_recognition","piracy","missions","hangars","item_finder"};
    return mode>=0&&mode<5?names[mode]:"";
}
inline bool available(const Json& release,int mode,bool screenReading){
    if(mode<0||mode>=5||(mode==0&&!screenReading))return false;
    const auto* modules=release.find("modules");
    if(!modules)return true; // Compatibility with existing Standard/Full packages.
    if(modules->kind!=Json::Kind::Array)return false;
    bool found=false,mining=false;
    for(const auto& row:modules->items){
        if(row.kind!=Json::Kind::String)continue;
        found|=row.text==module(mode);mining|=row.text=="mining_tools";
    }
    return found&&(mode!=0||mining);
}
inline std::vector<int> modes(const Json& release,bool screenReading){
    std::vector<int> result;for(int mode=0;mode<5;++mode)if(available(release,mode,screenReading))result.push_back(mode);return result;
}
inline int next(const std::vector<int>& modes,int current){
    if(modes.empty())return -1;
    for(size_t at=0;at<modes.size();++at)if(modes[at]==current)return modes[(at+1)%modes.size()];
    return modes.front();
}
inline bool workspaceAvailable(const Json& release,int tab,bool screenReading){
    static const char* actions[]={"directory","planner","servers","blueprints","settings","acceptance","hud_piracy"};
    if(tab==7)return !modes(release,screenReading).empty();
    return tab>=0&&tab<7&&actionAvailable(release,actions[tab],screenReading);
}
}
