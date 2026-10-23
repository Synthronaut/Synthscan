// SynthScan native lifecycle/workspace. Original mining application stays intact.
#define UNICODE
#define _UNICODE
#include "SynthScanShell.h"
#include "SynthJson.h"
#include "SynthDiaryUI.h"
#include "SynthNavUI.h"
#include "MiningAdvice.h"
#include "MinerGUI.h"
#include "AppPaths.h"
#include "ScreenCapture.h"
#include "resource.h"
#include <commctrl.h>
#include <commdlg.h>
#include <uxtheme.h>
#include <shellapi.h>
#include <dwmapi.h>
#include <gdiplus.h>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <set>
#include <cwctype>
#include <algorithm>
#include <fstream>
#pragma comment(lib,"comctl32.lib")
#pragma comment(lib,"uxtheme.lib")
namespace SynthScan {
namespace {
SCMiner::MinerGUI* mining=nullptr;
std::function<bool(const std::string&)> confirmOwned;
HANDLE mutexHandle=nullptr,readyHandle=nullptr,showHandle=nullptr,bridgeProcess=nullptr,job=nullptr,controlProcess=nullptr;
HWND host=nullptr,panel=nullptr,listing=nullptr,detail=nullptr,search=nullptr,kind=nullptr,category=nullptr,status=nullptr;
HWND autoCheck=nullptr,scanCheck=nullptr,hudCheck=nullptr,sessionCheck=nullptr,hotkey=nullptr,editName=nullptr,editReminder=nullptr,editMinutes=nullptr;
HFONT font=nullptr,titleFont=nullptr;
HBRUSH background=nullptr,card=nullptr;
bool isAutomatic=false,testing=false,attached=false,hudVisible=true,scanOnLaunch=true,showSession=true,hotkeyOK=false,snareAlerts=true;
bool pirateDetails=false,quest=false,pirate=false,miningResume=true,placementLocked=false,activityExpanded=true;
std::string activityCommandId;
int currentTab=0,hotkeyChoice=0,selected=-1;
Json state,settings,library;std::vector<Json> visible;
std::set<std::string> favorites;
std::unique_ptr<Gdiplus::Bitmap> icon;
std::string lastState,summary="Session service starting",note;
std::string controlCompleted="Startup registration updated.";
std::string reputationNotice;
std::filesystem::path root,data;
double lastStateAt=0;
double uiScale=1;
int px(int value){return int(std::lround(value*uiScale));}
NOTIFYICONDATAW tray{};
constexpr int HOTKEY=31001,TRAY=WM_APP+41;
constexpr COLORREF BG=RGB(20,23,29),CARD=RGB(29,33,41),TEXT=RGB(233,237,241),MUTED=RGB(149,160,173),GOLD=RGB(218,160,79);
double epoch(){return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
std::wstring lower(std::wstring value){for(auto& c:value)c=std::towlower(c);return value;}
std::wstring text(HWND h){int n=GetWindowTextLengthW(h);std::wstring s(n+1,0);GetWindowTextW(h,s.data(),n+1);s.resize(n);return s;}
std::wstring quoteArg(const std::wstring& s){std::wstring out=L"\"";size_t slash=0;for(auto c:s){if(c==L'\\'){slash++;continue;}if(c==L'"'){out.append(slash*2+1,L'\\');out+=c;}else{out.append(slash,L'\\');out+=c;}slash=0;}out.append(slash*2,L'\\');return out+L'"';}
std::filesystem::path startupLink(){wchar_t appdata[32768];DWORD n=GetEnvironmentVariableW(L"APPDATA",appdata,32768);return n?std::filesystem::path(appdata)/L"Microsoft/Windows/Start Menu/Programs/Startup/SynthScan Game Watcher.lnk":std::filesystem::path();}
bool spawnPython(const wchar_t* script,const std::vector<std::wstring>& args,HANDLE* result=nullptr){
    Json runtime=read(SCMiner::AppPaths::program()/L"native_runtime.json");
    auto py=wide(runtime.textOr("pythonw"));if(py.empty())return false;
    std::wstring command=quoteArg(py)+L" -B "+quoteArg((root/script).wstring());for(auto& s:args)command+=L" "+quoteArg(s);
    STARTUPINFOW si{sizeof(si)};PROCESS_INFORMATION pi{};
    if(!CreateProcessW(py.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW|BELOW_NORMAL_PRIORITY_CLASS,nullptr,root.c_str(),&si,&pi))return false;
    CloseHandle(pi.hThread);if(job&&std::wstring(script)==L"native_bridge.py")AssignProcessToJobObject(job,pi.hProcess);
    if(result)*result=pi.hProcess;else CloseHandle(pi.hProcess);return true;
}
void saveSettings(){settings=obj({{"scan_on_launch",boolean(scanOnLaunch)},{"show_hud",boolean(hudVisible)},{"session_strip",boolean(showSession)},{"snare_alerts",boolean(snareAlerts)},{"piracy_details",boolean(pirateDetails)},{"hud_mode",str(quest?"questing":pirate?"piracy":"mining")},{"mining_resume",boolean(miningResume)},{"hud_locked",boolean(placementLocked)},{"activity_expanded",boolean(activityExpanded)},{"hotkey",num(hotkeyChoice)}});if(!write(data/L"native_settings.json",settings))note="Could not save HUD settings.";}
void togglePlacement(){placementLocked=!placementLocked;if(mining)mining->updateClickThrough();saveSettings();}
void modeControls(){if(!mining)return;if(pirate)SetWindowTextW(GetDlgItem(mining->windowHandle(),31814),flag(field(state,"piracy_watch"),"waiting_active")?L"Pause wait":L"Start wait");if(pirate){SetWindowTextW(GetDlgItem(mining->windowHandle(),1002),pirateDetails?L"Details -":L"Details +");SetWindowTextW(GetDlgItem(mining->windowHandle(),31817),snareAlerts?L"Alerts on":L"Muted");}if(quest)SetWindowTextW(GetDlgItem(mining->windowHandle(),1002),L"Next");mining->placeOreRowsButton();for(int id:{31810,31811,31813})InvalidateRect(GetDlgItem(mining->windowHandle(),id),nullptr,FALSE);InvalidateRect(mining->windowHandle(),nullptr,FALSE);}
void setMode(int value){
    const int current=quest?2:pirate?1:0;
    if(current==value||!mining)return;
    if(current==0){miningResume=text(GetDlgItem(mining->windowHandle(),1002))==L"Live on";if(miningResume)SendMessageW(mining->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);endMiningRock();}
    pirate=value==1;quest=value==2;
    if(value==0){mining->setLiveModeActive(false);if(miningResume)SendMessageW(mining->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);}
    saveSettings();modeControls();mining->refreshActivityLayout();
}
void applyHotkey(){
    if(testing){hotkeyOK=true;return;}
    UnregisterHotKey(host,HOTKEY);
    UINT modifiers=hotkeyChoice==2?(MOD_CONTROL|MOD_SHIFT):(MOD_CONTROL|MOD_ALT);
    UINT key=hotkeyChoice==0?'H':VK_F10;
    hotkeyOK=RegisterHotKey(host,HOTKEY,modifiers|MOD_NOREPEAT,key)!=FALSE;
    if(!hotkeyOK)note="HUD hotkey is already used by another app. Choose another combination in Settings.";
}
void showHud(bool value){hudVisible=value;if(mining){if(value&&activityExpanded){ShowWindow(mining->windowHandle(),SW_SHOWNOACTIVATE);mining->keepOverlayAboveGame(true);}else mining->hide();}saveSettings();}
void setActivityExpanded(bool value){
    activityExpanded=value;
    if(mining){if(value&&hudVisible){if(!mining->isOverlayMode()){auto window=mining->windowHandle();bool hadNoActivate=(GetWindowLongPtrW(window,GWL_EXSTYLE)&WS_EX_NOACTIVATE)!=0;SetWindowLongPtrW(window,GWL_EXSTYLE,GetWindowLongPtrW(window,GWL_EXSTYLE)|WS_EX_NOACTIVATE);mining->toggleOverlayMode();if(!hadNoActivate)SetWindowLongPtrW(window,GWL_EXSTYLE,GetWindowLongPtrW(window,GWL_EXSTYLE)&~WS_EX_NOACTIVATE);}ShowWindow(mining->windowHandle(),SW_SHOWNOACTIVATE);mining->keepOverlayAboveGame(true);}else mining->hide();}
    saveSettings();
}
void activityControl(){
    auto request=read(data/L"activity_hud_command.json");auto id=request.textOr("id");double age=epoch()-request.numberOr("at");
    if(!id.empty()&&id!=activityCommandId&&request.numberOr("owner_pid")==GetCurrentProcessId()&&age>=-.25&&age<5&&request.textOr("action")=="set_activity_expanded"){
        activityCommandId=id;setActivityExpanded(flag(request,"expanded",activityExpanded));
    }
}
void desktop(){if(!mining)return;if(mining->isOverlayMode())mining->toggleOverlayMode();hudVisible=true;activityExpanded=true;mining->show();ShowWindow(mining->windowHandle(),SW_RESTORE);SetForegroundWindow(mining->windowHandle());saveSettings();}
void command(Json value){
    static unsigned sequence=0;char id[80];sprintf_s(id,"%020llu-%010u-%010u",GetTickCount64(),GetCurrentProcessId(),++sequence);
    value.members.push_back({"id",str(id)});value.members.push_back({"session_token",field(state,"session_token")});
    auto destination=data/L"workspace_command.json";
    if(!testing&&(value.textOr("action").find("diary_")==0||value.textOr("action").find("nav_")==0||value.textOr("action").find("session_")==0)){auto folder=data/L"diary_commands";std::error_code error;std::filesystem::create_directories(folder,error);destination=folder/std::filesystem::u8path(std::string(id)+".json");}
    if(!write(destination,value))note="Could not queue workspace action.";else note="Working…";
}
HWND control(const wchar_t* cls,const wchar_t* label,DWORD style,int x,int y,int w,int h,int id){
    if(cls==std::wstring(L"BUTTON")&&(style&0xf)==BS_PUSHBUTTON)style|=BS_OWNERDRAW;
    HWND hwnd=CreateWindowExW(cls==std::wstring(L"EDIT")?WS_EX_CLIENTEDGE:0,cls,label,WS_CHILD|WS_VISIBLE|style,px(x),px(y),px(w),px(h),panel,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    SetWindowTheme(hwnd,L"DarkMode_Explorer",nullptr);
    SendMessageW(hwnd,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return hwnd;
}
void addRow(const Json& row){
    int index=int(visible.size());visible.push_back(row);
    auto name=wide(row.textOr("name"));LVITEMW item{};item.mask=LVIF_TEXT;item.iItem=index;item.pszText=name.data();ListView_InsertItem(listing,&item);
    auto k=wide(row.textOr("kind")),c=wide(row.textOr("category"));ListView_SetItemText(listing,index,1,k.data());ListView_SetItemText(listing,index,2,c.data());
    if(currentTab==2){const char* keys[]={"joined_local","left_local","kind","shard_id","name","duration","visit"};for(int col=0;col<7;col++){auto value=wide(row.textOr(keys[col]));ListView_SetItemText(listing,index,col,value.data());}}
}
void listRows(){
    if(!listing)return;
    std::string prior=selected>=0&&selected<int(visible.size())?visible[selected].textOr("id"):"";
    SendMessageW(listing,WM_SETREDRAW,FALSE,0);ListView_DeleteAllItems(listing);visible.clear();selected=-1;icon.reset();
    std::wstring query=lower(text(search)),type=text(kind),cat=text(category);
    auto append=[&](const Json& row){
        if(!query.empty()){auto hay=lower(wide(row.textOr("name")+" "+row.textOr("detail")));if(currentTab==2){std::wistringstream terms(query);std::wstring term;while(terms>>term)if(hay.find(term)==std::wstring::npos)return;}else if(hay.find(query)==std::wstring::npos)return;}
        if(currentTab==0&&type==L"Favorites"&&!favorites.count(row.textOr("id")))return;
        if(currentTab==0&&type!=L"All"&&type!=L"Favorites"&&wide(row.textOr("kind"))!=type)return;
        if(currentTab==0&&cat!=L"All categories"&&wide(row.textOr("category"))!=cat)return;
        addRow(row);
    };
    if(currentTab==0)for(auto& row:field(library,"rows").items)append(row);
    if(currentTab==1)for(auto& row:field(state,"plans").items)append(row);
    if(currentTab==2)for(auto& row:field(state,"session_rows").items)append(row);
    if(currentTab==3){
        Json legacy=read(data/L"legacy/blueprints_library.json");
        for(auto& item:legacy.members)append(obj({{"id",str(item.first)},{"name",str(item.second.textOr("name",item.first))},{"kind",str("Legacy ownership")},{"category",str("Needs review")},{"detail",str("Imported ownership record. Verify it still applies after game wipes before confirming.\n\n"+encode(item.second))}}));
        Json inbox=read(data/L"fabricator_scan_inbox.json");
        for(auto& item:inbox.members)append(obj({{"id",str(item.first)},{"name",str(item.second.textOr("name"))},{"kind",str("Screen observation")},{"category",str("Unconfirmed")},{"detail",str(encode(item.second))}}));
        Json inv=read(data/L"legacy/inventory.json");
        for(auto& item:field(inv,"totals").members)append(obj({{"id",str(item.first)},{"name",str(item.first)},{"kind",str("Legacy cargo")},{"category",str("Imported snapshot")},{"detail",str("Preserved legacy inventory total: "+encode(item.second)+" SCU. This is a saved record, not a current cargo scan.\n\n"+encode(inv))}}));
    }
    SendMessageW(listing,WM_SETREDRAW,TRUE,0);InvalidateRect(listing,nullptr,TRUE);
    if(!visible.empty()){
        int index=0;for(int i=0;i<int(visible.size());i++)if(visible[i].textOr("id")==prior){index=i;break;}
        ListView_SetItemState(listing,index,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);ListView_EnsureVisible(listing,index,FALSE);
    }
    if(currentTab==2){auto count=int(field(state,"session_log").numberOr("count"));auto offset=int(field(state,"session_log").numberOr("offset"));auto label=std::to_string(visible.empty()?0:offset+1)+"–"+std::to_string(offset+int(visible.size()))+" of "+std::to_string(count)+" visits · times UTC+08:00";SetDlgItemTextW(panel,227,wide(label).c_str());EnableWindow(GetDlgItem(panel,225),offset>0);EnableWindow(GetDlgItem(panel,226),offset+100<count);}
    SetWindowTextW(status,wide(std::to_string(visible.size())+" entries · "+note).c_str());
}
void selection(){
    int i=ListView_GetNextItem(listing,-1,LVNI_SELECTED);if(i<0||i>=int(visible.size()))return;selected=i;
    auto row=visible[i];std::string body=row.textOr("detail");
    if(favorites.count(row.textOr("id")))body="★ Favorite\n\n"+body;
    std::wstring rendered=wide(body);for(size_t p=0;(p=rendered.find(L'\n',p))!=std::wstring::npos;p+=2)rendered.replace(p,1,L"\r\n");
    SetWindowTextW(detail,rendered.c_str());icon.reset();
    if(currentTab==2&&editReminder&&GetFocus()!=editReminder)SetWindowTextW(editReminder,wide(row.textOr("notes")).c_str());
    auto path=row.textOr("icon");if(!path.empty())icon=std::make_unique<Gdiplus::Bitmap>(wide(path).c_str());
    InvalidateRect(panel,nullptr,FALSE);
}
LRESULT CALLBACK headerPaint(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(message==WM_ERASEBKGND)return TRUE;
    if(message==WM_PAINT||message==WM_PRINTCLIENT){
        PAINTSTRUCT ps{};HDC dc=message==WM_PAINT?BeginPaint(hwnd,&ps):reinterpret_cast<HDC>(w);
        RECT rc;GetClientRect(hwnd,&rc);FillRect(dc,&rc,card);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,MUTED);SelectObject(dc,font);
        for(int i=0;i<Header_GetItemCount(hwnd);i++){RECT cell;Header_GetItemRect(hwnd,i,&cell);wchar_t label[200]{};HDITEMW item{};item.mask=HDI_TEXT;item.pszText=label;item.cchTextMax=200;Header_GetItem(hwnd,i,&item);cell.left+=px(8);DrawTextW(dc,label,-1,&cell,DT_SINGLELINE|DT_VCENTER|DT_NOPREFIX);}
        if(message==WM_PAINT)EndPaint(hwnd,&ps);return 0;
    }
    return DefSubclassProc(hwnd,message,w,l);
}
void rebuild(int tab){
    currentTab=tab;selected=-1;icon.reset();
    HWND child=GetWindow(panel,GW_CHILD);while(child){HWND next=GetWindow(child,GW_HWNDNEXT);DestroyWindow(child);child=next;}
    listing=detail=search=kind=category=nullptr;
    const wchar_t* names[]={L"Game library",L"Material picker",L"Server log",L"Review & imports",L"Startup & HUD"};
    for(int i=0;i<5;i++)control(L"BUTTON",names[i],BS_PUSHBUTTON,18+i*168,62,160,30,100+i);
    status=control(L"STATIC",wide(note).c_str(),SS_LEFT,20,596,816,45,200);
    if(tab==4){
        autoCheck=control(L"BUTTON",L"Launch SynthScan with Star Citizen",BS_AUTOCHECKBOX,28,122,700,28,301);
        scanCheck=control(L"BUTTON",L"Start mining scans automatically with the game",BS_AUTOCHECKBOX,28,166,700,28,302);
        hudCheck=control(L"BUTTON",L"Show HUD",BS_AUTOCHECKBOX,28,210,700,28,303);
        sessionCheck=control(L"BUTTON",L"Show shard, region and available measurements in the HUD",BS_AUTOCHECKBOX,28,254,720,28,304);
        SendMessageW(autoCheck,BM_SETCHECK,std::filesystem::exists(startupLink())?BST_CHECKED:BST_UNCHECKED,0);
        SendMessageW(scanCheck,BM_SETCHECK,scanOnLaunch?BST_CHECKED:BST_UNCHECKED,0);SendMessageW(hudCheck,BM_SETCHECK,hudVisible?BST_CHECKED:BST_UNCHECKED,0);
        SendMessageW(sessionCheck,BM_SETCHECK,showSession?BST_CHECKED:BST_UNCHECKED,0);
        control(L"BUTTON",L"Snare Watch: sound + banner for logged interdiction reports",BS_AUTOCHECKBOX,28,284,720,24,311);SendDlgItemMessageW(panel,311,BM_SETCHECK,snareAlerts?BST_CHECKED:BST_UNCHECKED,0);
        control(L"STATIC",L"Show / hide HUD hotkey",SS_LEFT,28,318,400,22,0);
        hotkey=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,28,346,310,180,305);
        for(auto value:{L"Ctrl + Alt + H",L"Ctrl + Alt + F10",L"Ctrl + Shift + F10"})SendMessageW(hotkey,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(value));
        SendMessageW(hotkey,CB_SETCURSEL,hotkeyChoice,0);
        control(L"BUTTON",L"Save startup & HUD settings",BS_PUSHBUTTON,28,390,300,34,306);
        control(L"BUTTON",L"Show / hide HUD now",BS_PUSHBUTTON,348,390,240,34,307);
        control(L"BUTTON",L"Open desktop view",BS_PUSHBUTTON,608,390,220,34,308);
        control(L"BUTTON",L"Enable player FPS · Windows permission",BS_PUSHBUTTON,28,435,390,30,309);
        control(L"BUTTON",L"Start network timing · Windows permission",BS_PUSHBUTTON,432,435,396,30,310);
        auto watcher=read(data/L"watcher_status.json");
        std::wstring explanation=L"Launching, scanning and showing the HUD are separate settings.\r\n";
        explanation+=testing?L"Offline UI check; global hotkeys are disabled. ":hotkeyOK?L"HUD hotkey registered. ":L"HUD hotkey unavailable. ";
        explanation+=wide(watcher.textOr("error"));
        explanation+=L"\r\nSnare Watch uses crime reports; unmonitored/friendly catches may be silent.\r\nServer FPS/population require a verified source.";
        if(flag(state,"fps_permission_required"))explanation+=L"\r\nUse the permission buttons above for player FPS/network timing.";
        explanation+=L"\r\nTiming helpers stop when SynthScan closes.";
        control(L"STATIC",explanation.c_str(),SS_LEFT,28,482,790,112,0);
        return;
    }
    search=control(L"EDIT",L"",ES_AUTOHSCROLL,20,112,tab==2?260:370,28,201);
    SendMessageW(search,EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(tab==2?L"Search time, shard, name or notes":L"Search items, materials or blueprints"));
    kind=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,tab==2?295:405,112,tab==2?170:160,200,202);
    if(tab==2){control(L"STATIC",L"Search name, shard, time or notes",SS_LEFT,20,94,260,17,0);control(L"STATIC",L"Region",SS_LEFT,295,94,170,17,0);category=control(L"EDIT",L"",ES_AUTOHSCROLL,480,112,145,28,203);control(L"EDIT",L"",ES_AUTOHSCROLL,640,112,145,28,221);control(L"BUTTON",L"Filter",BS_PUSHBUTTON,795,112,45,28,222);control(L"STATIC",L"From date",SS_LEFT,480,94,145,17,0);control(L"STATIC",L"Through date",SS_LEFT,640,94,145,17,0);SendMessageW(category,EM_SETCUEBANNER,TRUE,(LPARAM)L"YYYY-MM-DD");SendDlgItemMessageW(panel,221,EM_SETCUEBANNER,TRUE,(LPARAM)L"YYYY-MM-DD");}
    else category=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,580,112,260,250,203);
    if(tab==0){
        for(auto value:{L"All",L"Blueprint",L"Item",L"Material",L"Favorites"})SendMessageW(kind,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(value));
        std::set<std::string> cats;for(auto& row:field(library,"rows").items)cats.insert(row.textOr("category"));
        SendMessageW(category,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"All categories"));
        for(auto& value:cats){auto w=wide(value);SendMessageW(category,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(w.c_str()));}
    }else if(tab==1){
        for(auto value:{L"Ship",L"ROC",L"Hand",L"All"})SendMessageW(kind,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(value));
        for(auto value:{L"All",L"Stanton",L"Pyro",L"Nyx"})SendMessageW(category,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(value));
        SetWindowTextW(search,L"Taranite");
    }else if(tab==2){SendMessageW(kind,CB_ADDSTRING,0,(LPARAM)L"All regions");for(auto& value:field(field(state,"session_log"),"regions").items){auto region=wide(value.text);SendMessageW(kind,CB_ADDSTRING,0,(LPARAM)region.c_str());}}else{
        SendMessageW(kind,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"All"));
        SendMessageW(category,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"All categories"));
    }
    SendMessageW(kind,CB_SETCURSEL,0,0);if(tab!=2)SendMessageW(category,CB_SETCURSEL,0,0);else{const auto& f=field(field(state,"session_log"),"filters");SetWindowTextW(search,wide(f.textOr("query")).c_str());SetWindowTextW(category,wide(f.textOr("date_from")).c_str());SetDlgItemTextW(panel,221,wide(f.textOr("date_to")).c_str());auto region=wide(f.textOr("region"));int found=int(SendMessageW(kind,CB_FINDSTRINGEXACT,-1,(LPARAM)region.c_str()));if(found>=0)SendMessageW(kind,CB_SETCURSEL,found,0);}
    listing=control(WC_LISTVIEWW,L"",LVS_REPORT|LVS_SINGLESEL|LVS_SHOWSELALWAYS|WS_TABSTOP,20,155,820,tab==2?155:188,204);
    ListView_SetExtendedListViewStyle(listing,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER);ListView_SetBkColor(listing,CARD);ListView_SetTextBkColor(listing,CARD);ListView_SetTextColor(listing,TEXT);
    SetWindowSubclass(ListView_GetHeader(listing),headerPaint,1,0);
    const wchar_t* columns[]={L"Name",L"Type / weight",L"Category / region"};
    const wchar_t* sessionColumns[]={L"Joined",L"Left / observed",L"Region",L"Shard",L"Shard label",L"Duration",L"Visit"};int sessionWidths[]={160,160,85,65,130,85,100};
    for(int i=0;i<(tab==2?7:3);i++){LVCOLUMNW c{};c.mask=LVCF_TEXT|LVCF_WIDTH;c.pszText=const_cast<wchar_t*>(tab==2?sessionColumns[i]:columns[i]);c.cx=px(tab==2?sessionWidths[i]:(i==0?390:200));ListView_InsertColumn(listing,i,&c);}
    detail=control(L"EDIT",L"Select an entry",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL,100,355,740,184,205);
    if(tab==0){control(L"BUTTON",L"Favorite / unfavorite",BS_PUSHBUTTON,20,551,190,30,210);control(L"BUTTON",L"Mine this material",BS_PUSHBUTTON,224,551,190,30,211);}
    if(tab==1)control(L"BUTTON",L"Find mining destinations",BS_PUSHBUTTON,20,551,240,30,212);
    if(tab==2){
        control(L"BUTTON",L"Previous visits",BS_PUSHBUTTON,20,319,130,26,225);control(L"BUTTON",L"Next visits",BS_PUSHBUTTON,160,319,130,26,226);control(L"STATIC",L"",SS_LEFT,310,323,530,22,227);
        control(L"BUTTON",L"CSV…",BS_PUSHBUTTON,20,355,70,30,223);control(L"BUTTON",L"JSON…",BS_PUSHBUTTON,20,395,70,30,224);control(L"STATIC",L"Times:\r\nUTC+08",SS_LEFT,20,435,75,45,0);
        MoveWindow(detail,px(100),px(355),px(740),px(102),TRUE);
        editReminder=control(L"EDIT",L"",ES_MULTILINE|ES_AUTOVSCROLL|WS_VSCROLL,100,468,550,65,220);
        control(L"BUTTON",L"Save session note",BS_PUSHBUTTON,660,468,180,30,219);
        editName=control(L"EDIT",L"",ES_AUTOHSCROLL,20,551,300,28,215);
        SendMessageW(editName,EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(L"Shard name or reminder label"));
        control(L"BUTTON",L"Name current shard",BS_PUSHBUTTON,332,551,170,28,216);
        editMinutes=control(L"EDIT",L"60",ES_NUMBER|ES_AUTOHSCROLL,514,551,60,28,217);
        control(L"BUTTON",L"Current shard cooldown (min)",BS_PUSHBUTTON,586,551,250,28,218);
    }
    if(tab==3){control(L"BUTTON",L"Confirm selected blueprint owned",BS_PUSHBUTTON,20,551,300,30,213);control(L"BUTTON",L"Scan fabricator screen",BS_PUSHBUTTON,340,551,250,30,214);}
    listRows();
}
void saveOptions(){
    scanOnLaunch=SendMessageW(scanCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    showSession=SendMessageW(sessionCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    snareAlerts=SendDlgItemMessageW(panel,311,BM_GETCHECK,0,0)==BST_CHECKED;
    hotkeyChoice=int(SendMessageW(hotkey,CB_GETCURSEL,0,0));if(hotkeyChoice<0||hotkeyChoice>2)hotkeyChoice=0;
    bool wantHud=SendMessageW(hudCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    bool wantAuto=SendMessageW(autoCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    showHud(wantHud);applyHotkey();saveSettings();
    const auto watcher=read(data/L"watcher_status.json");
    const bool needsWatcher=wantAuto&&epoch()-watcher.numberOr("at")>10;
    if((wantAuto!=std::filesystem::exists(startupLink())||needsWatcher)&&!testing){
        if(controlProcess){note="A startup change is already running.";return;}
        if(!spawnPython(L"native_control.py",{wantAuto?L"--install":L"--uninstall"},&controlProcess))note="Could not start the startup helper.";
        else{note="Applying startup registration…";controlCompleted="Startup registration updated.";}
    }else note=hotkeyOK?"Settings saved.":"Settings saved; hotkey registration failed. Choose another combination.";
    InvalidateRect(mining->windowHandle(),nullptr,FALSE);SetWindowTextW(status,wide(note).c_str());
}
void handleAction(int id){
    if(id==222||id==223||id==224||id==225||id==226){Json c=obj({{"action",str(id==223||id==224?"session_export":"session_view")},{"query",str(utf8(text(search)))},{"region",str(SendMessageW(kind,CB_GETCURSEL,0,0)>0?utf8(text(kind)):"")},{"date_from",str(utf8(text(category)))},{"date_to",str(utf8(text(GetDlgItem(panel,221))))}});if(id==225||id==226)c.members.push_back({"offset",num(std::max(0.,field(state,"session_log").numberOr("offset")+(id==225?-100:100)))});if(id==223||id==224){if(testing)return;wchar_t path[32768]{};wcscpy_s(path,id==223?L"SynthScan server history.csv":L"SynthScan server history.json");OPENFILENAMEW f{sizeof(f)};f.hwndOwner=panel;f.lpstrFile=path;f.nMaxFile=32768;f.lpstrDefExt=id==223?L"csv":L"json";f.lpstrFilter=id==223?L"CSV file\0*.csv\0":L"JSON file\0*.json\0";f.Flags=OFN_OVERWRITEPROMPT|OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST;if(!GetSaveFileNameW(&f))return;c.members.push_back({"path",str(utf8(path))});c.members.push_back({"format",str(id==223?"csv":"json")});}command(c);return;}
    if(id>=100&&id<105){rebuild(id-100);return;}
    if(id==306){saveOptions();return;}
    if(id==307){showHud(!hudVisible);SendMessageW(hudCheck,BM_SETCHECK,hudVisible?BST_CHECKED:BST_UNCHECKED,0);return;}
    if(id==308){desktop();return;}
    if(id==309){
        if(testing)return;
        if(controlProcess){SetWindowTextW(status,L"A helper action is already running.");return;}
        controlCompleted="Windows timing helper requested. FPS appears after permission is granted.";
        if(!spawnPython(L"native_control.py",{L"--timing",std::to_wstring(GetCurrentProcessId())},&controlProcess))note="Could not start the timing-permission helper.";
        else note="Windows will ask for permission to read frame-timing events.";
        SetWindowTextW(status,wide(note).c_str());return;
    }
    if(id==310){
        if(testing)return;
        if(controlProcess){SetWindowTextW(status,L"A helper action is already running.");return;}
        controlCompleted="Network/FPS helper requested. Ping appears after permission is granted and a shard is joined.";
        if(!spawnPython(L"native_control.py",{L"--network",std::to_wstring(GetCurrentProcessId())},&controlProcess))note="Could not start the network-permission helper.";
        else note="Windows will ask for permission to read network timing and frame events.";
        SetWindowTextW(status,wide(note).c_str());return;
    }
    if(id==210&&selected>=0){auto key=visible[selected].textOr("id");if(favorites.count(key))favorites.erase(key);else favorites.insert(key);Json list=arr();for(auto& key:favorites)list.items.push_back(str(key));write(data/L"workspace_favorites.json",list);selection();return;}
    if(id==211&&selected>=0){auto row=visible[selected];if(row.textOr("kind")!="Material"){note="Select a material first.";SetWindowTextW(status,wide(note).c_str());return;}auto target=wide(row.textOr("name"));rebuild(1);SetWindowTextW(search,target.c_str());handleAction(212);return;}
    if(id==212){command(obj({{"action",str("plan")},{"targets",str(utf8(text(search)))},{"family",str(utf8(text(kind)))},{"system",str(utf8(text(category)))}}));return;}
    if(id==213&&selected>=0){auto row=visible[selected];if(row.textOr("kind")=="Legacy cargo"){note="Cargo is a saved snapshot; this button confirms blueprints only.";}
        else if(confirmOwned&&confirmOwned(row.textOr("name")))note="Blueprint confirmed in the native library.";else note="No unambiguous native blueprint match; original record kept for review.";
        SetWindowTextW(status,wide(note).c_str());return;}
    if(id==214){
        if(testing)return;
        auto viewport=SCMiner::ScreenCapture::gameViewport();if(!viewport){note="Star Citizen window is unavailable.";return;}
        ShowWindow(panel,SW_HIDE);DwmFlush();SCMiner::ScreenCapture capture;SCMiner::CaptureRegion region;
        region.x=viewport->x;region.y=viewport->y;region.width=viewport->width;region.height=viewport->height;region.autoDetect=false;
        auto frame=capture.captureRegion(region);auto path=data/L"fabricator_frame.png";
        if(!frame.empty()&&cv::imwrite(path.string(),frame))command(obj({{"action",str("fabricator_file")},{"path",str(utf8(path.wstring()))}}));
        else note="Could not capture the game frame.";
        ShowWindow(panel,SW_SHOWNOACTIVATE);return;
    }
    if(id==216){command(obj({{"action",str("name")},{"name",str(utf8(text(editName)))}}));return;}
    if(id==218){double minutes=std::wcstod(text(editMinutes).c_str(),nullptr);command(obj({{"action",str("cooldown")},{"label",str(utf8(text(editName)))},{"minutes",num(minutes)}}));return;}
    if(id==219&&selected>=0){command(obj({{"action",str("session_note")},{"session_id",field(visible[selected],"id")},{"text",str(utf8(text(editReminder)))}}));return;}
}
LRESULT CALLBACK panelProc(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    switch(message){
    case WM_COMMAND:{int id=LOWORD(w),code=HIWORD(w);if((id==201&&code==EN_CHANGE)||(id==202&&code==CBN_SELCHANGE)||(id==203&&code==CBN_SELCHANGE)){if(currentTab==0||currentTab==2||currentTab==3)SetTimer(hwnd,2,180,nullptr);return 0;}handleAction(id);return 0;}
    case WM_TIMER:if(w==2){KillTimer(hwnd,2);listRows();}return 0;
    case WM_NOTIFY:{
        auto header=reinterpret_cast<NMHDR*>(l);
        if(header->hwndFrom==listing&&header->code==LVN_ITEMCHANGED)selection();
        if(header->hwndFrom==listing&&header->code==NM_CUSTOMDRAW){auto draw=reinterpret_cast<NMLVCUSTOMDRAW*>(l);if(draw->nmcd.dwDrawStage==CDDS_PREPAINT)return CDRF_NOTIFYITEMDRAW;if(draw->nmcd.dwDrawStage==CDDS_ITEMPREPAINT){bool chosen=(ListView_GetItemState(listing,int(draw->nmcd.dwItemSpec),LVIS_SELECTED)&LVIS_SELECTED)!=0;draw->clrText=TEXT;draw->clrTextBk=chosen?RGB(76,58,32):CARD;draw->nmcd.uItemState&=~CDIS_SELECTED;return CDRF_NEWFONT;}}
        return 0;
    }
    case WM_CLOSE:ShowWindow(hwnd,SW_HIDE);return 0;
    case WM_DRAWITEM:{
        auto item=reinterpret_cast<DRAWITEMSTRUCT*>(l);
        if(item->CtlType!=ODT_BUTTON)break;
        HDC dc=item->hDC;RECT rc=item->rcItem;FillRect(dc,&rc,card);
        HPEN pen=CreatePen(PS_SOLID,1,(item->itemState&ODS_SELECTED)?GOLD:RGB(65,74,88));auto oldPen=SelectObject(dc,pen);auto oldBrush=SelectObject(dc,GetStockObject(NULL_BRUSH));
        RoundRect(dc,rc.left,rc.top,rc.right,rc.bottom,px(6),px(6));SelectObject(dc,oldBrush);SelectObject(dc,oldPen);DeleteObject(pen);
        SetBkMode(dc,TRANSPARENT);SetTextColor(dc,TEXT);SelectObject(dc,font);auto label=text(item->hwndItem);DrawTextW(dc,label.c_str(),-1,&rc,DT_CENTER|DT_VCENTER|DT_SINGLELINE|DT_NOPREFIX);
        if(item->itemState&ODS_FOCUS){InflateRect(&rc,-4,-4);DrawFocusRect(dc,&rc);}return TRUE;
    }
    case WM_CTLCOLORBTN:case WM_CTLCOLORLISTBOX:case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:{HDC dc=reinterpret_cast<HDC>(w);SetTextColor(dc,TEXT);SetBkColor(dc,message==WM_CTLCOLOREDIT?CARD:BG);return reinterpret_cast<LRESULT>(message==WM_CTLCOLOREDIT?card:background);}
    case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(hwnd,&ps);RECT rc;GetClientRect(hwnd,&rc);FillRect(dc,&rc,background);SetBkMode(dc,TRANSPARENT);SelectObject(dc,titleFont);SetTextColor(dc,GOLD);TextOutW(dc,px(20),px(20),L"SynthScan workspace",19);if(icon&&icon->GetLastStatus()==Gdiplus::Ok){Gdiplus::Graphics g(dc);g.SetInterpolationMode(Gdiplus::InterpolationModeHighQualityBicubic);g.DrawImage(icon.get(),px(20),px(365),px(64),px(64));}EndPaint(hwnd,&ps);return 0;}
    }
    return DefWindowProcW(hwnd,message,w,l);
}
void publishNativeStatus(){
    RECT overlayRect{};if(mining)GetWindowRect(mining->windowHandle(),&overlayRect);
    if(!testing&&mining)write(data/L"native_status.json",obj({{"at",num(epoch())},{"pid",num(GetCurrentProcessId())},{"scanner_active",boolean(!pirate&&!quest&&text(GetDlgItem(mining->windowHandle(),1002))==L"Live on")},{"piracy_details",boolean(pirateDetails)},{"hud_mode",str(quest?"questing":pirate?"piracy":"mining")},{"hud_locked",boolean(placementLocked)},{"activity_expanded",boolean(activityExpanded)},{"activity_command_id",str(activityCommandId)},{"hud_visible",boolean(IsWindowVisible(mining->windowHandle())!=FALSE)},{"overlay_mode",boolean(mining->isOverlayMode())},{"hud_topmost",boolean((GetWindowLongPtrW(mining->windowHandle(),GWL_EXSTYLE)&WS_EX_TOPMOST)!=0)},{"hud_position",obj({{"left",num(overlayRect.left)},{"top",num(overlayRect.top)},{"right",num(overlayRect.right)},{"bottom",num(overlayRect.bottom)}})},{"hotkey_registered",boolean(hotkeyOK)},{"bridge_age",num(lastStateAt?epoch()-lastStateAt:-1)}}));
}
void timer(){
    activityControl();
    static HWND previousForeground=nullptr;HWND foreground=GetForegroundWindow();
    if(mining&&hudVisible&&activityExpanded)mining->keepOverlayAboveGame(foreground!=previousForeground);
    previousForeground=foreground;
    if(pirate||quest)modeControls();
    if(showHandle&&WaitForSingleObject(showHandle,0)==WAIT_OBJECT_0)desktop();
    auto next=read(data/L"session_state.json",8*1024*1024);
    double stamp=next.numberOr("written_at");
    bool fresh=stamp>0&&epoch()-stamp>=0&&epoch()-stamp<4;
    if(fresh){
        const auto rep=next.textOr("reputation_notice");
        if(!rep.empty()&&rep!=reputationNotice&&!testing){
            reputationNotice=rep;
            NOTIFYICONDATAW message=tray;message.uFlags=NIF_INFO;
            message.dwInfoFlags=NIIF_INFO|NIIF_RESPECT_QUIET_TIME;
            wcscpy_s(message.szInfoTitle,L"Your reputation numbers are ready");
            wcscpy_s(message.szInfo,L"Fully restart Star Citizen when convenient to load the prepared numbers. Click to open setup and reputation status.");
            Shell_NotifyIconW(NIM_MODIFY,&message);
        }
        auto key=next.textOr("summary");if(key!=summary){summary=key;if(mining)InvalidateRect(mining->windowHandle(),nullptr,FALSE);}
        if(stamp!=lastStateAt){state=std::move(next);lastStateAt=stamp;note=state.textOr("note");
            SynthScanDiary::update(field(state,"diary"),field(state,"diary_result"),note);
            SynthScanNav::update(field(state,"navigation"));
            if(panel&&IsWindowVisible(panel)&&(currentTab==1||currentTab==2||currentTab==3)){
                auto key=encode(field(state,currentTab==1?"plans":currentTab==2?"session_rows":"review_revision"));if(key!=lastState&&GetFocus()!=editReminder){lastState=key;listRows();}
                SetWindowTextW(status,wide(note).c_str());
            }
        }
        if(readyHandle&&state.numberOr("owner_pid")==GetCurrentProcessId())SetEvent(readyHandle);
    }else if(summary!="Session service unavailable"){summary="Session service unavailable";SynthScanNav::update(obj({{"message",str("Session service unavailable; capture and navigation paused.")},{"guidance",obj({{"unavailable",str("No fresh service state")}})}}));if(mining)InvalidateRect(mining->windowHandle(),nullptr,FALSE);}
    if(controlProcess){DWORD code=STILL_ACTIVE;GetExitCodeProcess(controlProcess,&code);if(code!=STILL_ACTIVE){CloseHandle(controlProcess);controlProcess=nullptr;note=code==0?controlCompleted:read(data/L"control_status.json").textOr("error","Helper action failed. See native_control.log in your data folder.");if(status)SetWindowTextW(status,wide(note).c_str());}}
    publishNativeStatus();
}
LRESULT CALLBACK hostProc(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    if(message==TRAY&&l==NIN_BALLOONUSERCLICK){spawnPython(L"app_launcher.py",{L"--status"});return 0;}
    if(message==WM_APP+42){activityControl();publishNativeStatus();return 0;}
    if(message==WM_TIMER){timer();return 0;}
    if(message==WM_HOTKEY&&w==HOTKEY){showHud(!hudVisible);return 0;}
    if(message==TRAY){if(l==WM_LBUTTONDBLCLK){desktop();return 0;}if(l==WM_RBUTTONUP){HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,1,L"Open SynthScan");AppendMenuW(menu,MF_STRING,2,L"Show / hide HUD");AppendMenuW(menu,MF_STRING,3,L"Startup & HUD settings");AppendMenuW(menu,MF_STRING,4,L"Exit SynthScan");AppendMenuW(menu,MF_STRING|((pirate||quest)?0:MF_CHECKED),5,L"HUD mode: Mining");AppendMenuW(menu,MF_STRING|(pirate?MF_CHECKED:0),6,L"HUD mode: Piracy");AppendMenuW(menu,MF_STRING|(quest?MF_CHECKED:0),8,L"HUD mode: Missions");AppendMenuW(menu,MF_STRING|(placementLocked?MF_CHECKED:0),7,L"Lock HUD position (click-through)");POINT at;GetCursorPos(&at);SetForegroundWindow(hwnd);int choice=TrackPopupMenu(menu,TPM_RETURNCMD|TPM_RIGHTBUTTON,at.x,at.y,0,hwnd,nullptr);DestroyMenu(menu);if(choice==1)desktop();if(choice==2)showHud(!hudVisible);if(choice==3)workspace(4);if(choice==5||choice==6)setMode(choice==6);if(choice==8)setMode(2);if(choice==7)togglePlacement();if(choice==4&&mining)PostMessageW(mining->windowHandle(),WM_CLOSE,0,0);return 0;}}
    return DefWindowProcW(hwnd,message,w,l);
}
LRESULT CALLBACK mainSubclass(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(message==WM_COMMAND&&LOWORD(w)==31812){togglePlacement();return 0;}
    if(message==WM_COMMAND&&(LOWORD(w)==31814||LOWORD(w)==31815)){
        if(pirate)write(data/L"piracy_command.json",obj({{"action",str(LOWORD(w)==31814?"toggle_wait":"reset_wait")},{"owner_pid",num(GetCurrentProcessId())},{"at",num(epoch())}}));return 0;
    }
    if(message==WM_COMMAND&&LOWORD(w)==31813){setMode(2);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1002&&quest){write(data/L"questing_command.json",obj({{"action",str("next")},{"owner_pid",num(GetCurrentProcessId())}}));return 0;}
    if(message==WM_COMMAND&&(LOWORD(w)==31810||LOWORD(w)==31811)){setMode(LOWORD(w)==31811);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1002&&pirate){pirateDetails=!pirateDetails;saveSettings();modeControls();mining->refreshActivityLayout();return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==31817&&pirate){snareAlerts=!snareAlerts;saveSettings();modeControls();return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1017){
        if(mining&&mining->isOverlayMode()){
            HMENU mode=CreatePopupMenu();AppendMenuW(mode,MF_STRING|((pirate||quest)?0:MF_CHECKED),10,L"Mining HUD");AppendMenuW(mode,MF_STRING|(pirate?MF_CHECKED:0),11,L"Piracy HUD");AppendMenuW(mode,MF_STRING|(quest?MF_CHECKED:0),13,L"Missions HUD");AppendMenuW(mode,MF_STRING|(placementLocked?MF_CHECKED:0),12,L"Lock HUD position (click-through)");AppendMenuW(mode,MF_SEPARATOR,0,nullptr);AppendMenuW(mode,MF_STRING,4,L"Server log & interdiction history");AppendMenuW(mode,MF_STRING,6,L"Startup & HUD settings");AppendMenuW(mode,MF_STRING,14,L"Setup & reputation status");
            POINT at;GetCursorPos(&at);int choice=TrackPopupMenu(mode,TPM_RETURNCMD,at.x,at.y,0,hwnd,nullptr);DestroyMenu(mode);if(choice==12)togglePlacement();if(choice==13)setMode(2);if(choice==10||choice==11)setMode(choice==11);if(choice==4)workspace(2);if(choice==6)workspace(4);if(choice==14)spawnPython(L"app_launcher.py",{L"--status"});return 0;
        }
        HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,1,L"Keyboard shortcuts");AppendMenuW(menu,MF_STRING,2,L"Game library & artwork");AppendMenuW(menu,MF_STRING,3,L"Material picker");AppendMenuW(menu,MF_STRING,4,L"Server log");AppendMenuW(menu,MF_STRING,5,L"Review imported records");AppendMenuW(menu,MF_STRING,6,L"Startup & HUD settings");AppendMenuW(menu,MF_STRING,7,L"Show / hide HUD");AppendMenuW(menu,MF_STRING,8,L"Mining diary & personal records");AppendMenuW(menu,MF_STRING,9,L"Rock bookmarks & return test");AppendMenuW(menu,MF_STRING,14,L"Setup & reputation status");
        AppendMenuW(menu,MF_SEPARATOR,0,nullptr);AppendMenuW(menu,MF_STRING|((pirate||quest)?0:MF_CHECKED),10,L"HUD mode: Mining");AppendMenuW(menu,MF_STRING|(pirate?MF_CHECKED:0),11,L"HUD mode: Piracy");
        AppendMenuW(menu,MF_STRING|(quest?MF_CHECKED:0),13,L"HUD mode: Missions");AppendMenuW(menu,MF_STRING|(placementLocked?MF_CHECKED:0),12,L"Lock HUD position (click-through)");POINT at;GetCursorPos(&at);int choice=TrackPopupMenu(menu,TPM_RETURNCMD,at.x,at.y,0,hwnd,nullptr);DestroyMenu(menu);
        if(choice==14){spawnPython(L"app_launcher.py",{L"--status"});return 0;}if(choice==12){togglePlacement();return 0;}
        if(choice==13){setMode(2);return 0;}if(choice==10||choice==11){setMode(choice==11);return 0;}
        if(choice==1)return DefSubclassProc(hwnd,message,w,l);if(choice>=2&&choice<=6)workspace(choice-2);if(choice==7)showHud(!hudVisible);if(choice==8)SynthScanDiary::open();if(choice==9)SynthScanNav::open();return 0;
    }
    return DefSubclassProc(hwnd,message,w,l);
}
}
bool automatic(){return isAutomatic;}
bool piracyMode(){return pirate;}
bool piracyDetails(){return pirateDetails;}
int piracyHeight(){return pirateDetails?350:200;}
int activityFooterHeight(){return pirate?0:30;}
bool questingMode(){return quest;}
bool activityMode(){return pirate||quest;}
bool hudLocked(){return placementLocked;}
bool gameAvailable(){
    if(pirate||quest)return false;
    static double checked=-10;static bool available=false;
    if(epoch()-checked>=1){available=SCMiner::ScreenCapture::gameWindow()!=nullptr;checked=epoch();}
    return available;
}
bool begin(bool value){
    isAutomatic=value;mutexHandle=CreateMutexW(nullptr,FALSE,L"Local\\SynthScan.Native.App");
    if(!mutexHandle)return false;
    if(GetLastError()==ERROR_ALREADY_EXISTS){if(!value){HANDLE event=OpenEventW(EVENT_MODIFY_STATE,FALSE,L"Local\\SynthScan.Native.Show");if(event){SetEvent(event);CloseHandle(event);}}CloseHandle(mutexHandle);mutexHandle=nullptr;return false;}
    readyHandle=CreateEventW(nullptr,TRUE,FALSE,L"Local\\SynthScan.Native.Ready");showHandle=CreateEventW(nullptr,FALSE,FALSE,L"Local\\SynthScan.Native.Show");return true;
}
void attach(SCMiner::MinerGUI* gui,std::function<bool(const std::string&)> confirm){
    mining=gui;confirmOwned=std::move(confirm);attached=true;uiScale=GetDpiForWindow(gui->windowHandle())/96.0;if(uiScale<.75)uiScale=1;data=SCMiner::AppPaths::data();
    Json runtime=read(SCMiner::AppPaths::program()/L"native_runtime.json");root=std::filesystem::u8path(runtime.textOr("workspace"));
    settings=read(data/L"native_settings.json");scanOnLaunch=flag(settings,"scan_on_launch",true);hudVisible=flag(settings,"show_hud",true);activityExpanded=flag(settings,"activity_expanded",true);showSession=flag(settings,"session_strip",true);snareAlerts=flag(settings,"snare_alerts",true);pirate=settings.textOr("hud_mode")=="piracy";pirateDetails=flag(settings,"piracy_details",false);quest=settings.textOr("hud_mode")=="questing";miningResume=flag(settings,"mining_resume",scanOnLaunch);placementLocked=flag(settings,"hud_locked",false);gui->updateClickThrough();hotkeyChoice=int(settings.numberOr("hotkey"));if(hotkeyChoice<0||hotkeyChoice>2)hotkeyChoice=0;
    library=read(SCMiner::AppPaths::program()/L"workspace_library.json");for(auto& value:read(data/L"workspace_favorites.json").items)favorites.insert(value.text);
    SynthScanDiary::initialize(gui->windowHandle(),data,testing,[](Json value){command(value);});
    SynthScanNav::initialize(gui->windowHandle(),testing,[](Json value){command(value);});
    background=CreateSolidBrush(BG);card=CreateSolidBrush(CARD);
    font=CreateFontW(-px(15),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
    titleFont=CreateFontW(-px(24),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Bahnschrift");
    WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=hostProc;wc.lpszClassName=L"SynthScanHost";RegisterClassW(&wc);host=CreateWindowW(wc.lpszClassName,L"SynthScan services",0,0,0,0,0,nullptr,nullptr,wc.hInstance,nullptr);
    SetWindowSubclass(gui->windowHandle(),mainSubclass,1,0);SetWindowTextW(GetDlgItem(gui->windowHandle(),1017),L"More");applyHotkey();SetTimer(host,1,500,nullptr);
    if(!testing){
        job=CreateJobObjectW(nullptr,nullptr);if(job){JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};info.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;SetInformationJobObject(job,JobObjectExtendedLimitInformation,&info,sizeof(info));}
        std::error_code error;std::filesystem::remove(data/L"bridge_stop.json",error);
        if(!spawnPython(L"native_bridge.py",{L"--data-dir",data.wstring(),L"--owner",std::to_wstring(GetCurrentProcessId())},&bridgeProcess))note="Could not start session services. Check native_runtime.json.";
        tray.cbSize=sizeof(tray);tray.hWnd=host;tray.uID=1;tray.uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP;tray.uCallbackMessage=TRAY;tray.hIcon=LoadIconW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(IDI_APPICON));wcscpy_s(tray.szTip,L"SynthScan");Shell_NotifyIconW(NIM_ADD,&tray);
    }
    if((pirate||quest)&&text(GetDlgItem(gui->windowHandle(),1002))==L"Live on"){bool p=pirate,q=quest;pirate=false;quest=false;SendMessageW(gui->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);pirate=p;quest=q;}
    modeControls();
    if(isAutomatic){
        gui->restoreOverlayPlacement();
        LONG_PTR style=GetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE);SetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE,style|WS_EX_NOACTIVATE);
        if(!gui->isOverlayMode())gui->toggleOverlayMode();
        if((scanOnLaunch&&!pirate&&!quest)!=(text(GetDlgItem(gui->windowHandle(),1002))==L"Live on"))SendMessageW(gui->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);
        modeControls();ShowWindow(gui->windowHandle(),hudVisible&&activityExpanded?SW_SHOWNOACTIVATE:SW_HIDE);SetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE,GetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE)&~WS_EX_NOACTIVATE);gui->keepOverlayAboveGame(true);
    }
}
void workspace(int tab){
    if(!panel){WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=panelProc;wc.hCursor=LoadCursor(nullptr,IDC_ARROW);wc.hbrBackground=background;wc.lpszClassName=L"SynthScanWorkspace";RegisterClassW(&wc);panel=CreateWindowExW(0,wc.lpszClassName,L"SynthScan workspace",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,px(884),px(695),mining?mining->windowHandle():nullptr,nullptr,wc.hInstance,nullptr);SetWindowDisplayAffinity(panel,WDA_EXCLUDEFROMCAPTURE);BOOL dark=TRUE;DwmSetWindowAttribute(panel,20,&dark,sizeof(dark));}
    rebuild(tab);
    if(testing){SetWindowPos(panel,HWND_BOTTOM,-32000,-32000,0,0,SWP_NOSIZE|SWP_NOACTIVATE);ShowWindow(panel,SW_SHOWNOACTIVATE);}else{ShowWindow(panel,SW_SHOW);SetForegroundWindow(panel);}
}
int sessionHeight(){return attached&&showSession&&!pirate?44:0;}
void drawQuesting(Gdiplus::Graphics& g,float width,float height,float scale){
    Gdiplus::SolidBrush ink(Gdiplus::Color(255,233,237,241)),accent(Gdiplus::Color(255,83,208,159)),muted(Gdiplus::Color(255,149,160,173));
    auto line=[&](const std::string& text,float y,float size,Gdiplus::Brush* brush){Gdiplus::Font f(L"Segoe UI",size*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::StringFormat format;format.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);g.DrawString(wide(text).c_str(),-1,&f,Gdiplus::RectF(10*scale,y*scale,width-20*scale,23*scale),&format,brush);};
    const auto& model=field(state,"questing");
    const bool fresh=testing||(epoch()-lastStateAt<4&&state.numberOr("owner_pid")==GetCurrentProcessId());
    line("MISSIONS",8,13,&accent);
    line(fresh?model.textOr("title","Waiting for contract observations"):"Session service unavailable",43,16,&ink);
    line(fresh?model.textOr("source")+" · "+std::to_string(int(model.numberOr("count")))+" active":"Reads paused",70,10,&muted);
    if(fresh){int i=0;for(const auto& value:field(model,"lines").items){if(i==8)break;line(value.text,98+float(i++)*24,12,&ink);}}
    line(fresh?model.textOr("footer"):"Last data expired",300,10,&muted);
    line("Configured rewards / splits are estimates",323,10,&muted);
}
void drawPiracy(Gdiplus::Graphics& g,float width,float height,float scale){
    Gdiplus::SolidBrush ink(Gdiplus::Color(255,233,237,241)),gold(Gdiplus::Color(255,245,173,66)),muted(Gdiplus::Color(255,149,160,173)),green(Gdiplus::Color(255,83,208,159));
    Gdiplus::Pen border(Gdiplus::Color(255,54,62,73));
    g.DrawRectangle(&border,.5f,.5f,width-1,height-1);
    auto text=[&](const std::string& value,float x,float y,float size,Gdiplus::Brush* brush,float span){
        Gdiplus::Font f(L"Segoe UI",size*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::StringFormat format;
        format.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);
        g.DrawString(wide(value).c_str(),-1,&f,Gdiplus::RectF(x*scale,y*scale,span*scale,(size+8)*scale),&format,brush);
    };
    const float logicalWidth=width/scale;
    const bool fresh=testing||(epoch()-lastStateAt<4&&state.numberOr("owner_pid")==GetCurrentProcessId());
    const bool joined=fresh&&!state.textOr("session_token").empty();
    const auto& watch=field(state,"piracy_watch");const auto& metrics=field(watch,"metrics");
    const bool live=joined&&flag(watch,"fresh")&&(testing||(epoch()-watch.numberOr("observed_at")>=0&&epoch()-watch.numberOr("observed_at")<5));
    auto value=[&](const char* key,int precision=0){auto n=metrics.find(key);if(!live||!n||n->kind!=Json::Kind::Number)return std::string("--");std::ostringstream out;out<<std::fixed<<std::setprecision(precision)<<n->number;return out.str();};
    text("PIRACY",10,8,12,&gold,130);
    const char* labels[]={"SHARD PLAYERS","SERVER PLAYERS","SERVER FPS","PING (ms)"};
    const char* keys[]={"shard_pop","srv_pop","server_fps","ping_ms"};
    float col=(logicalWidth-20)/4;
    for(int i=0;i<4;i++){text(labels[i],10+col*i,40,10,&muted,col-6);text(value(keys[i],i>=2?1:0),10+col*i,55,28,&ink,col-6);}
    std::string status=!fresh?"Session service unavailable":!joined?"Join a shard to watch population":watch.textOr("status","Waiting for readable DisplayInfo");
    text(status,10,99,10,live?&green:&muted,275);
    auto delta=[&](const char* key){const auto& n=field(watch,key);if(!live||n.kind!=Json::Kind::Number)return std::string("--");return (n.number>=0?"+":"")+std::to_string(int(n.number));};
    text("Shard change   5m "+delta("delta_5m")+"   15m "+delta("delta_15m"),10,126,12,&ink,280);
    const auto& points=field(watch,"points").items;
    double low=1e9,high=-1;for(auto& point:points){low=std::min(low,point.numberOr("value"));high=std::max(high,point.numberOr("value"));}
    std::string range=points.empty()?"15 MIN HISTORY":"15 MIN · "+std::to_string(int(low))+"–"+std::to_string(int(high));
    text(range,300,99,10,&muted,logicalWidth-310);
    float gx=300*scale,gy=119*scale,gw=width-310*scale,gh=35*scale;
    g.DrawRectangle(&border,gx,gy,gw,gh);
    if(joined&&points.size()>1){
        Gdiplus::Pen graph(Gdiplus::Color(255,83,208,159),1.5f*scale);double span=std::max(1.,high-low),now=epoch();
        for(size_t i=1;i<points.size();i++){
            double a=points[i-1].numberOr("at"),b=points[i].numberOr("at");
            if(a<now-900||b-a>15||b>now)continue;
            float x1=gx+float((a-(now-900))/900)*gw,x2=gx+float((b-(now-900))/900)*gw;
            float y1=gy+gh-3*scale-float((points[i-1].numberOr("value")-low)/span)*(gh-6*scale),y2=gy+gh-3*scale-float((points[i].numberOr("value")-low)/span)*(gh-6*scale);
            g.DrawLine(&graph,x1,y1,x2,y2);
        }
    }else text("Collecting",309,127,10,&muted,logicalWidth-328);
    const auto& report=field(state,"interdictions");const auto& current=field(report,"current").items;
    const bool recent=joined&&!current.empty()&&epoch()-current.front().numberOr("at")>=0&&epoch()-current.front().numberOr("at")<8;
    if(recent)text("Logged interdiction: "+current.front().textOr("target"),10,160,11,&gold,logicalWidth-20);
    if(!pirateDetails)return;
    g.DrawLine(&border,10*scale,181*scale,width-10*scale,181*scale);
    int waited=joined?int(watch.numberOr("waiting_s")):0;std::ostringstream clock;clock<<std::setfill('0')<<std::setw(2)<<waited/3600<<":"<<std::setw(2)<<(waited/60)%60<<":"<<std::setw(2)<<waited%60;
    text("Waiting "+clock.str()+(flag(watch,"waiting_active")?" · running":" · paused"),10,190,14,&ink,logicalWidth-20);
    text("Logged interdiction reports: "+std::to_string(joined?int(report.numberOr("current_count")):0),10,252,12,&ink,logicalWidth-20);
    if(joined&&!current.empty()){
        double seconds=std::max(0.,epoch()-current.front().numberOr("at"));
        text(current.front().textOr("target"),10,277,16,recent?&gold:&ink,logicalWidth-20);
        text("Last report "+std::to_string(int(seconds<60?seconds:seconds/60))+(seconds<60?"s ago":"m ago"),335,281,11,&muted,logicalWidth-345);
    }else text("No logged reports on this visit",10,279,12,&muted,logicalWidth-20);
    text("Manual timer · crime reports only · population is not nearby traffic",10,311,10,&muted,logicalWidth-20);
}

