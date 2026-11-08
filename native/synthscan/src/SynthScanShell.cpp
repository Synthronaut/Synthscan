// SynthScan native lifecycle/workspace. Original mining application stays intact.
#define UNICODE
#define _UNICODE
#include "SynthScanShell.h"
#include "SynthFinderHUD.h"
#include "SynthHome.h"
#include "SynthPages.h"
#include "SynthDirectoryCard.h"
#include "FinderLayout.h"
#include "SynthItemIcons.h"
#include "HudVisibility.h"
#include "SynthMenu.h"
#include "SynthJson.h"
#include "JurisdictionBadge.h"
#include "SynthDiaryUI.h"
#include "SynthNavUI.h"
#include "MiningAdvice.h"
#include "MinerGUI.h"
#include "HudHotkeys.h"
#include "AppPaths.h"
#include "ScreenCapture.h"
#include "AfkNudge.h"
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
#include <future>
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
bool isAutomatic=false,testing=false,attached=false,hudVisible=true,scanOnLaunch=true,showSession=true,hotkeyOK=false,snareAlerts=true,hangars=false,finder=false;
bool pirateDetails=false,quest=false,pirate=false,miningResume=true,placementLocked=false,activityExpanded=true;
bool manualHudPreview=false;
std::string activityCommandId;
std::string directoryRowId,directoryItemId,directoryRequestId,directoryText,libraryRevision,libraryLoadingRevision,relatedItemId;
std::future<Json> libraryJob;
int currentTab=0,hotkeyChoice=0,selected=-1;
HudHotkeys::Config hudKeys;HudHotkeys::Gate hudKeyGate;HudHotkeys::Binding editedKeys[2];
HudHotkeys::Edge hudKeyEdges[2];HWND keyForeground=nullptr;
HWINEVENTHOOK foregroundHook=nullptr;bool keyEditing=false,keyScopeActive=false,toggleKeyOK=false,cycleKeyOK=false;
std::string keyError;unsigned togglePresses=0,cyclePresses=0,windowsKeyMessages=0,polledKeyEdges=0;double lastHudKeyAt=0;
Json state,settings,library;std::vector<Json> visible;
Json directoryShops;
HIMAGELIST directoryIcons=nullptr;
int directorySortColumn=-1;bool directorySortDescending=false;
std::set<std::string> favorites;
std::unique_ptr<Gdiplus::Bitmap> icon,hangarImage;
std::string lastState,summary="Session service starting",note;
std::string controlCompleted="Startup registration updated.";
std::string reputationNotice;
NOTIFYICONDATAW tray{};
bool userExitRequested=false;
AfkNudge afk;
AfkMousePulse afkPulse;
HWND afkGame=nullptr;
constexpr UINT_PTR AFK_PULSE_TIMER=3;
double lastAfkPulseAt=0;
void updateAfkIndicator(){
    if(mining)SetWindowTextW(GetDlgItem(mining->windowHandle(),1017),mining->isOverlayMode()?L"More":L"Home");
    if(tray.hWnd){auto label=wide(std::string("SynthScan — AFK ")+(afk.armed?"ON: ":"")+afk.status);wcsncpy_s(tray.szTip,label.c_str(),_TRUNCATE);tray.uFlags=NIF_TIP;Shell_NotifyIconW(NIM_MODIFY,&tray);}
}
void toggleAfk(){if(host)KillTimer(host,AFK_PULSE_TIMER);afkPulse.cancel();afkGame=nullptr;afk.toggle(GetTickCount64());updateAfkIndicator();}
void appendAfkMenu(HMENU menu,UINT id){
    auto label=wide(std::string("AFK mouse jiggler: ")+(afk.armed?"ON — ":"OFF — ")+afk.status);
    AppendMenuW(menu,MF_STRING|(afk.armed?MF_CHECKED:0),id,label.c_str());
}
void desktop();
constexpr UINT PROFILE_FIRST=12000,PROFILE_MANAGE=12100,PROFILE_EDIT=12101;
void appendProfileMenu(HMENU menu){
    if(!mining)return;
    HMENU profiles=CreatePopupMenu();
    const auto names=mining->miningProfileNames();
    for(size_t i=0;i<names.size()&&i<100;i++){
        std::wstring label;for(auto c:names[i]){label+=c;if(c==L'&')label+=L'&';}
        AppendMenuW(profiles,MF_STRING|(int(i)==mining->selectedMiningProfile()?MF_CHECKED:0),PROFILE_FIRST+UINT(i),label.c_str());
    }
    if(!names.empty())AppendMenuW(profiles,MF_SEPARATOR,0,nullptr);
    AppendMenuW(profiles,MF_STRING,PROFILE_MANAGE,L"Add / manage ship profiles…");
    AppendMenuW(profiles,MF_STRING|(names.empty()?MF_GRAYED:0),PROFILE_EDIT,L"Heads, modules & crafting…");
    AppendMenuW(menu,MF_POPUP,reinterpret_cast<UINT_PTR>(profiles),L"Ship profiles");
}
bool handleProfileChoice(int choice){
    if(!mining)return false;
    if(choice>=PROFILE_FIRST&&choice<PROFILE_MANAGE){mining->selectMiningProfile(choice-PROFILE_FIRST);return true;}
    if(choice==PROFILE_MANAGE||choice==PROFILE_EDIT){
        desktop();
        if(choice==PROFILE_MANAGE)mining->manageMiningProfiles();else mining->editMiningLoadout();
        return true;
    }
    return false;
}
std::filesystem::path root,data;
double lastStateAt=0;
double uiScale=1;
int px(int value){return int(std::lround(value*uiScale));}
constexpr int HOTKEY=31001,HOTKEY_CYCLE=31002,TRAY=WM_APP+41;
constexpr UINT HOTKEY_REFRESH=WM_APP+43;
constexpr UINT_PTR HUD_KEY_TIMER=4;
constexpr COLORREF BG=RGB(20,23,29),CARD=RGB(29,33,41),TEXT=RGB(233,237,241),MUTED=RGB(149,160,173),GOLD=RGB(98,204,255);
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
void saveSettings(){settings=obj({{"scan_on_launch",boolean(scanOnLaunch)},{"show_hud",boolean(hudVisible)},{"session_strip",boolean(showSession)},{"snare_alerts",boolean(snareAlerts)},{"piracy_details",boolean(pirateDetails)},{"hud_mode",str(finder?"finder":hangars?"hangars":quest?"questing":pirate?"piracy":"mining")},{"mining_resume",boolean(miningResume)},{"hud_locked",boolean(placementLocked)},{"activity_expanded",boolean(activityExpanded)},{"hotkey",num(hotkeyChoice)}});if(!write(data/L"native_settings.json",settings))note="Could not save HUD settings.";}
void togglePlacement(){placementLocked=!placementLocked;if(mining){mining->updateClickThrough();if(!placementLocked&&!testing)SetForegroundWindow(mining->windowHandle());}saveSettings();}
void modeControls(){if(!mining)return;SetWindowTextW(GetDlgItem(mining->windowHandle(),1017),mining->isOverlayMode()?L"More":L"Home");if(pirate)SetWindowTextW(GetDlgItem(mining->windowHandle(),31814),flag(field(state,"piracy_watch"),"waiting_active")?L"Pause wait":L"Start wait");if(pirate){SetWindowTextW(GetDlgItem(mining->windowHandle(),1002),pirateDetails?L"Details -":L"Details +");SetWindowTextW(GetDlgItem(mining->windowHandle(),31817),snareAlerts?L"Alerts on":L"Muted");}if(quest)SetWindowTextW(GetDlgItem(mining->windowHandle(),1002),L"Next");mining->placeOreRowsButton();for(int id:{31810,31811,31813,31818,31819})InvalidateRect(GetDlgItem(mining->windowHandle(),id),nullptr,FALSE);InvalidateRect(mining->windowHandle(),nullptr,FALSE);}
void setMode(int value){
    const int current=finder?4:hangars?3:quest?2:pirate?1:0;
    if(current==value||!mining)return;
    if(current==0){miningResume=text(GetDlgItem(mining->windowHandle(),1002))==L"Live on";if(miningResume)SendMessageW(mining->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);endMiningRock();}
    SynthFinder::sync(false);pirate=value==1;quest=value==2;hangars=value==3;finder=value==4;
    if(value==0){mining->setLiveModeActive(false);if(miningResume)SendMessageW(mining->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);}
    mining->updateClickThrough();saveSettings();modeControls();mining->refreshActivityLayout();
}
bool hotkeyContext(){
    if(!hudKeys.gameOnly)return true;auto game=SCMiner::ScreenCapture::gameWindow();if(!game)return false;
    auto foreground=GetForegroundWindow();return foreground==game||(mining&&GetAncestor(foreground,GA_ROOT)==mining->windowHandle());
}
std::wstring hotkeyStatus(){
    if(!hudKeys.enabled)return L"HUD shortcuts are disabled.";
    if(!keyError.empty())return wide(keyError);
    return std::wstring(hotkeyOK?L"Ready · ":L"Waiting for game/HUD focus · ")+L"Toggle: "+HudHotkeys::label(hudKeys.toggle)+L" · Cycle: "+HudHotkeys::label(hudKeys.cycle);
}
void applyHotkey(){
    bool wanted=!testing&&hudKeys.enabled&&!keyEditing&&hotkeyContext();
    keyForeground=wanted?GetForegroundWindow():nullptr;
    if(wanted!=keyScopeActive){
        KillTimer(host,HUD_KEY_TIMER);for(auto& edge:hudKeyEdges)edge.reset();
        UnregisterHotKey(host,HOTKEY);UnregisterHotKey(host,HOTKEY_CYCLE);toggleKeyOK=cycleKeyOK=hotkeyOK=false;keyScopeActive=wanted;
        if(wanted){
            keyError.clear();toggleKeyOK=hudKeys.toggle.key&&RegisterHotKey(host,HOTKEY,hudKeys.toggle.modifiers|MOD_NOREPEAT,hudKeys.toggle.key);
            cycleKeyOK=hudKeys.cycle.key&&RegisterHotKey(host,HOTKEY_CYCLE,hudKeys.cycle.modifiers|MOD_NOREPEAT,hudKeys.cycle.key);
            hotkeyOK=(!hudKeys.toggle.key||toggleKeyOK)&&(!hudKeys.cycle.key||cycleKeyOK);
            if(!hotkeyOK){keyError="Shortcut unavailable: "+utf8(HudHotkeys::label((!hudKeys.toggle.key||toggleKeyOK)?hudKeys.cycle:hudKeys.toggle))+" may already be used by another application. Choose another key or save to retry.";UnregisterHotKey(host,HOTKEY);UnregisterHotKey(host,HOTKEY_CYCLE);toggleKeyOK=cycleKeyOK=false;}
            if(hotkeyOK)SetTimer(host,HUD_KEY_TIMER,20,nullptr);
        }
    }
    if(panel&&currentTab==7&&status&&IsWindow(status))SetWindowTextW(status,hotkeyStatus().c_str());
}
void resetHotkeyRegistration(){KillTimer(host,HUD_KEY_TIMER);for(auto& edge:hudKeyEdges)edge.reset();UnregisterHotKey(host,HOTKEY);UnregisterHotKey(host,HOTKEY_CYCLE);keyScopeActive=hotkeyOK=toggleKeyOK=cycleKeyOK=false;applyHotkey();}
void CALLBACK foregroundChanged(HWINEVENTHOOK,DWORD,HWND,LONG,LONG,DWORD,DWORD){if(host)PostMessageW(host,HOTKEY_REFRESH,0,0);}
LRESULT CALLBACK shortcutEdit(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR which){
    if(message==WM_GETDLGCODE)return DLGC_WANTALLKEYS|DLGC_WANTARROWS|DLGC_WANTCHARS;
    if(message==WM_SETFOCUS){keyEditing=true;applyHotkey();SetWindowTextW(hwnd,L"Press a shortcut…");return 0;}
    if(message==WM_KILLFOCUS){keyEditing=false;hudKeyGate.suppressedUntil=GetTickCount64()+250;SetWindowTextW(hwnd,HudHotkeys::label(editedKeys[which]).c_str());applyHotkey();return 0;}
    if(message==WM_KEYDOWN||message==WM_SYSKEYDOWN){
        if(w==VK_ESCAPE){SetFocus(GetDlgItem(panel,354));return 0;}
        if(w==VK_CONTROL||w==VK_SHIFT||w==VK_MENU||w==VK_LWIN||w==VK_RWIN)return 0;
        HudHotkeys::Binding candidate{unsigned(w),unsigned(((GetKeyState(VK_CONTROL)&0x8000)?MOD_CONTROL:0)|((GetKeyState(VK_MENU)&0x8000)?MOD_ALT:0)|((GetKeyState(VK_SHIFT)&0x8000)?MOD_SHIFT:0))};
        if(w==VK_BACK||w==VK_DELETE)candidate={};
        if(!HudHotkeys::valid(candidate)){SetWindowTextW(status,L"Use a function key (except F12), or add Ctrl/Alt. Esc cancels; Backspace clears.");return 0;}
        editedKeys[which]=candidate;SetFocus(GetDlgItem(panel,354));return 0;
    }
    if(message==WM_CHAR||message==WM_SYSCHAR||message==WM_KEYUP||message==WM_SYSKEYUP)return 0;
    return DefSubclassProc(hwnd,message,w,l);
}

