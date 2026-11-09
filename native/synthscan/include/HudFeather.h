#pragma once
#include "HudTheme.h"
#ifdef _WIN32
#include <algorithm>
#include <cmath>

// A passive, per-pixel-alpha extension around the normal HUD. Keeping the
// center transparent preserves native child controls, text and click handling.
namespace HudFeather {
inline HWND window=nullptr;
inline int cachedWidth=0,cachedHeight=0,cachedPad=0;
inline RECT placed{};
inline bool syncing=false;
inline void destroy(){if(window&&IsWindow(window))DestroyWindow(window);window=nullptr;cachedWidth=cachedHeight=cachedPad=0;placed={};}
inline LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_NCHITTEST)return HTTRANSPARENT;
    if(message==WM_MOUSEACTIVATE)return MA_NOACTIVATE;
    return DefWindowProcW(hwnd,message,wp,lp);
}
__declspec(noinline) inline void sync(HWND owner,bool enabled,float scale){
    // Moving an owned layered window can synchronously change its owner's
    // z-order and re-enter WM_WINDOWPOSCHANGED. Never lay it out recursively.
    if(syncing)return;
    syncing=true;struct ResetSync {~ResetSync(){syncing=false;}} resetSync;
    if(!owner||!enabled||!IsWindowVisible(owner)||IsIconic(owner)||(GetWindowLongPtrW(owner,GWL_STYLE)&WS_CHILD)){
        if(window)ShowWindow(window,SW_HIDE);return;
    }
    RECT rect{};if(!GetWindowRect(owner,&rect))return;
    int pad=std::clamp(int(std::lround(12*scale)),6,28),cw=rect.right-rect.left,ch=rect.bottom-rect.top,w=cw+pad*2,h=ch+pad*2;
    if(cw<=0||ch<=0||w>8192||h>8192)return;
    if(!window){
        WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpfnWndProc=procedure;cls.lpszClassName=L"SCMinerHudFeather";RegisterClassW(&cls);
        window=CreateWindowExW(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE,cls.lpszClassName,L"SynthScan HUD feather",WS_POPUP,0,0,w,h,owner,nullptr,cls.hInstance,nullptr);
        if(!window)return;
    }
    if(w!=cachedWidth||h!=cachedHeight||pad!=cachedPad){
        BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=w;info.bmiHeader.biHeight=-h;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
        void* pixels=nullptr;HDC screen=GetDC(nullptr),memory=CreateCompatibleDC(screen);HBITMAP bitmap=CreateDIBSection(screen,&info,DIB_RGB_COLORS,&pixels,nullptr,0);
        if(bitmap&&pixels){
            auto old=SelectObject(memory,bitmap);auto out=static_cast<unsigned char*>(pixels);
            for(int y=0;y<h;y++)for(int x=0;x<w;x++,out+=4){
                out[0]=out[1]=out[2]=out[3]=0;
                if(x>=pad&&x<pad+cw&&y>=pad&&y<pad+ch)continue;
                float dx=std::max({float(pad-x)-.5f,0.f,float(x-pad-cw)+.5f}),dy=std::max({float(pad-y)-.5f,0.f,float(y-pad-ch)+.5f});
                float t=std::clamp(1-std::sqrt(dx*dx+dy*dy)/pad,0.f,1.f);int alpha=int(HudTheme::Opacity*t*t*(3-2*t));
                float blend=(std::clamp(float(x-pad)/cw,0.f,1.f)+std::clamp(float(y-pad)/ch,0.f,1.f))*.5f;
                out[0]=BYTE((HudTheme::Top.GetB()*(1-blend)+HudTheme::Bottom.GetB()*blend)*alpha/255);
                out[1]=BYTE((HudTheme::Top.GetG()*(1-blend)+HudTheme::Bottom.GetG()*blend)*alpha/255);
                out[2]=BYTE((HudTheme::Top.GetR()*(1-blend)+HudTheme::Bottom.GetR()*blend)*alpha/255);out[3]=BYTE(alpha);
            }
            POINT origin{0,0},destination{rect.left-pad,rect.top-pad};SIZE size{w,h};BLENDFUNCTION blend{AC_SRC_OVER,0,255,AC_SRC_ALPHA};
            if(UpdateLayeredWindow(window,screen,&destination,&size,memory,&origin,0,&blend,ULW_ALPHA)){cachedWidth=w;cachedHeight=h;cachedPad=pad;}
            SelectObject(memory,old);
        }
        if(bitmap)DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(nullptr,screen);
    }
    RECT outer{rect.left-pad,rect.top-pad,rect.right+pad,rect.bottom+pad};
    if(!IsWindowVisible(window)||!EqualRect(&outer,&placed)){
        placed=outer;
        SetWindowPos(window,HWND_TOPMOST,outer.left,outer.top,w,h,SWP_NOACTIVATE|SWP_NOOWNERZORDER|SWP_SHOWWINDOW);
    }
}
}
#else
namespace HudFeather {inline void destroy(){} inline void sync(HWND,bool,float){}}
#endif
