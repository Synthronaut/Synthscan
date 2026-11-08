#pragma once
namespace HudVisibility {
inline bool shouldShow(bool enabled,bool expanded,bool gameVisible,bool preview){return enabled&&expanded&&(gameVisible||preview);}
}
