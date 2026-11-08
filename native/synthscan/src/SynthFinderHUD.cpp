#include "SynthFinderHUD.h"
#include "SynthJson.h"
#include <commctrl.h>
#include <gdiplus.h>
#include <windowsx.h>
#include <shellapi.h>
#include <memory>
#include <atomic>
#include <cwctype>
#include <algorithm>
#include <sstream>
#include <iomanip>
#include <chrono>

namespace SynthFinder {
namespace {
using namespace SynthScan;
struct Row {Json value;std::wstring name,hay,display;};
using Index=std::vector<Row>;
std::shared_ptr<const Index> index,shown;
std::vector<size_t> matches;
HWND owner=nullptr,window=nullptr,search=nullptr,previousForeground=nullptr;
HFONT font=nullptr;HBRUSH fieldBrush=nullptr;
std::filesystem::path directory;Ownership ownership;
bool updating=false,visible=false,dropdown=false,pendingSearch=false,dragScroll=false;
size_t selected=size_t(-1);int highlighted=0,listOffset=0;
std::string requestId,shopText,rendered;
std::string marketText;Json marketLinks=arr();bool playerMarket=false;int qualityMinimum=0;
bool loading=false,retrying=false;ULONGLONG loadingStarted=0;
struct ReadyResult {std::string key,text;Json links;ULONGLONG at;};
std::vector<ReadyResult> readyResults;
const ReadyResult* recentResult(const std::vector<ReadyResult>& cache,const std::string& key,ULONGLONG now){
    for(const auto& entry:cache)if(entry.key==key&&now-entry.at<60000)return &entry;
    return nullptr;
}
bool qualityDropdown=false;int qualityHighlight=0;
struct MarketLink {Gdiplus::RectF rect;std::string url;};std::vector<MarketLink> linkHits;
float ui=1,scroll=0,contentHeight=0,viewHeight=0,dragStart=0,scrollStart=0;
int lastWidth=0,lastHeight=0;
constexpr int SEARCH_ID=43101;
constexpr UINT_PTR LOADING_TIMER=2;
void pollDetails();
// Same palette as MinerGUI's other activity tabs.
const Gdiplus::Color BG(255,15,16,19),CARD(255,24,26,30),BORDER(255,44,47,54),INK(255,238,239,241),MUTED(255,160,166,176),ACCENT(255,98,204,255);
void repaint(){if(window)InvalidateRect(window,nullptr,FALSE);}
std::wstring normalize(const std::wstring& text){
    std::wstring result,word;
    auto flush=[&](){if(word==L"i"||word==L"one")word=L"1";else if(word==L"ii"||word==L"two")word=L"2";else if(word==L"iii"||word==L"three")word=L"3";result+=word;word.clear();};
    for(wchar_t c:text){if(std::iswalnum(c))word+=wchar_t(std::towlower(c));else flush();}flush();return result;
}
std::vector<size_t> find(const Index& rows,const std::wstring& text){
    std::wistringstream words(text);std::vector<std::wstring> terms;std::wstring word;
    while(words>>word){auto n=normalize(word);if(!n.empty())terms.push_back(n);}
    auto prefix=normalize(text);std::vector<std::pair<int,size_t>> ranked;
    for(size_t i=0;i<rows.size();i++){
        bool all=true;for(const auto& term:terms)if(rows[i].hay.find(term)==std::wstring::npos){all=false;break;}
        if(prefix==L"comp45"&&(rows[i].value.numberOr("market_board")==4||rows[i].value.numberOr("market_board")==5))all=true;
        if(all)ranked.push_back({rows[i].name.rfind(prefix,0)==0?0:rows[i].name.find(prefix)!=std::wstring::npos?1:2,i});
    }
    auto priority=[&](size_t i){auto kind=rows[i].value.textOr("kind");return kind=="Ship"?0:kind=="Vehicle"?1:kind=="Component"?2:3;};
    std::stable_sort(ranked.begin(),ranked.end(),[&](auto a,auto b){if(priority(a.second)!=priority(b.second))return priority(a.second)<priority(b.second);if(a.first!=b.first)return a.first<b.first;
        bool marketA=rows[a.second].value.numberOr("market_item_id")>0,marketB=rows[b.second].value.numberOr("market_item_id")>0;
        if(marketA!=marketB)return marketA;return rows[a.second].name.size()<rows[b.second].name.size();});
    std::vector<size_t> result;for(size_t i=0;i<std::min(size_t(60),ranked.size());i++)result.push_back(ranked[i].second);return result;
}
std::wstring text(HWND target){int length=GetWindowTextLengthW(target);std::wstring value(length+1,0);GetWindowTextW(target,value.data(),length+1);value.resize(length);return value;}
std::string blueprintText(const Json& row,const Ownership& owned){
    std::ostringstream out;const auto& blueprints=field(row,"finder_blueprints").items;
    if(blueprints.empty())return "\nBLUEPRINT\nNo creation blueprint listed in the current catalog.\n";
    for(const auto& bp:blueprints){
        int state=owned?owned(int(bp.numberOr("reference_index",-1)),bp.textOr("reference_name")):-1;
        bool starter=flag(bp,"known_from_start");
        out<<"\nBLUEPRINT — "<<bp.textOr("name")<<"\n";
        out<<(starter?"Available by default":state==1?"Recorded as obtained":state==2?"Possibly obtained (inferred; not confirmed)":"Not recorded as obtained")<<"\n";
        out<<"MATERIALS TO CRAFT\n";
        const auto& materials=field(bp,"materials").items;
        if(materials.empty())out<<"Recipe inputs not recorded.\n";
        for(const auto& material:materials){
            out<<" • "<<std::setprecision(6)<<material.numberOr("amount")<<" "<<material.textOr("unit")<<" "<<material.textOr("material");
            auto quality=material.numberOr("min_quality");out<<(quality>0?" · min Q"+std::to_string(int(quality)):" · any quality")<<"\n";
        }
        if(!flag(bp,"recipe_verified"))out<<"Recipe is an older reference; verify it in game.\n";
        if(!starter&&state!=1){
            out<<"UNLOCK MISSIONS\n";const auto& missions=field(bp,"missions").items;
            if(missions.empty())out<<"No known mission source in this catalog.\n";
            for(const auto& mission:missions)out<<" • "<<mission.textOr("title")<<"\n   "<<mission.textOr("faction")<<" · "<<mission.textOr("system")<<" · "<<mission.textOr("standing")<<"\n";
            out<<"Source: "<<bp.textOr("unlock_source","Reference data")<<"\nReward pools do not guarantee a particular blueprint.\n";
        }
    }
    return out.str();
}

void render(){
    if(!shown||selected>=shown->size())return;
    const auto& row=(*shown)[selected].value;
    // Keep the body empty until price and recipe details can appear together.
    auto next=loading?std::string():(playerMarket?marketText:shopText)+"\n"+blueprintText(row,ownership);
    if(next!=rendered){rendered=std::move(next);repaint();}
}
std::vector<int> qualityChoices(){
    std::vector<int> values{0};if(!shown||selected>=shown->size())return values;
    for(const auto& value:field((*shown)[selected].value,"quality_values").items){int q=int(value.number);if(q>0&&q<=1000&&q==value.number&&std::find(values.begin(),values.end(),q)==values.end())values.push_back(q);}
    return values;
}
void releaseInput(){
    dropdown=false;qualityDropdown=false;repaint();
    if(!window)return;
    DWORD pid=0;GetWindowThreadProcessId(GetForegroundWindow(),&pid);
    HWND previous=previousForeground;previousForeground=nullptr;
    if(pid==GetCurrentProcessId()&&previous&&IsWindow(previous))SetForegroundWindow(previous);
}
void requestPrices(const Json& row){
    requestId="finder:"+std::to_string(GetTickCount64())+":"+row.textOr("id");
    loading=true;retrying=false;loadingStarted=GetTickCount64();marketLinks=arr();linkHits.clear();contentHeight=viewHeight=0;
    auto cacheKey=row.textOr("id")+"|"+row.textOr("item_id")+"|"+row.textOr("market_identity")+"|"+(playerMarket?"market":"shops")+"|"+std::to_string(qualityMinimum);
    if(const auto* cached=recentResult(readyResults,cacheKey,loadingStarted)){
        loading=false;if(playerMarket){marketText=cached->text;marketLinks=cached->links;}else shopText=cached->text;
    }
    // A small timer polls only the selected lookup, without waiting for the HUD
    // or session collectors. Animation runs solely while a lookup is pending.
    if(loading)SetTimer(window,LOADING_TIMER,50,nullptr);else KillTimer(window,LOADING_TIMER);
    if(playerMarket){
        write(directory/L"finder_market_request.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"at",num(std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count())},
              {"request_id",str(requestId)},{"row_id",field(row,"id")},{"item_id",field(row,"item_id")},{"market_item_id",field(row,"market_item_id")},{"market_identity",field(row,"market_identity")},{"quality_min",num(qualityMinimum)},{"quality_exact",SynthScan::boolean(true)}}));return;
    }
    write(directory/L"item_directory_request.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"at",num(std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count())},
          {"request_id",str(requestId)},{"row_id",field(row,"id")},{"item_id",field(row,"item_id")}}));
}
bool acceptsResult(const Json& result,DWORD pid,const std::string& request,const Json& row,bool market,int quality){
    return result.numberOr("owner_pid")==pid&&result.textOr("request_id")==request&&result.textOr("row_id")==row.textOr("id")&&
        result.textOr("item_id")==row.textOr("item_id")&&!flag(result,"loading")&&
        (!market||(result.numberOr("quality_min")==quality&&flag(result,"quality_exact")));
}
void pollDetails(){
    if((!loading&&!retrying)||!shown||selected>=shown->size())return;
    const auto& row=(*shown)[selected].value;
    auto result=SynthScan::read(directory/(playerMarket?L"finder_market_detail.json":L"item_directory_detail.json"),512*1024);
    if(!acceptsResult(result,GetCurrentProcessId(),requestId,row,playerMarket,qualityMinimum))return;
    if(playerMarket){marketText=result.textOr("text");marketLinks=field(result,"links");}else shopText=result.textOr("text");
    loading=false;retrying=flag(result,"error");
    if(retrying)SetTimer(window,LOADING_TIMER,250,nullptr);else KillTimer(window,LOADING_TIMER);
    auto key=row.textOr("id")+"|"+row.textOr("item_id")+"|"+row.textOr("market_identity")+"|"+(playerMarket?"market":"shops")+"|"+std::to_string(qualityMinimum);
    readyResults.erase(std::remove_if(readyResults.begin(),readyResults.end(),[&](const auto& entry){return entry.key==key;}),readyResults.end());
    if(readyResults.size()>=16)readyResults.erase(readyResults.begin());
    // Keep automatic retries live instead of giving failures a UI cache entry.
    if(!flag(result,"error"))readyResults.push_back({key,result.textOr("text"),field(result,"links"),GetTickCount64()});
    render();repaint();
}
void suggestions(){
    pendingSearch=false;KillTimer(window,1);auto latest=std::atomic_load(&index);if(!latest)return;
    shown=latest;auto query=text(search);matches.clear();
    matches=find(*shown,query);
    highlighted=0;listOffset=0;dropdown=true;repaint();
}
void choose(int match){
    if(match<0||match>=int(matches.size())||!shown)return;
    selected=matches[match];const auto& row=(*shown)[selected].value;
    qualityMinimum=0;qualityDropdown=false;
    if(row.textOr("kind")=="Market item")playerMarket=true;
    pendingSearch=false;KillTimer(window,1);updating=true;
    SetWindowTextW(search,wide(row.textOr("name")).c_str());SendMessageW(search,EM_SETSEL,0,-1);updating=false;
    dropdown=false;scroll=0;requestPrices(row);render();SetFocus(search);repaint();
}
void rounded(Gdiplus::Graphics& g,Gdiplus::RectF r,float radius,Gdiplus::Color color){
    Gdiplus::GraphicsPath path;float d=radius*2;
    path.AddArc(r.X,r.Y,d,d,180,90);path.AddArc(r.GetRight()-d,r.Y,d,d,270,90);path.AddArc(r.GetRight()-d,r.GetBottom()-d,d,d,0,90);path.AddArc(r.X,r.GetBottom()-d,d,d,90,90);path.CloseFigure();Gdiplus::SolidBrush brush(color);g.FillPath(&brush,&path);
}
float words(Gdiplus::Graphics& g,const std::wstring& value,float x,float y,float width,float size,Gdiplus::Color color,bool bold=false){
    Gdiplus::Font f(L"Segoe UI",size*ui,bold?Gdiplus::FontStyleBold:Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    Gdiplus::StringFormat format;format.SetTrimming(Gdiplus::StringTrimmingEllipsisWord);
    Gdiplus::RectF extent;g.MeasureString(value.c_str(),-1,&f,Gdiplus::RectF(x,y,width,10000),&format,&extent);
    Gdiplus::SolidBrush brush(color);g.DrawString(value.c_str(),-1,&f,Gdiplus::RectF(x,y,width,extent.Height+2),&format,&brush);return extent.Height;
}
int listRows(){RECT r{};GetClientRect(window,&r);return std::max(1,std::min(7,int((r.bottom-79*ui)/(44*ui))));}
void paint(HWND hwnd){
    PAINTSTRUCT ps{};HDC dc=BeginPaint(hwnd,&ps);RECT r{};GetClientRect(hwnd,&r);
    if(r.right>0&&r.bottom>0){
        Gdiplus::Bitmap buffer(r.right,r.bottom,PixelFormat32bppPARGB);Gdiplus::Graphics g(&buffer);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);g.Clear(BG);
        float w=float(r.right),h=float(r.bottom),pad=12*ui;linkHits.clear();float contentTop=(playerMarket?137.f:99.f)*ui;
        rounded(g,{pad,6*ui,w-pad*2,43*ui},10*ui,Gdiplus::Color(255,34,37,43));
        Gdiplus::Pen pen(GetFocus()==search?ACCENT:MUTED,1.5f*ui);
        g.DrawEllipse(&pen,pad+12*ui,19*ui,11*ui,11*ui);g.DrawLine(&pen,pad+22*ui,29*ui,pad+27*ui,34*ui);
        float ax=w-pad-18*ui;g.DrawLine(&pen,ax-4*ui,25*ui,ax,29*ui);g.DrawLine(&pen,ax,29*ui,ax+4*ui,25*ui);
        if(!dropdown){
            rounded(g,{pad,58*ui,97*ui,29*ui},6*ui,playerMarket?CARD:Gdiplus::Color(255,46,50,58));
            rounded(g,{pad+105*ui,58*ui,158*ui,29*ui},6*ui,playerMarket?Gdiplus::Color(255,46,50,58):CARD);
            words(g,L"SHOPS",pad+14*ui,65*ui,80*ui,10,playerMarket?MUTED:ACCENT,true);
            words(g,L"PLAYER MARKET",pad+118*ui,65*ui,140*ui,10,playerMarket?ACCENT:MUTED,true);
            words(g,L"UEX ↗",w-80*ui,65*ui,70*ui,11,ACCENT,true);
            if(playerMarket){
                rounded(g,{pad,96*ui,w-pad*2,27*ui},6*ui,CARD);
                auto label=qualityMinimum?L"Quality: Q"+std::to_wstring(qualityMinimum):L"Quality: Any";
                words(g,label,pad+12*ui,102*ui,w-pad*2-50*ui,11,ACCENT);
                words(g,qualityChoices().size()>1?L"⌄":L"",w-40*ui,100*ui,20*ui,12,MUTED);
            }
        }
        if(dropdown){
            words(g,matches.empty()?L"NO MATCHES":text(search).empty()?L"BROWSE ITEMS":L"MATCHING ITEMS",pad,59*ui,w-pad*2,10,MUTED,true);
            if(matches.empty())words(g,L"Try another spelling or a shorter name.",pad,87*ui,w-pad*2,14,INK);
            int rows=listRows();listOffset=std::clamp(listOffset,0,std::max(0,int(matches.size())-rows));
            for(int row=0;row<rows&&row+listOffset<int(matches.size());row++){
                int at=row+listOffset;float y=(79+44*row)*ui;
                if(at==highlighted)rounded(g,{pad,y,w-pad*2,41*ui},8*ui,Gdiplus::Color(255,46,50,58));
                const auto& value=(*shown)[matches[at]].value;
                words(g,wide(value.textOr("name")),pad+12*ui,y+3*ui,w-pad*2-24*ui,13,INK);
                words(g,wide(value.textOr("kind")),pad+12*ui,y+23*ui,w-pad*2-24*ui,10,at==highlighted?ACCENT:MUTED);
            }
        }else if(qualityDropdown){
            auto choices=qualityChoices();for(size_t i=0;i<choices.size();i++){
                float y=(130+25*i)*ui;if(int(i)==qualityHighlight)rounded(g,{pad,y,w-pad*2,24*ui},5*ui,Gdiplus::Color(255,46,50,58));
                words(g,choices[i]?L"Q"+std::to_wstring(choices[i]):L"Any quality",pad+12*ui,y+3*ui,w-pad*2-24*ui,12,int(i)==qualityHighlight?ACCENT:INK);
            }
        }else if(shown&&selected<shown->size()){
            auto state=g.Save();g.SetClip(Gdiplus::RectF(pad,contentTop,w-pad*2,h-contentTop-6*ui));
            float y=contentTop+5*ui-scroll;
            const auto& row=(*shown)[selected].value;
            y+=words(g,wide(row.textOr("name")),pad,y,w-pad*2,19,INK,true)+4*ui;
            y+=words(g,wide(row.textOr("kind"))+L"  ·  PURCHASE & CRAFTING",pad,y,w-pad*2,10,ACCENT,true)+15*ui;
            if(loading){
                // Delay the indicator briefly so fast cached lookups don't flash.
                if(GetTickCount64()-loadingStarted>=150){
                    Gdiplus::Pen spinner(ACCENT,2*ui);spinner.SetStartCap(Gdiplus::LineCapRound);spinner.SetEndCap(Gdiplus::LineCapRound);
                    float angle=float(GetTickCount64()%1000)*.36f;
                    g.DrawArc(&spinner,Gdiplus::RectF(pad+8*ui,y+3*ui,14*ui,14*ui),angle,250.f);
                    words(g,L"Loading details…",pad+33*ui,y,w-pad*2-40*ui,12,MUTED);
                }
            }
            std::istringstream lines(rendered);std::string line;
            while(std::getline(lines,line)){
                if(line.empty()){y+=10*ui;continue;}
                bool heading=line.rfind("BLUEPRINT",0)==0||line=="MATERIALS TO CRAFT"||line=="UNLOCK MISSIONS"||line.rfind("IN-GAME PURCHASE",0)==0||line.rfind("PLAYER MARKET",0)==0||line.rfind("SELLERS",0)==0||line.rfind("BUYERS",0)==0||line=="UEX QUALITY-TIER REFERENCE";
                if(heading){y+=9*ui;rounded(g,{pad,y-3*ui,w-pad*2,25*ui},5*ui,CARD);}
                bool link=playerMarket&&line.rfind("Open listing #",0)==0;
                auto color=heading||link?ACCENT:line.find("aUEC")!=std::string::npos?INK:line.rfind("Last checked",0)==0||line.rfind("Source:",0)==0?MUTED:INK;
                float height=words(g,wide(line),pad+8*ui,y,w-pad*2-23*ui,heading?10:12,color,heading);
                if(link&&y>=contentTop&&y+height<=h-6*ui)for(const auto& entry:marketLinks.items)if(entry.textOr("label")==line)linkHits.push_back({{pad,y,w-pad*2,height},entry.textOr("url")});
                y+=height+5*ui;
            }
            contentHeight=y+scroll-contentTop;viewHeight=h-contentTop-6*ui;g.Restore(state);
            float limit=std::max(0.f,contentHeight-viewHeight);if(scroll>limit){scroll=limit;repaint();}
            if(limit>0){float bar=std::max(28*ui,viewHeight*viewHeight/contentHeight);rounded(g,{w-6*ui,contentTop+(viewHeight-bar)*scroll/limit,3*ui,bar},1.5f*ui,MUTED);}
        }else{
            words(g,L"Find your next upgrade",pad+12*ui,contentTop+24*ui,w-pad*2-24*ui,21,INK,true);
            words(g,L"Search ships, components, materials and equipment.\nCompare shop prices or browse player offers.",pad+12*ui,contentTop+67*ui,w-pad*2-24*ui,14,MUTED);
            words(g,L"Click the search bar to browse.\nEnter selects · Esc returns to your previous app",pad+12*ui,contentTop+145*ui,w-pad*2-24*ui,11,ACCENT);
        }
        Gdiplus::Graphics screen(dc);screen.DrawImage(&buffer,0,0);
    }EndPaint(hwnd,&ps);
}
void layout(){
    RECT r{};GetClientRect(window,&r);if(font&&r.right==lastWidth&&r.bottom==lastHeight)return;
    lastWidth=r.right;lastHeight=r.bottom;ui=std::max(.6f,r.right/544.f);
    if(font)DeleteObject(font);font=CreateFontW(-int(14*ui),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
    if(search){MoveWindow(search,int(49*ui),int(17*ui),std::max(1,int(r.right)-int(100*ui)),int(24*ui),TRUE);SendMessageW(search,WM_SETFONT,(WPARAM)font,TRUE);}
    repaint();
}
void openMarketPage(const std::string& url){
    const std::string base="https://uexcorp.space/marketplace/";
    if(url.rfind(base,0)!=0||url.find_first_of("\r\n\"\\ ")!=std::string::npos)return;
    ShellExecuteW(owner,L"open",wide(url).c_str(),nullptr,nullptr,SW_SHOWNORMAL);
}
void updateMarketChoice(){
    qualityDropdown=false;scroll=0;rendered.clear();if(shown&&selected<shown->size()){requestPrices((*shown)[selected].value);render();}repaint();
}
LRESULT CALLBACK editProcedure(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(message==WM_MOUSEWHEEL)return SendMessageW(window,message,w,l);
    if(message==WM_LBUTTONDOWN){dropdown=true;suggestions();repaint();}
    if(message==WM_SETFOCUS||message==WM_KILLFOCUS)repaint();
    if(message==WM_GETDLGCODE)return DLGC_WANTALLKEYS|DLGC_WANTCHARS|DLGC_WANTARROWS;
    return DefSubclassProc(hwnd,message,w,l);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    if(message==WM_MOUSEACTIVATE){HWND previous=GetForegroundWindow();DWORD pid=0;GetWindowThreadProcessId(previous,&pid);if(pid!=GetCurrentProcessId())previousForeground=previous;return MA_ACTIVATE;}
    if(message==WM_COMMAND&&LOWORD(w)==SEARCH_ID&&HIWORD(w)==EN_CHANGE&&!updating){pendingSearch=true;SetTimer(hwnd,1,60,nullptr);return 0;}
    if(message==WM_TIMER&&w==1){suggestions();return 0;}
    if(message==WM_TIMER&&w==LOADING_TIMER){pollDetails();if(loading)repaint();return 0;}
    if(message==WM_PAINT){paint(hwnd);return 0;}
    if(message==WM_SIZE){layout();return 0;}
    if(message==WM_ERASEBKGND)return 1;
    if(message==WM_CTLCOLOREDIT){SetTextColor((HDC)w,RGB(238,239,241));SetBkColor((HDC)w,RGB(34,37,43));return(LRESULT)fieldBrush;}
    if(message==WM_LBUTTONDOWN){
        float x=GET_X_LPARAM(l)/ui,y=GET_Y_LPARAM(l)/ui;RECT r{};GetClientRect(hwnd,&r);
        if(y<51){SetFocus(search);suggestions();return 0;}
        if(dropdown){int at=listOffset+int((y-79)/44);if(y>=79&&at>=0&&at<int(matches.size()))choose(at);return 0;}
        if(y>=58&&y<=87){
            if(x>=r.right/ui-85){openMarketPage("https://uexcorp.space/marketplace/");return 0;}
            bool next=x>=117;if(x>=12&&x<=275&&next!=playerMarket){playerMarket=next;updateMarketChoice();}return 0;
        }
        if(playerMarket&&y>=96&&y<=123){auto choices=qualityChoices();qualityDropdown=choices.size()>1&&!qualityDropdown;qualityHighlight=int(std::find(choices.begin(),choices.end(),qualityMinimum)-choices.begin());repaint();return 0;}
        if(qualityDropdown){auto choices=qualityChoices();int at=int((y-130)/25);if(y>=130&&at>=0&&at<int(choices.size())){qualityMinimum=choices[at];updateMarketChoice();}else{qualityDropdown=false;repaint();}return 0;}
        for(const auto& hit:linkHits)if(hit.rect.Contains(float(GET_X_LPARAM(l)),float(GET_Y_LPARAM(l)))){openMarketPage(hit.url);return 0;}
        if(x>r.right/ui-15&&contentHeight>viewHeight){dragScroll=true;dragStart=float(GET_Y_LPARAM(l));scrollStart=scroll;SetCapture(hwnd);return 0;}
    }
    if(message==WM_MOUSEMOVE&&dragScroll){scroll=std::clamp(scrollStart+(GET_Y_LPARAM(l)-dragStart)*contentHeight/std::max(1.f,viewHeight),0.f,std::max(0.f,contentHeight-viewHeight));repaint();return 0;}
    if(message==WM_LBUTTONUP&&dragScroll){dragScroll=false;ReleaseCapture();return 0;}
    if(message==WM_MOUSEWHEEL){int steps=GET_WHEEL_DELTA_WPARAM(w)/WHEEL_DELTA;if(dropdown)listOffset=std::clamp(listOffset-steps*3,0,std::max(0,int(matches.size())-listRows()));else scroll=std::clamp(scroll-steps*64*ui,0.f,std::max(0.f,contentHeight-viewHeight));repaint();return 0;}
    if(message==WM_CLOSE){releaseInput();return 0;}
    return DefWindowProcW(hwnd,message,w,l);
}
void create(){
    if(window)return;
    WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanFinderHUD";cls.lpfnWndProc=procedure;cls.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&cls);
    fieldBrush=CreateSolidBrush(RGB(34,37,43));
    // Finder is part of the same layered HUD surface as the other tabs.
    // A second top-level window had independent activation/compositing and
    // could leave a gray rectangle when focus returned to the game.
    window=CreateWindowExW(0,cls.lpszClassName,L"SynthScan Finder",WS_CHILD|WS_CLIPCHILDREN,0,0,544,360,owner,nullptr,cls.hInstance,nullptr);
    search=CreateWindowExW(0,L"EDIT",L"",WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL,49,17,444,24,window,(HMENU)SEARCH_ID,cls.hInstance,nullptr);
    SendMessageW(search,EM_SETLIMITTEXT,120,0);SendMessageW(search,EM_SETCUEBANNER,TRUE,(LPARAM)L"Search ships, components, items…");
    SetWindowSubclass(search,editProcedure,1,0);layout();
}
}
void initialize(HWND parent,const std::filesystem::path& data,Ownership callback){owner=parent;directory=data;ownership=std::move(callback);}
void prepare(const SCMiner::JsonValue& library){
    auto next=std::make_shared<Index>();
    for(const auto& row:SynthScan::field(library,"rows").items){
        auto kind=row.textOr("kind");if((kind!="Item"&&kind!="Component"&&kind!="Ship"&&kind!="Vehicle"&&kind!="Market item")||row.textOr("item_id").empty())continue;
        auto name=SynthScan::wide(row.textOr("name"));Row item;item.value=SynthScan::obj({{"id",SynthScan::field(row,"id")},{"item_id",SynthScan::field(row,"item_id")},{"name",SynthScan::field(row,"name")},
            {"kind",SynthScan::field(row,"kind")},{"finder_blueprints",SynthScan::field(row,"finder_blueprints")},{"market_item_id",SynthScan::field(row,"market_item_id")},{"market_identity",SynthScan::field(row,"market_identity")},{"market_board",SynthScan::field(row,"market_board")},{"quality_values",SynthScan::field(row,"quality_values")}});
        item.name=normalize(name);item.hay=normalize(SynthScan::wide(row.textOr("search",row.textOr("name")+" "+row.textOr("category"))));item.display=name+L" · "+SynthScan::wide(kind);next->push_back(std::move(item));
    }
    std::atomic_store(&index,std::shared_ptr<const Index>(std::move(next)));
}

