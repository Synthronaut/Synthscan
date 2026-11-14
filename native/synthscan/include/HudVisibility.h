#pragma once
namespace HudVisibility {
inline bool shouldShow(bool enabled,bool expanded,bool gameVisible,bool preview){return enabled&&expanded&&(gameVisible||preview);}
inline bool miningOcrAllowed(bool activityMode,bool windowVisible,bool overlayMode,bool hudEnabled,bool expanded,bool rootIconic){
    if(activityMode||!windowVisible||rootIconic)return false;
    return !overlayMode||(hudEnabled&&expanded);
}
}
