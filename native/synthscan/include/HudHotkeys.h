#pragma once
#include "SynthJson.h"
#include <cstdint>

namespace HudHotkeys {
using namespace SynthScan;
struct Binding {unsigned key=0,modifiers=0;};
struct Config {bool enabled=false,gameOnly=true;Binding toggle{VK_F23,0},cycle{VK_F24,0};};
inline bool same(Binding a,Binding b){return a.key==b.key&&a.modifiers==b.modifiers;}
inline bool valid(Binding b){
    if(b.modifiers&~unsigned(MOD_CONTROL|MOD_ALT|MOD_SHIFT))return false;
    if(!b.key)return !b.modifiers;
    if(b.key==VK_F12||b.key>254||b.key==VK_LWIN||b.key==VK_RWIN)return false;
    if(b.key==VK_CONTROL||b.key==VK_SHIFT||b.key==VK_MENU||b.key==VK_LCONTROL||b.key==VK_RCONTROL||b.key==VK_LSHIFT||b.key==VK_RSHIFT||b.key==VK_LMENU||b.key==VK_RMENU)return false;
    return (b.key>=VK_F1&&b.key<=VK_F24)||(b.modifiers&(MOD_CONTROL|MOD_ALT));
}
inline std::string error(const Config& c){
    if(!valid(c.toggle)||!valid(c.cycle))return "Use F1–F24 (except reserved F12), or a key with Ctrl/Alt.";
    if(c.enabled&&!c.toggle.key&&!c.cycle.key)return "Assign at least one shortcut before enabling.";
    if(c.toggle.key&&same(c.toggle,c.cycle))return "HUD toggle and tab cycle need different shortcuts.";
    return "";
}
inline Json encodeConfig(const Config& c){return obj({{"schema",num(1)},{"enabled",SynthScan::boolean(c.enabled)},{"game_only",SynthScan::boolean(c.gameOnly)},{"toggle",obj({{"key",num(c.toggle.key)},{"modifiers",num(c.toggle.modifiers)}})},{"cycle",obj({{"key",num(c.cycle.key)},{"modifiers",num(c.cycle.modifiers)}})}});}
inline Config decodeConfig(const Json& value){
    Config c;if(value.numberOr("schema")!=1)return c;
    auto binding=[](const Json& value){auto k=value.numberOr("key"),m=value.numberOr("modifiers");if(k<0||k>254||k!=int(k)||m<0||m>7||m!=int(m))return Binding{255,0};return Binding{unsigned(k),unsigned(m)};};
    c.enabled=flag(value,"enabled");c.gameOnly=flag(value,"game_only",true);c.toggle=binding(field(value,"toggle"));c.cycle=binding(field(value,"cycle"));if(!error(c).empty())return Config{};return c;
}
inline std::wstring label(Binding b){
    if(!b.key)return L"Unassigned";std::wstring out;
    if(b.modifiers&MOD_CONTROL)out+=L"Ctrl + ";if(b.modifiers&MOD_ALT)out+=L"Alt + ";if(b.modifiers&MOD_SHIFT)out+=L"Shift + ";
    if(b.key>=VK_F1&&b.key<=VK_F24)return out+L"F"+std::to_wstring(b.key-VK_F1+1);
    wchar_t name[128]{};auto scan=MapVirtualKeyW(b.key,MAPVK_VK_TO_VSC);if(b.key==VK_INSERT||b.key==VK_DELETE||b.key==VK_HOME||b.key==VK_END||b.key==VK_PRIOR||b.key==VK_NEXT||b.key==VK_LEFT||b.key==VK_RIGHT||b.key==VK_UP||b.key==VK_DOWN)scan|=0x100;
    if(GetKeyNameTextW(LONG(scan<<16),name,128))return out+name;return out+L"Key "+std::to_wstring(b.key);
}
struct Gate {
    std::uint64_t last[2]{},suppressedUntil=0;bool seen[2]{};
    bool accept(int action,std::uint64_t now,bool enabled,bool registered,bool scope,bool editing,Binding binding,unsigned key,unsigned modifiers){
        if(action<0||action>1||!enabled||!registered||!scope||editing||now<suppressedUntil||!binding.key||key!=binding.key||(modifiers&7)!=binding.modifiers)return false;
        if(seen[action]&&now-last[action]<140)return false;seen[action]=true;last[action]=now;return true;
    }
};
inline int nextTab(int current){return current>=0&&current<4?current+1:0;}
}