void showHud(bool value){if(!value)SynthFinder::sync(false);manualHudPreview=value&&!SCMiner::ScreenCapture::gameWindow();hudVisible=value;if(mining){if(HudVisibility::shouldShow(value,activityExpanded,SCMiner::ScreenCapture::gameWindow()!=nullptr,manualHudPreview)){ShowWindow(mining->windowHandle(),SW_SHOWNOACTIVATE);mining->keepOverlayAboveGame(true);}else mining->hide();}saveSettings();}
void setActivityExpanded(bool value){
    if(value&&!SCMiner::ScreenCapture::gameWindow())manualHudPreview=true;
    activityExpanded=value;if(!value)SynthFinder::sync(false);
    if(mining){if(value&&hudVisible){if(!mining->isOverlayMode()){auto window=mining->windowHandle();bool hadNoActivate=(GetWindowLongPtrW(window,GWL_EXSTYLE)&WS_EX_NOACTIVATE)!=0;SetWindowLongPtrW(window,GWL_EXSTYLE,GetWindowLongPtrW(window,GWL_EXSTYLE)|WS_EX_NOACTIVATE);mining->toggleOverlayMode();if(!hadNoActivate)SetWindowLongPtrW(window,GWL_EXSTYLE,GetWindowLongPtrW(window,GWL_EXSTYLE)&~WS_EX_NOACTIVATE);}ShowWindow(mining->windowHandle(),SW_SHOWNOACTIVATE);mining->keepOverlayAboveGame(true);}else mining->hide();}
    saveSettings();
}
void handleHudHotkey(int id,LPARAM packed,bool polled=false){
    int action=id==HOTKEY?0:id==HOTKEY_CYCLE?1:-1;auto binding=action==0?hudKeys.toggle:hudKeys.cycle;
    if(action>=0){if(polled)++polledKeyEdges;else ++windowsKeyMessages;}
    if(testing||!mining||!hudKeyGate.accept(action,GetTickCount64(),hudKeys.enabled,hotkeyOK,hotkeyContext(),keyEditing,binding,HIWORD(packed),LOWORD(packed)))return;
    if(action==0)++togglePresses;else ++cyclePresses;lastHudKeyAt=epoch();
    auto window=mining->windowHandle();bool shown=mining->isOverlayMode()&&!SynthPages::contains(window)&&IsWindowVisible(window)&&activityExpanded;
    if(action==1){setMode(HudHotkeys::nextTab(finder?4:hangars?3:quest?2:pirate?1:0));if(!shown&&!SynthPages::contains(window))mining->hide();if(shown&&finder)SynthFinder::sync(true);return;}
    if(shown){showHud(false);return;}
    if(SynthPages::contains(window)){SynthHome::selectPage("home");SynthPages::release(window);}
    if(!mining->isOverlayMode())mining->toggleOverlayMode(false);
    setActivityExpanded(true);showHud(true);if(finder)SynthFinder::sync(true);
}
void pollHudKeys(){
    // Poll only the two configured keys, on the UI thread, while in scope.
    // Focus changes disarm immediately even before the foreground hook runs.
    if(testing||!hudKeys.enabled||!hotkeyOK||keyEditing||!keyForeground||GetForegroundWindow()!=keyForeground){for(auto& edge:hudKeyEdges)edge.reset();return;}
    unsigned modifiers=((GetAsyncKeyState(VK_CONTROL)&0x8000)?MOD_CONTROL:0)|((GetAsyncKeyState(VK_MENU)&0x8000)?MOD_ALT:0)|((GetAsyncKeyState(VK_SHIFT)&0x8000)?MOD_SHIFT:0)|(((GetAsyncKeyState(VK_LWIN)|GetAsyncKeyState(VK_RWIN))&0x8000)?MOD_WIN:0);
    HudHotkeys::Binding bindings[]{hudKeys.toggle,hudKeys.cycle};
    for(int action=0;action<2;++action)if(bindings[action].key&&hudKeyEdges[action].sample(unsigned(GetAsyncKeyState(bindings[action].key))))handleHudHotkey(action?HOTKEY_CYCLE:HOTKEY,MAKELPARAM(modifiers,bindings[action].key),true);
}
void dockHud(){if(!mining)return;setActivityExpanded(true);showHud(true);mining->dockOverlayTopRight();}
void activityControl(){
    auto request=read(data/L"activity_hud_command.json");auto id=request.textOr("id");double age=epoch()-request.numberOr("at");
    if(!id.empty()&&id!=activityCommandId&&request.numberOr("owner_pid")==GetCurrentProcessId()&&age>=-.25&&age<5){
        auto action=request.textOr("action");
        if(action=="dock_hud_top_right"){activityCommandId=id;dockHud();}
        else if(action=="set_activity_expanded"){
            activityCommandId=id;setActivityExpanded(flag(request,"expanded",activityExpanded));
        }else if(action=="set_afk_armed"&&field(request,"armed").kind==Json::Kind::Bool){
            activityCommandId=id;if(flag(request,"armed")!=afk.armed)toggleAfk();
        }
    }
}
void miningDesktop(){if(!mining)return;SynthHome::hide();if(mining->isOverlayMode())mining->toggleOverlayMode();hudVisible=true;activityExpanded=true;mining->show();ShowWindow(mining->windowHandle(),SW_RESTORE);SetForegroundWindow(mining->windowHandle());modeControls();saveSettings();}
void desktop(){SynthHome::show();}
void command(Json value){
    static unsigned sequence=0;char id[80];sprintf_s(id,"%020llu-%010u-%010u",GetTickCount64(),GetCurrentProcessId(),++sequence);
    value.members.push_back({"id",str(id)});value.members.push_back({"session_token",field(state,"session_token")});
    auto destination=data/L"workspace_command.json";
    if(!testing&&(value.textOr("action").find("diary_")==0||value.textOr("action").find("nav_")==0||value.textOr("action").find("session_")==0)){auto folder=data/L"diary_commands";std::error_code error;std::filesystem::create_directories(folder,error);destination=folder/std::filesystem::u8path(std::string(id)+".json");}
    if(!write(destination,value))note="Could not queue workspace action.";else note="Working…";
}
void homeAction(const std::string& value){
    if(!mining)return;
    SynthHome::pageHost();
    if(value=="mining"){
        ShowWindow(mining->windowHandle(),SW_HIDE);
        if(mining->isOverlayMode())mining->toggleOverlayMode(false);
        modeControls();SynthPages::mount(mining->windowHandle());
    }else if(value=="directory"||value=="servers"||value=="settings"||value=="acceptance"){
        workspace(value=="directory"?0:value=="servers"?2:value=="acceptance"?5:4);
        SynthPages::mount(panel,px(100));
    }else if(value=="blueprints"){mining->openBlueprintLibrary();SynthPages::mount(mining->craftingHandle());}
    else if(value=="refinery"){mining->openRefineryOrders();SynthPages::mount(mining->refineryHandle());}
    else if(value=="planner"){mining->openMiningPlanner();SynthPages::mount(mining->plannerHandle());}
    else if(value=="diary"){SynthScanDiary::open();SynthPages::mount(SynthScanDiary::window());}
    else if(value=="notes"){mining->openPersonalNotes();SynthPages::mount(mining->notesHandle());}
    else if(value=="bookmarks"){SynthScanNav::open();SynthPages::mount(SynthScanNav::window());}
    else if(value=="daylight"){
        write(data/L"daylight_embed_request.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"parent",num(double(reinterpret_cast<UINT_PTR>(SynthHome::pageHost())))},{"generation",num(SynthPages::generation())},{"at",num(epoch())}}));
        spawnPython(L"daylight_planner.py",{L"--embedded",L"--owner",std::to_wstring(GetCurrentProcessId())});
    }else if(value=="hud_piracy"){workspace(6);SynthPages::mount(panel,px(100));}
    else if(value=="dismiss_refinery")command(obj({{"action",str("dismiss_refinery_notices")}}));
    else if(value.rfind("hud_",0)==0){
        SynthPages::release(mining->windowHandle());
        setMode(value=="hud_finder"?4:value=="hud_missions"?2:value=="hud_hangars"?3:0);
        if(!mining->isOverlayMode())mining->toggleOverlayMode();
        setActivityExpanded(true);showHud(true);modeControls();
    }
}
HWND control(const wchar_t* cls,const wchar_t* label,DWORD style,int x,int y,int w,int h,int id){
    if(cls==std::wstring(L"BUTTON")&&(style&0xf)==BS_PUSHBUTTON)style|=BS_OWNERDRAW;
    HWND hwnd=CreateWindowExW(cls==std::wstring(L"EDIT")?WS_EX_CLIENTEDGE:0,cls,label,WS_CHILD|WS_VISIBLE|style,px(x),px(y),px(w),px(h),panel,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    SetWindowTheme(hwnd,L"DarkMode_Explorer",nullptr);
    SendMessageW(hwnd,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return hwnd;
}
void addRow(const Json& row){
    int index=int(visible.size());visible.push_back(row);
    auto name=wide(row.textOr("name"));LVITEMW item{};item.mask=LVIF_TEXT;item.iItem=index;item.pszText=name.data();
    if(currentTab==0){
        auto type=row.textOr("item_type");
        if(type.empty()){auto notes=row.textOr("detail");auto first=notes.find('\n');if(first!=std::string::npos){auto line=notes.substr(first+1,notes.find('\n',first+1)-first-1);auto separator=line.find(" · ");if(separator!=std::string::npos)type=line.substr(separator+4);}}
        item.mask|=LVIF_IMAGE;item.iImage=int(FinderItems::classify(row.textOr("kind"),row.textOr("category"),type,row.textOr("name"),row.textOr("item_record")));
    }
    ListView_InsertItem(listing,&item);
    auto k=wide(row.textOr("kind")),c=wide(row.textOr("category"));ListView_SetItemText(listing,index,1,k.data());ListView_SetItemText(listing,index,2,c.data());
    if(currentTab==2){const char* keys[]={"joined_local","left_local","kind","shard_id","name","duration","visit"};for(int col=0;col<7;col++){auto value=wide(row.textOr(keys[col]));ListView_SetItemText(listing,index,col,value.data());}}
}
void updateDirectoryCategories(){
    if(currentTab!=0||!category||!kind)return;
    auto prior=text(category),type=text(kind);std::set<std::string> cats;
    for(const auto& row:field(library,"rows").items){
        if(type!=L"All"&&type!=L"Favorites"&&wide(row.textOr("kind"))!=type)continue;
        if(type==L"Favorites"&&!favorites.count(row.textOr("id")))continue;
        cats.insert(row.textOr("category"));
    }
    SendMessageW(category,CB_RESETCONTENT,0,0);SendMessageW(category,CB_ADDSTRING,0,(LPARAM)L"All categories");
    for(auto& c:cats){auto value=wide(c);SendMessageW(category,CB_ADDSTRING,0,(LPARAM)value.c_str());}
    int found=int(SendMessageW(category,CB_FINDSTRINGEXACT,-1,(LPARAM)prior.c_str()));SendMessageW(category,CB_SETCURSEL,found>=0?found:0,0);
}
void listRows(){
    if(!listing)return;
    std::string prior=selected>=0&&selected<int(visible.size())?visible[selected].textOr("id"):"";
    SendMessageW(listing,WM_SETREDRAW,FALSE,0);ListView_DeleteAllItems(listing);visible.clear();selected=-1;icon.reset();if(currentTab==0)EnableWindow(GetDlgItem(panel,210),FALSE);
    std::wstring query=lower(text(search)),type=text(kind),cat=text(category);
    size_t matched=0;
    std::vector<const Json*> candidates;
    auto append=[&](const Json& row){
        if(currentTab==0){auto name=wide(row.textOr("name"));if(name.empty()||std::all_of(name.begin(),name.end(),[](wchar_t c){return std::iswspace(c)!=0;}))return;}
        if(currentTab==0&&!relatedItemId.empty()&&row.textOr("item_id")!=relatedItemId)return;
        if(!query.empty()&&relatedItemId.empty()){auto hay=lower(wide(row.textOr("search",row.textOr("name")+" "+row.textOr("detail"))));std::wistringstream terms(query);std::wstring term;while(terms>>term)if(hay.find(term)==std::wstring::npos)return;}
        if(currentTab==0&&type==L"Favorites"&&!favorites.count(row.textOr("id")))return;
        if(currentTab==0&&type!=L"All"&&type!=L"Favorites"&&wide(row.textOr("kind"))!=type&&!(type==L"Item"&&row.textOr("kind")=="Component"))return;
        if(currentTab==0&&cat!=L"All categories"&&wide(row.textOr("category"))!=cat)return;
        ++matched;if(currentTab==0)candidates.push_back(&row);else addRow(row);
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
    if(currentTab==0){
        if(directorySortColumn>=0){
            struct Entry {const Json* row;std::wstring key,name;};std::vector<Entry> ordered;
            const char* key=directorySortColumn==0?"name":directorySortColumn==1?"kind":"category";
            for(auto row:candidates)ordered.push_back({row,lower(wide(row->textOr(key))),lower(wide(row->textOr("name")))});
            std::stable_sort(ordered.begin(),ordered.end(),[](const Entry& a,const Entry& b){if(a.key!=b.key)return directorySortDescending?a.key>b.key:a.key<b.key;if(a.name!=b.name)return a.name<b.name;return a.row->textOr("id")<b.row->textOr("id");});
            candidates.clear();for(auto& entry:ordered)candidates.push_back(entry.row);
        }
        for(size_t i=0;i<std::min(size_t(300),candidates.size());++i)addRow(*candidates[i]);
    }
    SendMessageW(listing,WM_SETREDRAW,TRUE,0);InvalidateRect(listing,nullptr,TRUE);
    if(!visible.empty()){
        int index=0;for(int i=0;i<int(visible.size());i++)if(visible[i].textOr("id")==prior){index=i;break;}
        ListView_SetItemState(listing,index,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);ListView_EnsureVisible(listing,index,FALSE);
    }else{
        if(currentTab==0)SynthDirectoryCard::update(detail,obj({}),obj({}),false);else SetWindowTextW(detail,L"No matches. Change the search or filters.");directoryRowId.clear();directoryItemId.clear();directoryRequestId.clear();directoryText.clear();
    }
    if(currentTab==2){auto count=int(field(state,"session_log").numberOr("count"));auto offset=int(field(state,"session_log").numberOr("offset"));auto label=std::to_string(visible.empty()?0:offset+1)+"–"+std::to_string(offset+int(visible.size()))+" of "+std::to_string(count)+" visits · times UTC+08:00";SetDlgItemTextW(panel,227,wide(label).c_str());EnableWindow(GetDlgItem(panel,225),offset>0);EnableWindow(GetDlgItem(panel,226),offset+100<count);}
    SetWindowTextW(status,wide(std::to_string(visible.size())+" of "+std::to_string(matched)+" matches"+(matched>visible.size()?" · Narrow your search":"")+(currentTab==0?"":" · "+note)).c_str());
}
void renderDirectoryDetail(const Json& row){
    if(currentTab==0){SynthDirectoryCard::update(detail,row,directoryShops,favorites.count(row.textOr("id"))!=0);return;}
    std::string body=row.textOr("detail");
    if(currentTab==0&&!row.textOr("item_id").empty())body=row.textOr("name")+"\n\n"+directoryText+"\n\n"+body;
    if(favorites.count(row.textOr("id")))body="★ Favorite\n\n"+body;
    std::wstring rendered=wide(body);for(size_t p=0;(p=rendered.find(L'\n',p))!=std::wstring::npos;p+=2)rendered.replace(p,1,L"\r\n");
    SetWindowTextW(detail,rendered.c_str());
}
void selection(){
    int i=ListView_GetNextItem(listing,-1,LVNI_SELECTED);if(i<0||i>=int(visible.size()))return;selected=i;
    const auto& row=visible[i];
    if(currentTab==0&&!row.textOr("item_id").empty()){
        if(directoryRowId!=row.textOr("id")||directoryItemId!=row.textOr("item_id")){
            directoryRowId=row.textOr("id");directoryItemId=row.textOr("item_id");directoryRequestId=std::to_string(GetTickCount64())+":"+directoryRowId;
            directoryText="IN-GAME PURCHASE LOCATIONS — UEX Corp\nChecking shops in the background…";
            directoryShops=obj({{"loading",boolean(true)}});
            if(!testing)write(data/L"item_directory_request.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"at",num(epoch())},{"request_id",str(directoryRequestId)},{"row_id",str(directoryRowId)},{"item_id",field(row,"item_id")}}));
        }
    }else{directoryRowId.clear();directoryItemId.clear();directoryRequestId.clear();directoryText.clear();directoryShops=obj({});}
    renderDirectoryDetail(row);icon.reset();
    if(currentTab==0){EnableWindow(GetDlgItem(panel,210),TRUE);SetDlgItemTextW(panel,210,favorites.count(row.textOr("id"))?L"★ Remove favorite":L"☆ Add favorite");}
    if(currentTab==2&&editReminder&&GetFocus()!=editReminder)SetWindowTextW(editReminder,wide(row.textOr("notes")).c_str());
    auto path=row.textOr("icon");if(!path.empty())icon=std::make_unique<Gdiplus::Bitmap>(wide(path).c_str());
    InvalidateRect(panel,nullptr,FALSE);
}
LRESULT CALLBACK headerPaint(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(message==WM_ERASEBKGND)return TRUE;
    if(message==WM_PAINT||message==WM_PRINTCLIENT){
        PAINTSTRUCT ps{};HDC dc=message==WM_PAINT?BeginPaint(hwnd,&ps):reinterpret_cast<HDC>(w);
        RECT rc;GetClientRect(hwnd,&rc);FillRect(dc,&rc,card);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,MUTED);SelectObject(dc,font);
        for(int i=0;i<Header_GetItemCount(hwnd);i++){
            RECT cell;Header_GetItemRect(hwnd,i,&cell);wchar_t label[200]{};HDITEMW item{};item.mask=HDI_TEXT;item.pszText=label;item.cchTextMax=200;Header_GetItem(hwnd,i,&item);
            int x=cell.right-px(13),y=(cell.top+cell.bottom)/2;cell.left+=px(8);if(currentTab==0)cell.right-=px(24);DrawTextW(dc,label,-1,&cell,DT_SINGLELINE|DT_VCENTER|DT_NOPREFIX|DT_END_ELLIPSIS);
            if(currentTab==0){HPEN pen=CreatePen(PS_SOLID,px(1),i==directorySortColumn?GOLD:MUTED);auto old=SelectObject(dc,pen);
                auto arrow=[&](int cy,bool down){MoveToEx(dc,x-px(4),cy+(down?-px(2):px(2)),nullptr);LineTo(dc,x,cy+(down?px(2):-px(2)));LineTo(dc,x+px(4),cy+(down?-px(2):px(2)));};
                if(i==directorySortColumn)arrow(y,directorySortDescending);else{arrow(y-px(4),false);arrow(y+px(4),true);}SelectObject(dc,old);DeleteObject(pen);
            }
        }
        if(message==WM_PAINT)EndPaint(hwnd,&ps);return 0;
    }
    return DefSubclassProc(hwnd,message,w,l);
}
void layoutDirectory(){
    if(currentTab!=0||!panel||!listing||!detail||!search||!kind||!category)return;
    RECT rect{};GetClientRect(panel,&rect);float scale=GetDpiForWindow(panel)/96.f;
    auto layout=FinderLayout::calculate(int(rect.right/scale),int(rect.bottom/scale));
    auto move=[&](HWND child,const FinderLayout::Box& box){MoveWindow(child,int(box.x*scale),int(box.y*scale),int(box.width*scale),int(box.height*scale),TRUE);};
    move(search,layout.query);move(kind,layout.type);move(category,layout.category);move(listing,layout.results);move(detail,layout.details);
    int available=int(layout.results.width*scale)-GetSystemMetrics(SM_CXVSCROLL);
    ListView_SetColumnWidth(listing,0,available*54/100);ListView_SetColumnWidth(listing,1,available*18/100);ListView_SetColumnWidth(listing,2,available*28/100);
    move(GetDlgItem(panel,210),{20,layout.actions,196,32});
    move(status,{20,layout.footer,int(rect.right/scale)-40,22});
}
void rebuild(int tab){
    currentTab=tab;selected=-1;icon.reset();relatedItemId.clear();
    HWND child=GetWindow(panel,GW_CHILD);while(child){HWND next=GetWindow(child,GW_HWNDNEXT);DestroyWindow(child);child=next;}
    if(directoryIcons){ImageList_Destroy(directoryIcons);directoryIcons=nullptr;}
    listing=detail=search=kind=category=nullptr;keyEditing=false;applyHotkey();
    const wchar_t* names[]={L"Item directory",L"Material picker",L"Server log",L"Review & imports",L"Startup & HUD"};
    for(int i=0;i<5;i++)control(L"BUTTON",names[i],BS_PUSHBUTTON,18+i*168,62,160,30,100+i);
    status=control(L"STATIC",L"",SS_LEFT,20,596,816,45,200);
    if(tab==7){
        control(L"STATIC",L"HUD shortcuts",SS_LEFT,28,118,760,30,0);
        control(L"BUTTON",L"Enable HUD shortcuts",BS_AUTOCHECKBOX|WS_TABSTOP,28,166,370,30,350);SendDlgItemMessageW(panel,350,BM_SETCHECK,hudKeys.enabled?BST_CHECKED:BST_UNCHECKED,0);
        control(L"BUTTON",L"Only while game / HUD is focused",BS_AUTOCHECKBOX|WS_TABSTOP,430,166,400,30,351);SendDlgItemMessageW(panel,351,BM_SETCHECK,hudKeys.gameOnly?BST_CHECKED:BST_UNCHECKED,0);
        control(L"STATIC",L"Show / hide HUD",SS_LEFT,28,225,340,24,0);control(L"STATIC",L"Next HUD tab",SS_LEFT,430,225,340,24,0);
        editedKeys[0]=hudKeys.toggle;editedKeys[1]=hudKeys.cycle;
        for(int i=0;i<2;++i){auto edit=control(L"EDIT",HudHotkeys::label(editedKeys[i]).c_str(),ES_READONLY|WS_TABSTOP,28+i*402,254,340,32,352+i);SetWindowSubclass(edit,shortcutEdit,1,i);}
        control(L"STATIC",L"Click a field, then press your shortcut. Esc cancels; Backspace clears.\r\nUse a spare function key, or a combination with Ctrl/Alt.",SS_LEFT,28,303,790,48,0);
        control(L"BUTTON",L"Save shortcuts",BS_PUSHBUTTON|WS_TABSTOP,28,370,220,34,354);control(L"BUTTON",L"Use F23 / F24",BS_PUSHBUTTON|WS_TABSTOP,268,370,220,34,355);control(L"BUTTON",L"Back to settings",BS_PUSHBUTTON|WS_TABSTOP,508,370,220,34,356);
        control(L"STATIC",L"G502 X in G HUB: G8 → F23 (toggle), G7 → F24 (next tab).\r\nAssociate the profile with StarCitizen.exe, not just the launcher.\r\nCycle: Mining → Piracy → Missions → Hangars → Finder.\r\nCycling a hidden HUD keeps it hidden. No game input is sent.",SS_LEFT,28,433,790,120,0);
        SetWindowTextW(status,hotkeyStatus().c_str());return;
    }
    if(tab==5){
        SetWindowTextW(status,L"Settings are saved immediately.");
        auto prefs=read(data/L"contract_share_preferences.json");
        const wchar_t* labels[]={L"Automatically accept shared contracts",L"Automatically accept party invitations",L"Automatically accept friend requests"};
        const char* keys[]={"enabled","party_enabled","friend_enabled"};
        control(L"STATIC",L"Choose which incoming requests SynthScan can accept.",SS_LEFT,28,120,770,28,0);
        for(int i=0;i<3;++i){control(L"BUTTON",labels[i],BS_AUTOCHECKBOX|WS_TABSTOP,28,174+i*52,760,32,330+i);SendDlgItemMessageW(panel,330+i,BM_SETCHECK,flag(prefs,keys[i],false)?BST_CHECKED:BST_UNCHECKED,0);}
        control(L"STATIC",L"Keep Star Citizen focused. Game menus can block the accept key; SynthScan retries while the request is still active.",SS_LEFT,28,354,770,62,0);
        return;
    }
    if(tab==6){
        SetWindowTextW(status,L"Manual wait timer. Population observations do not confirm an interdiction.");
        control(L"BUTTON",L"Start / pause wait",BS_PUSHBUTTON,28,532,200,34,334);
        control(L"BUTTON",L"Clear wait",BS_PUSHBUTTON,248,532,170,34,335);
        return;
    }
    if(tab==4){
        autoCheck=control(L"BUTTON",L"Launch SynthScan with Star Citizen",BS_AUTOCHECKBOX,28,122,700,28,301);
        scanCheck=control(L"BUTTON",L"Start mining scans automatically with the game",BS_AUTOCHECKBOX,28,166,700,28,302);
        hudCheck=control(L"BUTTON",L"Show HUD",BS_AUTOCHECKBOX,28,210,700,28,303);
        sessionCheck=control(L"BUTTON",L"Show shard, region and available measurements in the HUD",BS_AUTOCHECKBOX,28,254,720,28,304);
        SendMessageW(autoCheck,BM_SETCHECK,std::filesystem::exists(startupLink())?BST_CHECKED:BST_UNCHECKED,0);
        SendMessageW(scanCheck,BM_SETCHECK,scanOnLaunch?BST_CHECKED:BST_UNCHECKED,0);SendMessageW(hudCheck,BM_SETCHECK,hudVisible?BST_CHECKED:BST_UNCHECKED,0);
        SendMessageW(sessionCheck,BM_SETCHECK,showSession?BST_CHECKED:BST_UNCHECKED,0);
        control(L"BUTTON",L"Snare Watch: sound + banner for logged interdiction reports",BS_AUTOCHECKBOX,28,284,720,24,311);SendDlgItemMessageW(panel,311,BM_SETCHECK,snareAlerts?BST_CHECKED:BST_UNCHECKED,0);
        control(L"BUTTON",L"HUD keyboard / mouse shortcuts…",BS_PUSHBUTTON,28,314,390,28,340);
        control(L"BUTTON",L"Open Hangars HUD",BS_PUSHBUTTON,28,346,300,30,312);
        control(L"BUTTON",L"Compboard inventory",BS_PUSHBUTTON,608,346,220,30,313);
        control(L"BUTTON",L"Save startup & HUD settings",BS_PUSHBUTTON,28,390,300,34,306);
        control(L"BUTTON",L"Show / hide HUD now",BS_PUSHBUTTON,348,390,240,34,307);
        control(L"BUTTON",L"Open desktop view",BS_PUSHBUTTON,608,390,220,34,308);
        control(L"BUTTON",L"Enable player FPS · Windows permission",BS_PUSHBUTTON,28,435,390,30,309);
        control(L"BUTTON",L"Start network timing · Windows permission",BS_PUSHBUTTON,432,435,396,30,310);
        auto watcher=read(data/L"watcher_status.json");
        std::wstring explanation=L"Launching, scanning and showing the HUD are separate settings.\r\n";
        explanation+=L"HUD shortcuts can be customized above. ";
        explanation+=wide(watcher.textOr("error"));
        explanation+=L"\r\nSnare Watch uses crime reports; unmonitored/friendly catches may be silent.\r\nServer FPS/population require a verified source.";
        if(flag(state,"fps_permission_required"))explanation+=L"\r\nUse the permission buttons above for player FPS/network timing.";
        explanation+=L"\r\nTiming helpers stop when SynthScan closes.";
        control(L"STATIC",explanation.c_str(),SS_LEFT,28,482,790,112,0);
        return;
    }
    search=control(L"EDIT",L"",ES_AUTOHSCROLL,20,112,tab==2?260:370,28,201);
    SendMessageW(search,EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(tab==2?L"Search time, shard, name or notes":L"Search items, blueprints or mission rewards"));
    kind=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,tab==2?295:405,112,tab==2?170:160,200,202);
    if(tab==2){control(L"STATIC",L"Search name, shard, time or notes",SS_LEFT,20,94,260,17,0);control(L"STATIC",L"Region",SS_LEFT,295,94,170,17,0);category=control(L"EDIT",L"",ES_AUTOHSCROLL,480,112,145,28,203);control(L"EDIT",L"",ES_AUTOHSCROLL,640,112,145,28,221);control(L"BUTTON",L"Filter",BS_PUSHBUTTON,795,112,45,28,222);control(L"STATIC",L"From date",SS_LEFT,480,94,145,17,0);control(L"STATIC",L"Through date",SS_LEFT,640,94,145,17,0);SendMessageW(category,EM_SETCUEBANNER,TRUE,(LPARAM)L"YYYY-MM-DD");SendDlgItemMessageW(panel,221,EM_SETCUEBANNER,TRUE,(LPARAM)L"YYYY-MM-DD");}
    else category=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,580,112,260,250,203);
    if(tab==0){
        for(auto value:{L"All",L"Blueprint",L"Item",L"Material",L"Component",L"Ship",L"Vehicle",L"Favorites"})SendMessageW(kind,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(value));
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
    listing=control(WC_LISTVIEWW,L"",LVS_REPORT|LVS_SINGLESEL|LVS_SHOWSELALWAYS|LVS_SHAREIMAGELISTS|WS_TABSTOP,20,155,820,tab==2?155:188,204);
    if(tab==0){directoryIcons=SynthItemIcons::create(GetDpiForWindow(panel));ListView_SetImageList(listing,directoryIcons,LVSIL_SMALL);}
    ListView_SetExtendedListViewStyle(listing,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER);ListView_SetBkColor(listing,CARD);ListView_SetTextBkColor(listing,CARD);ListView_SetTextColor(listing,TEXT);
    SetWindowSubclass(ListView_GetHeader(listing),headerPaint,1,0);
    const wchar_t* columns[]={L"Name",L"Type / weight",L"Category / region"};
    const wchar_t* sessionColumns[]={L"Joined",L"Left / observed",L"Region",L"Shard",L"Shard label",L"Duration",L"Visit"};int sessionWidths[]={160,160,85,65,130,85,100};
    for(int i=0;i<(tab==2?7:3);i++){LVCOLUMNW c{};c.mask=LVCF_TEXT|LVCF_WIDTH;c.pszText=const_cast<wchar_t*>(tab==2?sessionColumns[i]:columns[i]);c.cx=px(tab==2?sessionWidths[i]:(i==0?390:200));ListView_InsertColumn(listing,i,&c);}
    detail=tab==0?SynthDirectoryCard::create(panel,205,px(20),px(355),px(820),px(184)):control(L"EDIT",L"Select an entry",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL,100,355,740,184,205);
    if(tab==0){control(L"BUTTON",L"☆ Add favorite",BS_PUSHBUTTON,20,551,190,30,210);EnableWindow(GetDlgItem(panel,210),FALSE);}
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
    listRows();layoutDirectory();
}
void saveOptions(){
    scanOnLaunch=SendMessageW(scanCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    showSession=SendMessageW(sessionCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    snareAlerts=SendDlgItemMessageW(panel,311,BM_GETCHECK,0,0)==BST_CHECKED;
    bool wantHud=SendMessageW(hudCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    bool wantAuto=SendMessageW(autoCheck,BM_GETCHECK,0,0)==BST_CHECKED;
    showHud(wantHud);applyHotkey();saveSettings();
    const auto watcher=read(data/L"watcher_status.json");
    const bool needsWatcher=wantAuto&&epoch()-watcher.numberOr("at")>10;
    if((wantAuto!=std::filesystem::exists(startupLink())||needsWatcher)&&!testing){
        if(controlProcess){note="A startup change is already running.";return;}
        if(!spawnPython(L"native_control.py",{wantAuto?L"--install":L"--uninstall"},&controlProcess))note="Could not start the startup helper.";
        else{note="Applying startup registration…";controlCompleted="Startup registration updated.";}
    }else note="Settings saved.";
    InvalidateRect(mining->windowHandle(),nullptr,FALSE);SetWindowTextW(status,wide(note).c_str());
}
void handleAction(int id){
    if(id==340){rebuild(7);return;}
    if(currentTab==7&&id==356){rebuild(4);return;}
    if(currentTab==7&&id==355){editedKeys[0]={VK_F23,0};editedKeys[1]={VK_F24,0};SetDlgItemTextW(panel,352,L"F23");SetDlgItemTextW(panel,353,L"F24");SendDlgItemMessageW(panel,351,BM_SETCHECK,BST_CHECKED,0);SetWindowTextW(status,L"Recommended keys loaded. Save to apply.");return;}
    if(currentTab==7&&id==354){
        auto candidate=hudKeys;candidate.enabled=SendDlgItemMessageW(panel,350,BM_GETCHECK,0,0)==BST_CHECKED;candidate.gameOnly=SendDlgItemMessageW(panel,351,BM_GETCHECK,0,0)==BST_CHECKED;candidate.toggle=editedKeys[0];candidate.cycle=editedKeys[1];auto error=HudHotkeys::error(candidate);
        if(!error.empty()){SetWindowTextW(status,wide(error).c_str());return;}
        if(!write(data/L"hud_hotkeys.json",HudHotkeys::encodeConfig(candidate))){SetWindowTextW(status,L"Could not save shortcuts; previous settings retained.");return;}
        hudKeys=candidate;keyError.clear();hudKeyGate=HudHotkeys::Gate{};hudKeyGate.suppressedUntil=GetTickCount64()+250;resetHotkeyRegistration();SetWindowTextW(status,hotkeyStatus().c_str());return;
    }

    if(currentTab==5&&id>=330&&id<=332){
        auto prefs=read(data/L"contract_share_preferences.json");
        const char* keys[]={"enabled","party_enabled","friend_enabled"};
        Json changed=obj({});
        for(int i=0;i<3;++i)changed.members.push_back({keys[i],boolean(SendDlgItemMessageW(panel,330+i,BM_GETCHECK,0,0)==BST_CHECKED)});
        if(!write(data/L"contract_share_preferences.json",changed))SetWindowTextW(status,L"Could not save automatic acceptance settings.");
        else SetWindowTextW(status,L"Saved. The background watcher applies this setting immediately.");
        return;
    }
    if(currentTab==6&&(id==334||id==335)){
        write(data/L"piracy_command.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"at",num(epoch())},{"action",str(id==335?"reset_wait":"toggle_wait")}}));return;
    }

    if(id==312){setMode(3);showHud(true);setActivityExpanded(true);return;}
    if(id==313){if(!testing)spawnPython(L"compboard_tracker.py",{});return;}
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
    case WM_SIZE:layoutDirectory();return 0;
    case WM_COMMAND:{int id=LOWORD(w),code=HIWORD(w);if((id==201&&code==EN_CHANGE)||(id==202&&code==CBN_SELCHANGE)||(id==203&&code==CBN_SELCHANGE)){relatedItemId.clear();if(currentTab==0&&id==202)updateDirectoryCategories();if(currentTab==0||currentTab==2||currentTab==3)SetTimer(hwnd,2,180,nullptr);return 0;}handleAction(id);return 0;}
    case WM_TIMER:if(w==2){KillTimer(hwnd,2);listRows();}return 0;
    case WM_NOTIFY:{
        auto header=reinterpret_cast<NMHDR*>(l);
        if(currentTab==0&&header->hwndFrom==listing&&header->code==LVN_COLUMNCLICK){auto column=reinterpret_cast<NMLISTVIEW*>(l)->iSubItem;if(column>=0&&column<3){directorySortDescending=column==directorySortColumn?!directorySortDescending:false;directorySortColumn=column;listRows();InvalidateRect(ListView_GetHeader(listing),nullptr,FALSE);}return 0;}
        if(header->hwndFrom==listing&&header->code==LVN_ITEMCHANGED)selection();
        if(header->hwndFrom==listing&&header->code==NM_CUSTOMDRAW){auto draw=reinterpret_cast<NMLVCUSTOMDRAW*>(l);if(draw->nmcd.dwDrawStage==CDDS_PREPAINT)return CDRF_NOTIFYITEMDRAW;if(draw->nmcd.dwDrawStage==CDDS_ITEMPREPAINT){bool chosen=(ListView_GetItemState(listing,int(draw->nmcd.dwItemSpec),LVIS_SELECTED)&LVIS_SELECTED)!=0;draw->clrText=TEXT;draw->clrTextBk=chosen?RGB(25,58,82):CARD;draw->nmcd.uItemState&=~CDIS_SELECTED;return CDRF_NEWFONT;}}
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
    case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(hwnd,&ps);RECT rc;GetClientRect(hwnd,&rc);FillRect(dc,&rc,background);SetBkMode(dc,TRANSPARENT);SelectObject(dc,titleFont);SetTextColor(dc,GOLD);TextOutW(dc,px(20),px(20),L"SynthScan workspace",19);if(currentTab==6){Gdiplus::Graphics g(dc);g.TranslateTransform(float(px(20)),float(px(112)));drawPiracy(g,float(px(816)),float(px(400)),float(px(100))/100.f);}if(icon&&icon->GetLastStatus()==Gdiplus::Ok){Gdiplus::Graphics g(dc);g.SetInterpolationMode(Gdiplus::InterpolationModeHighQualityBicubic);g.DrawImage(icon.get(),px(20),px(365),px(64),px(64));}EndPaint(hwnd,&ps);return 0;}
    }
    return DefWindowProcW(hwnd,message,w,l);
}
void publishNativeStatus(){
    RECT overlayRect{};if(mining)GetWindowRect(mining->windowHandle(),&overlayRect);
    Json scan=obj({});
    if(mining){
        const auto& rock=mining->displayedRock();const auto& contents=mining->displayedContents();
        Json parts=arr();for(const auto& part:contents.parts)parts.items.push_back(obj({{"ore",str(part.ore)},{"percent",num(part.percent)},{"quality",num(part.quality)},{"inert",boolean(part.inert)}}));
        Json values=arr();if(mining->rockOnView())for(const auto& line:mining->displayedRockValueLines())values.items.push_back(str(utf8(line)));
        scan=obj({{"signature",num(mining->displayedSignature())},{"value_lines",values},{"read_age_seconds",num(mining->rockReadAgeSeconds())},{"on_view",boolean(mining->rockOnView())},{"mass",num(rock.mass)},{"scu",num(rock.scu)},{"ore",str(rock.ore)},
            {"whole",boolean(contents.whole)},{"partial",boolean(contents.partial)},{"sum",num(contents.sum)},{"parts",parts},
            {"reader_note",str(mining->contentsReadNote())}});
    }

    if(!testing&&mining)write(data/L"native_status.json",obj({{"window_handle",num(double(reinterpret_cast<UINT_PTR>(mining->windowHandle())))},{"at",num(epoch())},{"pid",num(GetCurrentProcessId())},{"afk_jiggler",obj({{"armed",boolean(afk.armed)},{"status",str(afk.status)},{"nudges",num(afk.nudges)},{"interval_seconds",num(AfkNudge::interval/1000)},{"next_in_seconds",num(afk.nextInSeconds)},{"first_pulse",boolean(afk.firstPulse())},{"pulse_active",boolean(afkPulse.active)},{"last_pulse_at",num(lastAfkPulseAt)},{"pulse_counts",num(15)}})},{"mining_scan",scan},{"scanner_active",boolean(!pirate&&!quest&&!hangars&&!finder&&text(GetDlgItem(mining->windowHandle(),1002))==L"Live on")},{"piracy_details",boolean(pirateDetails)},{"hud_mode",str(finder?"finder":hangars?"hangars":quest?"questing":pirate?"piracy":"mining")},{"hud_locked",boolean(placementLocked)},{"activity_expanded",boolean(activityExpanded)},{"activity_command_id",str(activityCommandId)},{"hud_visible",boolean(IsWindowVisible(mining->windowHandle())!=FALSE)},{"overlay_mode",boolean(mining->isOverlayMode())},{"hud_topmost",boolean((GetWindowLongPtrW(mining->windowHandle(),GWL_EXSTYLE)&WS_EX_TOPMOST)!=0)},{"hud_position",obj({{"left",num(overlayRect.left)},{"top",num(overlayRect.top)},{"right",num(overlayRect.right)},{"bottom",num(overlayRect.bottom)}})},{"hotkey_registered",boolean(hotkeyOK)},{"hud_hotkeys",obj({{"enabled",boolean(hudKeys.enabled)},{"game_only",boolean(hudKeys.gameOnly)},{"active_scope",boolean(keyScopeActive)},{"toggle_registered",boolean(toggleKeyOK)},{"cycle_registered",boolean(cycleKeyOK)},{"error",str(keyError)},{"windows_messages",num(windowsKeyMessages)},{"polled_edges",num(polledKeyEdges)},{"toggle_presses",num(togglePresses)},{"cycle_presses",num(cyclePresses)},{"last_action_at",num(lastHudKeyAt)}})},{"bridge_age",num(lastStateAt?epoch()-lastStateAt:-1)}}));
}
bool afkHeldInput(){
    for(int key=1;key<255;key++)if(GetAsyncKeyState(key)&0x8000)return true;
    return false;
}
bool afkConnected(HWND game){
    if(!game||epoch()-lastStateAt<0||epoch()-lastStateAt>=4||state.textOr("session_token").empty())return false;
    DWORD pid=0;GetWindowThreadProcessId(game,&pid);
    for(const auto& candidate:field(state,"game_pids").items)if(pid&&candidate.number==pid)return true;
    return false;
}
void pulseAfk(){
    if(testing||!afk.armed||!afkPulse.active){KillTimer(host,AFK_PULSE_TIMER);afkPulse.cancel();return;}
    LASTINPUTINFO input{sizeof(input)};
    if(GetForegroundWindow()!=afkGame||!afkConnected(afkGame)||afkHeldInput()||
       !GetLastInputInfo(&input)||!afkPulse.acceptsInput(input.dwTime)){
        // Do not fight a returning player by completing the inverse movement.
        KillTimer(host,AFK_PULSE_TIMER);afkPulse.cancel();afk.interrupted(GetTickCount64());updateAfkIndicator();return;
    }
    if(!afkPulse.ready(GetTickCount64()))return;
    INPUT event{};event.type=INPUT_MOUSE;
    event.mi.dwFlags=MOUSEEVENTF_MOVE|MOUSEEVENTF_MOVE_NOCOALESCE;
    event.mi.dx=afkPulse.delta();event.mi.time=GetTickCount();
    // Explicit timestamps let the short sequence distinguish its own input from
    // a returning player's input without installing global mouse/keyboard hooks.
    if(SendInput(1,&event,sizeof(INPUT))!=1){
        KillTimer(host,AFK_PULSE_TIMER);afkPulse.cancel();afk.sent(GetTickCount64(),false);updateAfkIndicator();return;
    }
    afkPulse.sent(GetTickCount64(),event.mi.time);
    if(!afkPulse.active){
        KillTimer(host,AFK_PULSE_TIMER);afk.sent(GetTickCount64(),true);lastAfkPulseAt=epoch();updateAfkIndicator();publishNativeStatus();
    }
}
void tickAfk(){
    if(testing||!afk.armed||afkPulse.active)return;
    HWND game=SCMiner::ScreenCapture::gameWindow();
    HWND foreground=GetForegroundWindow();
    LASTINPUTINFO info{sizeof(info)};
    bool valid=GetLastInputInfo(&info)!=FALSE;
    const bool fresh=epoch()-lastStateAt>=0&&epoch()-lastStateAt<4;
    const std::string previous=afk.status;bool wasArmed=afk.armed;
    const bool present=game||!fresh||!field(state,"game_pids").items.empty();
    if(afk.due(GetTickCount64(),present,game&&foreground==game,afkConnected(game),valid,
               valid?DWORD(GetTickCount()-info.dwTime):0,afkHeldInput())){
        LASTINPUTINFO finalInput{sizeof(finalInput)};
        if(!afkHeldInput()&&GetForegroundWindow()==game&&GetLastInputInfo(&finalInput)&&finalInput.dwTime==info.dwTime){
            afkGame=game;afkPulse.start(GetTickCount64(),info.dwTime);
            if(SetTimer(host,AFK_PULSE_TIMER,20,nullptr))pulseAfk();
            else {afkPulse.cancel();afk.sent(GetTickCount64(),false);}
        }
    }
    if(previous!=afk.status||wasArmed!=afk.armed)updateAfkIndicator();
}
void pollItemDirectory(){
    if(testing)return;
    auto meta=read(data/L"item_directory_catalog.json");
    auto revision=meta.textOr("revision");
    if(libraryJob.valid()&&libraryJob.wait_for(std::chrono::seconds(0))==std::future_status::ready){
        try{auto next=libraryJob.get();if(!field(next,"rows").items.empty()){
            library=std::move(next);libraryRevision=libraryLoadingRevision;
            if(panel&&IsWindowVisible(panel)&&currentTab==0){
                updateDirectoryCategories();
                listRows();
            }
        }}catch(...){note="Item catalog refresh failed; keeping the previous catalog.";}
    }
    if(!revision.empty()&&revision!=libraryRevision&&!libraryJob.valid()){
        libraryLoadingRevision=revision;auto path=data/L"workspace_library.json";
        libraryJob=std::async(std::launch::async,[path](){auto next=read(path,64*1024*1024);SynthFinder::prepare(next);return next;});
    }
    if(panel&&IsWindowVisible(panel)&&currentTab==0&&selected>=0&&selected<int(visible.size())){
        auto result=read(data/L"item_directory_detail.json",512*1024);
        if(result.numberOr("owner_pid")==GetCurrentProcessId()&&result.textOr("request_id")==directoryRequestId&&result.textOr("row_id")==visible[selected].textOr("id")&&result.textOr("item_id")==visible[selected].textOr("item_id")){
            auto next=result.textOr("text");if(!next.empty()&&(next!=directoryText||encode(result)!=encode(directoryShops))){directoryText=std::move(next);directoryShops=result;renderDirectoryDetail(visible[selected]);}
        }
    }
}
void timer(){
    static bool previousGame=false;bool game=SCMiner::ScreenCapture::gameWindow()!=nullptr;
    if(previousGame&&!game)manualHudPreview=false;previousGame=game;
    if(mining&&mining->isOverlayMode()){
        bool wanted=HudVisibility::shouldShow(hudVisible,activityExpanded,game,manualHudPreview);
        if(bool(IsWindowVisible(mining->windowHandle()))!=wanted)ShowWindow(mining->windowHandle(),wanted?SW_SHOWNOACTIVATE:SW_HIDE);
    }
    if(panel&&IsWindowVisible(panel)&&currentTab==6)InvalidateRect(panel,nullptr,FALSE);
    if(panel&&IsWindowVisible(panel)&&currentTab==5){
        auto watcher=read(data/L"contract_share_status.json");
        bool fresh=watcher.numberOr("owner_pid")==GetCurrentProcessId()&&epoch()-watcher.numberOr("at")>=0&&epoch()-watcher.numberOr("at")<3;
        SetWindowTextW(status,wide(fresh?watcher.textOr("decision","Waiting for a request"):"Settings saved. Waiting for the background watcher.").c_str());
    }

    pollItemDirectory();
    SynthFinder::sync(finder&&mining&&mining->isOverlayMode()&&hudVisible&&activityExpanded&&IsWindowVisible(mining->windowHandle()));
    activityControl();
    static HWND previousForeground=nullptr;HWND foreground=GetForegroundWindow();
    if(mining){mining->updateClickThrough();if(hudVisible&&activityExpanded)mining->keepOverlayAboveGame(foreground!=previousForeground);}
    previousForeground=foreground;
    if(activityMode())modeControls();
    if(showHandle&&WaitForSingleObject(showHandle,0)==WAIT_OBJECT_0)desktop();
    auto next=read(data/L"session_state.json",8*1024*1024);
    double stamp=next.numberOr("written_at");
    bool fresh=stamp>0&&epoch()-stamp>=0&&epoch()-stamp<4;
    if(fresh){
        SynthHome::update(field(next,"home"),next.textOr("identity"),!next.textOr("session_token").empty());
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
        if(stamp!=lastStateAt){bool refineryChanged=field(next,"home").textOr("refinery_notice")!=field(state,"home").textOr("refinery_notice");state=std::move(next);lastStateAt=stamp;note=state.textOr("note");if(refineryChanged&&mining)mining->refreshActivityLayout();
            SynthScanDiary::update(field(state,"diary"),field(state,"diary_result"),note);
            SynthScanNav::update(field(state,"navigation"));
            if(panel&&IsWindowVisible(panel)&&(currentTab==1||currentTab==2||currentTab==3)){
                auto key=encode(field(state,currentTab==1?"plans":currentTab==2?"session_rows":"review_revision"));if(key!=lastState&&GetFocus()!=editReminder){lastState=key;listRows();}
                if(currentTab!=2)SetWindowTextW(status,wide(note).c_str());else SetWindowTextW(status,L"");
            }
        }
        if(readyHandle&&state.numberOr("owner_pid")==GetCurrentProcessId())SetEvent(readyHandle);
    }else if(summary!="Session service unavailable"){SynthHome::update(field(state,"home"),"",false);summary="Session service unavailable";SynthScanNav::update(obj({{"message",str("Session service unavailable; capture and navigation paused.")},{"guidance",obj({{"unavailable",str("No fresh service state")}})}}));if(mining)InvalidateRect(mining->windowHandle(),nullptr,FALSE);}
    if(controlProcess){DWORD code=STILL_ACTIVE;GetExitCodeProcess(controlProcess,&code);if(code!=STILL_ACTIVE){CloseHandle(controlProcess);controlProcess=nullptr;note=code==0?controlCompleted:read(data/L"control_status.json").textOr("error","Helper action failed. See native_control.log in your data folder.");if(status)SetWindowTextW(status,wide(note).c_str());}}
    tickAfk();applyHotkey();
    publishNativeStatus();
}
LRESULT CALLBACK hostProc(HWND hwnd,UINT message,WPARAM w,LPARAM l){
    LRESULT menuResult=0;if(SynthMenus::message(message,w,l,menuResult))return menuResult;
    if(message==TRAY&&l==NIN_BALLOONUSERCLICK){spawnPython(L"app_launcher.py",{L"--status"});return 0;}
    if(message==WM_APP+42){activityControl();publishNativeStatus();return 0;}
    if(message==WM_TIMER){if(w==AFK_PULSE_TIMER)pulseAfk();else if(w==HUD_KEY_TIMER)pollHudKeys();else timer();return 0;}
    if(message==HOTKEY_REFRESH){applyHotkey();return 0;}
    if(message==WM_HOTKEY){handleHudHotkey(int(w),l);return 0;}
    if(message==TRAY){if(l==WM_LBUTTONDBLCLK){desktop();return 0;}if(l==WM_RBUTTONUP){HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,1,L"Open SynthScan");AppendMenuW(menu,MF_STRING,2,L"Show / hide HUD");AppendMenuW(menu,MF_STRING,3,L"Startup & HUD settings");AppendMenuW(menu,MF_STRING,4,L"Exit SynthScan");AppendMenuW(menu,MF_STRING|(activityMode()?0:MF_CHECKED),5,L"HUD mode: Mining");AppendMenuW(menu,MF_STRING|(pirate?MF_CHECKED:0),6,L"HUD mode: Piracy");AppendMenuW(menu,MF_STRING|(quest?MF_CHECKED:0),8,L"HUD mode: Missions");AppendMenuW(menu,MF_STRING|(placementLocked?MF_CHECKED:0),7,L"Lock HUD position");AppendMenuW(menu,MF_STRING,20,L"Dock HUD top right");AppendMenuW(menu,MF_STRING|(finder?MF_CHECKED:0),19,L"HUD mode: Finder");AppendMenuW(menu,MF_STRING|(hangars?MF_CHECKED:0),9,L"HUD mode: Hangars");AppendMenuW(menu,MF_STRING,10,L"Compboard inventory");AppendMenuW(menu,MF_STRING,11,L"Daylight planner");appendAfkMenu(menu,12);AppendMenuW(menu,MF_STRING,13,L"Automatic acceptance…");POINT at;GetCursorPos(&at);SetForegroundWindow(hwnd);appendProfileMenu(menu);int choice=SynthMenus::track(menu,TPM_RETURNCMD|TPM_RIGHTBUTTON,at.x,at.y,0,hwnd,nullptr);DestroyMenu(menu);if(choice==20){dockHud();return 0;}if(handleProfileChoice(choice))return 0;if(choice==19){setMode(4);showHud(true);setActivityExpanded(true);return 0;}if(choice==1)desktop();if(choice==2)showHud(!hudVisible);if(choice==3)workspace(4);if(choice==5||choice==6)setMode(choice==6);if(choice==8)setMode(2);if(choice==7)togglePlacement();if(choice==9){setMode(3);showHud(true);setActivityExpanded(true);}if(choice==10)spawnPython(L"compboard_tracker.py",{});if(choice==11)spawnPython(L"daylight_planner.py",{});if(choice==12)toggleAfk();if(choice==13)spawnPython(L"contract_share_helper.py",{L"--owner",std::to_wstring(GetCurrentProcessId())});if(choice==4&&mining){markUserExit();PostMessageW(mining->windowHandle(),WM_CLOSE,0,0);}return 0;}}
    return DefWindowProcW(hwnd,message,w,l);
}
LRESULT CALLBACK mainSubclass(HWND hwnd,UINT message,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    LRESULT menuResult=0;if(SynthMenus::message(message,w,l,menuResult))return menuResult;
    if(message==WM_ACTIVATEAPP)SynthFinder::activationChanged(w!=0);
    if(message==WM_SYSCOMMAND&&(w&0xfff0)==0xf020){setActivityExpanded(false);return 0;}
    if(message==WM_COMMAND&&l&&mining&&mining->isOverlayMode()) {
        DWORD foreground=0;GetWindowThreadProcessId(GetForegroundWindow(),&foreground);
        if(foreground!=GetCurrentProcessId()&&!mining->isOverlayButton(reinterpret_cast<HWND>(l)))return 0;
    }
    if(message==WM_COMMAND&&LOWORD(w)==31812){togglePlacement();return 0;}
    if(message==WM_COMMAND&&(LOWORD(w)==31814||LOWORD(w)==31815)){
        if(pirate)write(data/L"piracy_command.json",obj({{"action",str(LOWORD(w)==31814?"toggle_wait":"reset_wait")},{"owner_pid",num(GetCurrentProcessId())},{"at",num(epoch())}}));return 0;
    }
    if(message==WM_COMMAND&&LOWORD(w)==31819){setMode(4);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==31818){setMode(3);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==31813){setMode(2);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1002&&quest){write(data/L"questing_command.json",obj({{"action",str("next")},{"owner_pid",num(GetCurrentProcessId())}}));return 0;}
    if(message==WM_COMMAND&&(LOWORD(w)==31810||LOWORD(w)==31811)){setMode(LOWORD(w)==31811);return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1002&&pirate){pirateDetails=!pirateDetails;saveSettings();modeControls();mining->refreshActivityLayout();return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==31817&&pirate){snareAlerts=!snareAlerts;saveSettings();modeControls();return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1011){if(mining->isOverlayMode())desktop();else{mining->toggleOverlayMode();modeControls();}return 0;}
    if(message==WM_COMMAND&&LOWORD(w)==1017){
        if(mining&&!mining->isOverlayMode()){SynthHome::selectPage("home");desktop();return 0;}
        if(mining&&mining->isOverlayMode()){
            HMENU mode=CreatePopupMenu();AppendMenuW(mode,MF_STRING|(activityMode()?0:MF_CHECKED),10,L"Mining HUD");AppendMenuW(mode,MF_STRING|(pirate?MF_CHECKED:0),11,L"Piracy HUD");AppendMenuW(mode,MF_STRING|(quest?MF_CHECKED:0),13,L"Missions HUD");AppendMenuW(mode,MF_STRING|(finder?MF_CHECKED:0),19,L"Finder HUD");AppendMenuW(mode,MF_STRING|(hangars?MF_CHECKED:0),15,L"Hangars HUD");AppendMenuW(mode,MF_STRING|(placementLocked?MF_CHECKED:0),12,L"Lock HUD position");AppendMenuW(mode,MF_STRING,20,L"Dock HUD top right");AppendMenuW(mode,MF_STRING,16,L"Daylight planner");appendAfkMenu(mode,17);AppendMenuW(mode,MF_STRING,18,L"Automatic acceptance…");AppendMenuW(mode,MF_SEPARATOR,0,nullptr);AppendMenuW(mode,MF_STRING,4,L"Server log & interdiction history");AppendMenuW(mode,MF_STRING,6,L"Startup & HUD settings");AppendMenuW(mode,MF_STRING,14,L"Setup & reputation status");
            POINT at;GetCursorPos(&at);appendProfileMenu(mode);int choice=SynthMenus::track(mode,TPM_RETURNCMD,at.x,at.y,0,hwnd,nullptr);DestroyMenu(mode);if(choice==20){dockHud();return 0;}if(handleProfileChoice(choice))return 0;if(choice==19){setMode(4);showHud(true);setActivityExpanded(true);return 0;}if(choice==18)spawnPython(L"contract_share_helper.py",{L"--owner",std::to_wstring(GetCurrentProcessId())});if(choice==17)toggleAfk();if(choice==16)spawnPython(L"daylight_planner.py",{});if(choice==12)togglePlacement();if(choice==15)setMode(3);if(choice==13)setMode(2);if(choice==10||choice==11)setMode(choice==11);if(choice==4)workspace(2);if(choice==6)workspace(4);if(choice==14)spawnPython(L"app_launcher.py",{L"--status"});return 0;
        }
        HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,2,L"Item directory");AppendMenuW(menu,MF_STRING,3,L"Material picker");AppendMenuW(menu,MF_STRING,4,L"Server log");AppendMenuW(menu,MF_STRING,5,L"Review imported records");AppendMenuW(menu,MF_STRING,6,L"Startup & HUD settings");AppendMenuW(menu,MF_STRING,7,L"Show / hide HUD");AppendMenuW(menu,MF_STRING,8,L"Mining diary & personal records");AppendMenuW(menu,MF_STRING,9,L"Rock bookmarks & return test");AppendMenuW(menu,MF_STRING,16,L"Daylight planner");AppendMenuW(menu,MF_STRING,14,L"Setup & reputation status");
        appendAfkMenu(menu,17);AppendMenuW(menu,MF_STRING,18,L"Automatic acceptance…");AppendMenuW(menu,MF_SEPARATOR,0,nullptr);AppendMenuW(menu,MF_STRING|(activityMode()?0:MF_CHECKED),10,L"HUD mode: Mining");AppendMenuW(menu,MF_STRING|(pirate?MF_CHECKED:0),11,L"HUD mode: Piracy");
        AppendMenuW(menu,MF_STRING|(quest?MF_CHECKED:0),13,L"HUD mode: Missions");AppendMenuW(menu,MF_STRING|(finder?MF_CHECKED:0),19,L"HUD mode: Finder");AppendMenuW(menu,MF_STRING|(hangars?MF_CHECKED:0),15,L"HUD mode: Hangars");AppendMenuW(menu,MF_STRING|(placementLocked?MF_CHECKED:0),12,L"Lock HUD position");AppendMenuW(menu,MF_STRING,20,L"Dock HUD top right");POINT at;GetCursorPos(&at);appendProfileMenu(menu);int choice=SynthMenus::track(menu,TPM_RETURNCMD,at.x,at.y,0,hwnd,nullptr);DestroyMenu(menu);if(choice==20){dockHud();return 0;}if(handleProfileChoice(choice))return 0;if(choice==19){setMode(4);showHud(true);setActivityExpanded(true);return 0;}
        if(choice==18){spawnPython(L"contract_share_helper.py",{L"--owner",std::to_wstring(GetCurrentProcessId())});return 0;}
        if(choice==17){toggleAfk();return 0;}
        if(choice==16){spawnPython(L"daylight_planner.py",{});return 0;}
        if(choice==14){spawnPython(L"app_launcher.py",{L"--status"});return 0;}if(choice==12){togglePlacement();return 0;}
        if(choice==15){setMode(3);return 0;}if(choice==13){setMode(2);return 0;}if(choice==10||choice==11){setMode(choice==11);return 0;}
        if(choice==1)return DefSubclassProc(hwnd,message,w,l);if(choice>=2&&choice<=6)workspace(choice-2);if(choice==7)showHud(!hudVisible);if(choice==8)SynthScanDiary::open();if(choice==9)SynthScanNav::open();return 0;
    }
    return DefSubclassProc(hwnd,message,w,l);
}
}
bool automatic(){return isAutomatic;}
bool piracyMode(){return pirate;}
bool piracyDetails(){return pirateDetails;}
int piracyHeight(){return pirateDetails?350:200;}
int activityFooterHeight(){return 30;}
bool questingMode(){return quest;}
bool activityMode(){return pirate||quest||hangars||finder;}
bool finderMode(){return finder;}
bool finderKey(unsigned int message,size_t value,void* target){return SynthFinder::key(message,WPARAM(value),HWND(target));}
bool finderOwnsInput(void* target){return SynthFinder::owns(HWND(target));}
bool hangarsMode(){return hangars;}
bool hudLocked(){return placementLocked;}
bool gameAvailable(){
    if(activityMode())return false;
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
void attach(SCMiner::MinerGUI* gui,std::function<bool(const std::string&)> confirm,std::function<int(int,const std::string&)> ownership){
    mining=gui;confirmOwned=std::move(confirm);attached=true;uiScale=GetDpiForWindow(gui->windowHandle())/96.0;if(uiScale<.75)uiScale=1;data=SCMiner::AppPaths::data();
    Json runtime=read(SCMiner::AppPaths::program()/L"native_runtime.json");root=std::filesystem::u8path(runtime.textOr("workspace"));
    hudKeys=HudHotkeys::decodeConfig(read(data/L"hud_hotkeys.json"));
    settings=read(data/L"native_settings.json");scanOnLaunch=flag(settings,"scan_on_launch",true);hudVisible=flag(settings,"show_hud",true);activityExpanded=flag(settings,"activity_expanded",true);showSession=flag(settings,"session_strip",true);finder=settings.textOr("hud_mode")=="finder";hangars=settings.textOr("hud_mode")=="hangars";snareAlerts=flag(settings,"snare_alerts",true);pirate=settings.textOr("hud_mode")=="piracy";pirateDetails=flag(settings,"piracy_details",false);quest=settings.textOr("hud_mode")=="questing";miningResume=flag(settings,"mining_resume",scanOnLaunch);placementLocked=flag(settings,"hud_locked",false);gui->updateClickThrough();hotkeyChoice=int(settings.numberOr("hotkey"));if(hotkeyChoice<0||hotkeyChoice>2)hotkeyChoice=0;
    library=read(data/L"workspace_library.json",64*1024*1024);if(field(library,"rows").items.empty())library=read(SCMiner::AppPaths::program()/L"workspace_library.json");for(auto& value:read(data/L"workspace_favorites.json").items)favorites.insert(value.text);
    SynthHome::initialize(gui->windowHandle(),data,homeAction);
    SynthFinder::initialize(gui->windowHandle(),data,std::move(ownership));SynthFinder::prepare(library);
    SynthScanDiary::initialize(gui->windowHandle(),data,testing,[](Json value){command(value);});
    SynthScanNav::initialize(gui->windowHandle(),testing,[](Json value){command(value);});
    background=CreateSolidBrush(BG);card=CreateSolidBrush(CARD);
    font=CreateFontW(-px(15),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
    titleFont=CreateFontW(-px(24),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Bahnschrift");
    WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=hostProc;wc.lpszClassName=L"SynthScanHost";RegisterClassW(&wc);host=CreateWindowW(wc.lpszClassName,L"SynthScan services",0,0,0,0,0,nullptr,nullptr,wc.hInstance,nullptr);
    SetWindowSubclass(gui->windowHandle(),mainSubclass,1,0);SetWindowTextW(GetDlgItem(gui->windowHandle(),1017),L"More");if(!testing)foregroundHook=SetWinEventHook(EVENT_SYSTEM_FOREGROUND,EVENT_SYSTEM_FOREGROUND,nullptr,foregroundChanged,0,0,WINEVENT_OUTOFCONTEXT);applyHotkey();SetTimer(host,1,500,nullptr);
    if(!testing){
        job=CreateJobObjectW(nullptr,nullptr);if(job){JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};info.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_BREAKAWAY_OK;SetInformationJobObject(job,JobObjectExtendedLimitInformation,&info,sizeof(info));}
        std::error_code error;std::filesystem::remove(data/L"bridge_stop.json",error);
        if(!spawnPython(L"native_bridge.py",{L"--data-dir",data.wstring(),L"--owner",std::to_wstring(GetCurrentProcessId())},&bridgeProcess))note="Could not start session services. Check native_runtime.json.";
        tray.cbSize=sizeof(tray);tray.hWnd=host;tray.uID=1;tray.uFlags=NIF_MESSAGE|NIF_ICON|NIF_TIP;tray.uCallbackMessage=TRAY;tray.hIcon=LoadIconW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(IDI_APPICON));wcscpy_s(tray.szTip,L"SynthScan");Shell_NotifyIconW(NIM_ADD,&tray);
    }
    if(activityMode()&&text(GetDlgItem(gui->windowHandle(),1002))==L"Live on"){bool p=pirate,q=quest,h=hangars,f=finder;pirate=false;quest=false;hangars=false;finder=false;SendMessageW(gui->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);pirate=p;quest=q;hangars=h;finder=f;}
    modeControls();
    if(isAutomatic){
        gui->restoreOverlayPlacement();
        LONG_PTR style=GetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE);SetWindowLongPtrW(gui->windowHandle(),GWL_EXSTYLE,style|WS_EX_NOACTIVATE);
        if(!gui->isOverlayMode())gui->toggleOverlayMode(false);
        if((scanOnLaunch&&!pirate&&!quest&&!hangars&&!finder)!=(text(GetDlgItem(gui->windowHandle(),1002))==L"Live on"))SendMessageW(gui->windowHandle(),WM_COMMAND,MAKEWPARAM(1002,BN_CLICKED),0);
        modeControls();ShowWindow(gui->windowHandle(),HudVisibility::shouldShow(hudVisible,activityExpanded,SCMiner::ScreenCapture::gameWindow()!=nullptr,false)?SW_SHOWNOACTIVATE:SW_HIDE);gui->updateClickThrough();gui->keepOverlayAboveGame(true);
    }else if(!testing){desktop();}
}
void workspace(int tab){
    if(!panel||!IsWindow(panel)){WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=panelProc;wc.hCursor=LoadCursor(nullptr,IDC_ARROW);wc.hbrBackground=background;wc.lpszClassName=L"SynthScanWorkspace";RegisterClassW(&wc);panel=CreateWindowExW(0,wc.lpszClassName,L"SynthScan workspace",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,px(884),px(695),mining?mining->windowHandle():nullptr,nullptr,wc.hInstance,nullptr);SetWindowDisplayAffinity(panel,WDA_EXCLUDEFROMCAPTURE);BOOL dark=TRUE;DwmSetWindowAttribute(panel,20,&dark,sizeof(dark));}
    rebuild(tab);
    if(testing){SetWindowPos(panel,HWND_BOTTOM,-32000,-32000,0,0,SWP_NOSIZE|SWP_NOACTIVATE);ShowWindow(panel,SW_SHOWNOACTIVATE);}else{ShowWindow(panel,SW_SHOW);SetForegroundWindow(panel);}
}
std::string refineryNotice(){return !activityMode()?field(state,"home").textOr("refinery_notice"):"";}
int sessionHeight(){return !attached?0:(showSession&&!pirate&&!hangars&&!finder?44:0)+(refineryNotice().empty()?0:18);}
void drawFinder(Gdiplus::Graphics& g,float width,float height,float scale){
    Gdiplus::SolidBrush ink(Gdiplus::Color(255,233,237,241));
    Gdiplus::Font title(L"Segoe UI",15*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    g.DrawString(L"FINDER",-1,&title,Gdiplus::PointF(16*scale,10*scale),&ink);
}
void drawHangars(Gdiplus::Graphics& g,float width,float height,float scale){
    const auto model=read(data/L"hangar_hud.json",16384);
    const bool fresh=model.numberOr("owner_pid")==GetCurrentProcessId()&&epoch()-model.numberOr("at")>=0&&epoch()-model.numberOr("at")<4;
    auto& image=hangarImage;
    static std::filesystem::file_time_type stamp{};
    std::error_code error;auto path=data/L"hangar_hud.png";auto changed=std::filesystem::last_write_time(path,error);
    if(fresh&&!error&&(!image||changed!=stamp)){
        std::ifstream file(path,std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(file)),{});
        if(!bytes.empty()&&bytes.size()<1024*1024){
            HGLOBAL memory=GlobalAlloc(GMEM_MOVEABLE,bytes.size());
            if(memory){void* buffer=GlobalLock(memory);if(buffer){memcpy(buffer,bytes.data(),bytes.size());GlobalUnlock(memory);IStream* stream=nullptr;
                if(SUCCEEDED(CreateStreamOnHGlobal(memory,TRUE,&stream))){
                    {std::unique_ptr<Gdiplus::Bitmap> decoded(Gdiplus::Bitmap::FromStream(stream));
                        if(decoded&&decoded->GetLastStatus()==Gdiplus::Ok&&decoded->GetWidth()==860&&decoded->GetHeight()==300){
                            Gdiplus::Rect rect(0,0,860,300);image.reset(decoded->Clone(rect,PixelFormat32bppPARGB));stamp=changed;
                        }}
                    stream->Release();
                }else GlobalFree(memory);
            }else GlobalFree(memory);}
        }
    }
    if(fresh&&image){g.DrawImage(image.get(),Gdiplus::RectF(0,0,width,150*scale));return;}
    Gdiplus::SolidBrush ink(Gdiplus::Color(255,199,178,140)),muted(Gdiplus::Color(255,149,160,173));
    Gdiplus::Font title(L"Segoe UI",11*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel),body(L"Segoe UI",13*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    g.DrawString(L"PYAM / EXECUTIVE",-1,&title,Gdiplus::PointF(18*scale,12*scale),&ink);
    g.DrawString(L"Timing unavailable · waiting for sync",-1,&body,Gdiplus::PointF(18*scale,62*scale),&muted);
}
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
    Gdiplus::SolidBrush ink(Gdiplus::Color(255,233,237,241)),gold(Gdiplus::Color(255,98,204,255)),muted(Gdiplus::Color(255,149,160,173)),green(Gdiplus::Color(255,83,208,159));
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
    const bool available=joined&&!metrics.members.empty()&&(testing||(epoch()-watch.numberOr("observed_at")>=0&&epoch()-watch.numberOr("observed_at")<=10));
    auto value=[&](const char* key,int precision=0){auto n=metrics.find(key);if(!available||!n||n->kind!=Json::Kind::Number)return std::string("--");std::ostringstream out;out<<std::fixed<<std::setprecision(precision)<<n->number;return out.str();};
    text("PIRACY",10,8,12,&gold,130);
    drawJurisdictionBadge(g,jurisdictionBadgeModel(state,joined,epoch()),130,3,logicalWidth-140,scale,epoch());
    const char* labels[]={"SHARD PLAYERS","SERVER PLAYERS","SERVER FPS","PING (ms)"};
    const char* keys[]={"shard_pop","srv_pop","server_fps","ping_ms"};
    float col=(logicalWidth-20)/4;
    if(available){
        for(int i=0;i<4;i++){double age=field(watch,"field_ages").numberOr(keys[i]);auto label=std::string(labels[i])+(age>4?" · "+std::to_string(int(age))+"s":"");text(label,10+col*i,40,10,&muted,col-6);text(value(keys[i],i>=2?1:0),10+col*i,55,28,age>4?&muted:&ink,col-6);}
    }else{
        const auto& logged=field(state,"interdictions");text("LOGGED INTERDICTION REPORTS",10,40,10,&muted,logicalWidth/2-20);
        text(joined?std::to_string(int(logged.numberOr("current_count"))):"--",10,55,28,&ink,logicalWidth/2-20);
        int seconds=joined?int(watch.numberOr("waiting_s")):0;std::ostringstream wait;wait<<std::setfill('0')<<std::setw(2)<<seconds/3600<<":"<<std::setw(2)<<(seconds/60)%60<<":"<<std::setw(2)<<seconds%60;
        text("MANUAL WAIT · "+std::string(flag(watch,"waiting_active")?"RUNNING":"PAUSED"),logicalWidth/2,40,10,&muted,logicalWidth/2-12);text(wait.str(),logicalWidth/2,55,26,&ink,logicalWidth/2-12);
    }
    std::string status=!fresh?"Session service unavailable":!joined?"Join a shard to watch population":watch.textOr("status","Waiting for readable DisplayInfo");
    text(status,10,99,10,live?&green:&muted,275);
    auto delta=[&](const char* key){const auto& n=field(watch,key);if(!live||n.kind!=Json::Kind::Number)return std::string("--");return (n.number>=0?"+":"")+std::to_string(int(n.number));};
    text(available?"Shard change   5m "+delta("delta_5m")+"   15m "+delta("delta_15m"):"Log alerts and wait timer work without debug text",10,126,available?12:10,&ink,280);
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
    text("Station / guard hostility: UNKNOWN · zone reports do not predict attacks",10,311,10,&muted,logicalWidth-20);
}

void drawSession(Gdiplus::Graphics& g,float width,float top,float height,float scale){
    if(!attached||height<=0)return;
    Gdiplus::SolidBrush bg(Gdiplus::Color(255,20,23,29)),fg(Gdiplus::Color(255,205,214,225)),muted(Gdiplus::Color(255,149,160,173));
    g.FillRectangle(&bg,1.f,top,width-2,height-2);
    Gdiplus::Pen line(Gdiplus::Color(255,54,62,73));g.DrawLine(&line,10*scale,top,width-10*scale,top);
    Gdiplus::Font f(L"Segoe UI",10*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    Gdiplus::StringFormat format;format.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);
    auto refinery=refineryNotice();
    if(!refinery.empty()){
        Gdiplus::SolidBrush accent(Gdiplus::Color(255,98,204,255));
        g.DrawString(wide(refinery).c_str(),-1,&f,Gdiplus::RectF(10*scale,top+(showSession?44:3)*scale,width-20*scale,16*scale),&format,&accent);
    }
    if(!showSession)return;
    std::string value=epoch()-lastStateAt<4?state.textOr("identity",summary):"Session service unavailable";
    g.DrawString(wide(value).c_str(),-1,&f,Gdiplus::RectF(10*scale,top+5*scale,width-20*scale,16*scale),&format,&fg);
    bool fresh=epoch()-lastStateAt<4;
    std::string second;
    if(fresh){for(auto& metric:field(state,"metrics").items){if(!second.empty())second+=" · ";second+=metric.text;}
        auto location=state.textOr("location");if(!location.empty())second+=(second.empty()?"":" · ")+location;
    }else second="More → Startup & HUD settings";
    auto count=fresh?field(state,"cooldowns").items.size():0;if(count)second+=(second.empty()?"":" · ")+std::to_string(count)+" shard reminder(s)";
    if(second.empty())second="Use HUD + / HUD - or the tray menu · More → Server log";
    g.DrawString(wide(second).c_str(),-1,&f,Gdiplus::RectF(10*scale,top+22*scale,width-20*scale,16*scale),&format,&muted);
}
void markUserExit(){userExitRequested=true;}
bool closeToTray(){
    if(userExitRequested)return false;
    if(!testing)write(data/L"native_window_close.json",obj({{"at",num(epoch())},{"pid",num(GetCurrentProcessId())},{"action",str("hidden_to_tray")}}));
    setActivityExpanded(false);
    return true;
}
void shutdown(){
    if(foregroundHook){UnhookWinEvent(foregroundHook);foregroundHook=nullptr;}
    if(host)KillTimer(host,AFK_PULSE_TIMER);afkPulse.cancel();afk=AfkNudge{};
    hangarImage.reset();icon.reset();
    SynthHome::close();SynthFinder::close();SynthScanDiary::close();SynthScanNav::close();
    if(attached&&!testing){Json exit=obj({{"at",num(epoch())},{"pid",num(GetCurrentProcessId())},{"reason",str(userExitRequested?"user":"shutdown")},{"game_pids",field(state,"game_pids")}});write(data/L"native_exit.json",exit);}
    if(host){KillTimer(host,1);KillTimer(host,HUD_KEY_TIMER);UnregisterHotKey(host,HOTKEY);UnregisterHotKey(host,HOTKEY_CYCLE);Shell_NotifyIconW(NIM_DELETE,&tray);}
    if(bridgeProcess){write(data/L"bridge_stop.json",obj({{"owner_pid",num(GetCurrentProcessId())}}));WaitForSingleObject(bridgeProcess,2000);}
    if(job)CloseHandle(job);job=nullptr;
    if(bridgeProcess)CloseHandle(bridgeProcess);if(controlProcess)CloseHandle(controlProcess);
    if(panel)DestroyWindow(panel);panel=nullptr;if(directoryIcons)ImageList_Destroy(directoryIcons);directoryIcons=nullptr;if(host)DestroyWindow(host);host=nullptr;
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
    // Exercise real queued keyboard/dialog messages on this isolated fixture.
    // Escape used to become IDCANCEL -> WM_CLOSE -> full application exit.
    PostMessageW(gui.windowHandle(),WM_KEYDOWN,'Q',0);gui.processMessages();
    bool plainQSurvives=gui.isOpen()&&IsWindow(gui.windowHandle());
    bool overlayBeforeKeys=gui.isOverlayMode();int keyboardActions=0;
    gui.setSnapshotCallback([&keyboardActions](){keyboardActions++;});
    gui.setKeepRecordingCallback([&keyboardActions](){keyboardActions++;});
    PostMessageW(gui.windowHandle(),WM_HOTKEY,1,0);
    PostMessageW(gui.windowHandle(),WM_HOTKEY,2,0);
    PostMessageW(gui.windowHandle(),WM_KEYDOWN,'O',0);
    PostMessageW(gui.windowHandle(),WM_SYSKEYDOWN,VK_F4,0);
    gui.processMessages();
    result.members.push_back({"keyboard_actions_disabled",boolean(keyboardActions==0&&gui.isOpen()&&gui.isOverlayMode()==overlayBeforeKeys&&!gui.snapshotHotkeyHeld())});
    PostMessageW(gui.windowHandle(),WM_KEYDOWN,VK_ESCAPE,0);gui.processMessages();
    bool escapeSurvives=gui.isOpen()&&IsWindow(gui.windowHandle())&&!userExitRequested;
    SendMessageW(gui.windowHandle(),WM_COMMAND,IDCANCEL,0);gui.processMessages();
    bool cancelSurvives=gui.isOpen()&&IsWindow(gui.windowHandle())&&!userExitRequested;
    SendMessageW(gui.windowHandle(),WM_CLOSE,0,0);
    bool closeSurvives=gui.isOpen()&&IsWindow(gui.windowHandle())&&!IsWindowVisible(gui.windowHandle())&&!activityExpanded&&!userExitRequested;
    setActivityExpanded(true);
    bool restoredAfterClose=gui.isOpen()&&IsWindowVisible(gui.windowHandle())&&gui.isOverlayMode();
    if(gui.isOverlayMode())gui.toggleOverlayMode();
    result.members.push_back({"plain_q_does_not_quit",boolean(plainQSurvives)});
    result.members.push_back({"escape_does_not_quit",boolean(escapeSurvives)});
    result.members.push_back({"dialog_cancel_does_not_quit",boolean(cancelSurvives)});
    result.members.push_back({"window_close_keeps_app_running",boolean(closeSurvives)});
    result.members.push_back({"hud_restores_after_window_close",boolean(restoredAfterClose)});
    Json tabs=arr();
    SCMiner::RockStats sample;sample.mass=98000;sample.ore="Quantanium";
    for(int i=0;i<100;i++)observeMiningRock(sample,nullptr,"Stanton","Wala","MOLE",41002);
    endMiningRock();int encounters=0;for(auto& file:std::filesystem::directory_iterator(data/L"diary_inbox"))if(file.path().extension()==L".json")encounters++;
    result.members.push_back({"diary_native_encounters",num(encounters)});
    state=read(std::filesystem::u8path(directory)/"session_test_model.json");auto diaryModel=read(std::filesystem::u8path(directory)/"diary_test_model.json");bool editorRoute=false,shareRoute=false,navRoute=false,sessionRoute=false;int timelineColumns=0,timelineRows=0;
    const bool priceFixtures=std::filesystem::exists(std::filesystem::u8path(directory)/"pricing/commodities.json");
    for(int tab=-2;tab<(priceFixtures?16:14);tab++){
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
            bool unlocked=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)!=0;
            POINT point{12,12};ClientToScreen(target,&point);bool caption=SendMessageW(target,WM_NCHITTEST,0,MAKELPARAM(point.x,point.y))==HTTRANSPARENT;
            SendMessageW(target,WM_COMMAND,31812,0);bool locked=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)!=0;
            SendMessageW(target,WM_COMMAND,31812,0);bool unlockedAgain=(GetWindowLongPtrW(target,GWL_EXSTYLE)&WS_EX_TRANSPARENT)!=0;
            result.members.push_back({"hud_passive_while_game_active",boolean(unlocked&&caption&&unlockedAgain)});result.members.push_back({"hud_lock_clickthrough",boolean(locked&&!hudLocked())});
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
        else if(tab==15||(tab==13&&!priceFixtures)){
            if(!gui.isOverlayMode())gui.toggleOverlayMode();
            setMode(3);target=gui.windowHandle();
            auto fixture=std::filesystem::u8path(directory)/"hangar_card.png";
            if(std::filesystem::exists(fixture)){std::error_code error;std::filesystem::copy_file(fixture,data/L"hangar_hud.png",std::filesystem::copy_options::overwrite_existing,error);write(data/L"hangar_hud.json",obj({{"at",num(epoch())},{"owner_pid",num(GetCurrentProcessId())}}));}
            gui.refreshActivityLayout();for(int frame=0;frame<8;frame++){gui.processMessages();UpdateWindow(target);Sleep(20);}
            RECT cardRect{};GetClientRect(target,&cardRect);
            bool selected=hangarsMode()&&!piracyMode()&&!questingMode()&&read(data/L"native_settings.json").textOr("hud_mode")=="hangars";
            result.members.push_back({"hangars_tab_compact_and_pauses_scanner",boolean(selected&&!IsWindowVisible(GetDlgItem(target,1002))&&IsWindowVisible(GetDlgItem(target,31818))&&sessionHeight()==0&&cardRect.bottom<=240)});
            observeMiningRock(sample,nullptr,"Stanton","Wala","MOLE",41002);int count=0;for(auto& f:std::filesystem::directory_iterator(data/L"diary_inbox"))if(f.path().extension()==L".json")count++;
            result.members.push_back({"hangars_blocks_mining_diary",boolean(count==encounters)});
            setMode(0);bool resumed=!activityMode()&&text(GetDlgItem(target,1002))==L"Live on";setMode(3);gui.refreshActivityLayout();gui.processMessages();
            result.members.push_back({"hangars_mining_resume",boolean(resumed&&hangarsMode())});
        }
        else if(tab==13||tab==14){
            setMode(0);if(tab==13&&!gui.isOverlayMode())gui.toggleOverlayMode();
            if(tab==14&&gui.isOverlayMode())gui.toggleOverlayMode();
            auto prices=std::make_shared<SCMiner::RockPriceBook>();std::string why;
            auto cache=std::filesystem::u8path(directory)/"pricing";
            bool loaded=prices->read(encode(read(cache/"commodities.json")),encode(read(cache/"terminals.json")),encode(read(cache/"raw_prices.json")),encode(read(cache/"prices.json")),encode(read(cache/"market_averages.json")),(long long)epoch(),"4.10.2",why);
            gui.setUexPrices(true,nullptr,(long long)epoch(),"");gui.setRockPrices(loaded?prices:nullptr,why);
            sample.ore="Gold";sample.mass=40000;sample.scu=100;gui.updateRock(sample);
            SCMiner::RockContents contents;contents.whole=true;contents.parts={{"Gold",false,10,1000},{"Gold",false,20,350},{"",true,70,0}};gui.setRockContents(contents);
            const auto captured=read(std::filesystem::u8path(directory)/"mining_frame_model.json");
            if(!field(captured,"parts").items.empty()) {
                sample.mass=(float)captured.numberOr("mass");sample.scu=(float)captured.numberOr("scu");sample.ore=captured.textOr("ore");
                sample.resistance=(float)captured.numberOr("resistance");sample.instability=(float)captured.numberOr("instability");
                gui.setCurrentSystem(captured.textOr("system"));
                gui.updateRock(sample);contents.parts.clear();contents.whole=flag(captured,"whole");contents.partial=flag(captured,"partial");contents.sum=0;
                for(const auto& p:field(captured,"parts").items)contents.parts.push_back({p.textOr("ore"),p.textOr("ore").empty(),(float)p.numberOr("percent"),(int)p.numberOr("quality")});
                for(const auto& p:contents.parts)contents.sum+=p.percent;
                gui.setRockContents(contents);
            }
            auto value=prices->estimate(sample.scu,contents,captured.textOr("system","Stanton"),2,(long long)epoch());
            result.members.push_back({tab==13?"rock_price_live_payloads":"rock_price_full_layout",boolean(loaded&&value.rawKnown&&value.refinedKnown&&(!field(captured,"parts").items.empty()||value.playerCoverage>0))});
            for(int frame=0;frame<8;frame++){gui.processMessages();InvalidateRect(gui.windowHandle(),nullptr,FALSE);UpdateWindow(gui.windowHandle());Sleep(20);}
            target=gui.windowHandle();
        }
        else{workspace(tab);target=panel;if(tab==0){
            int shipType=int(SendMessageW(kind,CB_FINDSTRINGEXACT,-1,(LPARAM)L"Ship"));SendMessageW(kind,CB_SETCURSEL,shipType,0);updateDirectoryCategories();
            bool scoped=true;int categories=int(SendMessageW(category,CB_GETCOUNT,0,0));
            for(int i=1;i<categories;i++){wchar_t label[512]{};SendMessageW(category,CB_GETLBTEXT,i,(LPARAM)label);bool found=false;for(const auto& row:field(library,"rows").items)if(row.textOr("kind")=="Ship"&&wide(row.textOr("category"))==label)found=true;scoped=scoped&&found;}
            result.members.push_back({"finder_categories_scoped_to_type",boolean(scoped&&shipType>=0)});
            result.members.push_back({"finder_redundant_actions_removed",boolean(!GetDlgItem(panel,211)&&!GetDlgItem(panel,228))});
            SetWindowTextW(search,wide(read(std::filesystem::u8path(directory)/"finder_test_model.json").textOr("query","Arrow")).c_str());listRows();if(!visible.empty()){ListView_SetItemState(listing,0,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);selection();}
        }if(tab==2){timelineColumns=Header_GetItemCount(ListView_GetHeader(listing));timelineRows=ListView_GetItemCount(listing);SendMessageW(panel,WM_COMMAND,222,0);sessionRoute=read(data/L"workspace_command.json").textOr("action")=="session_view";}}
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
    showHud(true);bool shown=IsWindowVisible(gui.windowHandle())!=FALSE;
    showHud(false);bool hidden=IsWindowVisible(gui.windowHandle())==FALSE;
    SendMessageW(host,WM_HOTKEY,HOTKEY,0);
    bool hotkeyIgnored=!IsWindowVisible(gui.windowHandle())&&!hotkeyOK;
    result.members.push_back({"mouse_visibility_route",boolean(shown&&hidden)});
    result.members.push_back({"hotkey_messages_ignored",boolean(hotkeyIgnored)});
    // Hidden-window integration fixture: repeated ready notifications must not
    // hide/show the mounted page; navigation must retain redraw suppression.
    WNDCLASSW transitionClass{};transitionClass.hInstance=GetModuleHandleW(nullptr);transitionClass.lpszClassName=L"SynthPageTransitionFixture";
    transitionClass.lpfnWndProc=[](HWND h,UINT m,WPARAM w,LPARAM l)->LRESULT{if(m==WM_SHOWWINDOW)SetWindowLongPtrW(h,GWLP_USERDATA,GetWindowLongPtrW(h,GWLP_USERDATA)+1);return DefWindowProcW(h,m,w,l);};RegisterClassW(&transitionClass);
    HWND fixtureRoot=CreateWindowW(transitionClass.lpszClassName,L"",WS_POPUP,-32000,-32000,640,480,nullptr,nullptr,transitionClass.hInstance,nullptr);
    SynthPages::initialize(fixtureRoot);SynthPages::place(0,0,640,480,true);
    HWND first=CreateWindowW(transitionClass.lpszClassName,L"",WS_POPUP,0,0,640,480,nullptr,nullptr,transitionClass.hInstance,nullptr);
    HWND second=CreateWindowW(transitionClass.lpszClassName,L"",WS_POPUP,0,0,640,480,nullptr,nullptr,transitionClass.hInstance,nullptr);
    SynthPages::mount(first);auto shows=GetWindowLongPtrW(first,GWLP_USERDATA);SynthPages::mount(first);
    bool stable=GetWindowLongPtrW(first,GWLP_USERDATA)==shows;
    auto oldGeneration=SynthPages::generation();SynthPages::hide();SynthPages::mount(first);
    SendMessageW(SynthPages::host(),WM_APP+417,(WPARAM)first,oldGeneration);
    bool lateReady=(GetWindowLongPtrW(first,GWL_STYLE)&WS_VISIBLE)!=0&&SynthPages::current()==first;
    result.members.push_back({"stale_page_ready_cannot_hide_reused_page",boolean(lateReady)});
    SynthPages::beginTransition();SynthPages::mount(second);SynthPages::place(0,0,600,440,true);
    bool held=(GetWindowLongPtrW(SynthPages::host(),GWL_STYLE)&WS_VISIBLE)==0;
    SynthPages::endTransition();bool committed=(GetWindowLongPtrW(SynthPages::host(),GWL_STYLE)&WS_VISIBLE)!=0&&SynthPages::current()==second&&GetParent(second)==SynthPages::host();
    result.members.push_back({"page_ready_mount_is_idempotent",boolean(stable)});result.members.push_back({"page_transition_holds_redraw_until_ready",boolean(held&&committed)});
    SynthPages::close();DestroyWindow(first);DestroyWindow(second);DestroyWindow(fixtureRoot);
    write(std::filesystem::u8path(directory)/"ui_test.json",result);shutdown();return field(library,"rows").items.empty()||!persisted||!shown||!hidden||!hotkeyIgnored?3:0;
}
}
