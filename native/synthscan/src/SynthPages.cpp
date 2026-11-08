#include "SynthPages.h"
#include <commctrl.h>
#include <map>
#include <string>
#include <algorithm>
#include <windowsx.h>
#include <uxtheme.h>

namespace SynthPages {
namespace {
struct Page {LONG_PTR style=0,ex=0;HWND parent=nullptr;int width=0,height=0,crop=0,x=0,y=0;bool captured=false;};
HWND mainWindow=nullptr,container=nullptr,active=nullptr;HHOOK hook=nullptr;
std::map<HWND,Page> pages;bool arranging=false;unsigned revision=1;
constexpr UINT READY=WM_APP+417;
void arrange(){
    if(!container||!active||!IsWindow(active)||arranging)return;
    auto& page=pages[active];RECT r{};GetClientRect(container,&r);
    int width=std::max(int(r.right),page.width),height=std::max(int(r.bottom)+page.crop,page.height);
    page.x=std::clamp(page.x,0,std::max(0,width-int(r.right)));page.y=std::clamp(page.y,0,std::max(0,height-page.crop-int(r.bottom)));
    SCROLLINFO si{sizeof(si),SIF_RANGE|SIF_PAGE|SIF_POS};si.nMin=0;si.nMax=width-1;si.nPage=r.right;si.nPos=page.x;SetScrollInfo(container,SB_HORZ,&si,TRUE);
    si.nMax=height-page.crop-1;si.nPage=r.bottom;si.nPos=page.y;SetScrollInfo(container,SB_VERT,&si,TRUE);
    arranging=true;SetWindowPos(active,nullptr,-page.x,-page.crop-page.y,width,height,SWP_NOZORDER|SWP_NOACTIVATE);arranging=false;
}
LRESULT CALLBACK childProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp,UINT_PTR,DWORD_PTR){
    if(msg==WM_WINDOWPOSCHANGING&&contains(hwnd)&&!arranging){
        auto position=reinterpret_cast<WINDOWPOS*>(lp);auto& p=pages[hwnd];
        position->x=-p.x;position->y=-p.crop-p.y;position->flags|=SWP_NOACTIVATE|SWP_NOZORDER;
    }
    if(msg==WM_NCDESTROY){RemoveWindowSubclass(hwnd,childProc,1);pages.erase(hwnd);if(active==hwnd)active=nullptr;}
    return DefSubclassProc(hwnd,msg,wp,lp);
}
LRESULT CALLBACK hostProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
    if(msg==WM_SIZE){arrange();return 0;}
    if(msg==READY){auto page=reinterpret_cast<HWND>(wp);if(IsWindow(page)){if(unsigned(lp)==revision)mount(page);else ShowWindow(page,SW_HIDE);}return 0;}
    if((msg==WM_VSCROLL||msg==WM_HSCROLL||msg==WM_MOUSEWHEEL)&&active){
        auto& p=pages[active];bool vertical=msg!=WM_HSCROLL;int bar=vertical?SB_VERT:SB_HORZ;
        SCROLLINFO si{sizeof(si),SIF_ALL};GetScrollInfo(hwnd,bar,&si);int at=si.nPos;
        if(msg==WM_MOUSEWHEEL)at-=GET_WHEEL_DELTA_WPARAM(wp)/WHEEL_DELTA*70;
        else switch(LOWORD(wp)){case SB_LINEUP:at-=30;break;case SB_LINEDOWN:at+=30;break;case SB_PAGEUP:at-=si.nPage;break;case SB_PAGEDOWN:at+=si.nPage;break;case SB_THUMBTRACK:at=si.nTrackPos;break;}
        (vertical?p.y:p.x)=std::clamp(at,0,std::max(0,si.nMax-int(si.nPage)+1));arrange();return 0;
    }
    if(msg==WM_ERASEBKGND){RECT r{};GetClientRect(hwnd,&r);HBRUSH b=CreateSolidBrush(RGB(15,16,19));FillRect((HDC)wp,&r,b);DeleteObject(b);return 1;}
    return DefWindowProcW(hwnd,msg,wp,lp);
}
LRESULT CALLBACK createHook(int code,WPARAM wp,LPARAM lp){
    if(code==HCBT_CREATEWND&&container&&IsWindowVisible(mainWindow)){
        auto create=reinterpret_cast<CBT_CREATEWNDW*>(lp)->lpcs;
        if(!(create->style&WS_CHILD)&&!IS_INTRESOURCE(create->lpszClass)){
            std::wstring cls=create->lpszClass;
            bool tool=(cls.rfind(L"SCMiner",0)==0||cls.rfind(L"SynthScan",0)==0)&&
                cls!=L"SCMinerGUI"&&cls!=L"SynthScanHome"&&cls!=L"SynthScanPageHost"&&cls!=L"SynthScanHost"&&
                cls.find(L"Suggest")==std::wstring::npos&&cls.find(L"Popup")==std::wstring::npos&&cls.find(L"Overlay")==std::wstring::npos;
            if(tool){
                Page p;p.style=create->style;p.ex=create->dwExStyle;p.parent=create->hwndParent;p.width=std::max(100,create->cx);p.height=std::max(100,create->cy);p.captured=true;
                pages[reinterpret_cast<HWND>(wp)]=p;
                create->style=(create->style&~(WS_POPUP|WS_CAPTION|WS_THICKFRAME|WS_SYSMENU|WS_MINIMIZEBOX|WS_MAXIMIZEBOX))|WS_CHILD|WS_CLIPCHILDREN;
                create->dwExStyle&=~(WS_EX_APPWINDOW|WS_EX_TOOLWINDOW|WS_EX_TOPMOST|WS_EX_NOACTIVATE);
                create->hwndParent=container;create->x=create->y=0;
                PostMessageW(container,READY,wp,revision);
            }
        }
    }
    return CallNextHookEx(hook,code,wp,lp);
}
}
void initialize(HWND main){
    mainWindow=main;if(container)return;
    WNDCLASSW cls{};cls.lpfnWndProc=hostProc;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanPageHost";cls.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&cls);
    container=CreateWindowExW(WS_EX_CONTROLPARENT,cls.lpszClassName,L"",WS_CHILD|WS_CLIPCHILDREN|WS_VSCROLL|WS_HSCROLL,0,0,10,10,main,nullptr,cls.hInstance,nullptr);
    SetWindowTheme(container,L"DarkMode_Explorer",nullptr);
    hook=SetWindowsHookExW(WH_CBT,createHook,nullptr,GetCurrentThreadId());
}
void place(int x,int y,int width,int height,bool visible){if(container){MoveWindow(container,x,y,width,height,TRUE);ShowWindow(container,visible?SW_SHOW:SW_HIDE);arrange();}}
void mount(HWND page,int cropTop){
    if(!container||!page||!IsWindow(page))return;
    if(active&&active!=page)ShowWindow(active,SW_HIDE);
    auto found=pages.find(page);
    if(found==pages.end()){
        RECT r{};GetClientRect(page,&r);Page value;value.style=GetWindowLongPtrW(page,GWL_STYLE);value.ex=GetWindowLongPtrW(page,GWL_EXSTYLE);value.parent=GetParent(page);value.width=r.right;value.height=r.bottom;
        pages[page]=value;
    }
    auto& value=pages[page];if(cropTop)value.crop=cropTop;
    ShowWindow(page,SW_HIDE);SetWindowLongPtrW(page,GWL_STYLE,(GetWindowLongPtrW(page,GWL_STYLE)&~(WS_POPUP|WS_CAPTION|WS_THICKFRAME|WS_SYSMENU|WS_MINIMIZEBOX|WS_MAXIMIZEBOX))|WS_CHILD|WS_CLIPCHILDREN);
    SetWindowLongPtrW(page,GWL_EXSTYLE,(GetWindowLongPtrW(page,GWL_EXSTYLE)&~(WS_EX_APPWINDOW|WS_EX_TOOLWINDOW|WS_EX_TOPMOST|WS_EX_NOACTIVATE))|WS_EX_CONTROLPARENT);
    SetWindowDisplayAffinity(page,WDA_NONE);SetParent(page,container);SetWindowSubclass(page,childProc,1,0);active=page;arrange();ShowWindow(page,SW_SHOW);
}
void release(HWND page){
    auto found=pages.find(page);if(found==pages.end())return;auto value=found->second;
    ShowWindow(page,SW_HIDE);RemoveWindowSubclass(page,childProc,1);SetParent(page,value.parent);
    SetWindowLongPtrW(page,GWL_STYLE,value.style);SetWindowLongPtrW(page,GWL_EXSTYLE,value.ex);
    SetWindowPos(page,nullptr,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_FRAMECHANGED);
    pages.erase(found);if(active==page)active=nullptr;
}
void hide(){++revision;if(active)ShowWindow(active,SW_HIDE);active=nullptr;}
void close(){if(hook)UnhookWindowsHookEx(hook);hook=nullptr;while(!pages.empty())release(pages.begin()->first);if(container)DestroyWindow(container);container=nullptr;}
bool contains(HWND page){return container&&GetParent(page)==container;}
HWND host(){return container;}HWND current(){return active;}
unsigned generation(){return revision;}
}