void sync(bool show){
    if(!owner)return;
    if(!show){if(window&&visible){releaseInput();ShowWindow(window,SW_HIDE);KillTimer(window,LOADING_TIMER);}visible=false;return;}
    create();RECT r{};GetClientRect(owner,&r);float scale=r.right/560.f;int margin=int(8*scale),top=int(42*scale),bottom=int(37*scale);
    int width=r.right-r.left-2*margin,height=r.bottom-r.top-top-bottom;if(width<100||height<80)return;
    RECT current{};GetWindowRect(window,&current);MapWindowPoints(HWND_DESKTOP,owner,reinterpret_cast<POINT*>(&current),2);
    if(!visible||current.left!=margin||current.top!=top||current.right-current.left!=width||current.bottom-current.top!=height)
        SetWindowPos(window,nullptr,margin,top,width,height,SWP_NOACTIVATE|SWP_NOZORDER|SWP_SHOWWINDOW);
    visible=true;
    if(loading||retrying)SetTimer(window,LOADING_TIMER,loading?50:250,nullptr);
    auto latest=std::atomic_load(&index);
    if(latest&&shown&&latest!=shown){
        std::string id,item,marketIdentity;if(selected<shown->size()){id=(*shown)[selected].value.textOr("id");item=(*shown)[selected].value.textOr("item_id");marketIdentity=(*shown)[selected].value.textOr("market_identity");}
        shown=latest;selected=size_t(-1);
        for(size_t i=0;!id.empty()&&i<shown->size();i++)if((*shown)[i].value.textOr("id")==id){selected=i;break;}
        if(selected>=shown->size()){requestId.clear();rendered.clear();loading=false;retrying=false;KillTimer(window,LOADING_TIMER);}
        else{
            auto choices=qualityChoices();bool invalid=std::find(choices.begin(),choices.end(),qualityMinimum)==choices.end();if(invalid)qualityMinimum=0;
            if(invalid||(*shown)[selected].value.textOr("item_id")!=item||(*shown)[selected].value.textOr("market_identity")!=marketIdentity)requestPrices((*shown)[selected].value);
        }
        if(dropdown)suggestions();repaint();
    }
    pollDetails();if(shown&&selected<shown->size())render();
}
void activationChanged(bool active){
    if(!window||!visible)return;
    if(!active){dropdown=false;qualityDropdown=false;KillTimer(window,1);pendingSearch=false;}
    RedrawWindow(window,nullptr,nullptr,RDW_INVALIDATE|RDW_ALLCHILDREN);
}
bool owns(HWND target){return visible&&window&&(target==window||IsChild(window,target));}
bool key(UINT message,WPARAM value,HWND target){
    if(!owns(target)||message!=WM_KEYDOWN)return false;
    if(value==VK_ESCAPE){if(qualityDropdown){qualityDropdown=false;repaint();}else releaseInput();return true;}
    if(qualityDropdown&&(value==VK_UP||value==VK_DOWN||value==VK_RETURN)){
        auto choices=qualityChoices();if(value==VK_RETURN){qualityMinimum=choices[std::clamp(qualityHighlight,0,int(choices.size())-1)];updateMarketChoice();}
        else{qualityHighlight=std::clamp(qualityHighlight+(value==VK_DOWN?1:-1),0,int(choices.size())-1);repaint();}return true;
    }
    if(value=='A'&&(GetKeyState(VK_CONTROL)&0x8000)){SendMessageW(search,EM_SETSEL,0,-1);return true;}
    if(value==VK_DOWN||value==VK_UP){
        if(pendingSearch||!dropdown)suggestions();else highlighted=std::clamp(highlighted+(value==VK_DOWN?1:-1),0,std::max(0,int(matches.size())-1));
        if(highlighted<listOffset)listOffset=highlighted;if(highlighted>=listOffset+listRows())listOffset=highlighted-listRows()+1;repaint();return true;
    }
    if(value==VK_RETURN){if(pendingSearch)suggestions();if(dropdown)choose(highlighted);return true;}
    if(value==VK_TAB){if(dropdown)choose(highlighted);else SetFocus(search);return true;}
    return false;
}
void close(){if(window)DestroyWindow(window);window=nullptr;search=nullptr;visible=false;if(font)DeleteObject(font);font=nullptr;if(fieldBrush)DeleteObject(fieldBrush);fieldBrush=nullptr;}
bool selfTest(){
    Row one;one.name=normalize(L"Helix I Mining Laser");one.hay=one.name;Row two;two.name=normalize(L"Helix II Mining Laser");two.hay=two.name;
    auto matches=find(Index{one,two},L"helix one");if(matches.empty()||matches[0]!=0)return false;
    Row shirt;shirt.name=normalize(L"Carrack T-Shirt");shirt.hay=shirt.name;shirt.value=SynthScan::obj({{"kind",SynthScan::str("Item")}});
    Row ship;ship.name=normalize(L"Anvil Carrack Expedition");ship.hay=ship.name;ship.value=SynthScan::obj({{"kind",SynthScan::str("Ship")}});
    Index crowded(80,shirt);crowded.push_back(ship);auto ships=find(crowded,L"Carrack");if(ships.empty()||ships[0]!=80)return false;
    crowded[0].name=crowded[0].hay=normalize(L"600i Shirt");crowded[80].name=crowded[80].hay=normalize(L"600i Explorer");auto six=find(crowded,L"600");if(six.empty()||six[0]!=80||find(crowded,L"")[0]!=80)return false;
    using namespace SynthScan;auto bp=obj({{"name",str("Test")},{"reference_index",num(1)},{"materials",arr()},{"missions",arr()}});
    std::vector<ReadyResult> cache{{"market|975","Complete prices",arr(),100}};
    const auto* cached=recentResult(cache,"market|975",101);
    if(!cached||cached->text!="Complete prices"||recentResult(cache,"market|916",101)||recentResult(cache,"market|975",60100))return false;
    bp.members[2].second.items.push_back(obj({{"material",str("Copper")},{"amount",num(2)},{"unit",str("SCU")},{"min_quality",num(900)}}));
    bp.members[3].second.items.push_back(obj({{"title",str("Reward mission")}}));auto blueprints=arr();blueprints.items.push_back(bp);auto row=obj({{"finder_blueprints",blueprints}});
    auto unowned=blueprintText(row,[](int,const std::string&){return 0;}),owned=blueprintText(row,[](int,const std::string&){return 1;});
    if(unowned.find("Reward mission")==std::string::npos||unowned.find("min Q900")==std::string::npos||owned.find("Reward mission")!=std::string::npos||owned.find("Copper")==std::string::npos)return false;
    auto selectedRow=obj({{"id",str("selected")},{"item_id",str("item")}});
    auto result=obj({{"owner_pid",num(42)},{"request_id",str("new")},{"row_id",str("selected")},{"item_id",str("item")},{"quality_min",num(975)},{"quality_exact",SynthScan::boolean(true)},{"loading",SynthScan::boolean(true)}});
    if(acceptsResult(result,42,"new",selectedRow,true,975))return false; // intermediate content stays hidden
    for(auto& member:result.members)if(member.first=="loading")member.second=SynthScan::boolean(false);
    return acceptsResult(result,42,"new",selectedRow,true,975)&&!acceptsResult(result,42,"old",selectedRow,true,975)&&
        !acceptsResult(result,42,"new",selectedRow,true,916)&&!acceptsResult(result,43,"new",selectedRow,true,975);
}
}
