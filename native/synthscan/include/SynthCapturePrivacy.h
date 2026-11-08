#pragma once
#include "AppPaths.h"
#include "SynthJson.h"
#include <mutex>
#include <chrono>

namespace CapturePrivacy {
struct Policy {bool paused=false,pauseUnfocused=true;};
inline std::mutex policyMutex;
inline Policy cached;
inline ULONGLONG checked=0;
inline std::mutex activityMutex;
inline ULONGLONG lastFrame=0;inline double captureMs=0;inline std::string captureNote;
inline void observed(bool frame,double ms,const std::string& note){std::lock_guard<std::mutex> lock(activityMutex);if(frame){lastFrame=GetTickCount64();captureMs=ms;}captureNote=note;}
inline Policy policy(){
    std::lock_guard<std::mutex> lock(policyMutex);auto now=GetTickCount64();
    if(!checked||now-checked>=200){
        auto file=SCMiner::AppPaths::data()/L"capture_privacy.json";
        auto j=SynthScan::read(file,4096);
        // A malformed existing policy must not silently resume capture.
        std::error_code ec;bool exists=std::filesystem::exists(file,ec);
        bool invalid=bool(ec)||(exists&&(j.kind!=SynthScan::Json::Kind::Object||j.numberOr("schema")!=1));
        for(const char* key:{"paused","pause_unfocused"})if(auto value=j.find(key);value&&value->kind!=SynthScan::Json::Kind::Bool)invalid=true;
        cached={invalid||SynthScan::flag(j,"paused"),SynthScan::flag(j,"pause_unfocused",true)};checked=now;
    }
    return cached;
}
inline void set(Policy value){
    auto j=SynthScan::read(SCMiner::AppPaths::data()/L"capture_privacy.json",4096);
    if(j.kind!=SynthScan::Json::Kind::Object)j=SynthScan::obj();
    auto put=[&](const char* key,SynthScan::Json field){for(auto& pair:j.members)if(pair.first==key){pair.second=field;return;}j.members.push_back({key,field});};
    put("schema",SynthScan::num(1));put("paused",SynthScan::boolean(value.paused));put("pause_unfocused",SynthScan::boolean(value.pauseUnfocused));
    if(SynthScan::write(SCMiner::AppPaths::data()/L"capture_privacy.json",j)){
        std::lock_guard<std::mutex> lock(policyMutex);cached=value;checked=GetTickCount64();
    }
}
inline bool focused(HWND game){
    HWND foreground=GetForegroundWindow();if(foreground==game)return true;
    DWORD pid=0;GetWindowThreadProcessId(foreground,&pid);return pid==GetCurrentProcessId();
}
inline SynthScan::Json snapshot(){
    auto p=policy();auto helper=SynthScan::read(SCMiner::AppPaths::data()/L"capture_activity.json",1024);
    double now=std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();double helperAge=(now-helper.numberOr("at"))*1000;
    if(helper.textOr("source")!="verified_game_window_wgc"||helperAge<0||helperAge>2000)helperAge=-1;
    std::lock_guard<std::mutex> lock(activityMutex);double age=lastFrame?double(GetTickCount64()-lastFrame):-1;
    if(helperAge>=0&&(age<0||helperAge<age))age=helperAge;
    return SynthScan::obj({{"paused",SynthScan::boolean(p.paused)},{"pause_unfocused",SynthScan::boolean(p.pauseUnfocused)},{"source",SynthScan::str("verified_game_window_wgc")},{"automatic_images",SynthScan::boolean(false)},{"frame_age_ms",SynthScan::num(age)},{"capture_ms",SynthScan::num(captureMs)},{"note",SynthScan::str(captureNote)}});
}
}
