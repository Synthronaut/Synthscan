#include "SynthHome.h"
#include "SynthJson.h"
#include "resource.h"
#include "SynthPages.h"
#include "SynthGlass.h"
#include "SynthPageHelp.h"
#include "NativeRedraw.h"
#include "HudModules.h"
#include "AppPaths.h"
#include <commctrl.h>
#include "SynthCapturePrivacy.h"
#include <gdiplus.h>
#include <dwmapi.h>
#include <algorithm>
#include <map>
#include <memory>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <windowsx.h>

namespace SynthHome {
namespace {
using namespace SynthScan;
HWND window=nullptr,owner=nullptr,helpPopup=nullptr;std::filesystem::path directory;
std::function<void(const std::string&)> action;
Json overview;std::string identity,lastAction;bool connected=false,previous=false,sessionChosen=false,helpHot=false,lockHot=false,navLocked=false,dragActive=false,suppressNextClick=false;
std::string activePage="home";
std::vector<std::string> pageHistory={"home"};
int pageHistoryIndex=0;
bool navigatingHistory=false;
float scale=1;
RECT helpRect{};
HWND dragButton=nullptr;
POINT dragStartScreen{};
const Gdiplus::Color BG(255,15,16,19),SIDE(255,19,21,25),CARD(255,24,26,30),BORDER(255,44,47,54),INK(255,238,239,241),MUTED(255,160,166,176),ACCENT(255,98,204,255);
struct Button {HWND hwnd;int id;std::wstring label;std::string action;bool navigation;};
std::vector<Button> buttons;
bool isDraggableNav(const Button& b){return b.navigation&&b.action!="home"&&b.action!="exit";}
float navStepLogical(float height){
    int navCount=int(std::count_if(buttons.begin(),buttons.end(),[](const auto& b){return b.navigation&&b.action!="exit";}));
    return std::min(39.f,std::max(24.f,(height-262.f)/std::max(1,navCount)));
}
void saveSidebarOrder(){
    if(directory.empty())return;
    Json order=arr();
    for(const auto& b:buttons)if(isDraggableNav(b))order.items.push_back(str(b.action));
    write(directory/L"sidebar_order.json",obj({{"order",order},{"locked",SynthScan::boolean(navLocked)}}));
}
void loadSidebarOrder(){
    if(directory.empty())return;
    Json saved=read(directory/L"sidebar_order.json");
    if(saved.kind!=Json::Kind::Object)return;
    navLocked=flag(saved,"locked",false);
    const auto& items=field(saved,"order").items;
    if(items.empty())return;
    std::vector<Button> homeBtns,dragBtns,tailBtns;
    for(const auto& b:buttons){
        if(b.navigation&&b.action=="home")homeBtns.push_back(b);
        else if(isDraggableNav(b))dragBtns.push_back(b);
        else tailBtns.push_back(b);
    }
    std::vector<Button> sorted;
    for(const auto& entry:items){
        if(entry.kind!=Json::Kind::String)continue;
        auto it=std::find_if(dragBtns.begin(),dragBtns.end(),[&](const auto& b){return b.action==entry.text;});
        if(it!=dragBtns.end()){sorted.push_back(*it);dragBtns.erase(it);}
    }
    for(const auto& rem:dragBtns)sorted.push_back(rem);
    buttons.clear();
    buttons.insert(buttons.end(),homeBtns.begin(),homeBtns.end());
    buttons.insert(buttons.end(),sorted.begin(),sorted.end());
    buttons.insert(buttons.end(),tailBtns.begin(),tailBtns.end());
}
bool available(const std::string& command){
    static const auto release=read(SCMiner::AppPaths::program().parent_path().parent_path()/L"release.json");
    return HudModules::actionAvailable(release,command,SynthEdition::screenReading);
}
void rounded(Gdiplus::Graphics& g,Gdiplus::RectF r,Gdiplus::Color color,float radius=10){
    radius*=scale;float d=radius*2;Gdiplus::GraphicsPath p;
    p.AddArc(r.X,r.Y,d,d,180,90);p.AddArc(r.GetRight()-d,r.Y,d,d,270,90);
    p.AddArc(r.GetRight()-d,r.GetBottom()-d,d,d,0,90);p.AddArc(r.X,r.GetBottom()-d,d,d,90,90);p.CloseFigure();
    Gdiplus::SolidBrush b(color);g.FillPath(&b,&p);
}
void words(Gdiplus::Graphics& g,const std::wstring& text,float x,float y,float w,float h,float size,Gdiplus::Color color,bool bold=false){
    Gdiplus::Font font(L"Segoe UI",size*scale,bold?Gdiplus::FontStyleBold:Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    Gdiplus::StringFormat format;format.SetTrimming(Gdiplus::StringTrimmingEllipsisWord);
    Gdiplus::SolidBrush brush(color);g.DrawString(text.c_str(),-1,&font,Gdiplus::RectF(x*scale,y*scale,w*scale,h*scale),&format,&brush);
}
std::wstring number(double n){std::wostringstream s;s<<std::fixed<<std::setprecision(0)<<n;return s.str();}
std::wstring clockLabel(double at){if(at<=0)return L"";std::time_t t=static_cast<std::time_t>(at);std::tm local{};localtime_s(&local,&t);wchar_t text[32]{};wcsftime(text,32,L"%H:%M",&local);return text;}
void publish(){
    if(!window)return;RECT r{};GetWindowRect(window,&r);
    write(directory/L"home_status.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"visible",SynthScan::boolean(IsWindowVisible(window)!=0)},
        {"last_action",str(lastAction)},{"previous_session",SynthScan::boolean(previous)},
        {"synthstrings",field(overview,"synthstrings")},
        {"active_page",str(activePage)},{"page_handle",num(double(reinterpret_cast<UINT_PTR>(SynthPages::current())))},
        {"left",num(r.left)},{"top",num(r.top)},{"right",num(r.right)},{"bottom",num(r.bottom)}}));
}
std::wstring currentHeading(){
    std::wstring heading=L"Home";
    for(const auto& button:buttons)if(button.navigation&&button.action==activePage)heading=button.label;
    return heading;
}
void updateHelpRect(Gdiplus::Graphics* existing=nullptr){
    if(!window||!SynthPageHelp::find(activePage)){helpRect={};return;}
    RECT r{};GetClientRect(window,&r);
    float width=r.right/scale,main=width-248;
    std::wstring heading=currentHeading();
    HDC dc=existing?nullptr:GetDC(window);
    std::unique_ptr<Gdiplus::Graphics> owned;
    if(!existing&&dc)owned=std::make_unique<Gdiplus::Graphics>(dc);
    Gdiplus::Graphics* g=existing?existing:owned.get();
    float headingW=220.f;
    if(g){
        Gdiplus::Font font(L"Segoe UI",29*scale,Gdiplus::FontStyleBold,Gdiplus::UnitPixel);
        Gdiplus::StringFormat format;format.SetTrimming(Gdiplus::StringTrimmingEllipsisWord);
        Gdiplus::RectF measured;
        g->MeasureString(heading.c_str(),-1,&font,Gdiplus::RectF(0,0,main*scale,40*scale),&format,&measured);
        headingW=measured.Width/scale;
    }
    if(dc)ReleaseDC(window,dc);
    float x=std::min(224.f+headingW+12.f,width-44.f),y=36.f,sz=24.f;
    helpRect={LONG(x*scale),LONG(y*scale),LONG((x+sz)*scale),LONG((y+sz)*scale)};
}
LRESULT CALLBACK helpPopupProc(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    if(message==WM_ERASEBKGND){RECT r{};GetClientRect(hwnd,&r);static HBRUSH bg=CreateSolidBrush(RGB(15,16,19));FillRect(reinterpret_cast<HDC>(w),&r,bg);return 1;}
    return DefWindowProcW(hwnd,message,w,l);
}
void hideHelpTooltip(){
    if(helpPopup){
        ShowWindow(helpPopup,SW_HIDE);
        SetWindowPos(helpPopup,nullptr,-32000,-32000,0,0,SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_HIDEWINDOW);
    }
}
void showHelpCard(const SynthPageHelp::PageHelp& help,RECT anchorClient,bool preferRight=false){
    if(!window||!IsWindowVisible(window))return;
    if(!helpPopup){
        WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanHelpPopup";cls.lpfnWndProc=helpPopupProc;cls.hbrBackground=CreateSolidBrush(RGB(15,16,19));cls.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&cls);
        helpPopup=CreateWindowExW(WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_TOPMOST|WS_EX_NOACTIVATE|WS_EX_TRANSPARENT,cls.lpszClassName,L"",WS_POPUP,-32000,-32000,10,10,window,nullptr,cls.hInstance,nullptr);
    }
    RECT r{};GetClientRect(window,&r);
    int maxW=std::max(int(320*scale),int(r.right-int(240*scale)));
    HDC screenDC=GetDC(nullptr);
    HDC memDC=CreateCompatibleDC(screenDC);
    SynthPageHelp::TooltipMetrics metrics;
    {
        Gdiplus::Graphics measureG(memDC);
        metrics=SynthPageHelp::measureTooltip(measureG,help,scale,maxW);
    }
    BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=metrics.width;bi.bmiHeader.biHeight=-metrics.height;bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    void* bits=nullptr;
    HBITMAP dib=CreateDIBSection(memDC,&bi,DIB_RGB_COLORS,&bits,nullptr,0);
    if(dib&&bits){
        HGDIOBJ oldBmp=SelectObject(memDC,dib);
        {
            Gdiplus::Bitmap canvas(metrics.width,metrics.height,metrics.width*4,PixelFormat32bppPARGB,static_cast<BYTE*>(bits));
            Gdiplus::Graphics g(&canvas);
            g.Clear(Gdiplus::Color(0,0,0,0));
            SynthPageHelp::paintTooltipCard(g,help,metrics,scale);
        }
        GdiFlush();
        RECT anchor=anchorClient;
        MapWindowPoints(window,nullptr,reinterpret_cast<POINT*>(&anchor),2);
        MONITORINFO mi{sizeof(mi)};
        GetMonitorInfoW(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&mi);
        int tipX=preferRight?anchor.right+int(10*scale):anchor.left-int(14*scale);
        int tipY=preferRight?anchor.bottom-metrics.height:anchor.bottom+int(8*scale);
        if(tipX+metrics.width>mi.rcWork.right-12)tipX=mi.rcWork.right-12-metrics.width;
        if(tipX<mi.rcWork.left+12)tipX=mi.rcWork.left+12;
        if(tipY+metrics.height>mi.rcWork.bottom-12){
            int above=anchor.top-metrics.height-int(8*scale);
            tipY=above>=mi.rcWork.top+12?above:std::max(int(mi.rcWork.top+12),int(mi.rcWork.bottom-12-metrics.height));
        }
        if(tipY<mi.rcWork.top+12)tipY=mi.rcWork.top+12;
        POINT ptDst{tipX,tipY},ptSrc{0,0};
        SIZE sz{metrics.width,metrics.height};
        BLENDFUNCTION blend{AC_SRC_OVER,0,255,AC_SRC_ALPHA};
        UpdateLayeredWindow(helpPopup,screenDC,&ptDst,&sz,memDC,&ptSrc,0,&blend,ULW_ALPHA);
        SetWindowPos(helpPopup,HWND_TOPMOST,tipX,tipY,metrics.width,metrics.height,SWP_NOACTIVATE|SWP_SHOWWINDOW);
        SelectObject(memDC,oldBmp);
        DeleteObject(dib);
    }
    DeleteDC(memDC);
    ReleaseDC(nullptr,screenDC);
}
void showHelpTooltip(){
    const auto* help=SynthPageHelp::find(activePage);
    if(!help){hideHelpTooltip();return;}
    updateHelpRect();
    showHelpCard(*help,helpRect,false);
}
void showLockTooltip(){
    HWND lockBtn=GetDlgItem(window,118);
    if(!lockBtn){hideHelpTooltip();return;}
    RECT anchor{};GetWindowRect(lockBtn,&anchor);
    MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&anchor),2);
    static const SynthPageHelp::PageHelp lockedHelp{
        "nav_lock",L"Tab Order Locked",
        L"Sidebar drag-to-reorder is disabled so your custom tab layout stays put.",
        {L"Click this lock icon anytime to unlock and drag feature tabs into a new order."}
    };
    static const SynthPageHelp::PageHelp unlockedHelp{
        "nav_lock",L"Drag Tabs to Reorder",
        L"Drag any feature tab up or down in the sidebar to customize your tab order.",
        {L"Your order saves automatically on this PC. Click this lock icon when done to disable dragging."}
    };
    showHelpCard(navLocked?lockedHelp:unlockedHelp,anchor,true);
}
void layout(){
    if(!window)return;RECT r{};GetClientRect(window,&r);
    scale=std::max(.7f,std::min(float(GetDpiForWindow(window))/96.f,std::min(r.right/900.f,r.bottom/760.f)));
    int tiles=int(std::count_if(buttons.begin(),buttons.end(),[](const auto& b){return b.id>=200&&b.id<=203;})),tileAt=0;
    float width=r.right/scale,height=r.bottom/scale,main=width-248,gap=12,tile=(main-std::max(0,tiles-1)*gap)/std::max(1,tiles);
    int nav=0;
    float navStep=navStepLogical(height);
    NativeRedraw::Layout pending(window);
    for(auto& b:buttons){
        float x=16,y=110+nav*navStep,w=170,h=std::min(34.f,navStep-4);
        if(b.id==117){x=16;y=height-134;w=170;h=32;}
        else if(b.id==118){x=158;y=height-70;w=28;h=22;}
        else if(b.navigation)nav++;
        else if(b.id>=200&&b.id<=203){x=224+(tileAt++)*(tile+gap);y=119;w=tile;h=82;}
        else if(b.id==210||b.id==211){w=136;h=30;x=width-302+(b.id-210)*142;y=234;}
        else if(b.id==212){x=width-192;y=622;w=166;h=30;}
        else if(b.id==213){x=width-160;y=686;w=134;h=28;}
        else if(b.id==214){x=width-306;y=686;w=134;h=28;}
        const bool hasNotice=(b.id!=212||!overview.textOr("refinery_notice").empty())&&
            ((b.id!=213&&b.id!=214)||(available("strings_settings")&&!field(overview,"synthstrings").textOr("title").empty()));
        pending.place(b.hwnd,int(x*scale),int(y*scale),int(w*scale),int(h*scale),b.navigation||b.id==118||(activePage=="home"&&hasNotice));
    }
    pending.apply();
    updateHelpRect();
    SynthPages::place(int(218*scale),int(110*scale),int((width-234)*scale),std::max(1,int(r.bottom)-int(124*scale)),activePage!="home");
}
struct FleetRecap {
    bool synced=false;
    int earnedCount=0;
    int pledgedCount=0;
    int execEarned=0;
    int wikeloEarned=0;
    std::vector<std::wstring> recentShips;
};
FleetRecap cachedFleet;
std::filesystem::file_time_type cachedFleetMtime{};
std::filesystem::path cachedFleetDir;
const FleetRecap& loadFleetRecap(){
    if(directory.empty())return cachedFleet;
    std::error_code ec;
    auto path=directory/L"knick_knacks_state.json";
    if(!std::filesystem::exists(path,ec)){
        if(cachedFleetDir!=directory){cachedFleet={};cachedFleetDir=directory;}
        return cachedFleet;
    }
    auto mtime=std::filesystem::last_write_time(path,ec);
    if(!ec&&cachedFleetDir==directory&&mtime==cachedFleetMtime&&cachedFleet.synced)return cachedFleet;
    cachedFleetDir=directory;cachedFleetMtime=mtime;
    Json st=read(path,16*1024*1024);
    if(st.kind!=Json::Kind::Object||st.textOr("status")!="ok")return cachedFleet;
    FleetRecap next;
    next.synced=true;
    const auto& sc=field(st,"ship_counts");
    next.earnedCount=int(sc.numberOr("ingame_earned",0));
    next.pledgedCount=int(sc.numberOr("pledged",0));
    struct ShipRow { std::string createdAt; std::wstring label; };
    std::vector<ShipRow> rows;
    std::map<uint32_t,std::string> createdByCrc;
    for(const auto& item:field(st,"account_items").items){
        if(item.textOr("category")=="ships"&&item.textOr("source_kind")=="ingame_ltp"){
            uint32_t c=uint32_t(std::llround(item.numberOr("crc",0.0)));
            std::string cat=item.textOr("created_at");
            if(c&&(!createdByCrc.count(c)||cat>createdByCrc[c]))createdByCrc[c]=cat;
        }
    }
    for(const auto& s:field(st,"ships").items){
        if(!flag(s,"owned"))continue;
        std::string own=s.textOr("ownership");
        std::string ch=s.textOr("channel");
        if(ch=="exec_hangar")next.execEarned++;
        if(ch=="wikelo"||flag(s,"also_wikelo"))next.wikeloEarned++;
        if(own!="ingame_earned")continue;
        uint32_t c=uint32_t(std::llround(s.numberOr("crc",0.0)));
        std::string created=s.textOr("created_at");
        if(created.empty()&&createdByCrc.count(c))created=createdByCrc[c];
        std::wstring lbl=wide(s.textOr("name"));
        int q=int(s.numberOr("quantity",1));
        if(q>1)lbl+=L" ("+std::to_wstring(q)+L"×)";
        rows.push_back({created,lbl});
    }
    if(next.earnedCount==0&&!rows.empty())next.earnedCount=int(rows.size());
    std::sort(rows.begin(),rows.end(),[](const ShipRow& a,const ShipRow& b){
        if(a.createdAt!=b.createdAt)return a.createdAt>b.createdAt;
        return a.label<b.label;
    });
    for(size_t i=0;i<std::min(size_t(6),rows.size());++i)next.recentShips.push_back(rows[i].label);
    cachedFleet=std::move(next);
    return cachedFleet;
}
// Paint the same surface in parent and child coordinates. A flat child clear
// leaves visible square corners around translucent rounded buttons.
void paintSurface(Gdiplus::Graphics& g,int widthPixels,int heightPixels){
    g.Clear(BG);SynthGlass::ambient(g,{0,0,float(widthPixels),float(heightPixels)});
    float width=widthPixels/scale,height=heightPixels/scale,main=width-248,col3=(main-24.f)/3.f,kpiW=(main-36.f)/4.f;
    Gdiplus::SolidBrush side(SIDE);g.FillRectangle(&side,0.f,0.f,200*scale,float(heightPixels));
    SynthGlass::panel(g,{12*scale,14*scale,188*scale,float(heightPixels)-28*scale},false,false,18*scale);
    Gdiplus::Pen sep(Gdiplus::Color(40,174,193,219),std::max(1.f,scale));
    g.DrawLine(&sep,24*scale,(height-144)*scale,188*scale,(height-144)*scale);
    if(activePage!="home")return;
    for(int i=0;i<4;i++)rounded(g,{(224.f+i*(kpiW+12.f))*scale,282*scale,kpiW*scale,72*scale},CARD);
    for(int i=0;i<3;i++)rounded(g,{(224.f+i*(col3+12.f))*scale,371*scale,col3*scale,220*scale},CARD);
    if(available("refinery")&&!overview.textOr("refinery_notice").empty())rounded(g,{224*scale,609*scale,main*scale,59*scale},CARD);
    if(available("strings_settings")&&!field(overview,"synthstrings").textOr("title").empty())
        rounded(g,{224*scale,678*scale,main*scale,std::max(70.f,height-696.f)*scale},CARD);
}
void buttonSurface(Gdiplus::Graphics& g,HWND child){
    RECT at{},root{};GetWindowRect(child,&at);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&at),2);GetClientRect(window,&root);
    auto saved=g.Save();g.TranslateTransform(-float(at.left),-float(at.top));paintSurface(g,root.right,root.bottom);g.Restore(saved);
}
std::wstring patchDetails(){
    const auto& strings=field(overview,"synthstrings");
    std::string text=strings.textOr("patch_label","Star Citizen · patch number unavailable")+"\n\n"+
        strings.textOr("status_label","Text status unavailable")+"\n"+strings.textOr("summary")+
        "\n\nSynthStrings adds blueprint and reputation information to in-game text.";
    if(strings.numberOr("at")>0){std::time_t t=static_cast<std::time_t>(strings.numberOr("at"));std::tm local{};localtime_s(&local,&t);wchar_t label[80]{};wcsftime(label,80,L"%d %b %Y, %H:%M",&local);text+="\nLast text check: "+utf8(label);}
    return wide(text);
}
LRESULT CALLBACK navigationHover(HWND hwnd,UINT m,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    // BUTTON's default erase uses the system button-face brush, which is light
    // even though WM_DRAWITEM later paints a dark tile.
    if(m==WM_ERASEBKGND){Gdiplus::Graphics g(reinterpret_cast<HDC>(w));g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);buttonSurface(g,hwnd);return 1;}
    if(m==WM_LBUTTONDOWN){
        int id=GetDlgCtrlID(hwnd);
        auto found=std::find_if(buttons.begin(),buttons.end(),[&](const auto& b){return b.id==id;});
        if(found!=buttons.end()&&isDraggableNav(*found)&&!navLocked){
            dragButton=hwnd;dragActive=false;GetCursorPos(&dragStartScreen);
        }
    }
    if(m==WM_MOUSEMOVE){
        if(!GetPropW(hwnd,L"SynthGlass.Hot")){
            SetPropW(hwnd,L"SynthGlass.Hot",HANDLE(1));TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);InvalidateRect(hwnd,nullptr,FALSE);
            if(GetDlgCtrlID(hwnd)==118&&!lockHot){lockHot=true;showLockTooltip();}
        }
        if(dragButton==hwnd&&!navLocked&&(w&MK_LBUTTON)){
            POINT cur{};GetCursorPos(&cur);
            if(!dragActive&&std::abs(cur.y-dragStartScreen.y)>=int(6*scale)){
                dragActive=true;hideHelpTooltip();InvalidateRect(hwnd,nullptr,FALSE);
            }
            if(dragActive&&window){
                POINT cl=cur;ScreenToClient(window,&cl);
                RECT r{};GetClientRect(window,&r);
                float step=navStepLogical(r.bottom/scale);
                int dragIndices[32]{};int count=0;int curPos=-1;
                for(int i=0;i<int(buttons.size());++i){
                    if(isDraggableNav(buttons[i])){
                        if(buttons[i].hwnd==hwnd)curPos=count;
                        if(count<32)dragIndices[count++]=i;
                    }
                }
                if(count>1&&curPos>=0){
                    bool hasHome=std::any_of(buttons.begin(),buttons.end(),[](const auto& b){return b.navigation&&b.action=="home";});
                    int slot=int(std::floor((cl.y/scale-110.f)/step))-(hasHome?1:0);
                    slot=std::clamp(slot,0,count-1);
                    if(slot!=curPos){
                        int fromIdx=dragIndices[curPos],toIdx=dragIndices[slot];
                        Button moved=buttons[fromIdx];
                        buttons.erase(buttons.begin()+fromIdx);
                        buttons.insert(buttons.begin()+toIdx,moved);
                        layout();
                        for(const auto& b:buttons)if(b.navigation)InvalidateRect(b.hwnd,nullptr,FALSE);
                    }
                }
                return 0;
            }
        }
    }
    if(m==WM_LBUTTONUP){
        if(dragButton==hwnd){
            bool wasDragging=dragActive;
            dragButton=nullptr;dragActive=false;
            if(wasDragging){
                suppressNextClick=true;
                ReleaseCapture();
                saveSidebarOrder();
                layout();
                for(const auto& b:buttons)if(b.navigation)InvalidateRect(b.hwnd,nullptr,FALSE);
                return 0;
            }
        }
    }
    if(m==WM_CAPTURECHANGED){
        if(dragButton==hwnd){
            bool wasDragging=dragActive;
            dragButton=nullptr;dragActive=false;
            if(wasDragging){
                saveSidebarOrder();layout();
                for(const auto& b:buttons)if(b.navigation)InvalidateRect(b.hwnd,nullptr,FALSE);
            }
        }
    }
    if(m==WM_MOUSELEAVE){
        RemovePropW(hwnd,L"SynthGlass.Hot");InvalidateRect(hwnd,nullptr,FALSE);
        if(GetDlgCtrlID(hwnd)==118&&lockHot){lockHot=false;hideHelpTooltip();}
    }
    if(m==WM_NCDESTROY){
        if(dragButton==hwnd){dragButton=nullptr;dragActive=false;}
        RemovePropW(hwnd,L"SynthGlass.Hot");RemoveWindowSubclass(hwnd,navigationHover,1);
    }
    return DefSubclassProc(hwnd,m,w,l);
}
void add(int id,const wchar_t* label,const char* command,bool navigation){
    const auto release=read(SCMiner::AppPaths::program().parent_path().parent_path()/L"release.json");
    if(!HudModules::actionAvailable(release,command,SynthEdition::screenReading))return;
    HWND child=CreateWindowExW(0,L"BUTTON",label,WS_CHILD|WS_VISIBLE|WS_CLIPSIBLINGS|WS_TABSTOP|BS_OWNERDRAW,0,0,10,10,window,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    SetWindowSubclass(child,navigationHover,1,0);
    buttons.push_back({child,id,label,command,navigation});
}
void paintButton(const DRAWITEMSTRUCT& item){
    auto found=std::find_if(buttons.begin(),buttons.end(),[&](const auto& b){return b.id==int(item.CtlID);});if(found==buttons.end())return;
    const auto& b=*found;int width=item.rcItem.right-item.rcItem.left,height=item.rcItem.bottom-item.rcItem.top;
    if(width<=0||height<=0)return;
    Gdiplus::Bitmap frame(width,height,PixelFormat32bppPARGB);
    {Gdiplus::Graphics g(&frame);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
    bool dragging=(dragActive&&b.hwnd==dragButton);
    bool selected=(b.navigation&&b.action==activePage)||(b.id==210&&!previous)||(b.id==211&&previous)||dragging;
    buttonSurface(g,item.hwndItem);
    Gdiplus::RectF r(0,0,float(item.rcItem.right),float(item.rcItem.bottom));
    bool hot=(item.itemState&ODS_HOTLIGHT)!=0||GetPropW(item.hwndItem,L"SynthGlass.Hot")!=nullptr;
    if(b.id==118){
        SynthGlass::panel(g,{1,1,r.Width-2,r.Height-2},!navLocked,hot||bool(item.itemState&ODS_SELECTED),6*scale);
        Gdiplus::Color col=!navLocked?SynthGlass::Accent:(hot?SynthGlass::Ink:SynthGlass::Muted);
        Gdiplus::Pen p(col,std::max(1.2f,1.4f*scale));p.SetStartCap(Gdiplus::LineCapRound);p.SetEndCap(Gdiplus::LineCapRound);p.SetLineJoin(Gdiplus::LineJoinRound);
        float cx=r.Width*.5f,cy=r.Height*.5f;
        Gdiplus::GraphicsPath body;SynthGlass::shape(body,{cx-4.5f*scale,cy-1.f*scale,9.f*scale,6.5f*scale},1.8f*scale);
        Gdiplus::SolidBrush fill(Gdiplus::Color(!navLocked?55:25,col.GetR(),col.GetG(),col.GetB()));
        g.FillPath(&fill,&body);g.DrawPath(&p,&body);
        if(navLocked){
            g.DrawArc(&p,cx-3.f*scale,cy-6.f*scale,6.f*scale,6.5f*scale,180.f,180.f);
            g.DrawLine(&p,cx-3.f*scale,cy-2.8f*scale,cx-3.f*scale,cy-1.f*scale);
            g.DrawLine(&p,cx+3.f*scale,cy-2.8f*scale,cx+3.f*scale,cy-1.f*scale);
        }else{
            g.DrawArc(&p,cx-1.f*scale,cy-6.5f*scale,6.f*scale,6.5f*scale,180.f,180.f);
            g.DrawLine(&p,cx-1.f*scale,cy-3.3f*scale,cx-1.f*scale,cy-1.f*scale);
        }
    }else{
    if(!b.navigation||selected||hot)SynthGlass::panel(g,{1,1,r.Width-2,r.Height-2},selected,hot||bool(item.itemState&ODS_SELECTED),9*scale);
    const bool tile=b.id>=200&&b.id<=203;
    std::wstring label=b.label;auto cut=label.find(L'\n');
    if(b.navigation){SynthGlass::rounded(g,{8*scale,(r.Height-24*scale)/2,24*scale,24*scale},Gdiplus::Color(38,154,185,206),7*scale);SynthGlass::icon(g,b.action,{12*scale,(r.Height-16*scale)/2,16*scale,16*scale},selected?SynthGlass::Accent:SynthGlass::Muted);
        bool showGrip=isDraggableNav(b)&&!navLocked;
        SynthGlass::text(g,label,{37*scale,0,r.Width-(showGrip?50*scale:43*scale),r.Height},11.2f*scale,selected?SynthGlass::Ink:SynthGlass::Muted,selected);
        if(showGrip){
            Gdiplus::SolidBrush grip(Gdiplus::Color(hot||dragging?180:65,160,175,195));
            float gx=r.Width-11*scale,gy=r.Height*.5f-4.5f*scale,dr=1.05f*scale;
            for(int row=0;row<3;++row)for(int col=0;col<2;++col)
                g.FillEllipse(&grip,gx+col*3.2f*scale,gy+row*3.5f*scale,dr*2,dr*2);
        }
    }else if(tile)words(g,label.substr(0,cut),16,16,r.Width/scale-28,26,15,INK,true);
    else SynthGlass::text(g,label,{12*scale,0,r.Width-24*scale,r.Height},12*scale,INK,true);
    if(cut!=std::wstring::npos)words(g,label.substr(cut+1),16,45,r.Width/scale-28,28,11,MUTED);
    }
    if(item.itemState&ODS_FOCUS){Gdiplus::Pen pen(Gdiplus::Color(100,161,205,208));Gdiplus::GraphicsPath focus;SynthGlass::shape(focus,{2,2,r.Width-5,r.Height-5},8*scale);g.DrawPath(&pen,&focus);}
    }
    // Commit only the complete button, respecting the supplied owner's DC clip.
    Gdiplus::Graphics screen(item.hDC);screen.DrawImage(&frame,int(item.rcItem.left),int(item.rcItem.top));
}
void paint(HDC target=nullptr){
    PAINTSTRUCT ps{};HDC dc=target?target:BeginPaint(window,&ps);RECT r{};GetClientRect(window,&r);
    if(r.right>0&&r.bottom>0){
        Gdiplus::Bitmap bitmap(r.right,r.bottom,PixelFormat32bppPARGB);Gdiplus::Graphics g(&bitmap);
        g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
        float width=r.right/scale,height=r.bottom/scale,main=width-248,col=(main-16)/2;
        paintSurface(g,r.right,r.bottom);
        static HICON logo=LoadIconW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(IDI_APPICON));
        HDC iconDC=g.GetHDC();DrawIconEx(iconDC,int(24*scale),int(29*scale),logo,int(32*scale),int(32*scale),0,nullptr,DI_NORMAL);g.ReleaseHDC(iconDC);
        words(g,L"SynthScan",66,29,130,31,20,INK,true);
        words(g,L"YOUR VERSE, CONNECTED",24,73,164,20,9,MUTED,true);
        auto cap=CapturePrivacy::snapshot();double age=cap.numberOr("frame_age_ms",-1);
        words(g,!SynthEdition::screenReading?L"NO SCREEN READER INSTALLED":CapturePrivacy::policy().paused?L"CAPTURE PAUSED":age>=0&&age<1500?L"READING GAME WINDOW":L"CAPTURE IDLE · GAME ONLY",24,height-91,164,20,10,ACCENT,true);
        words(g,L"LOCAL PROFILE",24,height-66,130,20,9,ACCENT,true);
        words(g,L"Your records stay on this PC",24,height-45,166,30,10,MUTED);
        std::wstring heading=currentHeading();
        words(g,heading,224,30,main,40,29,INK,true);
        updateHelpRect(&g);
        if(SynthPageHelp::find(activePage)&&helpRect.right>helpRect.left){
            Gdiplus::RectF hr(float(helpRect.left),float(helpRect.top),float(helpRect.right-helpRect.left),float(helpRect.bottom-helpRect.top));
            Gdiplus::SolidBrush fill(helpHot?Gdiplus::Color(245,38,62,82):Gdiplus::Color(220,24,34,48));
            g.FillEllipse(&fill,hr);
            Gdiplus::Pen ring(helpHot?Gdiplus::Color(235,98,204,255):Gdiplus::Color(115,98,204,255),std::max(1.f,1.25f*scale));
            g.DrawEllipse(&ring,hr);
            Gdiplus::Font qFont(L"Segoe UI",13.5f*scale,Gdiplus::FontStyleBold,Gdiplus::UnitPixel);
            Gdiplus::StringFormat qFmt;qFmt.SetAlignment(Gdiplus::StringAlignmentCenter);qFmt.SetLineAlignment(Gdiplus::StringAlignmentCenter);
            Gdiplus::SolidBrush qBrush(helpHot?INK:ACCENT);
            g.DrawString(L"?",-1,&qFont,hr,&qFmt,&qBrush);
        }
        words(g,activePage=="home"?L"Find your next upgrade. See what you've accomplished.":activePage=="people"?L"A familiar face in a very large universe.":activePage=="executive_hangar"?L"Watch the window. Keep your next full set ready.":activePage=="planner"?L"Ore finder, location presets, rock memories and hauls.":activePage=="roulette"?L"Let fate decide your next challenge in the verse.":L"",224,76,main,28,13,MUTED);
        if(activePage=="home"){
        float col3=(main-24.f)/3.f,kpiW=(main-36.f)/4.f;
        float xCol1=240.f,xCol2=240.f+col3+12.f,xCol3=240.f+2.f*(col3+12.f),colTextW=col3-32.f;
        const auto& fleet=loadFleetRecap();
        words(g,L"SESSION & FLEET RECAP",224,241,main-300,24,11,ACCENT,true);
        const Json& session=field(overview,previous?"previous":"current");
        const auto& blueprints=field(session,"blueprints").items;const auto& rep=field(session,"reputation").items;
        for(int i=0;i<4;i++){
            float x=224.f+i*(kpiW+12.f);
            std::wstring count=i==0?number(double(blueprints.size())):i==1?number(session.numberOr("contracts_completed")):i==2?number(double(rep.size())):(fleet.synced?number(double(fleet.earnedCount)):L"—");
            words(g,count,x+15,290,kpiW-30,33,25,i==3&&fleet.synced?Gdiplus::Color(255,118,217,163):INK,true);
            words(g,i==0?L"Blueprints received":i==1?L"Contracts completed":i==2?L"Reputation changes":L"Ships earned in-game",x+15,327,kpiW-30,20,11,MUTED);
        }
        words(g,L"Blueprints received",xCol1,387,colTextW,26,14,INK,true);
        words(g,L"Reputation balance changes",xCol2,387,colTextW,26,14,INK,true);
        words(g,L"Ships earned in-game",xCol3,387,colTextW,26,14,INK,true);
        auto baseline=clockLabel(session.numberOr("rep_baseline_at"));
        auto checked=clockLabel(session.numberOr("rep_checked_at"));
        if(!baseline.empty())words(g,L"Baseline "+baseline+L" · last read "+checked,xCol2,411,colTextW,18,10,MUTED);
        const bool reputationAvailable=available("strings_settings")||available("mission_log");
        words(g,reputationAvailable?L"Account balances · checks about every 30s":L"Saved account balance changes",xCol2,430,colTextW,18,10,MUTED);
        if(blueprints.empty())words(g,session.kind==Json::Kind::Null?L"No saved session yet. Play normally to build your recap.":L"No blueprint grants recorded in this session.",xCol1,432,colTextW,68,12,MUTED);
        for(size_t i=0;i<std::min(size_t(6),blueprints.size());i++)words(g,wide(blueprints[i].textOr("name")),xCol1,428+23*float(i),colTextW,23,12,INK);
        if(blueprints.size()>6)words(g,L"+ "+std::to_wstring(blueprints.size()-6)+(available("blueprints")?L" more · open Blueprint library":L" more saved grants"),xCol1,568,colTextW,18,10,ACCENT);
        if(rep.empty())words(g,session.numberOr("rep_checked_at")>0?L"No balance changes between the saved reads.":!reputationAvailable?L"No saved balance changes. Your retained records stay available here.":L"Waiting for verified reputation balances. Mission payouts aren't treated as confirmed gains.",xCol2,453,colTextW,85,12,MUTED);
        for(size_t i=0;i<std::min(size_t(4),rep.size());i++){
            const auto& change=rep[i];float y=453+32*float(i);
            auto delta=change.numberOr("delta");auto label=wide(change.textOr("faction"))+L"  "+(delta>0?L"+":L"")+number(delta);
            words(g,label,xCol2,y,colTextW,22,12,delta>0?ACCENT:INK,true);
            auto scope=wide(change.textOr("scope"));if(flag(change,"standing_changed"))scope+=L" · standing changed";
            words(g,scope+L" · "+number(change.numberOr("before"))+L" → "+number(change.numberOr("after")),xCol2,y+17,colTextW,18,10,MUTED);
        }
        if(!fleet.synced){
            words(g,L"Long-Term Persistence fleet · syncs automatically",xCol3,411,colTextW,18,10,MUTED);
            words(g,L"Open Knick-Knacks while signed in to sync your earned ships, Executive Hangar collection, and Wikelo fleet.",xCol3,442,colTextW,85,12,MUTED);
        }else{
            std::wstring breakdown=std::to_wstring(fleet.execEarned)+L"/8 Exec Hangar · "+std::to_wstring(fleet.wikeloEarned)+L" Wikelo · "+std::to_wstring(fleet.pledgedCount)+L" Pledged";
            words(g,breakdown,xCol3,411,colTextW,18,10,ACCENT,true);
            words(g,L"Latest additions to your LTP fleet",xCol3,430,colTextW,18,10,MUTED);
            if(fleet.recentShips.empty()){
                words(g,L"No in-game earned ships recorded yet.",xCol3,453,colTextW,60,12,MUTED);
            }else{
                for(size_t i=0;i<std::min(size_t(5),fleet.recentShips.size());++i){
                    words(g,fleet.recentShips[i],xCol3,452+22*float(i),colTextW,22,12,INK);
                }
                int moreShips=std::max(0,fleet.earnedCount-int(std::min(size_t(5),fleet.recentShips.size())));
                std::wstring foot=moreShips>0?(L"+ "+std::to_wstring(moreShips)+L" more · open Knick-Knacks Fleet ↗"):L"Open Knick-Knacks Fleet ↗";
                words(g,foot,xCol3,568,colTextW,18,10,ACCENT);
            }
        }
        auto notice=overview.textOr("refinery_notice");
        if(available("refinery")&&!notice.empty()){
            words(g,wide(notice),240,621,main-200,23,13,ACCENT,true);
            words(g,L"Confirmed game notification · dismiss after reviewing your orders",240,645,main-200,19,10,MUTED);
        }
        const auto& strings=field(overview,"synthstrings");
        if(available("strings_settings")&&!strings.textOr("title").empty()){
            const auto kind=strings.textOr("status_kind");
            const auto color=kind=="ready"?Gdiplus::Color(255,118,217,163):(kind=="off"||kind=="info")?MUTED:kind=="updating"?ACCENT:Gdiplus::Color(255,255,195,105);
            float cardHeight=std::max(70.f,height-696.f);
            if(kind=="ready")SynthGlass::icon(g,"check",{240*scale,690*scale,17*scale,17*scale},color);
            else if(kind=="off"||kind=="updating")SynthGlass::icon(g,kind=="updating"?"refresh":"clear",{240*scale,690*scale,17*scale,17*scale},color);
            else if(kind!="info") {Gdiplus::Pen pen(color,1.5f*scale);Gdiplus::PointF points[]={{248.5f*scale,690*scale},{240*scale,706*scale},{257*scale,706*scale},{248.5f*scale,690*scale}};g.DrawLines(&pen,points,4);g.DrawLine(&pen,248.5f*scale,695*scale,248.5f*scale,700*scale);g.DrawLine(&pen,248.5f*scale,702.5f*scale,248.5f*scale,703*scale);}
            words(g,wide(strings.textOr("patch_label","Star Citizen · patch number unavailable")),kind=="info"?240:263,688,kind=="info"?main-324:main-347,24,13,INK,true);
            std::string detail=strings.textOr("status_label","Text status unavailable")+" · "+strings.textOr("summary");
            words(g,wide(detail),240,716,main-32,cardHeight-42,11,color);
        }else{
            words(g,connected?wide(identity):L"No live shard observation",224,690,main,22,11,connected?INK:MUTED);
            words(g,flag(overview,"history_warning")?L"Saved recap could not be read. The original file has been preserved.":L"Reputation is net balance change between reads; activity before the baseline is not included.",224,716,main,28,10,MUTED);
        }
        }
        Gdiplus::Graphics screen(dc);screen.DrawImage(&bitmap,0,0);
    }if(!target)EndPaint(window,&ps);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    if(message==WM_PAINT){paint();return 0;}
    if(message==WM_PRINTCLIENT){paint(reinterpret_cast<HDC>(w));return 0;}
    if(message==WM_SIZE){hideHelpTooltip();helpHot=false;lockHot=false;layout();InvalidateRect(hwnd,nullptr,FALSE);return 0;}
    if(message==WM_MOVE){hideHelpTooltip();return 0;}
    if(message==WM_ACTIVATE&&LOWORD(w)==WA_INACTIVE){if(helpHot){helpHot=false;InvalidateRect(hwnd,&helpRect,FALSE);}lockHot=false;dragButton=nullptr;dragActive=false;hideHelpTooltip();return 0;}
    if(message==WM_SETCURSOR&&LOWORD(l)==HTCLIENT&&SynthPageHelp::find(activePage)){
        POINT pt{};GetCursorPos(&pt);ScreenToClient(hwnd,&pt);
        if(PtInRect(&helpRect,pt)){SetCursor(LoadCursor(nullptr,IDC_HAND));return TRUE;}
    }
    if(message==WM_LBUTTONDOWN&&activePage=="home"){
        RECT r{};GetClientRect(hwnd,&r);
        float lx=float(GET_X_LPARAM(l))/scale,ly=float(GET_Y_LPARAM(l))/scale;
        float width=r.right/scale,main=width-248.f,col3=(main-24.f)/3.f,kpiW=(main-36.f)/4.f;
        if(ly>=282.f&&ly<=354.f){
            float x4=224.f+3.f*(kpiW+12.f);
            if(lx>=x4&&lx<=x4+kpiW&&available("knick_knacks")){navigate("knick_knacks");return 0;}
        }
        if(ly>=371.f&&ly<=591.f){
            float x1=224.f,x2=224.f+col3+12.f,x3=224.f+2.f*(col3+12.f);
            if(lx>=x1&&lx<=x1+col3&&available("blueprints")){navigate("blueprints");return 0;}
            if(lx>=x2&&lx<=x2+col3&&available("mission_log")){navigate("mission_log");return 0;}
            if(lx>=x3&&lx<=x3+col3&&available("knick_knacks")){navigate("knick_knacks");return 0;}
        }
    }
    if(message==WM_MOUSEMOVE){
        POINT pt{GET_X_LPARAM(l),GET_Y_LPARAM(l)};
        bool over=SynthPageHelp::find(activePage)!=nullptr&&PtInRect(&helpRect,pt)!=FALSE;
        if(over!=helpHot){
            helpHot=over;
            InvalidateRect(hwnd,&helpRect,FALSE);
            if(over){
                TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);
                showHelpTooltip();
            }else hideHelpTooltip();
        }else if(over){
            TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);
        }
        return 0;
    }
    if(message==WM_MOUSELEAVE){
        if(helpHot){helpHot=false;InvalidateRect(hwnd,&helpRect,FALSE);}
        if(!lockHot)hideHelpTooltip();
        return 0;
    }
    if(message==WM_ERASEBKGND){RECT r{};GetClientRect(hwnd,&r);static HBRUSH surface=CreateSolidBrush(RGB(15,16,19));FillRect(reinterpret_cast<HDC>(w),&r,surface);return 1;}
    if(message==WM_DRAWITEM){paintButton(*reinterpret_cast<DRAWITEMSTRUCT*>(l));return TRUE;}
    if(message==WM_COMMAND&&HIWORD(w)==BN_CLICKED){
        if(suppressNextClick){suppressNextClick=false;return 0;}
        int id=LOWORD(w);
        if(id==118){
            navLocked=!navLocked;
            saveSidebarOrder();
            for(const auto& b:buttons)if(b.navigation||b.id==118)InvalidateRect(b.hwnd,nullptr,FALSE);
            if(lockHot)showLockTooltip();
            publish();
            return 0;
        }
        if(id==213){
            const auto kind=field(overview,"synthstrings").textOr("status_kind");
            MessageBoxW(hwnd,patchDetails().c_str(),L"Star Citizen patch status",MB_OK|((kind=="attention"||kind=="unknown")?MB_ICONWARNING:MB_ICONINFORMATION));return 0;
        }
        if(id==210||id==211){previous=id==211;sessionChosen=true;InvalidateRect(hwnd,nullptr,FALSE);for(auto& b:buttons)InvalidateRect(b.hwnd,nullptr,FALSE);publish();return 0;}
        auto found=std::find_if(buttons.begin(),buttons.end(),[&](const auto& b){return b.id==id;});
        if(found!=buttons.end()){
            lastAction=found->action;
            if(found->navigation&&lastAction!="modules"&&lastAction!="exit")navigate(lastAction);
            else if(action)action(lastAction);
            publish();
        }return 0;
    }
    if(message==WM_CLOSE){helpHot=false;lockHot=false;dragButton=nullptr;dragActive=false;hideHelpTooltip();ShowWindow(hwnd,SW_HIDE);publish();return 0;}
    if(message==WM_APPCOMMAND){
        const short cmd=GET_APPCOMMAND_LPARAM(l);
        if(cmd==APPCOMMAND_BROWSER_BACKWARD){navigateBack();return TRUE;}
        if(cmd==APPCOMMAND_BROWSER_FORWARD){navigateForward();return TRUE;}
    }
    if(message==WM_DPICHANGED){helpHot=false;lockHot=false;hideHelpTooltip();auto r=reinterpret_cast<RECT*>(l);SetWindowPos(hwnd,nullptr,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER|SWP_NOACTIVATE);layout();return 0;}
    if(message==WM_EXITSIZEMOVE)publish();
    return DefWindowProcW(hwnd,message,w,l);
}
void create(){
    if(window)return;WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanHome";cls.lpfnWndProc=procedure;cls.hbrBackground=CreateSolidBrush(RGB(15,16,19));cls.hCursor=LoadCursor(nullptr,IDC_ARROW);cls.hIcon=LoadIconW(cls.hInstance,MAKEINTRESOURCEW(IDI_APPICON));RegisterClassW(&cls);
    MONITORINFO info{sizeof(info)};GetMonitorInfo(MonitorFromWindow(owner,MONITOR_DEFAULTTONEAREST),&info);
    float dpi=GetDpiForWindow(owner)/96.f;int width=std::min(int(1360*dpi),int(info.rcWork.right-info.rcWork.left)-48),height=std::min(int(940*dpi),int(info.rcWork.bottom-info.rcWork.top)-48);
    // The page controls already buffer their own painting. Whole-tree Windows
    // compositing re-enters the custom People controls during layout and can
    // trap this UI thread in a synchronous WM_PAINT loop.
    window=CreateWindowExW(WS_EX_APPWINDOW|WS_EX_CONTROLPARENT,cls.lpszClassName,L"SynthScan — Home",WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,
        info.rcWork.left+(info.rcWork.right-info.rcWork.left-width)/2,info.rcWork.top+(info.rcWork.bottom-info.rcWork.top-height)/2,width,height,nullptr,nullptr,cls.hInstance,nullptr);
    BOOL dark=TRUE;DwmSetWindowAttribute(window,20,&dark,sizeof(dark));
    SynthPages::initialize(window);
    const wchar_t* names[]={L"Home",L"Item & Ship Finder",L"Citizens",L"Mission & Wallet Log",L"Knick-Knacks",L"Server History",L"Blueprint Library",L"Mining Tools",L"Refinery",L"Executive Hangar",L"Flight / Piracy",L"Day/Night Forecast",L"Automations",L"Fate Roulette",L"Settings"};
    const char* actions[]={"home","directory","people","mission_log","knick_knacks","servers","blueprints","planner","refinery","executive_hangar","hud_piracy","daylight","acceptance","roulette","settings"};
    for(int i=0;i<int(sizeof(names)/sizeof(names[0]));i++)add(strcmp(actions[i],"settings")==0?114:100+i,names[i],actions[i],true);
    add(200,L"Mining HUD\nAutomatic scan reading","hud_mining",false);add(201,L"Finder HUD\nShops & player market","hud_finder",false);
    add(202,L"Missions HUD\nContracts & reputation","hud_missions",false);add(203,L"Hangars HUD\nContested-zone timing","hud_hangars",false);
    add(210,L"This session","this",false);add(211,L"Previous session","previous",false);add(212,L"Dismiss notices","dismiss_refinery",false);
    add(213,L"Patch status","strings_details",false);
    add(214,L"Text settings","strings_settings",false);
    add(117,L"Exit SynthScan","exit",true);
    add(118,L"Lock tab order","toggle_nav_lock",false);
    loadSidebarOrder();
    layout();
}
}
void initialize(HWND parent,const std::filesystem::path& data,std::function<void(const std::string&)> callback){owner=parent;directory=data;action=std::move(callback);}
void update(const SCMiner::JsonValue& incoming,const std::string& label,bool live){
    Json value=incoming;
    value.members.erase(std::remove_if(value.members.begin(),value.members.end(),[](const auto& item){
        return (item.first=="synthstrings"&&!available("strings_settings"))||(item.first=="refinery_notice"&&!available("refinery"));
    }),value.members.end());
    static bool wasPaused=false;bool paused=CapturePrivacy::policy().paused;
    bool changed=encode(value)!=encode(overview)||identity!=label||connected!=live||paused!=wasPaused;wasPaused=paused;
    bool noticesChanged=overview.textOr("refinery_notice")!=value.textOr("refinery_notice")||
        field(overview,"synthstrings").textOr("title")!=field(value,"synthstrings").textOr("title");
    overview=value;identity=label;connected=live;
    if(window&&noticesChanged)layout();
    if(!sessionChosen&&value.kind==Json::Kind::Object){
        const auto& current=field(value,"current");
        previous=field(value,"previous").kind==Json::Kind::Object&&field(current,"blueprints").items.empty()&&field(current,"reputation").items.empty()&&current.numberOr("contracts_completed")==0;
        sessionChosen=true;
    }
    if(window)publish();
    if(window&&changed){
        RECT r{};GetClientRect(window,&r);
        RECT statusStrip{0,std::max(0,int(r.bottom)-int(105*scale)),int(200*scale),r.bottom};
        InvalidateRect(window,&statusStrip,FALSE);
        if(activePage=="home"){
            RECT content{int(200*scale),0,r.right,r.bottom};
            InvalidateRect(window,&content,FALSE);
            for(auto& b:buttons)if(b.id==210||b.id==211)InvalidateRect(b.hwnd,nullptr,FALSE);
        }
        publish();
    }
}
void show(){create();if(owner&&(GetWindowLongPtrW(owner,GWL_EXSTYLE)&WS_EX_TOPMOST))SetWindowPos(owner,HWND_NOTOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);ShowWindow(window,SW_SHOW);ShowWindow(window,SW_RESTORE);SetForegroundWindow(window);publish();}
void hide(){helpHot=false;hideHelpTooltip();if(window){ShowWindow(window,SW_HIDE);publish();}}
HWND pageHost(){create();return SynthPages::host();}
void selectPage(const std::string& name){
    std::string previousPage=activePage;
    activePage=name;
    helpHot=false;hideHelpTooltip();
    if(activePage=="home")SynthPages::hide();
    else SynthPages::advanceGeneration();
    if(window){
        updateHelpRect();
        for(const auto& b:buttons){
            if(b.navigation&&(b.action==previousPage||b.action==activePage))
                InvalidateRect(b.hwnd,nullptr,FALSE);
        }
        RECT r{};GetClientRect(window,&r);
        if((previousPage=="home")!=(activePage=="home")||previousPage.empty()){
            layout();
            RECT content{int(200*scale),0,r.right,r.bottom};
            InvalidateRect(window,&content,FALSE);
        }else{
            RECT header{int(200*scale),0,r.right,int(110*scale)};
            InvalidateRect(window,&header,FALSE);
        }
    }
    publish();
}
void navigate(const std::string& name){
    if(!available(name))return;
    // Copy before dispatch: navigation may update the selected action itself.
    const std::string destination=name;lastAction=destination;
    SynthPages::beginTransition();
    const std::string pageDest=(destination=="bookmarks"||destination=="diary")?"planner":destination;
    if(!navigatingHistory&&pageDest!="modules"&&pageDest!="exit"&&pageDest!="strings_settings"&&pageDest!="strings_details"&&pageDest.rfind("hud_",0)!=0){
        if(pageHistory.empty()||pageHistory[size_t(pageHistoryIndex)]!=pageDest){
            if(pageHistoryIndex+1<int(pageHistory.size()))pageHistory.resize(size_t(pageHistoryIndex+1));
            pageHistory.push_back(pageDest);
            if(pageHistory.size()>64)pageHistory.erase(pageHistory.begin());
            pageHistoryIndex=int(pageHistory.size())-1;
        }
    }
    selectPage(pageDest);
    if(destination!="home"&&action)action(destination);
    SynthPages::endTransition();publish();
}
bool stepPageHistory(int delta){
    if(!visible())return false;
    const int targetIdx=pageHistoryIndex+delta;
    if(targetIdx>=0&&targetIdx<int(pageHistory.size())){
        pageHistoryIndex=targetIdx;
        navigatingHistory=true;
        navigate(pageHistory[size_t(pageHistoryIndex)]);
        navigatingHistory=false;
        return true;
    }
    std::vector<std::string> navs;
    for(const auto& b:buttons)if(b.navigation&&b.action!="exit"&&b.action!="modules"&&available(b.action))navs.push_back(b.action);
    auto it=std::find(navs.begin(),navs.end(),activePage);
    if(it!=navs.end()){
        const int nextPos=int(it-navs.begin())+delta;
        if(nextPos>=0&&nextPos<int(navs.size())){
            navigate(navs[size_t(nextPos)]);
            return true;
        }
    }
    return false;
}
bool navigateBack(){return stepPageHistory(-1);}
bool navigateForward(){return stepPageHistory(1);}
std::string selectedPage(){return activePage;}
bool visible(){return window&&IsWindowVisible(window);}
bool active(){return visible()&&GetAncestor(GetForegroundWindow(),GA_ROOT)==window;}
bool routeMessage(MSG& message){
    if(window&&visible()&&(message.hwnd==window||IsChild(window,message.hwnd))){
        if(message.message==WM_XBUTTONDOWN){
            const WORD xbtn=GET_XBUTTON_WPARAM(message.wParam);
            if(xbtn==XBUTTON1){navigateBack();return true;}
            if(xbtn==XBUTTON2){navigateForward();return true;}
        }
        if(message.message==WM_XBUTTONUP||message.message==WM_XBUTTONDBLCLK)return true;
        if(message.message==WM_APPCOMMAND){
            const short cmd=GET_APPCOMMAND_LPARAM(message.lParam);
            if(cmd==APPCOMMAND_BROWSER_BACKWARD){navigateBack();return true;}
            if(cmd==APPCOMMAND_BROWSER_FORWARD){navigateForward();return true;}
        }
    }
    if(window&&message.message==WM_MOUSEWHEEL){
        HWND host=SynthPages::host();
        HWND current=SynthPages::current();
        POINT at{GET_X_LPARAM(message.lParam),GET_Y_LPARAM(message.lParam)};
        HWND hit=WindowFromPoint(at);
        if(activePage=="blueprints"||activePage=="executive_hangar"||activePage=="roulette"||activePage=="mission_log"){
            if(current&&(hit==current||IsChild(current,hit))){SendMessageW(current,message.message,message.wParam,message.lParam);return true;}
        }
        if(host&&(hit==host||IsChild(host,hit))){
            wchar_t cls[64]{};GetClassNameW(hit,cls,64);
            bool innerScroll=false;
            if(wcscmp(cls,L"Edit")==0){
                DWORD style=GetWindowLongPtrW(hit,GWL_STYLE);
                if((style&ES_MULTILINE)&&(style&WS_VSCROLL))innerScroll=true;
            }else if(wcscmp(cls,WC_LISTVIEWW)==0){
                SCROLLINFO si{sizeof(si),SIF_RANGE|SIF_PAGE};
                if(GetScrollInfo(hit,SB_VERT,&si)&&si.nMax>=(int)si.nPage&&si.nPage>0)innerScroll=true;
            }else if(wcscmp(cls,L"ComboLBox")==0){
                innerScroll=true;
            }
            if(!innerScroll){
                SendMessageW(host,WM_MOUSEWHEEL,message.wParam,message.lParam);
                return true;
            }
        }
    }
    if(activePage=="blueprints"){
        HWND current=SynthPages::current();
        if(current&&(message.hwnd==current||IsChild(current,message.hwnd)))return false;
    }
    return window&&(message.hwnd==window||IsChild(window,message.hwnd))&&IsDialogMessage(window,&message);
}
void close(){helpHot=false;lockHot=false;dragButton=nullptr;dragActive=false;suppressNextClick=false;hideHelpTooltip();if(helpPopup)DestroyWindow(helpPopup);helpPopup=nullptr;SynthPages::close();if(window)DestroyWindow(window);window=nullptr;buttons.clear();helpRect={};}
int paintCheck(const std::filesystem::path& output){
    // Exercise the actual Home BUTTON procedures, including the erase phase
    // that a final-frame WM_PRINT screenshot cannot reveal. All HWNDs stay hidden.
    std::filesystem::create_directories(output);
    HWND foreground=GetForegroundWindow();
    INITCOMMONCONTROLSEX controls{sizeof(controls),ICC_STANDARD_CLASSES};InitCommonControlsEx(&controls);
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;Gdiplus::GdiplusStartup(&token,&input,nullptr);
    HWND fixture=CreateWindowExW(WS_EX_NOACTIVATE,L"STATIC",L"Hidden paint check",WS_POPUP,-32000,-32000,10,10,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    bool exitRouted=false;
    initialize(fixture,output,[&](const std::string& command){exitRouted=command=="exit";});create();
    SetWindowPos(window,nullptr,-32000,-32000,1240,840,SWP_NOZORDER|SWP_NOACTIVATE);
    BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=2048;info.bmiHeader.biHeight=-1024;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
    HDC dc=CreateCompatibleDC(nullptr);void* pixels=nullptr;HBITMAP bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,nullptr,0);HGDIOBJ old=SelectObject(dc,bitmap);
    RECT all{0,0,2048,1024};HBRUSH sentinel=CreateSolidBrush(RGB(241,12,219));bool eraseDark=true,bounded=true,painted=true,cornersMatch=true;
    HDC referenceDC=CreateCompatibleDC(nullptr);void* referencePixels=nullptr;HBITMAP referenceBitmap=CreateDIBSection(referenceDC,&info,DIB_RGB_COLORS,&referencePixels,nullptr,0);auto referenceOld=SelectObject(referenceDC,referenceBitmap);
    overview=obj({{"synthstrings",obj({{"title",str("Fixture")},{"patch_label",str("Star Citizen 4.10.2 · LIVE")},{"status_kind",str("info")},{"status_label",str("Game text unchanged")},{"summary",str("No action needed.")}})}});layout();
    auto sameColor=[](COLORREF a,COLORREF b){return std::abs(int(GetRValue(a))-int(GetRValue(b)))<=1&&std::abs(int(GetGValue(a))-int(GetGValue(b)))<=1&&std::abs(int(GetBValue(a))-int(GetBValue(b)))<=1;};
    int cases=0;LARGE_INTEGER start{},finish{},frequency{};QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&start);
    for(int cycle=0;cycle<12;cycle++){
        SetWindowPos(window,nullptr,0,0,cycle%2?1000:1400,cycle%2?780:980,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
        RECT root{};GetClientRect(window,&root);{Gdiplus::Graphics g(referenceDC);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);paintSurface(g,root.right,root.bottom);}GdiFlush();
        for(const auto& button:buttons){
            RECT at{};GetWindowRect(button.hwnd,&at);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&at),2);
            RECT r{};GetClientRect(button.hwnd,&r);FillRect(dc,&all,sentinel);IntersectClipRect(dc,0,0,r.right,r.bottom);
            SendMessageW(button.hwnd,WM_ERASEBKGND,reinterpret_cast<WPARAM>(dc),0);
            GdiFlush();auto erased=GetPixel(dc,2,2);eraseDark&=GetRValue(erased)<100&&GetGValue(erased)<100&&GetBValue(erased)<100;
            cornersMatch&=sameColor(GetPixel(dc,0,0),GetPixel(referenceDC,at.left,at.top));
            SelectClipRgn(dc,nullptr);bounded&=GetPixel(dc,r.right+2,2)==RGB(241,12,219);
            FillRect(dc,&all,sentinel);IntersectClipRect(dc,0,0,r.right,r.bottom);
            DRAWITEMSTRUCT item{};item.CtlType=ODT_BUTTON;item.CtlID=button.id;item.itemAction=ODA_DRAWENTIRE;item.hwndItem=button.hwnd;item.hDC=dc;item.rcItem=r;
            SendMessageW(window,WM_DRAWITEM,button.id,reinterpret_cast<LPARAM>(&item));
            GdiFlush();SelectClipRgn(dc,nullptr);
            auto corner=GetPixel(dc,2,2);painted&=GetRValue(corner)<100&&GetGValue(corner)<100&&GetBValue(corner)<100;
            bounded&=GetPixel(dc,r.right+2,2)==RGB(241,12,219);
            for(POINT corner: {POINT{0,0},POINT{r.right-1,0},POINT{0,r.bottom-1},POINT{r.right-1,r.bottom-1}})
                cornersMatch&=sameColor(GetPixel(dc,corner.x,corner.y),GetPixel(referenceDC,at.left+corner.x,at.top+corner.y));
            ++cases;
        }
    }
    // Render hidden, synthetic Home fixtures through the actual parent and
    // owner-draw procedures. No game capture, focus changes or game file writes.
    bool sidebarClean=GetDlgItem(window,116)==nullptr;
    bool screenshots=true,patchShown=patchDetails().find(L"4.10.2")!=std::wstring::npos;
    auto models=read(output/L"home_test_model.json");
    auto samples=field(models,"cases").items;
    if(samples.empty())samples.push_back(field(overview,"synthstrings"));
    const CLSID png={0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};
    for(const auto& sample:samples)for(int width:{1000,1400}){
        overview=obj({{"synthstrings",sample}});
        SetWindowPos(window,nullptr,0,0,width,width==1000?780:980,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);layout();
        RECT root{};GetClientRect(window,&root);paint(dc);
        for(const auto& button:buttons){
            if(!IsWindowVisible(button.hwnd)&&!((GetWindowLongPtrW(button.hwnd,GWL_STYLE)&WS_VISIBLE)!=0))continue;
            RECT at{},r{};GetWindowRect(button.hwnd,&at);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&at),2);GetClientRect(button.hwnd,&r);
            POINT origin{};SetViewportOrgEx(dc,at.left,at.top,&origin);
            DRAWITEMSTRUCT item{};item.CtlType=ODT_BUTTON;item.CtlID=button.id;item.itemAction=ODA_DRAWENTIRE;item.hwndItem=button.hwnd;item.hDC=dc;item.rcItem=r;
            paintButton(item);SetViewportOrgEx(dc,origin.x,origin.y,nullptr);
        }
        GdiFlush();Gdiplus::Bitmap frame(2048,1024,2048*4,PixelFormat32bppRGB,static_cast<BYTE*>(pixels));
        std::unique_ptr<Gdiplus::Bitmap> cropped(frame.Clone(0,0,root.right,root.bottom,PixelFormat32bppRGB));
        auto path=output/(L"home_"+wide(sample.textOr("status_kind","unknown"))+L"_"+std::to_wstring(width)+L".png");
        screenshots&=cropped&&cropped->Save(path.c_str(),&png,nullptr)==Gdiplus::Ok;
        write(output/(L"patch_dialog_"+wide(sample.textOr("status_kind","unknown"))+L".json"),obj({{"text",str(utf8(patchDetails()))}}));
    }
    // Verify page-help coverage, header ? badge bounds, and offscreen tooltip rendering
    bool helpVerified=SynthPageHelp::find("home")==nullptr;
    selectPage("home");
    helpVerified&=(helpRect.right==helpRect.left);
    for(const auto& b:buttons){
        if(!b.navigation||b.action=="exit"||b.action=="home")continue;
        const auto* h=SynthPageHelp::find(b.action);
        helpVerified&=(h!=nullptr&&wcslen(h->title)>0&&wcslen(h->summary)>0&&!h->tips.empty());
        if(h){
            selectPage(b.action);
            helpVerified&=(helpRect.right>helpRect.left&&helpRect.top>=0&&helpRect.bottom<=int(110*scale));
            for(int width:{1000,1400}){
                int maxW=std::max(int(320*scale),int(width*scale-int(240*scale)));
                Gdiplus::Graphics mg(dc);
                auto metrics=SynthPageHelp::measureTooltip(mg,*h,scale,maxW);
                helpVerified&=(metrics.width>0&&metrics.height>0&&metrics.height<=700);
                Gdiplus::Bitmap tipBmp(metrics.width,metrics.height,PixelFormat32bppPARGB);
                Gdiplus::Graphics tg(&tipBmp);
                SynthPageHelp::paintTooltipCard(tg,*h,metrics,scale);
                if(b.action=="planner"&&width==1400){
                    paint(dc);
                    Gdiplus::Bitmap frame(2048,1024,2048*4,PixelFormat32bppRGB,static_cast<BYTE*>(pixels));
                    RECT root{};GetClientRect(window,&root);
                    std::unique_ptr<Gdiplus::Bitmap> cropped(frame.Clone(0,0,root.right,root.bottom,PixelFormat32bppRGB));
                    screenshots&=cropped&&cropped->Save((output/L"page_help_header_planner.png").c_str(),&png,nullptr)==Gdiplus::Ok;
                    screenshots&=tipBmp.Save((output/L"page_help_tooltip_planner.png").c_str(),&png,nullptr)==Gdiplus::Ok;
                }
            }
        }
    }
    selectPage("home");
    // Verify Exit button separation, lock toggle, and sidebar drag order persistence
    bool exitBelowNav=false,lockVerified=GetDlgItem(window,118)!=nullptr;
    {
        RECT exitRect{};HWND exitBtn=GetDlgItem(window,117);
        int maxNavBottom=0;
        for(const auto& b:buttons){
            if(isDraggableNav(b)||(b.navigation&&b.action=="home")){
                RECT br{};GetWindowRect(b.hwnd,&br);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&br),2);
                maxNavBottom=std::max(maxNavBottom,int(br.bottom));
            }
        }
        if(exitBtn){
            GetWindowRect(exitBtn,&exitRect);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&exitRect),2);
            RECT root{};GetClientRect(window,&root);
            exitBelowNav=exitRect.top>=maxNavBottom+8&&exitRect.bottom<=root.bottom-int(88*scale);
        }
        std::vector<std::string> beforeOrder;
        for(const auto& b:buttons)if(isDraggableNav(b))beforeOrder.push_back(b.action);
        if(beforeOrder.size()>=2){
            int firstIdx=-1,secondIdx=-1;
            for(int i=0;i<int(buttons.size());++i)if(isDraggableNav(buttons[i])){if(firstIdx<0)firstIdx=i;else if(secondIdx<0){secondIdx=i;break;}}
            if(firstIdx>=0&&secondIdx>firstIdx){
                std::swap(buttons[firstIdx],buttons[secondIdx]);
                SendMessageW(window,WM_COMMAND,MAKEWPARAM(118,BN_CLICKED),0); // toggles navLocked=true and saves
                lockVerified&=navLocked;
                std::swap(buttons[firstIdx],buttons[secondIdx]); // scramble in memory, then reload saved order
                loadSidebarOrder();
                std::vector<std::string> afterOrder;
                for(const auto& b:buttons)if(isDraggableNav(b))afterOrder.push_back(b.action);
                lockVerified&=(afterOrder.size()==beforeOrder.size()&&afterOrder[0]==beforeOrder[1]&&afterOrder[1]==beforeOrder[0]);
                // Restore default unlocked state in fixture output
                std::swap(buttons[firstIdx],buttons[secondIdx]);
                SendMessageW(window,WM_COMMAND,MAKEWPARAM(118,BN_CLICKED),0);
                lockVerified&=!navLocked;
            }
        }
    }
    // Repeating an unchanged layout must not send another WINDOWPOSCHANGED to
    // every control. Count actual native notifications, not requested positions.
    unsigned notifications=0;
    auto count=+[](HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR data)->LRESULT{if(m==WM_WINDOWPOSCHANGED)++*reinterpret_cast<unsigned*>(data);return DefSubclassProc(h,m,w,l);};
    for(const auto& b:buttons)SetWindowSubclass(b.hwnd,count,99,reinterpret_cast<DWORD_PTR>(&notifications));
    for(int i=0;i<20;i++)layout();
    for(const auto& b:buttons)RemoveWindowSubclass(b.hwnd,count,99);
    SendMessageW(window,WM_COMMAND,MAKEWPARAM(117,BN_CLICKED),0);
    bool composited=(GetWindowLongPtrW(window,GWL_EXSTYLE)&WS_EX_COMPOSITED)!=0;
    QueryPerformanceCounter(&finish);bool focus=foreground==GetForegroundWindow();
    write(output/L"paint_validation.json",obj({{"feature_modules_removed_from_sidebar",SynthScan::boolean(sidebarClean)},{"button_corners_match_parent",SynthScan::boolean(cornersMatch)},{"patch_dialog_has_installed_patch",SynthScan::boolean(patchShown)},{"home_screenshots_saved",SynthScan::boolean(screenshots)},{"page_help_verified",SynthScan::boolean(helpVerified)},{"exit_below_nav_verified",SynthScan::boolean(exitBelowNav)},{"sidebar_order_lock_verified",SynthScan::boolean(lockVerified)},{"erase_stays_dark",SynthScan::boolean(eraseDark)},{"owner_draw_stays_in_bounds",SynthScan::boolean(bounded)},{"buttons_painted",SynthScan::boolean(painted)},{"descendants_composited",SynthScan::boolean(composited)},{"unchanged_layout_notifications",num(notifications)},{"foreground_unchanged",SynthScan::boolean(focus)},{"button_paint_cases",num(cases)},{"elapsed_ms",num((finish.QuadPart-start.QuadPart)*1000./frequency.QuadPart)}}));
    SelectObject(referenceDC,referenceOld);DeleteObject(referenceBitmap);DeleteDC(referenceDC);
    SelectObject(dc,old);DeleteObject(bitmap);DeleteObject(sentinel);DeleteDC(dc);close();DestroyWindow(fixture);Gdiplus::GdiplusShutdown(token);
    return sidebarClean&&cornersMatch&&screenshots&&patchShown&&helpVerified&&exitBelowNav&&lockVerified&&eraseDark&&bounded&&painted&&!composited&&focus&&notifications==0&&exitRouted?0:3;
}
}