void drawSession(Gdiplus::Graphics& g,float width,float top,float height,float scale){
    if(!attached||!showSession||height<=0)return;
    Gdiplus::SolidBrush bg(Gdiplus::Color(255,20,23,29)),fg(Gdiplus::Color(255,205,214,225)),muted(Gdiplus::Color(255,149,160,173));
    g.FillRectangle(&bg,1.f,top,width-2,height-2);
    Gdiplus::Pen line(Gdiplus::Color(255,54,62,73));g.DrawLine(&line,10*scale,top,width-10*scale,top);
    Gdiplus::Font f(L"Segoe UI",10*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    Gdiplus::StringFormat format;format.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);
    std::string value=epoch()-lastStateAt<4?state.textOr("identity",summary):"Session service unavailable";
    g.DrawString(wide(value).c_str(),-1,&f,Gdiplus::RectF(10*scale,top+5*scale,width-20*scale,16*scale),&format,&fg);
    bool fresh=epoch()-lastStateAt<4;
    std::string second;
    if(fresh){for(auto& metric:field(state,"metrics").items){if(!second.empty())second+=" · ";second+=metric.text;}
        auto location=state.textOr("location");if(!location.empty())second+=(second.empty()?"":" · ")+location;
    }else second="More → Startup & HUD settings";
    auto count=fresh?field(state,"cooldowns").items.size():0;if(count)second+=(second.empty()?"":" · ")+std::to_string(count)+" shard reminder(s)";
    if(second.empty())second=(hotkeyChoice==0?"Ctrl+Alt+H":hotkeyChoice==1?"Ctrl+Alt+F10":"Ctrl+Shift+F10")+std::string(" · HUD visibility · More → Server log");
    g.DrawString(wide(second).c_str(),-1,&f,Gdiplus::RectF(10*scale,top+22*scale,width-20*scale,16*scale),&format,&muted);
}
void shutdown(){
    SynthScanDiary::close();SynthScanNav::close();
    if(attached&&!testing){Json exit=obj({{"at",num(epoch())},{"reason",str("user")},{"game_pids",field(state,"game_pids")}});write(data/L"native_exit.json",exit);}
    if(host){KillTimer(host,1);UnregisterHotKey(host,HOTKEY);Shell_NotifyIconW(NIM_DELETE,&tray);}
    if(bridgeProcess){write(data/L"bridge_stop.json",obj({{"owner_pid",num(GetCurrentProcessId())}}));WaitForSingleObject(bridgeProcess,2000);}
    if(job)CloseHandle(job);job=nullptr;
    if(bridgeProcess)CloseHandle(bridgeProcess);if(controlProcess)CloseHandle(controlProcess);
    if(panel)DestroyWindow(panel);panel=nullptr;if(host)DestroyWindow(host);host=nullptr;
    if(font)DeleteObject(font);if(titleFont)DeleteObject(titleFont);if(background)DeleteObject(background);if(card)DeleteObject(card);
    if(readyHandle)CloseHandle(readyHandle);if(showHandle)CloseHandle(showHandle);if(mutexHandle)CloseHandle(mutexHandle);
    readyHandle=showHandle=mutexHandle=nullptr;attached=false;mining=nullptr;
}
int uiTest(const std::string& directory){
    testing=true;SCMiner::AppPaths::useDataFolder(std::filesystem::u8path(directory)/"data");
    SCMiner::MinerGUI gui;gui.setHeadless(true);if(!gui.initialize(GetModuleHandleW(nullptr)))return 2;
    RECT work{};SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);
    {std::ofstream fixture(SCMiner::AppPaths::data()/L"window.txt");fixture<<"left=64\ntop=64\nright=964\nbottom=964\nmaximised=0\n";}
    HWND startupForeground=GetForegroundWindow();gui.setHeadless(false);gui.restoreOverlayPlacement();RECT restoredAt{};GetWindowRect(gui.windowHandle(),&restoredAt);
    bool startupPlacement=!IsWindowVisible(gui.windowHandle())&&GetForegroundWindow()==startupForeground&&restoredAt.left==work.left+64&&restoredAt.top==work.top+64;
    gui.setHeadless(true);gui.show();isAutomatic=true;attach(&gui,[](const std::string&){return true;});
    bool automaticOverlay=gui.isOverlayMode()&&(GetWindowLongPtrW(gui.windowHandle(),GWL_EXSTYLE)&WS_EX_TOPMOST)!=0&&GetForegroundWindow()==startupForeground;
    isAutomatic=false;gui.toggleOverlayMode();
    Json result=obj({{"schema",num(1)},{"native_gui",boolean(true)},{"library_rows",num(double(field(library,"rows").items.size()))}});
    result.members.push_back({"automatic_placement_loaded_without_activation",boolean(startupPlacement)});
    result.members.push_back({"automatic_attach_starts_topmost_overlay",boolean(automaticOverlay)});
    Json tabs=arr();
    SCMiner::RockStats sample;sample.mass=98000;sample.ore="Quantanium";
    for(int i=0;i<100;i++)observeMiningRock(sample,nullptr,"Stanton","Wala","MOLE",41002);
    endMiningRock();int encounters=0;for(auto& file:std::filesystem::directory_iterator(data/L"diary_inbox"))if(file.path().extension()==L".json")encounters++;
    result.members.push_back({"diary_native_encounters",num(encounters)});
    state=read(std::filesystem::u8path(directory)/"session_test_model.json");auto diaryModel=read(std::filesystem::u8path(directory)/"diary_test_model.json");bool editorRoute=false,shareRoute=false,navRoute=false,sessionRoute=false;int timelineColumns=0,timelineRows=0;
    for(int tab=-2;tab<13;tab++){
        HWND target;
        if(tab==-2)target=gui.windowHandle();
        else if(tab==-1){gui.toggleOverlayMode();target=gui.windowHandle();}
        else if(tab==5){
            SynthScanDiary::update(diaryModel,obj(),"");SynthScanDiary::open();target=SynthScanDiary::window();
            if(!field(diaryModel,"rows").items.empty()){
                ListView_SetItemState(GetDlgItem(target,411),0,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);
                SendMessageW(target,WM_COMMAND,440,0);editorRoute=read(data/L"workspace_command.json").textOr("action")=="diary_save";
                SynthScanDiary::update(diaryModel,obj({{"command_id",str("ui-save")},{"entry",field(field(diaryModel,"rows").items.front(),"entry")},{"note",str("Isolated UI fixture · not a real player record")}}),"");
            }
        }
        else if(tab==6){
            auto path=std::filesystem::u8path(directory)/"share_fixture.png";
            if(std::filesystem::exists(path)&&!field(diaryModel,"rows").items.empty()){
                SendMessageW(SynthScanDiary::window(),WM_COMMAND,456,0);shareRoute=read(data/L"workspace_command.json").textOr("action")=="diary_share";
                SynthScanDiary::update(diaryModel,obj({{"command_id",str("ui-share")},{"preview",str(utf8(path.wstring()))},{"note",str("Local preview only")}}),"");
            }
            target=SynthScanDiary::previewWindow();if(!target)target=SynthScanDiary::window();
        }
        else if(tab==7){SynthScanNav::update(read(std::filesystem::u8path(directory)/"navigation_test_model.json"));SynthScanNav::open();target=SynthScanNav::window();SendMessageW(target,WM_COMMAND,710,0);auto nc=read(data/L"workspace_command.json");navRoute=nc.textOr("action")=="nav_arm"&&nc.textOr("role")=="mark"&&!nc.textOr("body_id").empty();}
        else if(tab==8){state=read(std::filesystem::u8path(directory)/"piracy_test_model.json");lastStateAt=epoch();gui.setLiveModeActive(true);SendMessageW(gui.windowHandle(),WM_COMMAND,31811,0);result.members.push_back({"piracy_mode_pauses_scanner",boolean(piracyMode()&&text(GetDlgItem(gui.windowHandle(),1002))==L"Details +"&&read(data/L"native_settings.json").textOr("hud_mode")=="piracy")});observeMiningRock(sample,nullptr,"Stanton","Wala","MOLE",41002);int count=0;for(auto& f:std::filesystem::directory_iterator(data/L"diary_inbox"))if(f.path().extension()==L".json")count++;result.members.push_back({"piracy_blocks_mining_diary",boolean(count==encounters)});target=gui.windowHandle();
            SendMessageW(target,WM_COMMAND,1002,0);
            SendMessageW(target,WM_COMMAND,31814,0);auto waitCommand=read(data/L"piracy_command.json");
            bool waitRoute=waitCommand.textOr("action")=="toggle_wait"&&waitCommand.numberOr("owner_pid")==GetCurrentProcessId();
            SendMessageW(target,WM_COMMAND,31815,0);auto resetCommand=read(data/L"piracy_command.json");
            result.members.push_back({"piracy_wait_controls_route",boolean(waitRoute&&resetCommand.textOr("action")=="reset_wait"&&IsWindowVisible(GetDlgItem(target,31814))&&IsWindowVisible(GetDlgItem(target,31815)))});
            SendMessageW(target,WM_COMMAND,1002,0);
            RECT compact;GetWindowRect(target,&compact);COLORREF color=0;BYTE alpha=0;DWORD layerFlags=0;
            bool opaque=GetLayeredWindowAttributes(target,&color,&alpha,&layerFlags)&&alpha==255;
            result.members.push_back({"piracy_compact_wide_opaque",boolean(compact.right-compact.left>=600&&compact.bottom-compact.top<300&&opaque&&sessionHeight()==0&&!IsWindowVisible(GetDlgItem(target,31814)))});
            RECT before,after;GetWindowRect(target,&before);HWND foreground=GetForegroundWindow();SetWindowPos(target,HWND_NOTOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);
            auto request=obj({{"id",str("collapse-test")},{"action",str("set_activity_expanded")},{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId())},{"expanded",boolean(false)}});
            write(data/L"activity_hud_command.json",request);SendMessageW(host,WM_APP+42,0,0);
            bool collapsed=!IsWindowVisible(target)&&hudVisible&&!activityExpanded&&pirate;
            showHud(false);showHud(true);collapsed=collapsed&&!IsWindowVisible(target);
            bool persisted=!flag(read(data/L"native_settings.json"),"activity_expanded",true);
            request=obj({{"id",str("expand-test")},{"action",str("set_activity_expanded")},{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId())},{"expanded",boolean(true)}});
            write(data/L"activity_hud_command.json",request);SendMessageW(host,WM_APP+42,0,0);GetWindowRect(target,&after);
            bool restored=IsWindowVisible(target)&&activityExpanded&&pirate&&before.left==after.left&&before.top==after.top;
            bool raised=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0&&GetForegroundWindow()==foreground;
            SetWindowPos(target,HWND_NOTOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);mining->keepOverlayAboveGame();
            result.members.push_back({"activity_topmost_restored_without_activation",boolean(raised&&(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0&&GetForegroundWindow()==foreground)});
            auto bad=obj({{"id",str("wrong-owner")},{"action",str("set_activity_expanded")},{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId()+1)},{"expanded",boolean(false)}});write(data/L"activity_hud_command.json",bad);SendMessageW(host,WM_APP+42,0,0);
            result.members.push_back({"activity_collapse_preserves_server_setting",boolean(collapsed&&persisted)});
            result.members.push_back({"activity_expand_restores_position_and_tab",boolean(restored&&activityExpanded&&activityCommandId=="expand-test")});
            result.members.push_back({"activity_tabs_visible",boolean(IsWindowVisible(GetDlgItem(target,31810))&&IsWindowVisible(GetDlgItem(target,31811)))});
        }
        else if(tab==9){state=obj({{"session_token",str("fixture")},{"identity",str("DEMO SHARD · US-EAST")},{"interdictions",obj({{"current",arr()},{"current_count",num(0)}})}});lastStateAt=epoch();target=gui.windowHandle();}
        else if(tab==10){SendMessageW(gui.windowHandle(),WM_COMMAND,31810,0);result.members.push_back({"mining_mode_restores_scanner",boolean(!piracyMode()&&text(GetDlgItem(gui.windowHandle(),1002))==L"Live on"&&read(data/L"native_settings.json").textOr("hud_mode")=="mining")});target=gui.windowHandle();
            if(placementLocked)togglePlacement();SendMessageW(target,WM_ACTIVATEAPP,FALSE,0);
            bool unlocked=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)==0;
            POINT point{12,12};ClientToScreen(target,&point);bool caption=SendMessageW(target,WM_NCHITTEST,0,MAKELPARAM(point.x,point.y))==HTCAPTION;
            SendMessageW(target,WM_COMMAND,31812,0);bool locked=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)!=0;
            SendMessageW(target,WM_COMMAND,31812,0);bool unlockedAgain=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)==0;
            result.members.push_back({"hud_drag_while_game_active",boolean(unlocked&&caption&&unlockedAgain)});result.members.push_back({"hud_lock_clickthrough",boolean(locked&&!hudLocked())});
        }
        else if(tab==11){
            Json questLines=arr();for(auto value:{"Configured payout: 12,000 aUEC","Mission participants: 2","Equal-split scenario: 6,000 aUEC each","Adagio / Standing: +100 base rep","Equal-split scenario: +50 rep each","Adagio: 249 / 800 verified"})questLines.items.push_back(str(value));
            state=obj({{"questing",obj({{"title",str("DEMO · Delivery contract")},{"count",num(2)},{"source",str("Selected contract · not game tracking")},{"footer",str("Synthetic fixture · balances verified 12s ago")},{"lines",questLines}})}});
            lastStateAt=epoch();SendMessageW(gui.windowHandle(),WM_COMMAND,31813,0);target=gui.windowHandle();
            bool selected=questingMode()&&!piracyMode()&&read(data/L"native_settings.json").textOr("hud_mode")=="questing"&&text(GetDlgItem(target,1002))==L"Next";
            observeMiningRock(sample,nullptr,"Stanton","Wala","MOLE",41002);int count=0;for(auto& f:std::filesystem::directory_iterator(data/L"diary_inbox"))if(f.path().extension()==L".json")count++;
            result.members.push_back({"questing_mode_pauses_scanner_and_diary",boolean(selected&&count==encounters&&IsWindowVisible(GetDlgItem(target,31813)))});
            SendMessageW(target,WM_COMMAND,1002,0);auto qc=read(data/L"questing_command.json");result.members.push_back({"questing_next_contract_route",boolean(qc.textOr("action")=="next"&&qc.numberOr("owner_pid")==GetCurrentProcessId())});
            setMode(1);setMode(0);bool resumed=!activityMode()&&text(GetDlgItem(target,1002))==L"Live on";setMode(2);
            result.members.push_back({"questing_piracy_mining_resume",boolean(resumed&&questingMode()&&text(GetDlgItem(target,1002))==L"Next")});
        }
        else if(tab==12){state=read(std::filesystem::u8path(directory)/"piracy_test_model.json");lastStateAt=epoch();setMode(1);SendMessageW(gui.windowHandle(),WM_COMMAND,1002,0);target=gui.windowHandle();result.members.push_back({"piracy_details_expand",boolean(piracyDetails()&&IsWindowVisible(GetDlgItem(target,31814))&&IsWindowVisible(GetDlgItem(target,31817)))});}
        else{workspace(tab);target=panel;if(tab==2){timelineColumns=Header_GetItemCount(ListView_GetHeader(listing));timelineRows=ListView_GetItemCount(listing);SendMessageW(panel,WM_COMMAND,222,0);sessionRoute=read(data/L"workspace_command.json").textOr("action")=="session_view";}}
        gui.processMessages();UpdateWindow(target);
        RECT rc;GetClientRect(target,&rc);HDC dc=GetDC(target),mem=CreateCompatibleDC(dc);HBITMAP bm=CreateCompatibleBitmap(dc,rc.right,rc.bottom);auto old=SelectObject(mem,bm);
        DWORD affinity=0;GetWindowDisplayAffinity(target,&affinity);SetWindowDisplayAffinity(target,WDA_NONE);PrintWindow(target,mem,PW_CLIENTONLY);SetWindowDisplayAffinity(target,affinity);
        BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=rc.right;bi.bmiHeader.biHeight=-rc.bottom;bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
        cv::Mat image(rc.bottom,rc.right,CV_8UC4);SelectObject(mem,old);GetDIBits(dc,bm,0,rc.bottom,image.data,&bi,DIB_RGB_COLORS);std::string name=tab==-2?"native_main":tab==-1?"native_overlay":"workspace_"+std::to_string(tab);cv::imwrite((std::filesystem::u8path(directory)/(name+".png")).string(),image);
        DeleteObject(bm);DeleteDC(mem);ReleaseDC(target,dc);if(tab>=0)tabs.items.push_back(num(tab));
    }
    result.members.push_back({"tabs",tabs});result.members.push_back({"startup_settings",boolean(autoCheck&&scanCheck&&hudCheck)});
    result.members.push_back({"session_filter_route",boolean(sessionRoute)});result.members.push_back({"session_columns",num(timelineColumns)});result.members.push_back({"session_rows",num(timelineRows)});result.members.push_back({"navigation_arm_route",boolean(navRoute)});result.members.push_back({"diary_editor_route",boolean(editorRoute)});result.members.push_back({"diary_share_route",boolean(shareRoute)});
    SendMessageW(scanCheck,BM_SETCHECK,BST_UNCHECKED,0);SendMessageW(hudCheck,BM_SETCHECK,BST_UNCHECKED,0);saveOptions();
    auto saved=read(data/L"native_settings.json");result.members.push_back({"snare_watch_setting",boolean(flag(saved,"snare_alerts",false))});bool persisted=!flag(saved,"scan_on_launch",true)&&!flag(saved,"show_hud",true);
    result.members.push_back({"settings_persisted",boolean(persisted)});
    SendMessageW(host,WM_HOTKEY,HOTKEY,0);bool shown=IsWindowVisible(gui.windowHandle())!=FALSE;
    SendMessageW(host,WM_HOTKEY,HOTKEY,0);bool hidden=IsWindowVisible(gui.windowHandle())==FALSE;
    result.members.push_back({"hotkey_message_route",boolean(shown&&hidden)});
    write(std::filesystem::u8path(directory)/"ui_test.json",result);shutdown();return field(library,"rows").items.empty()||!persisted||!shown||!hidden?3:0;
}
}
