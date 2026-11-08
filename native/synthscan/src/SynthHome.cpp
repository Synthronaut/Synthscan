#include "SynthHome.h"
#include "SynthJson.h"
#include "resource.h"
#include <gdiplus.h>
#include <dwmapi.h>
#include <algorithm>
#include <memory>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <windowsx.h>

namespace SynthHome {
namespace {
using namespace SynthScan;
HWND window=nullptr,owner=nullptr;std::filesystem::path directory;
std::function<void(const std::string&)> action;
Json overview;std::string identity,lastAction;bool connected=false,previous=false,sessionChosen=false;
float scale=1;
const Gdiplus::Color BG(255,15,16,19),SIDE(255,19,21,25),CARD(255,24,26,30),BORDER(255,44,47,54),INK(255,238,239,241),MUTED(255,160,166,176),ACCENT(255,238,178,70);
struct Button {HWND hwnd;int id;std::wstring label;std::string action;bool navigation;};
std::vector<Button> buttons;
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
        {"left",num(r.left)},{"top",num(r.top)},{"right",num(r.right)},{"bottom",num(r.bottom)}}));
}
void layout(){
    if(!window)return;RECT r{};GetClientRect(window,&r);
    scale=std::max(.7f,std::min(float(GetDpiForWindow(window))/96.f,std::min(r.right/900.f,r.bottom/760.f)));
    float width=r.right/scale,main=width-248,gap=12,tile=(main-3*gap)/4;
    int nav=0;
    for(auto& b:buttons){
        float x=16,y=110+nav*39,w=170,h=34;
        if(b.navigation)nav++;
        else if(b.id>=200&&b.id<=203){x=224+(b.id-200)*(tile+gap);y=119;w=tile;h=82;}
        else if(b.id==210||b.id==211){w=114;h=30;x=width-264+(b.id-210)*120;y=234;}
        else if(b.id==212){x=width-192;y=622;w=166;h=30;}
        MoveWindow(b.hwnd,int(x*scale),int(y*scale),int(w*scale),int(h*scale),TRUE);
    }
    InvalidateRect(window,nullptr,FALSE);
}
void add(int id,const wchar_t* label,const char* command,bool navigation){
    HWND child=CreateWindowExW(0,L"BUTTON",label,WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_OWNERDRAW,0,0,10,10,window,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    buttons.push_back({child,id,label,command,navigation});
}
void paintButton(const DRAWITEMSTRUCT& item){
    auto found=std::find_if(buttons.begin(),buttons.end(),[&](const auto& b){return b.id==int(item.CtlID);});if(found==buttons.end())return;
    const auto& b=*found;Gdiplus::Graphics g(item.hDC);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
    bool selected=b.id==100||(b.id==210&&!previous)||(b.id==211&&previous);
    g.Clear(b.navigation?SIDE:BG);Gdiplus::RectF r(0,0,float(item.rcItem.right),float(item.rcItem.bottom));
    rounded(g,r,(item.itemState&ODS_SELECTED)?Gdiplus::Color(255,58,50,34):selected?Gdiplus::Color(255,43,38,29):CARD,7);
    if(b.navigation&&selected)rounded(g,{0,7*scale,3*scale,r.Height-14*scale},ACCENT,1);
    const bool tile=b.id>=200&&b.id<=203;
    std::wstring label=b.label;auto cut=label.find(L'\n');
    words(g,label.substr(0,cut),tile?16:14,tile?16:8,r.Width/scale-28,26,tile?15:12,selected||tile?ACCENT:INK,true);
    if(cut!=std::wstring::npos)words(g,label.substr(cut+1),16,45,r.Width/scale-28,28,11,MUTED);
    if(item.itemState&ODS_FOCUS){Gdiplus::Pen pen(ACCENT);g.DrawRectangle(&pen,2.f,2.f,r.Width-5,r.Height-5);}
}
void paint(){
    PAINTSTRUCT ps{};HDC dc=BeginPaint(window,&ps);RECT r{};GetClientRect(window,&r);
    if(r.right>0&&r.bottom>0){
        Gdiplus::Bitmap bitmap(r.right,r.bottom,PixelFormat32bppPARGB);Gdiplus::Graphics g(&bitmap);g.Clear(BG);
        g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
        float width=r.right/scale,height=r.bottom/scale,main=width-248,col=(main-16)/2;
        Gdiplus::SolidBrush side(SIDE);g.FillRectangle(&side,0.f,0.f,200*scale,float(r.bottom));
        rounded(g,{24*scale,29*scale,32*scale,32*scale},ACCENT,8);
        words(g,L"S",33,30,24,30,21,BG,true);words(g,L"SynthScan",66,29,130,31,20,INK,true);
        words(g,L"YOUR VERSE, CONNECTED",24,73,164,20,9,MUTED,true);
        words(g,L"LOCAL PROFILE",24,height-66,164,20,9,ACCENT,true);
        words(g,L"Your records stay on this PC",24,height-45,166,30,10,MUTED);
        words(g,L"Home",224,30,main,40,29,INK,true);
        words(g,L"Find your next upgrade. See what you've accomplished.",224,76,main,28,13,MUTED);
        words(g,L"SESSION RECAP",224,241,main-260,24,11,ACCENT,true);
        const Json& session=field(overview,previous?"previous":"current");
        const auto& blueprints=field(session,"blueprints").items;const auto& rep=field(session,"reputation").items;
        for(int i=0;i<3;i++){
            float x=224+i*(main+12)/3,w=(main-24)/3;
            rounded(g,{x*scale,282*scale,w*scale,72*scale},CARD);
            auto count=i==0?number(double(blueprints.size())):i==1?number(session.numberOr("contracts_completed")):number(double(rep.size()));
            words(g,count,x+15,290,w-30,33,25,INK,true);
            words(g,i==0?L"Blueprints received":i==1?L"Contracts completed":L"Reputation changes",x+15,327,w-30,20,11,MUTED);
        }
        rounded(g,{224*scale,371*scale,col*scale,220*scale},CARD);
        rounded(g,{(240+col)*scale,371*scale,col*scale,220*scale},CARD);
        words(g,L"Blueprints received",240,387,col-32,26,14,INK,true);
        words(g,L"Observed reputation changes",256+col,387,col-32,26,14,INK,true);
        auto baseline=clockLabel(session.numberOr("rep_baseline_at"));
        if(!baseline.empty())words(g,L"Verified baseline · "+baseline,256+col,411,col-32,18,10,MUTED);
        if(blueprints.empty())words(g,session.kind==Json::Kind::Null?L"No saved session yet. Play normally to build your recap.":L"No blueprint grants recorded in this session.",240,432,col-32,68,12,MUTED);
        for(size_t i=0;i<std::min(size_t(6),blueprints.size());i++)words(g,wide(blueprints[i].textOr("name")),240,428+23*float(i),col-32,23,12,INK);
        if(blueprints.size()>6)words(g,L"+ "+std::to_wstring(blueprints.size()-6)+L" more · open Blueprint library",240,568,col-32,18,10,ACCENT);
        if(rep.empty())words(g,session.numberOr("rep_checked_at")>0?L"No balance changes since this session's first verified read.":L"Waiting for verified reputation balances. Mission payouts aren't treated as confirmed gains.",256+col,432,col-32,85,12,MUTED);
        for(size_t i=0;i<std::min(size_t(4),rep.size());i++){
            const auto& change=rep[i];float y=437+37*float(i);
            auto delta=change.numberOr("delta");auto label=wide(change.textOr("faction"))+L"  "+(delta>0?L"+":L"")+number(delta);
            words(g,label,256+col,y,col-32,22,12,delta>0?ACCENT:INK,true);
            auto scope=wide(change.textOr("scope"));if(flag(change,"standing_changed"))scope+=L" · standing changed";
            words(g,scope,256+col,y+19,col-32,18,10,MUTED);
        }
        rounded(g,{224*scale,609*scale,main*scale,59*scale},CARD);
        auto notice=overview.textOr("refinery_notice");
        words(g,notice.empty()?L"Refinery reminders":wide(notice),240,621,main-200,23,13,notice.empty()?INK:ACCENT,true);
        words(g,notice.empty()?L"Completed-order notifications appear here and in the Mining HUD.":L"Confirmed game notification · dismiss after reviewing your orders",240,645,main-200,19,10,MUTED);
        words(g,connected?wide(identity):L"No live shard observation",224,690,main,22,11,connected?INK:MUTED);
        words(g,flag(overview,"history_warning")?L"Saved recap could not be read. The original file has been preserved.":L"Recap includes logged grants and completions; reputation is measured between verified reads.",224,716,main,28,10,MUTED);
        Gdiplus::Graphics screen(dc);screen.DrawImage(&bitmap,0,0);
    }EndPaint(window,&ps);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    if(message==WM_PAINT){paint();return 0;}
    if(message==WM_SIZE){layout();return 0;}
    if(message==WM_ERASEBKGND)return 1;
    if(message==WM_DRAWITEM){paintButton(*reinterpret_cast<DRAWITEMSTRUCT*>(l));return TRUE;}
    if(message==WM_COMMAND&&HIWORD(w)==BN_CLICKED){
        int id=LOWORD(w);
        if(id==210||id==211){previous=id==211;sessionChosen=true;InvalidateRect(hwnd,nullptr,FALSE);for(auto& b:buttons)InvalidateRect(b.hwnd,nullptr,FALSE);publish();return 0;}
        auto found=std::find_if(buttons.begin(),buttons.end(),[&](const auto& b){return b.id==id;});
        if(found!=buttons.end()&&found->action!="home"){lastAction=found->action;publish();if(action)action(lastAction);}return 0;
    }
    if(message==WM_CLOSE){ShowWindow(hwnd,SW_HIDE);publish();return 0;}
    if(message==WM_DPICHANGED){auto r=reinterpret_cast<RECT*>(l);SetWindowPos(hwnd,nullptr,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER|SWP_NOACTIVATE);layout();return 0;}
    if(message==WM_EXITSIZEMOVE)publish();
    return DefWindowProcW(hwnd,message,w,l);
}
void create(){
    if(window)return;WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanHome";cls.lpfnWndProc=procedure;cls.hCursor=LoadCursor(nullptr,IDC_ARROW);cls.hIcon=LoadIconW(cls.hInstance,MAKEINTRESOURCEW(IDI_APPICON));RegisterClassW(&cls);
    MONITORINFO info{sizeof(info)};GetMonitorInfo(MonitorFromWindow(owner,MONITOR_DEFAULTTONEAREST),&info);
    float dpi=GetDpiForWindow(owner)/96.f;int width=std::min(int(1060*dpi),int(info.rcWork.right-info.rcWork.left)-48),height=std::min(int(800*dpi),int(info.rcWork.bottom-info.rcWork.top)-48);
    window=CreateWindowExW(WS_EX_APPWINDOW|WS_EX_CONTROLPARENT,cls.lpszClassName,L"SynthScan — Home",WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,
        info.rcWork.left+(info.rcWork.right-info.rcWork.left-width)/2,info.rcWork.top+(info.rcWork.bottom-info.rcWork.top-height)/2,width,height,owner,nullptr,cls.hInstance,nullptr);
    BOOL dark=TRUE;DwmSetWindowAttribute(window,20,&dark,sizeof(dark));
    const wchar_t* names[]={L"Home",L"Mining",L"Item & ship finder",L"Blueprint library",L"Refinery orders",L"Mining planner",L"Piracy HUD",L"Server history",L"Mining diary",L"Personal notes",L"Rock bookmarks",L"Daylight",L"Automatic acceptance",L"Settings"};
    const char* actions[]={"home","mining","directory","blueprints","refinery","planner","hud_piracy","servers","diary","notes","bookmarks","daylight","acceptance","settings"};
    for(int i=0;i<int(sizeof(names)/sizeof(names[0]));i++)add(100+i,names[i],actions[i],true);
    add(200,L"Mining HUD\nAutomatic scan reading","hud_mining",false);add(201,L"Finder HUD\nShops & player market","hud_finder",false);
    add(202,L"Missions HUD\nContracts & reputation","hud_missions",false);add(203,L"Hangars HUD\nContested-zone timing","hud_hangars",false);
    add(210,L"This session","this",false);add(211,L"Previous session","previous",false);add(212,L"Dismiss notices","dismiss_refinery",false);
    layout();
}
}
void initialize(HWND parent,const std::filesystem::path& data,std::function<void(const std::string&)> callback){owner=parent;directory=data;action=std::move(callback);}
void update(const SCMiner::JsonValue& value,const std::string& label,bool live){
    bool changed=encode(value)!=encode(overview)||identity!=label||connected!=live;
    overview=value;identity=label;connected=live;
    if(!sessionChosen&&value.kind==Json::Kind::Object){
        const auto& current=field(value,"current");
        previous=field(value,"previous").kind==Json::Kind::Object&&field(current,"blueprints").items.empty()&&field(current,"reputation").items.empty()&&current.numberOr("contracts_completed")==0;
        sessionChosen=true;
    }
    if(window&&changed){InvalidateRect(window,nullptr,FALSE);for(auto& b:buttons)if(b.id==210||b.id==211)InvalidateRect(b.hwnd,nullptr,FALSE);publish();}
}
void show(){create();ShowWindow(window,SW_SHOW);ShowWindow(window,SW_RESTORE);SetForegroundWindow(window);publish();}
void hide(){if(window){ShowWindow(window,SW_HIDE);publish();}}
bool visible(){return window&&IsWindowVisible(window);}
bool routeMessage(MSG& message){return window&&(message.hwnd==window||IsChild(window,message.hwnd))&&IsDialogMessage(window,&message);}
void close(){if(window)DestroyWindow(window);window=nullptr;buttons.clear();}
}
