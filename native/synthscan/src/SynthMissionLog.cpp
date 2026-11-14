#define UNICODE
#define _UNICODE
#include "SynthMissionLog.h"
#include "SynthJson.h"
#include "SynthPages.h"
#include "SynthGlass.h"
#include "NativeRedraw.h"
#include <commctrl.h>
#include <commdlg.h>
#include <uxtheme.h>
#include <chrono>
#include <ctime>
#include <algorithm>
#include <sstream>
#include <iomanip>

namespace SynthMissionLog {
namespace {
using namespace SynthScan;
HWND page=nullptr,list=nullptr,detail=nullptr;HFONT font=nullptr;std::filesystem::path folder;
Json model;std::string selected,lastRows,lastColumns;bool filling=false;float scale=1;
HBRUSH surface=CreateSolidBrush(RGB(14,18,25)),input=CreateSolidBrush(RGB(24,30,40));
const char* categoryKeys[]={"unclassified","mission_reward","player_transfer","repair","refuel","store_purchase","vehicle_purchase","cargo_trade","fees","other"};
const wchar_t* categoryLabels[]={L"Unclassified",L"Mission reward",L"Player transfer",L"Repairs",L"Refueling",L"Store purchase",L"Vehicle / equipment",L"Cargo trading",L"Fees / fines",L"Other"};
double now(){return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
int px(float value){return int(value*scale);}
std::wstring amount(double value,bool sign=false){std::wostringstream s;if(sign&&value>0)s<<L'+';s<<std::fixed<<std::setprecision(0)<<value;return s.str();}
std::wstring when(double value){if(value<=0)return L"Unknown";std::time_t at=std::time_t(value);std::tm local{};localtime_s(&local,&at);wchar_t text[40]{};wcsftime(text,40,L"%m-%d %H:%M:%S",&local);return text;}
HWND control(int id){return GetDlgItem(page,id);}
int choice(int id){return int(SendMessageW(control(id),CB_GETCURSEL,0,0));}
std::string text(int id){int length=GetWindowTextLengthW(control(id));std::wstring value(length+1,0);GetWindowTextW(control(id),value.data(),length+1);value.resize(length);return utf8(value);}
void queue(Json value){
    static unsigned sequence=0;auto commands=folder/L"mission_log_commands";std::error_code error;std::filesystem::create_directories(commands,error);
    auto id=std::to_string(GetTickCount64())+"-"+std::to_string(GetCurrentProcessId())+"-"+std::to_string(++sequence);
    value.members.push_back({"id",str(id)});write(commands/std::filesystem::u8path(id+".json"),value);
}
void request(int offset=0){
    const char* modes[]={"all","missions","reputation","rewards","wallet","sessions"};
    const char* outcomes[]={"","completed","failed","abandoned","active"};
    const char* directions[]={"","gains","losses"};
    queue(obj({{"action",str("view")},{"query",str(text(501))},{"mode",str(modes[std::clamp(choice(506),0,5)])},
               {"outcome",str(outcomes[std::clamp(choice(507),0,4)])},{"direction",str(directions[std::clamp(choice(509),0,2)])},
               {"category",str(choice(514)>0?categoryKeys[std::clamp(choice(514)-1,0,9)]:"")},
               {"current_session",SynthScan::boolean(choice(508)==1)},{"offset",num(std::max(0,offset))}}));
}
void classifyMenu(){
    int at=ListView_GetNextItem(list,-1,LVNI_SELECTED);const auto& rows=field(model,"entries").items;
    if(at<0||size_t(at)>=rows.size()||!flag(rows[at],"is_wallet"))return;
    HMENU menu=CreatePopupMenu();for(int i=0;i<10;i++)AppendMenuW(menu,MF_STRING|(rows[at].textOr("category")==categoryKeys[i]?MF_CHECKED:0),1000+i,categoryLabels[i]);
    POINT cursor{};GetCursorPos(&cursor);int chosen=int(TrackPopupMenu(menu,TPM_RETURNCMD|TPM_NONOTIFY,cursor.x,cursor.y,0,page,nullptr));DestroyMenu(menu);
    if(chosen>=1000&&chosen<1010)queue(obj({{"action",str("classify_wallet")},{"change_id",field(rows[at],"change_id")},{"category",str(categoryKeys[chosen-1000])}}));
}
void exportFile(int id){
    const wchar_t* ext=id==503?L"csv":id==504?L"json":L"html";
    wchar_t path[32768]{};swprintf_s(path,L"SynthScan mission and wallet report.%s",ext);
    OPENFILENAMEW dialog{sizeof(dialog)};dialog.hwndOwner=page;dialog.lpstrFile=path;dialog.nMaxFile=32768;
    dialog.lpstrFilter=id==503?L"CSV data\0*.csv\0":id==504?L"JSON with source observations\0*.json\0":L"Readable HTML report\0*.html\0";
    dialog.lpstrDefExt=ext;dialog.Flags=OFN_OVERWRITEPROMPT|OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST;
    if(GetSaveFileNameW(&dialog))queue(obj({{"action",str("export")},{"path",str(utf8(path))}}));
}
void layout(){
    if(!page)return;RECT r{};GetClientRect(page,&r);scale=GetDpiForWindow(page)/96.f;float w=r.right/scale,h=r.bottom/scale;
    NativeRedraw::Layout pending(page);
    auto put=[&](int id,float x,float y,float width,float height){pending.place(control(id),px(x),px(y),std::max(1,px(width)),std::max(1,px(height)));};
    put(503,w-280,14,78,30);put(504,w-194,14,78,30);put(505,w-108,14,92,30);
    float filter=(w-64)/5;const int filterIds[]={506,507,508,509,514};for(int i=0;i<5;i++)put(filterIds[i],16+i*(filter+8),83,filter,210);
    put(501,16,121,std::max(120.f,w-302),29);put(502,w-278,121,78,29);put(510,w-192,121,84,29);put(511,w-100,121,84,29);
    put(500,16,182,w-32,std::max(100.f,h-362));put(512,16,std::max(292.f,h-170),w-32,139);
    pending.apply();
    InvalidateRect(page,nullptr,FALSE);
}
void selectDetail(){
    int at=ListView_GetNextItem(list,-1,LVNI_SELECTED);const auto& rows=field(model,"entries").items;
    if(at<0||size_t(at)>=rows.size()){SetWindowTextW(detail,L"Select an activity to inspect the balance window, reward comparisons and source coverage.");return;}
    // Preserve the detail box scroll position when updating the same entry
    // (e.g. a background classification change) so the user is not jerked back
    // to the top while reading evidence halfway down.
    const std::string nextId=rows[at].textOr("id");
    const int savedLine=(nextId==selected)?int(SendMessageW(detail,EM_GETFIRSTVISIBLELINE,0,0)):0;
    selected=nextId;auto body=rows[at].textOr("detail");std::string lines;for(char c:body){if(c=='\n'&&(lines.empty()||lines.back()!='\r'))lines+='\r';lines+=c;}SetWindowTextW(detail,wide(lines).c_str());
    if(savedLine>0)SendMessageW(detail,EM_LINESCROLL,0,savedLine);
}
void paintHeader(HWND hwnd,HDC target=nullptr){
    PAINTSTRUCT ps{};HDC dc=target?target:BeginPaint(hwnd,&ps);RECT client{};GetClientRect(hwnd,&client);
    HBRUSH fill=CreateSolidBrush(RGB(28,39,51)),border=CreateSolidBrush(RGB(52,67,81));FillRect(dc,&client,fill);
    auto previous=SelectObject(dc,font);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(161,205,208));
    for(int i=0;i<Header_GetItemCount(hwnd);i++){RECT at{};Header_GetItemRect(hwnd,i,&at);wchar_t value[160]{};HDITEMW item{};item.mask=HDI_TEXT;item.pszText=value;item.cchTextMax=160;Header_GetItem(hwnd,i,&item);RECT label=at;label.left+=px(7);label.right-=px(5);DrawTextW(dc,value,-1,&label,DT_SINGLELINE|DT_VCENTER|DT_END_ELLIPSIS);RECT edge{at.right-1,at.top,at.right,at.bottom};FillRect(dc,&edge,border);}
    SelectObject(dc,previous);DeleteObject(fill);DeleteObject(border);if(!target)EndPaint(hwnd,&ps);
}
LRESULT CALLBACK headerProcedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp,UINT_PTR,DWORD_PTR){
    if(message==WM_PAINT){paintHeader(hwnd);return 0;}
    if(message==WM_PRINTCLIENT){paintHeader(hwnd,reinterpret_cast<HDC>(wp));return 0;}
    if(message==WM_ERASEBKGND)return 1;
    if(message==WM_NCDESTROY)RemoveWindowSubclass(hwnd,headerProcedure,1);
    return DefSubclassProc(hwnd,message,wp,lp);
}
void refresh(){
    auto next=read(folder/L"mission_log_view.json",32*1024*1024);if(next.kind!=Json::Kind::Object)return;
    auto columns=encode(field(next,"columns")),rows=encode(field(next,"entries"));
    bool columnsChanged=columns!=lastColumns,rowsChanged=rows!=lastRows;
    model=std::move(next);
    if(columnsChanged||rowsChanged){
        // Preserve scroll position across background refreshes so the user
        // is not snapped back to the top whenever new data arrives.
        const int savedTop=columnsChanged?0:ListView_GetTopIndex(list);
        const int savedHoriz=columnsChanged?0:GetScrollPos(list,SB_HORZ);
        filling=true;SendMessageW(list,WM_SETREDRAW,FALSE,0);ListView_DeleteAllItems(list);
        if(columnsChanged){
            while(ListView_DeleteColumn(list,0)){}
            const auto& labels=field(model,"columns").items;
            for(size_t i=0;i<labels.size();i++)if(labels[i].items.size()==2){auto name=wide(labels[i].items[0].text);LVCOLUMNW column{LVCF_TEXT|LVCF_WIDTH|LVCF_SUBITEM};column.pszText=name.data();column.cx=px(float(labels[i].items[1].number));column.iSubItem=int(i);ListView_InsertColumn(list,int(i),&column);}
        }
        int selection=-1;const auto& entries=field(model,"entries").items;
        for(size_t i=0;i<entries.size();i++){
            const auto& cells=field(entries[i],"cells").items;
            for(size_t c=0;c<cells.size();c++){
                auto label=wide(cells[c].text);if(c==0){LVITEMW item{LVIF_TEXT|LVIF_PARAM};item.iItem=int(i);item.pszText=label.data();item.lParam=LPARAM(i);ListView_InsertItem(list,&item);}else ListView_SetItemText(list,int(i),int(c),label.data());
            }
            if(entries[i].textOr("id")==selected)selection=int(i);
        }
        if(selection>=0){
            ListView_SetItemState(list,selection,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);
        } else if(savedTop>0){
            // No selected row to anchor on; scroll back to where the user was.
            const int newCount=ListView_GetItemCount(list);
            const int clampedTop=std::min(savedTop,std::max(0,newCount-1));
            ListView_EnsureVisible(list,std::min(clampedTop+ListView_GetCountPerPage(list)-1,newCount-1),FALSE);
            ListView_EnsureVisible(list,clampedTop,FALSE);
        }
        // Restore horizontal scroll offset.
        if(savedHoriz!=0)ListView_Scroll(list,savedHoriz-GetScrollPos(list,SB_HORZ),0);
        SendMessageW(list,WM_SETREDRAW,TRUE,0);InvalidateRect(list,nullptr,TRUE);filling=false;selectDetail();lastRows=rows;lastColumns=columns;
    }
    EnableWindow(control(510),model.numberOr("display_offset")>0);
    EnableWindow(control(511),model.numberOr("display_offset")+model.numberOr("display_limit")<model.numberOr("display_count"));
    EnableWindow(control(514),choice(506)==0||choice(506)==4);
    EnableWindow(control(507),choice(506)==0||choice(506)==1||choice(506)==3);
    InvalidateRect(page,nullptr,FALSE);
}
void paint(HDC target=nullptr){
    PAINTSTRUCT ps{};HDC dc=target?target:BeginPaint(page,&ps);RECT r{};GetClientRect(page,&r);
    Gdiplus::Graphics g(dc);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
    g.Clear(SynthGlass::Base);float w=r.right/scale,h=r.bottom/scale;
    SynthGlass::text(g,L"MISSION & WALLET HISTORY",{16*scale,8*scale,(w-310)*scale,25*scale},14*scale,SynthGlass::Accent,true);
    const auto& sessions=field(model,"sessions").items;const Json* current=nullptr;
    for(const auto& s:sessions)if(s.textOr("id")==model.textOr("current_session")){current=&s;break;}
    auto summary=current?L"This session · "+amount(current->numberOr("completed"))+L" completed · "+amount(current->numberOr("failed"))+L" failed / other · "+amount(current->numberOr("abandoned"))+L" abandoned":L"Waiting for a saved session";
    SynthGlass::text(g,summary,{16*scale,34*scale,(w-32)*scale,22*scale},11.5f*scale,SynthGlass::Ink);
    std::wstring net;
    if(current){
        for(const auto& change:field(*current,"reputation").items){if(!net.empty())net+=L" · ";net+=wide(change.textOr("faction"))+L" "+amount(change.numberOr("delta"),true);}
        for(const auto& change:field(*current,"wallet").items)if(change.textOr("currency")=="AUEC"&&field(change,"delta").kind==Json::Kind::Number){if(!net.empty())net+=L" · ";net+=L"aUEC net "+amount(change.numberOr("delta"),true);}
        if(model.numberOr("wallet_reads")>1){if(!net.empty())net+=L" · ";net+=L"Unclassified "+amount(field(*current,"wallet_reconciliation").numberOr("unclassified_net"),true)+L" aUEC";}
    }
    SynthGlass::text(g,net.empty()?L"Balances are retained from the first verified read; earlier activity may be missing.":net,{16*scale,57*scale,(w-32)*scale,20*scale},10.5f*scale,SynthGlass::Muted);
    auto coverage=model.textOr("mode")=="wallet"?L"Wallet entries are net changes between reads; offsetting transactions between reads can be missed.":L"Balance windows show measured changes. Mission links and split matches are comparisons, not confirmed receipts.";
    SynthGlass::text(g,coverage,{16*scale,154*scale,(w-32)*scale,20*scale},10*scale,SynthGlass::Muted);
    std::wstring footer=now()-model.numberOr("written_at")>8?L"Recorder offline · showing saved observations":flag(model,"recording")?L"Recording · "+amount(model.numberOr("reputation_reads"))+L" reputation reads · "+amount(model.numberOr("wallet_reads"))+L" wallet reads":L"Collection paused · account access disabled";
    auto error=model.textOr("error");if(!error.empty())footer+=L" · "+wide(error);
    if(!model.textOr("wallet_error").empty())footer+=L" · Wallet refresh unavailable";
    if(model.numberOr("latest_rep_at")>0)footer+=L" · rep "+when(model.numberOr("latest_rep_at"));
    if(model.numberOr("latest_wallet_at")>0)footer+=L" · wallet "+when(model.numberOr("latest_wallet_at"));
    footer+=L" · "+amount(model.numberOr("display_count"))+L" matching activities";
    if(!model.textOr("note").empty()&&now()<model.numberOr("note_until"))footer=wide(model.textOr("note"));
    SynthGlass::text(g,footer,{16*scale,(h-27)*scale,(w-32)*scale,23*scale},10*scale,SynthGlass::Muted);
    if(!target)EndPaint(page,&ps);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_SIZE){layout();return 0;}
    if(message==WM_TIMER){refresh();return 0;}
    if(message==WM_PAINT){paint();return 0;}
    if(message==WM_PRINTCLIENT){paint(reinterpret_cast<HDC>(wp));return 0;}
    if(message==WM_ERASEBKGND)return 1;
    if(message==WM_CTLCOLORSTATIC||message==WM_CTLCOLOREDIT||message==WM_CTLCOLORLISTBOX){auto dc=reinterpret_cast<HDC>(wp);SetTextColor(dc,RGB(220,230,239));SetBkColor(dc,RGB(24,30,40));return LRESULT(input);}
    if(message==WM_MEASUREITEM){auto item=reinterpret_cast<MEASUREITEMSTRUCT*>(lp);if(item->CtlType==ODT_COMBOBOX){item->itemHeight=px(22);return TRUE;}}
    if(message==WM_DRAWITEM){
        auto item=reinterpret_cast<DRAWITEMSTRUCT*>(lp);Gdiplus::Graphics g(item->hDC);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
        if(item->CtlType==ODT_COMBOBOX){
            std::wstring label;int at=int(item->itemID);
            if(at>=0){int length=int(SendMessageW(item->hwndItem,CB_GETLBTEXTLEN,at,0));if(length>=0&&length<500){label.resize(length+1);SendMessageW(item->hwndItem,CB_GETLBTEXT,at,reinterpret_cast<LPARAM>(label.data()));label.resize(length);}}
            else{wchar_t value[500]{};GetWindowTextW(item->hwndItem,value,500);label=value;}
            Gdiplus::SolidBrush brush(item->itemState&ODS_SELECTED?Gdiplus::Color(255,39,66,76):Gdiplus::Color(255,24,30,40));
            g.FillRectangle(&brush,int(item->rcItem.left),int(item->rcItem.top),int(item->rcItem.right-item->rcItem.left),int(item->rcItem.bottom-item->rcItem.top));
            SynthGlass::text(g,label,{float(item->rcItem.left)+6*scale,float(item->rcItem.top),float(item->rcItem.right-item->rcItem.left)-10*scale,float(item->rcItem.bottom-item->rcItem.top)},12*scale,SynthGlass::Ink);return TRUE;
        }
        g.Clear(SynthGlass::Base);g.ScaleTransform(scale,scale);wchar_t label[80]{};GetWindowTextW(item->hwndItem,label,80);SynthGlass::button(g,{0,0,item->rcItem.right/scale,item->rcItem.bottom/scale},label,"",false,(item->itemState&ODS_SELECTED)!=0,(item->itemState&ODS_DISABLED)!=0);return TRUE;
    }
    if(message==WM_NOTIFY){
        auto header=reinterpret_cast<NMHDR*>(lp);
        if(header->hwndFrom==list&&header->code==LVN_ITEMCHANGED&&!filling)selectDetail();
        if(header->hwndFrom==list&&header->code==NM_RCLICK){classifyMenu();return 0;}
        if(header->hwndFrom==list&&header->code==NM_CUSTOMDRAW){
            auto draw=reinterpret_cast<NMLVCUSTOMDRAW*>(lp);
            if(draw->nmcd.dwDrawStage==CDDS_PREPAINT)return CDRF_NOTIFYITEMDRAW;
            if(draw->nmcd.dwDrawStage==CDDS_ITEMPREPAINT)return CDRF_NOTIFYSUBITEMDRAW;
            if(draw->nmcd.dwDrawStage==(CDDS_ITEMPREPAINT|CDDS_SUBITEM)){
                const auto& entries=field(model,"entries").items;auto row=size_t(draw->nmcd.dwItemSpec);
                if(row<entries.size()){const auto& cells=field(entries[row],"cells").items;if(size_t(draw->iSubItem)<cells.size()){
                    auto value=cells[draw->iSubItem].text;draw->clrText=!value.empty()&&value[0]=='-'?RGB(244,133,145):!value.empty()&&value[0]=='+'?RGB(127,217,200):RGB(221,232,241);
                }}return CDRF_NEWFONT;
            }
        }
    }
    if(message==WM_CONTEXTMENU&&reinterpret_cast<HWND>(wp)==list&&lp==-1){classifyMenu();return 0;}
    if(message==WM_COMMAND){
        int id=LOWORD(wp),code=HIWORD(wp);
        if(id==502&&code==BN_CLICKED)request();
        else if(id>=503&&id<=505&&code==BN_CLICKED)exportFile(id);
        else if(((id>=506&&id<=509)||id==514)&&code==CBN_SELCHANGE)request();
        else if(id==510&&code==BN_CLICKED)request(int(model.numberOr("display_offset"))-100);
        else if(id==511&&code==BN_CLICKED)request(int(model.numberOr("display_offset"))+100);
        return 0;
    }
    if(message==WM_CLOSE){ShowWindow(hwnd,SW_HIDE);return 0;}
    return DefWindowProcW(hwnd,message,wp,lp);
}
HWND add(const wchar_t* cls,const wchar_t* title,DWORD style,int id){auto hwnd=CreateWindowExW(0,cls,title,WS_CHILD|WS_VISIBLE|WS_TABSTOP|style,0,0,1,1,page,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);SendMessageW(hwnd,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return hwnd;}
void combo(int id,std::initializer_list<const wchar_t*> labels){auto hwnd=add(L"COMBOBOX",L"",CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS|WS_VSCROLL,id);for(auto label:labels)SendMessageW(hwnd,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(label));SendMessageW(hwnd,CB_SETCURSEL,0,0);}
}
void show(HWND parent,const std::filesystem::path& directory){
    folder=directory;
    if(!page){
        scale=GetDpiForWindow(parent)/96.f;INITCOMMONCONTROLSEX common{sizeof(common),ICC_LISTVIEW_CLASSES};InitCommonControlsEx(&common);
        WNDCLASSW cls{};cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanMissionLog";cls.lpfnWndProc=procedure;cls.hCursor=LoadCursorW(nullptr,IDC_ARROW);RegisterClassW(&cls);
        page=CreateWindowExW(WS_EX_CONTROLPARENT,cls.lpszClassName,L"Mission & wallet log",WS_CHILD|WS_CLIPCHILDREN,0,0,1050,700,parent,nullptr,cls.hInstance,nullptr);
        font=CreateFontW(-px(12),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        list=add(WC_LISTVIEWW,L"",LVS_REPORT|LVS_SINGLESEL|LVS_SHOWSELALWAYS|WS_BORDER,500);ListView_SetExtendedListViewStyle(list,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER|LVS_EX_LABELTIP);
        SetWindowTheme(list,L"DarkMode_Explorer",nullptr);ListView_SetBkColor(list,RGB(18,23,31));ListView_SetTextBkColor(list,RGB(18,23,31));ListView_SetTextColor(list,RGB(221,232,241));
        SetWindowSubclass(ListView_GetHeader(list),headerProcedure,1,0);
        add(L"EDIT",L"",ES_AUTOHSCROLL|WS_BORDER,501);SendMessageW(control(501),EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(L"Search missions, organizations or activity"));
        add(L"BUTTON",L"Search",BS_OWNERDRAW,502);add(L"BUTTON",L"CSV",BS_OWNERDRAW,503);add(L"BUTTON",L"JSON",BS_OWNERDRAW,504);add(L"BUTTON",L"Report",BS_OWNERDRAW,505);
        combo(506,{L"All activity",L"Missions",L"Reputation changes",L"Mission rewards",L"aUEC ledger",L"Session recaps"});
        combo(507,{L"All outcomes",L"Completed",L"Failed / other",L"Abandoned",L"Active"});combo(508,{L"All sessions",L"This session"});combo(509,{L"All changes",L"Increases / gains",L"Decreases / losses"});
        combo(514,{L"All wallet categories",L"Unclassified",L"Mission reward",L"Player transfer",L"Repairs",L"Refueling",L"Store purchase",L"Vehicle / equipment",L"Cargo trading",L"Fees / fines",L"Other"});
        add(L"BUTTON",L"Previous",BS_OWNERDRAW,510);add(L"BUTTON",L"Next",BS_OWNERDRAW,511);
        detail=add(L"EDIT",L"Select an activity to inspect its evidence.",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL|WS_BORDER,512);
        SendMessageW(detail,EM_SETLIMITTEXT,100000,0);SetTimer(page,1,1000,nullptr);
    }
    refresh();request();SynthPages::mount(page);layout();ShowWindow(page,SW_SHOW);
}
void close(){if(page)DestroyWindow(page);page=nullptr;list=nullptr;detail=nullptr;if(font)DeleteObject(font);font=nullptr;lastRows.clear();lastColumns.clear();model={};}
}
