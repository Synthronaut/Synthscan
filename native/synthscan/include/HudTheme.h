#pragma once
#include <windows.h>
#include <gdiplus.h>

namespace HudTheme {
inline const Gdiplus::Color Top(255,23,27,35),Bottom(255,12,16,22);
inline const Gdiplus::Color Text(255,240,237,229),Muted(255,169,161,142),Faint(255,136,149,164);
inline const Gdiplus::Color Border(90,102,113,127);
inline constexpr BYTE Opacity=235;
inline constexpr int Width=480,MainHeight=360,HangarWidth=430;
inline Gdiplus::Color modeAccent(int mode){
    switch(mode){
        case 1:return Gdiplus::Color(255,239,108,116); // Piracy: red
        case 2:return Gdiplus::Color(255,103,213,154); // Missions: green
        case 3:return Gdiplus::Color(255,156,117,236); // Hangars: royal purple
        case 4:return Gdiplus::Color(255,229,227,220); // Finder: gray off-white
        default:return Gdiplus::Color(255,98,204,255); // Mining: existing cyan
    }
}
inline void backdrop(Gdiplus::Graphics& g,Gdiplus::RectF rect){
    Gdiplus::LinearGradientBrush fill(rect,Top,Bottom,Gdiplus::LinearGradientModeForwardDiagonal);
    g.FillRectangle(&fill,rect);
}
}
