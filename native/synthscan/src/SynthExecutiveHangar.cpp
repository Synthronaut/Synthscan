#include "SynthExecutiveHangar.h"
#include "SynthJson.h"
#include "SynthGlass.h"
#include "SynthPages.h"
#include "NativeRedraw.h"
#include <commctrl.h>
#include <windowsx.h>
#include <chrono>
#include <algorithm>
#include <cmath>
#include <uxtheme.h>

namespace SynthExecutiveHangar { namespace {
using namespace SynthScan;
using namespace Gdiplus;
HWND page=nullptr;
Json inventory,timing;std::function<bool(Json)> send;
bool busy=false;
std::string note;float scale=1;int scroll=0,contentHeight=0;
const Color Blue(255,98,204,255),Green(255,125,211,174);
double epoch(){return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
bool fresh(const Json& value){return value.numberOr("owner_pid")==GetCurrentProcessId()&&epoch()-value.numberOr("at")>=0&&epoch()-value.numberOr("at")<4;}
bool ready(){return fresh(inventory)&&!flag(inventory,"unavailable")&&field(inventory,"counts").items.size()==7;}
struct Layout {float width;bool wide;RectF hero,boards,ships;float bottom;};
Layout geometry(float width){
    // The timer always owns the full width; no narrow card beside a wide table.
    bool wide=width>=850;
    RectF hero(18,52,width-36,wide?304.f:326.f);
    RectF boards(18,hero.GetBottom()+18,width-36,386);
    RectF ships(18,boards.GetBottom()+18,width-36,404);
    return {width,wide,hero,boards,ships,ships.GetBottom()+54};
}
RectF controlRect(int id,const Layout& l){
    if(id==600)return {l.width-166,5,148,32};
    return {l.width-324,5,146,32};
}
const wchar_t* caption(int id){return id==600?L"Open Hangars HUD":L"Refresh timing";}
void updateControls(){}
void layout(){
    if(!page)return;RECT client{};GetClientRect(page,&client);scale=std::max(.7f,GetDpiForWindow(page)/96.f);
    auto l=geometry(client.right/scale);contentHeight=int(l.bottom*scale);
    scroll=std::clamp(scroll,0,std::max(0,contentHeight-int(client.bottom)));
    SCROLLINFO si{sizeof(si),SIF_RANGE|SIF_PAGE|SIF_POS,0,std::max(0,contentHeight-1),UINT(client.bottom),scroll};SetScrollInfo(page,SB_VERT,&si,TRUE);
    NativeRedraw::Layout move(page);
    auto place=[&](int id){auto r=controlRect(id,l);move.place(GetDlgItem(page,id),int(r.X*scale),int(r.Y*scale)-scroll,int(r.Width*scale),int(r.Height*scale),true);};
    place(600);place(601);move.apply();
}
void act(int id){
    if(!send)return;
    if(id==600||id==601){send(obj({{"action",str(id==600?"open_hud":"refresh_timing")}}));}
}
void centerText(Graphics& g,const std::wstring& value,RectF r,float size,Color color,bool bold=false,const wchar_t* family=L"Segoe UI"){
    Font font(family,size,bold?FontStyleBold:FontStyleRegular,UnitPixel);SolidBrush brush(color);
    StringFormat format;format.SetAlignment(StringAlignmentCenter);format.SetLineAlignment(StringAlignmentCenter);format.SetFormatFlags(StringFormatFlagsNoWrap);
    g.DrawString(value.c_str(),-1,&font,r,&format,&brush);
}
void paintButton(Graphics& g,RectF r,int id,bool hot=false,bool down=false,bool disabled=false,bool focus=false){
    SynthGlass::button(g,r,caption(id),"",hot,down,disabled);
    if(focus)SynthGlass::rounded(g,{r.X+2,r.Y+2,r.Width-4,r.Height-4},Color(0,0,0,0),7,Blue);
}
void paintContent(Graphics& g,const Layout& l){
    auto hero=l.hero,boards=l.boards;const bool known=fresh(timing);const auto& view=field(timing,"view");const auto& verification=field(timing,"verification");
    std::string phase=known?view.textOr("phase"):"waiting";bool synced=known&&flag(verification,"community_synced");
    SynthGlass::text(g,L"YOUR CONTESTED-ZONE FLIGHT PLAN",{18,5,std::max(100.f,l.width-360),32},10,SynthGlass::Muted);
    SynthGlass::panel(g,hero,false,false,18);
    auto saved=g.Save();GraphicsPath clip;SynthGlass::shape(clip,hero,18);g.SetClip(&clip);
    GraphicsPath halo;halo.AddEllipse(hero.X+hero.Width*.3f,hero.Y-210,hero.Width,600.f);PathGradientBrush glow(&halo);glow.SetCenterColor(Color(35,53,156,224));Color edge(0,53,156,224);int n=1;glow.SetSurroundColors(&edge,&n);g.FillPath(&glow,&halo);
    Pen grid(Color(10,98,204,255),1);for(float x=hero.X+24;x<hero.GetRight();x+=48)g.DrawLine(&grid,x,hero.Y,x,hero.GetBottom());
    Pen rail(Color(150,98,204,255),2);g.DrawLine(&rail,hero.X+28,hero.Y+1,hero.X+148,hero.Y+1);g.Restore(saved);
    float timerWidth=hero.Width-(l.wide?308.f:40.f);float timerX=hero.X+20;
    SynthGlass::icon(g,"executive_hangar",{hero.X+26,hero.Y+22,24,24},Blue);
    SynthGlass::text(g,L"PYAM / EXECUTIVE HANGAR",{hero.X+60,hero.Y+22,hero.Width-250,24},11,Blue,true);
    SynthGlass::rounded(g,{hero.GetRight()-174,hero.Y+22,148,24},synced?Color(25,125,211,174):Color(25,98,204,255),7);
    centerText(g,synced?L"COMMUNITY SYNC":L"TIMING UNVERIFIED",{hero.GetRight()-174,hero.Y+22,148,24},9,synced?Green:Blue,true);
    std::wstring status=phase=="open"?L"HANGAR OPEN / WINDOW CLOSES IN":phase=="charging"?L"POWER CELLS CHARGING / NEXT OPENING IN":phase=="reset"?L"POWER CYCLE RESET / NEXT CHANGE IN":L"WAITING FOR A VERIFIED SCHEDULE";
    centerText(g,status,{timerX,hero.Y+73,timerWidth,22},10,SynthGlass::Muted,true);
    double remaining=known?std::max(0.,view.numberOr("remaining_ms")/1000.-std::max(0.,epoch()-timing.numberOr("at"))):0;
    int seconds=int(std::ceil(remaining));wchar_t digits[48]{};swprintf_s(digits,L"%02d:%02d:%02d",seconds/3600,(seconds/60)%60,seconds%60);
    std::wstring clock=known&&view.kind==Json::Kind::Object?digits:L"--:--:--";
    float fontSize=std::clamp(timerWidth/5.35f,48.f,112.f);
    // Fixed-width digits keep the countdown steady as individual seconds change.
    centerText(g,clock,{timerX,hero.Y+99,timerWidth,132},fontSize,Color(16,98,204,255),true,L"Consolas");
    centerText(g,clock,{timerX,hero.Y+96,timerWidth,132},fontSize,SynthGlass::Ink,true,L"Consolas");
    float clockWidth=fontSize*.602f*8,clockLeft=timerX+(timerWidth-clockWidth)/2;
    for(int i=0;i<3;++i)centerText(g,i==0?L"HOURS":i==1?L"MINUTES":L"SECONDS",{clockLeft+fontSize*.602f*(i*3),hero.Y+218,fontSize*1.204f,22},9,Blue,true);
    const auto& lights=field(view,"lights").items;int charged=0;
    for(const auto& light:lights)charged+=light.text=="green";
    if(l.wide){
        float cx=hero.GetRight()-144,cy=hero.Y+168;Pen outline(Color(24,98,204,255),1);g.DrawEllipse(&outline,cx-106,cy-106,212.f,212.f);
        for(int i=0;i<5;++i){std::string light=known&&lights.size()==5?lights[i].text:"empty";Color color=light=="green"?Green:light=="red"?Color(255,215,131,145):Color(255,48,65,82);
            Pen track(Color(80,color.GetR(),color.GetG(),color.GetB()),11),segment(Color(synced?255:165,color.GetR(),color.GetG(),color.GetB()),5);
            g.DrawArc(&track,cx-85,cy-85,170.f,170.f,float(-84+i*72),60.f);g.DrawArc(&segment,cx-85,cy-85,170.f,170.f,float(-84+i*72),60.f);
        }
        centerText(g,known?std::to_wstring(charged)+L" / 5":L"-- / 5",{cx-75,cy-41,150,60},38,SynthGlass::Ink,true,L"Consolas");
        centerText(g,L"POWER CELLS",{cx-90,cy+18,180,25},10,Blue,true);
        SynthGlass::text(g,wide(verification.textOr("reason","Reset events can change the schedule.")),{timerX+12,hero.GetBottom()-40,timerWidth-24,24},10,SynthGlass::Muted);
    }else{
        float x=hero.X+(hero.Width-220)/2;
        for(int i=0;i<5;++i){std::string light=known&&lights.size()==5?lights[i].text:"empty";Color color=light=="green"?Green:light=="red"?Color(255,215,131,145):Color(255,48,65,82);
            SynthGlass::rounded(g,{x+i*46,hero.Y+268,36,7},Color(synced?255:165,color.GetR(),color.GetG(),color.GetB()),3);
        }
        centerText(g,L"POWER CELLS",{hero.X+20,hero.Y+288,hero.Width-40,20},9,SynthGlass::Muted,true);
    }
    SynthGlass::panel(g,boards,false,false,18);
    SynthGlass::text(g,L"Comp board inventory",{boards.X+20,boards.Y+14,boards.Width-190,30},17,SynthGlass::Ink,true);
    bool autoSynced=ready()&&flag(inventory,"auto_synced");
    SynthGlass::text(g,autoSynced?L"Auto-detected from live Knick-Knacks storage":L"Syncs automatically from your Star Citizen storage",{boards.X+20,boards.Y+44,boards.Width-40,21},10,SynthGlass::Muted);
    int sets=ready()?int(inventory.numberOr("complete_sets")):0;
    SynthGlass::rounded(g,{boards.GetRight()-150,boards.Y+16,130,28},Color(28,98,204,255),7);
    SynthGlass::text(g,ready()?std::to_wstring(sets)+(sets==1?L" full set":L" full sets"):L"Full sets —",{boards.GetRight()-139,boards.Y+16,112,28},12,Blue,true);
    const wchar_t* locations[]={L"Checkmate",L"Checkmate",L"Checkmate",L"Orbituary",L"Ruin Station",L"Ruin Station",L"Orbituary"};
    SynthGlass::text(g,L"BOARD",{boards.X+20,boards.Y+72,70,18},9,SynthGlass::Muted);SynthGlass::text(g,L"LOCATION",{boards.X+112,boards.Y+72,140,18},9,SynthGlass::Muted);SynthGlass::text(g,L"OWNED",{boards.GetRight()-98,boards.Y+72,78,18},9,SynthGlass::Muted);
    Pen rule(Color(26,174,193,219));
    const auto& counts=field(inventory,"counts").items;
    for(int i=0;i<7;++i){
        float y=boards.Y+94+i*36;
        SynthGlass::text(g,L"DCHS-0"+std::to_wstring(i+1),{boards.X+20,y,88,26},12,SynthGlass::Ink,true);
        SynthGlass::text(g,locations[i],{boards.X+112,y,std::max(40.f,boards.Width-220),26},11,SynthGlass::Muted);
        int cnt=ready()&&i<int(counts.size())?int(counts[i].number):0;
        SynthGlass::rounded(g,{boards.GetRight()-96,y-1,76,26},cnt>0?Color(32,125,211,174):Color(255,19,25,35),7);
        centerText(g,ready()?std::to_wstring(cnt)+L"×":L"—",{boards.GetRight()-96,y-1,76,26},13,ready()?(cnt>0?Green:SynthGlass::Muted):SynthGlass::Muted,true);
        g.DrawLine(&rule,boards.X+20,y+31,boards.GetRight()-20,y+31);
    }
    std::string message=!ready()?"Inventory unavailable · waiting for Knick-Knacks sync":autoSynced?"Counts reflect spare DCHS-01 through DCHS-07 Comp-Boards across your stations.":"Waiting for live Knick-Knacks inventory sync to populate DCHS-01 through DCHS-07.";
    SynthGlass::text(g,wide(message),{boards.X+20,boards.Y+350,boards.Width-40,25},10,SynthGlass::Muted);

    auto ships=l.ships;
    SynthGlass::panel(g,ships,false,false,18);
    SynthGlass::text(g,L"Executive hangar ships checklist",{ships.X+20,ships.Y+14,ships.Width-190,30},17,SynthGlass::Ink,true);
    SynthGlass::text(g,autoSynced?L"Auto-detected from your live Star Citizen LTP fleet":L"Syncs automatically from your Star Citizen account",{ships.X+20,ships.Y+44,ships.Width-40,21},10,SynthGlass::Muted);

    struct DefaultExecShip { uint32_t crc; const wchar_t* name; const wchar_t* role; };
    static constexpr int kExecShipCount=8;
    static const DefaultExecShip defaultShips[kExecShipCount]={
        {2651921316u, L"Anvil F7A Hornet Mk II (PYAM Exec)", L"Fighter"},
        {981430424u,  L"Anvil F8C Lightning (PYAM Exec)", L"Fighter"},
        {3494349459u, L"Drake Corsair (PYAM Exec)", L"Exploration"},
        {4155388182u, L"Drake Cutlass Black (PYAM Exec)", L"Multi-Role"},
        {1054717367u, L"Gatac Syulen (PYAM Exec)", L"Starter / Cargo"},
        {3428858608u, L"Mirai Guardian MX Wikelo War Special", L"Combat"},
        {2002062392u, L"RSI Meteor PYAM Exec", L"Combat"},
        {1109514387u, L"RSI Scorpius Stealth (PYAM Exec)", L"Fighter"},
    };
    const auto& execItems=field(inventory,"exec_ships").items;
    auto findExecItem=[&](int idx)->const Json*{
        uint32_t wantCrc=defaultShips[idx].crc;
        for(const auto& item:execItems){
            if(uint32_t(std::llround(item.numberOr("crc",0.0)))==wantCrc)return &item;
        }
        return (idx>=0&&idx<int(execItems.size())&&execItems[size_t(idx)].numberOr("crc",0.0)==0.0)?&execItems[size_t(idx)]:nullptr;
    };
    int collectedCount=0;
    bool shipsKnown=!execItems.empty();
    for(int i=0;i<kExecShipCount;++i){
        const Json* matched=shipsKnown?findExecItem(i):nullptr;
        if(matched&&flag(*matched,"owned"))collectedCount++;
    }
    SynthGlass::rounded(g,{ships.GetRight()-158,ships.Y+16,138,28},collectedCount==kExecShipCount?Color(32,125,211,174):Color(28,98,204,255),7);
    centerText(g,shipsKnown?std::to_wstring(collectedCount)+L" / "+std::to_wstring(kExecShipCount)+L" collected":L"Checklist —",{ships.GetRight()-158,ships.Y+16,138,28},12,collectedCount==kExecShipCount?Green:Blue,true);

    SynthGlass::text(g,L"REWARD SHIP",{ships.X+52,ships.Y+72,220,18},9,SynthGlass::Muted);
    if(l.wide)SynthGlass::text(g,L"ROLE",{ships.X+360,ships.Y+72,120,18},9,SynthGlass::Muted);
    SynthGlass::text(g,L"STATUS",{ships.GetRight()-130,ships.Y+72,110,18},9,SynthGlass::Muted);

    for(int i=0;i<kExecShipCount;++i){
        float y=ships.Y+94+i*36;
        const Json* matched=shipsKnown?findExecItem(i):nullptr;
        std::wstring sName=matched&&!matched->textOr("name").empty()?wide(matched->textOr("name")):defaultShips[i].name;
        std::wstring sRole=matched&&!matched->textOr("role").empty()?wide(matched->textOr("role")):defaultShips[i].role;
        bool owned=matched&&flag(*matched,"owned");
        int qty=matched?int(matched->numberOr("quantity",1)):0;

        RectF chk(ships.X+20,y+2,22,22);
        SynthGlass::rounded(g,chk,owned?Color(38,125,211,174):Color(255,19,25,35),6,owned?Color(140,125,211,174):Color(60,148,163,184));
        if(owned)centerText(g,L"✓",chk,13,Green,true);

        float nameW=l.wide?296.f:std::max(80.f,ships.Width-200.f);
        SynthGlass::text(g,sName,{ships.X+52,y,nameW,26},12,owned?SynthGlass::Ink:SynthGlass::Muted,owned);
        if(l.wide)SynthGlass::text(g,sRole,{ships.X+360,y,140,26},11,SynthGlass::Muted);

        RectF pill(ships.GetRight()-132,y-1,112,26);
        SynthGlass::rounded(g,pill,owned?Color(32,125,211,174):Color(255,19,25,35),7);
        std::wstring statusTxt=!shipsKnown?L"—":owned?(qty>1?L"✓ Collected ("+std::to_wstring(qty)+L"×)":L"✓ Collected"):L"Uncollected";
        centerText(g,statusTxt,pill,11.5f,owned?Green:SynthGlass::Muted,owned);
        g.DrawLine(&rule,ships.X+20,y+31,ships.GetRight()-20,y+31);
    }

    SynthGlass::text(g,L"Community schedule · individual claims and unannounced resets cannot be inferred.",{18,l.bottom-38,l.width-36,24},10,SynthGlass::Muted);
}
void invalidateArea(RectF r){
    RECT client{LONG(std::floor(r.X*scale)),LONG(std::floor(r.Y*scale))-scroll,LONG(std::ceil(r.GetRight()*scale)),LONG(std::ceil(r.GetBottom()*scale))-scroll};
    InvalidateRect(page,&client,FALSE);
}
void invalidateInventory(){
    if(!page)return;RECT r{};GetClientRect(page,&r);auto g=geometry(r.right/scale);
    invalidateArea(g.boards);invalidateArea(g.ships);
}
LRESULT CALLBACK hover(HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(m==WM_ERASEBKGND)return 1;
    if(m==WM_MOUSEMOVE&&!GetPropW(h,L"Hangar.Hot")){SetPropW(h,L"Hangar.Hot",HANDLE(1));TRACKMOUSEEVENT t{sizeof(t),TME_LEAVE,h,0};TrackMouseEvent(&t);InvalidateRect(h,nullptr,FALSE);}
    if(m==WM_MOUSELEAVE){RemovePropW(h,L"Hangar.Hot");InvalidateRect(h,nullptr,FALSE);}
    return DefSubclassProc(h,m,w,l);
}
LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
    if(m==WM_SIZE){layout();InvalidateRect(h,nullptr,FALSE);return 0;}
    if(m==WM_ERASEBKGND)return 1;
    if(m==WM_MOUSEWHEEL||m==WM_VSCROLL){int next=scroll;if(m==WM_MOUSEWHEEL)next-=GET_WHEEL_DELTA_WPARAM(w)*60/120;else{SCROLLINFO si{sizeof(si),SIF_TRACKPOS};GetScrollInfo(h,SB_VERT,&si);switch(LOWORD(w)){case SB_LINEUP:next-=30;break;case SB_LINEDOWN:next+=30;break;case SB_PAGEUP:next-=300;break;case SB_PAGEDOWN:next+=300;break;case SB_THUMBTRACK:next=si.nTrackPos;break;}}scroll=next;layout();InvalidateRect(h,nullptr,FALSE);return 0;}
    if(m==WM_COMMAND){if(HIWORD(w)==BN_CLICKED)act(LOWORD(w));return 0;}
    if(m==WM_DRAWITEM){
        auto d=(DRAWITEMSTRUCT*)l;int width=d->rcItem.right,height=d->rcItem.bottom;if(width<=0||height<=0)return TRUE;
        RECT client{};GetClientRect(h,&client);auto layout=geometry(client.right/scale);auto r=controlRect(int(d->CtlID),layout);
        Bitmap frame(width,height,PixelFormat32bppPARGB);{
            Graphics g(&frame);g.Clear(SynthGlass::Base);g.SetSmoothingMode(SmoothingModeAntiAlias);g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
            g.TranslateTransform(-r.X*scale,-r.Y*scale);g.ScaleTransform(scale,scale);
            paintButton(g,r,int(d->CtlID),GetPropW(d->hwndItem,L"Hangar.Hot")!=nullptr,bool(d->itemState&ODS_SELECTED),bool(d->itemState&ODS_DISABLED),bool(d->itemState&ODS_FOCUS));
        }Graphics screen(d->hDC);screen.DrawImage(&frame,0,0);return TRUE;
    }
    if(m==WM_PAINT){PAINTSTRUCT ps{};auto dc=BeginPaint(h,&ps);RECT r{};GetClientRect(h,&r);if(r.right>0&&r.bottom>0){Bitmap image(r.right,r.bottom,PixelFormat32bppPARGB);{Graphics g(&image);g.Clear(SynthGlass::Base);g.SetSmoothingMode(SmoothingModeAntiAlias);g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);g.TranslateTransform(0,-float(scroll));g.ScaleTransform(scale,scale);paintContent(g,geometry(r.right/scale));}Graphics screen(dc);screen.DrawImage(&image,0,0);}EndPaint(h,&ps);return 0;}
    return DefWindowProcW(h,m,w,l);
}
}
void show(HWND parent,std::function<bool(Json)> action){
    send=std::move(action);if(!page){WNDCLASSW c{};c.hInstance=GetModuleHandleW(nullptr);c.lpfnWndProc=proc;c.lpszClassName=L"SynthScanExecutiveHangar";c.hCursor=LoadCursor(nullptr,IDC_ARROW);c.hbrBackground=CreateSolidBrush(RGB(14,18,25));RegisterClassW(&c);page=CreateWindowExW(WS_EX_CONTROLPARENT,c.lpszClassName,L"Executive Hangar",WS_CHILD|WS_CLIPCHILDREN|WS_VSCROLL,0,0,1,1,parent,nullptr,c.hInstance,nullptr);
        SetWindowTheme(page,L"DarkMode_Explorer",nullptr);
        for(int id:{600,601}){auto child=CreateWindowW(L"BUTTON",caption(id),WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_OWNERDRAW,0,0,1,1,page,(HMENU)INT_PTR(id),c.hInstance,nullptr);SetWindowSubclass(child,hover,1,0);}
    }
    SynthPages::mount(page);ShowWindow(page,SW_SHOW);layout();
}
void update(const Json& boards,const Json& clock,bool pending,const std::string& message){
    std::string prevSig=encode(field(inventory,"counts"))+"|"+encode(field(inventory,"exec_ships"));
    inventory=boards;timing=clock;busy=pending;note=message;
    bool inventoryChanged=prevSig!=(encode(field(inventory,"counts"))+"|"+encode(field(inventory,"exec_ships")));
    if(page&&IsWindowVisible(page)){
        RECT client{};GetClientRect(page,&client);invalidateArea(geometry(client.right/scale).hero);
        if(inventoryChanged)invalidateInventory();
    }
}
void close(){if(page)DestroyWindow(page);page=nullptr;}
int preview(const std::filesystem::path& directory){
    // Render the production canvas and control geometry without creating HWNDs.
    std::filesystem::create_directories(directory);GdiplusStartupInput input;ULONG_PTR token=0;if(GdiplusStartup(&token,&input,nullptr)!=Ok)return 2;
    Json counts=arr();for(int count:{4,2,3,8,7,6,5})counts.items.push_back(num(count));inventory=obj({{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId())},{"counts",counts},{"complete_sets",num(2)},{"auto_synced",SynthScan::boolean(true)}});
    Json lights=arr();for(const auto* value:{"green","green","green","empty","empty"})lights.items.push_back(str(value));timing=obj({{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId())},{"view",obj({{"phase",str("charging")},{"remaining_ms",num(4294000)},{"lights",lights}})},{"verification",obj({{"community_synced",SynthScan::boolean(false)},{"reason",str("Timing unverified for this patch")}})}});
    bool ok=true;const CLSID png={0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};
    for(int width:{500,650,850,1100,1600}){auto l=geometry(float(width));Bitmap bitmap(width,int(l.bottom),PixelFormat32bppPARGB);{Graphics g(&bitmap);g.Clear(SynthGlass::Base);g.SetSmoothingMode(SmoothingModeAntiAlias);g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);paintContent(g,l);
        for(int id:{600,601}){auto r=controlRect(id,l);ok&=r.X>=0&&r.GetRight()<=width&&r.Y>=0&&r.GetBottom()<=l.bottom;paintButton(g,r,id);}}
        ok&=bitmap.Save((directory/(L"executive_hangar_"+std::to_wstring(width)+L".png")).c_str(),&png,nullptr)==Ok;
    }
    GdiplusShutdown(token);return ok?0:3;
}
}
