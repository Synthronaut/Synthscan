#include "SynthHome.h"
#include "SynthJson.h"
#include "resource.h"
#include "SynthPages.h"
#include "SynthGlass.h"
#include "NativeRedraw.h"
#include "HudModules.h"
#include "AppPaths.h"
#include <commctrl.h>
#include "SynthCapturePrivacy.h"
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
std::string activePage="home";
float scale=1;
const Gdiplus::Color BG(255,15,16,19),SIDE(255,19,21,25),CARD(255,24,26,30),BORDER(255,44,47,54),INK(255,238,239,241),MUTED(255,160,166,176),ACCENT(255,98,204,255);
struct Button {HWND hwnd;int id;std::wstring label;std::string action;bool navigation;};
std::vector<Button> buttons;
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
void layout(){
    if(!window)return;RECT r{};GetClientRect(window,&r);
    scale=std::max(.7f,std::min(float(GetDpiForWindow(window))/96.f,std::min(r.right/900.f,r.bottom/760.f)));
    int tiles=int(std::count_if(buttons.begin(),buttons.end(),[](const auto& b){return b.id>=200&&b.id<=203;})),tileAt=0;
    float width=r.right/scale,main=width-248,gap=12,tile=(main-std::max(0,tiles-1)*gap)/std::max(1,tiles);
    int nav=0;int navCount=int(std::count_if(buttons.begin(),buttons.end(),[](const auto& b){return b.navigation;}));
    float navStep=std::min(39.f,(r.bottom/scale-198.f)/std::max(1,navCount));
    NativeRedraw::Layout pending(window);
    for(auto& b:buttons){
        float x=16,y=110+nav*navStep,w=170,h=std::min(34.f,navStep-4);
        if(b.navigation)nav++;
        else if(b.id>=200&&b.id<=203){x=224+(tileAt++)*(tile+gap);y=119;w=tile;h=82;}
        else if(b.id==210||b.id==211){w=136;h=30;x=width-302+(b.id-210)*142;y=234;}
        else if(b.id==212){x=width-192;y=622;w=166;h=30;}
        else if(b.id==213){x=width-160;y=686;w=134;h=28;}
        else if(b.id==214){x=width-306;y=686;w=134;h=28;}
        const bool hasNotice=(b.id!=212||!overview.textOr("refinery_notice").empty())&&
            ((b.id!=213&&b.id!=214)||(available("strings_settings")&&!field(overview,"synthstrings").textOr("title").empty()));
        pending.place(b.hwnd,int(x*scale),int(y*scale),int(w*scale),int(h*scale),b.navigation||(activePage=="home"&&hasNotice));
    }
    pending.apply();
    SynthPages::place(int(218*scale),int(110*scale),int((width-234)*scale),std::max(1,int(r.bottom)-int(124*scale)),activePage!="home");
}
// Paint the same surface in parent and child coordinates. A flat child clear
// leaves visible square corners around translucent rounded buttons.
void paintSurface(Gdiplus::Graphics& g,int widthPixels,int heightPixels){
    g.Clear(BG);SynthGlass::ambient(g,{0,0,float(widthPixels),float(heightPixels)});
    float width=widthPixels/scale,height=heightPixels/scale,main=width-248,col=(main-16)/2;
    Gdiplus::SolidBrush side(SIDE);g.FillRectangle(&side,0.f,0.f,200*scale,float(heightPixels));
    SynthGlass::panel(g,{12*scale,14*scale,188*scale,float(heightPixels)-28*scale},false,false,18*scale);
    if(activePage!="home")return;
    for(int i=0;i<3;i++)rounded(g,{(224+i*(main+12)/3)*scale,282*scale,(main-24)/3*scale,72*scale},CARD);
    rounded(g,{224*scale,371*scale,col*scale,220*scale},CARD);
    rounded(g,{(240+col)*scale,371*scale,col*scale,220*scale},CARD);
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
    if(m==WM_MOUSEMOVE&&!GetPropW(hwnd,L"SynthGlass.Hot")){SetPropW(hwnd,L"SynthGlass.Hot",HANDLE(1));TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);InvalidateRect(hwnd,nullptr,FALSE);}
    if(m==WM_MOUSELEAVE){RemovePropW(hwnd,L"SynthGlass.Hot");InvalidateRect(hwnd,nullptr,FALSE);}
    if(m==WM_NCDESTROY){RemovePropW(hwnd,L"SynthGlass.Hot");RemoveWindowSubclass(hwnd,navigationHover,1);}
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
    bool selected=(b.navigation&&b.action==activePage)||(b.id==210&&!previous)||(b.id==211&&previous);
    buttonSurface(g,item.hwndItem);
    Gdiplus::RectF r(0,0,float(item.rcItem.right),float(item.rcItem.bottom));
    bool hot=(item.itemState&ODS_HOTLIGHT)!=0||GetPropW(item.hwndItem,L"SynthGlass.Hot")!=nullptr;
    if(!b.navigation||selected||hot)SynthGlass::panel(g,{1,1,r.Width-2,r.Height-2},selected,hot||bool(item.itemState&ODS_SELECTED),9*scale);
    const bool tile=b.id>=200&&b.id<=203;
    std::wstring label=b.label;auto cut=label.find(L'\n');
    if(b.navigation){SynthGlass::rounded(g,{8*scale,(r.Height-24*scale)/2,24*scale,24*scale},Gdiplus::Color(38,154,185,206),7*scale);SynthGlass::icon(g,b.action,{12*scale,(r.Height-16*scale)/2,16*scale,16*scale},selected?SynthGlass::Accent:SynthGlass::Muted);
        SynthGlass::text(g,label,{40*scale,0,r.Width-47*scale,r.Height},11.5f*scale,selected?SynthGlass::Ink:SynthGlass::Muted,selected);
    }else if(tile)words(g,label.substr(0,cut),16,16,r.Width/scale-28,26,15,INK,true);
    else SynthGlass::text(g,label,{12*scale,0,r.Width-24*scale,r.Height},12*scale,INK,true);
    if(cut!=std::wstring::npos)words(g,label.substr(cut+1),16,45,r.Width/scale-28,28,11,MUTED);
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
        words(g,L"LOCAL PROFILE",24,height-66,164,20,9,ACCENT,true);
        words(g,L"Your records stay on this PC",24,height-45,166,30,10,MUTED);
        std::wstring heading=L"Home";
        for(const auto& button:buttons)if(button.navigation&&button.action==activePage)heading=button.label;
        words(g,heading,224,30,main,40,29,INK,true);
        words(g,activePage=="home"?L"Find your next upgrade. See what you've accomplished.":activePage=="people"?L"A familiar face in a very large universe.":activePage=="executive_hangar"?L"Watch the window. Keep your next full set ready.":L"",224,76,main,28,13,MUTED);
        if(activePage=="home"){
        words(g,L"SESSION RECAP",224,241,main-300,24,11,ACCENT,true);
        const Json& session=field(overview,previous?"previous":"current");
        const auto& blueprints=field(session,"blueprints").items;const auto& rep=field(session,"reputation").items;
        for(int i=0;i<3;i++){
            float x=224+i*(main+12)/3,w=(main-24)/3;
            auto count=i==0?number(double(blueprints.size())):i==1?number(session.numberOr("contracts_completed")):number(double(rep.size()));
            words(g,count,x+15,290,w-30,33,25,INK,true);
            words(g,i==0?L"Blueprints received":i==1?L"Contracts completed":L"Reputation changes",x+15,327,w-30,20,11,MUTED);
        }
        words(g,L"Blueprints received",240,387,col-32,26,14,INK,true);
        words(g,L"Reputation balance changes",256+col,387,col-32,26,14,INK,true);
        auto baseline=clockLabel(session.numberOr("rep_baseline_at"));
        auto checked=clockLabel(session.numberOr("rep_checked_at"));
        if(!baseline.empty())words(g,L"Baseline "+baseline+L" · last read "+checked,256+col,411,col-32,18,10,MUTED);
        const bool reputationAvailable=available("strings_settings")||available("mission_log");
        words(g,reputationAvailable?L"Account balances · checks about every 30s while playing":L"Saved account balance changes",256+col,430,col-32,18,10,MUTED);
        if(blueprints.empty())words(g,session.kind==Json::Kind::Null?L"No saved session yet. Play normally to build your recap.":L"No blueprint grants recorded in this session.",240,432,col-32,68,12,MUTED);
        for(size_t i=0;i<std::min(size_t(6),blueprints.size());i++)words(g,wide(blueprints[i].textOr("name")),240,428+23*float(i),col-32,23,12,INK);
        if(blueprints.size()>6)words(g,L"+ "+std::to_wstring(blueprints.size()-6)+(available("blueprints")?L" more · open Blueprint library":L" more saved grants"),240,568,col-32,18,10,ACCENT);
        if(rep.empty())words(g,session.numberOr("rep_checked_at")>0?L"No balance changes between the saved reads.":!reputationAvailable?L"No saved balance changes. Your retained records stay available here.":L"Waiting for verified reputation balances. Mission payouts aren't treated as confirmed gains.",256+col,453,col-32,85,12,MUTED);
        for(size_t i=0;i<std::min(size_t(4),rep.size());i++){
            const auto& change=rep[i];float y=453+32*float(i);
            auto delta=change.numberOr("delta");auto label=wide(change.textOr("faction"))+L"  "+(delta>0?L"+":L"")+number(delta);
            words(g,label,256+col,y,col-32,22,12,delta>0?ACCENT:INK,true);
            auto scope=wide(change.textOr("scope"));if(flag(change,"standing_changed"))scope+=L" · standing changed";
            words(g,scope+L" · "+number(change.numberOr("before"))+L" → "+number(change.numberOr("after")),256+col,y+17,col-32,18,10,MUTED);
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
    if(message==WM_SIZE){layout();InvalidateRect(hwnd,nullptr,FALSE);return 0;}
    if(message==WM_ERASEBKGND){RECT r{};GetClientRect(hwnd,&r);static HBRUSH surface=CreateSolidBrush(RGB(15,16,19));FillRect(reinterpret_cast<HDC>(w),&r,surface);return 1;}
    if(message==WM_DRAWITEM){paintButton(*reinterpret_cast<DRAWITEMSTRUCT*>(l));return TRUE;}
    if(message==WM_COMMAND&&HIWORD(w)==BN_CLICKED){
        int id=LOWORD(w);
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
    if(message==WM_CLOSE){ShowWindow(hwnd,SW_HIDE);publish();return 0;}
    if(message==WM_DPICHANGED){auto r=reinterpret_cast<RECT*>(l);SetWindowPos(hwnd,nullptr,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER|SWP_NOACTIVATE);layout();return 0;}
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
    const wchar_t* names[]={L"Home",L"Item & Ship Finder",L"People",L"Mission & Wallet Log",L"Server History",L"Blueprint Library",L"Mining Planner",L"Mining Diary",L"Refinery",L"Executive Hangar",L"Piracy",L"Day/Night Forecast",L"Automatic Acceptance",L"Settings"};
    const char* actions[]={"home","directory","people","mission_log","servers","blueprints","planner","diary","refinery","executive_hangar","hud_piracy","daylight","acceptance","settings"};
    for(int i=0;i<int(sizeof(names)/sizeof(names[0]));i++)add(i==13?114:100+i,names[i],actions[i],true);
    add(200,L"Mining HUD\nAutomatic scan reading","hud_mining",false);add(201,L"Finder HUD\nShops & player market","hud_finder",false);
    add(202,L"Missions HUD\nContracts & reputation","hud_missions",false);add(203,L"Hangars HUD\nContested-zone timing","hud_hangars",false);
    add(210,L"This session","this",false);add(211,L"Previous session","previous",false);add(212,L"Dismiss notices","dismiss_refinery",false);
    add(213,L"Patch status","strings_details",false);
    add(214,L"Text settings","strings_settings",false);
    add(117,L"Exit SynthScan","exit",true);
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
void hide(){if(window){ShowWindow(window,SW_HIDE);publish();}}
HWND pageHost(){create();return SynthPages::host();}
void selectPage(const std::string& name){
    std::string previousPage=activePage;
    activePage=name;
    if(activePage=="home")SynthPages::hide();
    else SynthPages::advanceGeneration();
    if(window){
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
    SynthPages::beginTransition();selectPage(destination=="bookmarks"?"diary":destination);
    if(destination!="home"&&action)action(destination);
    SynthPages::endTransition();publish();
}
std::string selectedPage(){return activePage;}
bool visible(){return window&&IsWindowVisible(window);}
bool active(){return visible()&&GetAncestor(GetForegroundWindow(),GA_ROOT)==window;}
bool routeMessage(MSG& message){
    if(window&&message.message==WM_MOUSEWHEEL&&activePage=="blueprints"){
        HWND page=SynthPages::current();POINT at{GET_X_LPARAM(message.lParam),GET_Y_LPARAM(message.lParam)};
        // Wheel ownership follows the hovered recipe, not the last focused
        // sidebar button. Its own handler chooses sources versus page scroll.
        if(page&&WindowFromPoint(at)==page){SendMessageW(page,message.message,message.wParam,message.lParam);return true;}
    }
    return window&&(message.hwnd==window||IsChild(window,message.hwnd))&&IsDialogMessage(window,&message);
}
void close(){SynthPages::close();if(window)DestroyWindow(window);window=nullptr;buttons.clear();}
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
    write(output/L"paint_validation.json",obj({{"feature_modules_removed_from_sidebar",SynthScan::boolean(sidebarClean)},{"button_corners_match_parent",SynthScan::boolean(cornersMatch)},{"patch_dialog_has_installed_patch",SynthScan::boolean(patchShown)},{"home_screenshots_saved",SynthScan::boolean(screenshots)},{"erase_stays_dark",SynthScan::boolean(eraseDark)},{"owner_draw_stays_in_bounds",SynthScan::boolean(bounded)},{"buttons_painted",SynthScan::boolean(painted)},{"descendants_composited",SynthScan::boolean(composited)},{"unchanged_layout_notifications",num(notifications)},{"foreground_unchanged",SynthScan::boolean(focus)},{"button_paint_cases",num(cases)},{"elapsed_ms",num((finish.QuadPart-start.QuadPart)*1000./frequency.QuadPart)}}));
    SelectObject(referenceDC,referenceOld);DeleteObject(referenceBitmap);DeleteDC(referenceDC);
    SelectObject(dc,old);DeleteObject(bitmap);DeleteObject(sentinel);DeleteDC(dc);close();DestroyWindow(fixture);Gdiplus::GdiplusShutdown(token);
    return sidebarClean&&cornersMatch&&screenshots&&patchShown&&eraseDark&&bounded&&painted&&!composited&&focus&&notifications==0&&exitRouted?0:3;
}
}
