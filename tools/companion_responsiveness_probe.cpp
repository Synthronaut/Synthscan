// Standalone synthetic UI regression test. No app startup, capture, game input,
// network service or personal profile. An external runner enforces a timeout.
#include "../native/synthscan/src/SynthCompanion.cpp"
#include "SynthHome.h"
#include "AppPaths.h"
#include <thread>
#include <atomic>
#include <iostream>

namespace {
unsigned long paints=0,sizes=0,commands=0;
std::atomic<unsigned> callCount=0;std::atomic<unsigned long long> recent[32]{};
LRESULT CALLBACK countMessages(int code,WPARAM wp,LPARAM lp){
    if(code>=0){auto p=reinterpret_cast<CWPSTRUCT*>(lp);unsigned at=callCount++;recent[at%32]=(static_cast<unsigned long long>(unsigned(GetDlgCtrlID(p->hwnd)))<<32)|p->message;if(p->message==WM_PAINT)++paints;if(p->message==WM_SIZE)++sizes;if(p->message==WM_COMMAND)++commands;}
    return CallNextHookEx(nullptr,code,wp,lp);
}
}
int wmain(int argc,wchar_t** argv){
    if(argc<2)return 2;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    bool composited=argc>2&&std::wstring(argv[2])==L"--composited";
    // Hard stop even if a native message handler never returns.
    std::thread([](){Sleep(20000);unsigned n=callCount.load();std::cerr<<"HARD TIMEOUT messages="<<n<<std::endl;for(unsigned i=n>32?n-32:0;i<n;i++){auto entry=recent[i%32].load();std::cerr<<"id="<<(entry>>32)<<" message="<<(entry&0xffffffff)<<std::endl;}ExitProcess(124);}).detach();
    // Render genuine visible HWNDs on an unshown desktop. The player's desktop
    // is never switched, covered, captured or sent input.
    auto desktopName=L"SynthScanFixture-"+std::to_wstring(GetCurrentProcessId());
    HDESK desktop=CreateDesktopW(desktopName.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);
    if(!desktop||!SetThreadDesktop(desktop))return 5;
    using namespace SynthScan;
    SynthCompanion::inPreview=true;
    std::filesystem::path output=argv[1];std::filesystem::create_directories(output);
    SCMiner::AppPaths::useDataFolder(output);
    if(argc>2&&std::wstring(argv[2])==L"--preview")return SynthCompanion::preview(output);
    auto trace=[&](const char* phase){std::ofstream f(output/L"phase.txt");f<<phase<<" paints="<<paints<<" sizes="<<sizes<<" commands="<<commands;f.flush();};
    trace("desktop-ready");
    if(!SynthCompanion::chosen().empty()||!SynthCompanion::actionSelection().items.empty())return 7;
    Json rows=arr();for(int i=0;i<400;i++)rows.items.push_back(obj({{"id",str("synthetic-"+std::to_string(i))},{"handle",str("Fixture pilot "+std::to_string(i))},{"tag",str(i%2?"Friendly, Trader":"")},{"on_shard",SynthScan::boolean(true)}}));
    Json state=obj({{"owner_pid",num(GetCurrentProcessId())},{"written_at",num(SynthCompanion::now())},{"session_token",str("fixture-only")},{"rows",rows},{"action_people",arr()},{"friends_known",SynthScan::boolean(true)},{"party_known",SynthScan::boolean(true)},{"tag_options",arr()},{"roster_at",num(SynthCompanion::now())}});
    write(output/L"companion_state.json",state);
    INITCOMMONCONTROLSEX cc{sizeof(cc),ICC_LISTVIEW_CLASSES|ICC_STANDARD_CLASSES};InitCommonControlsEx(&cc);
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;Gdiplus::GdiplusStartup(&token,&input,nullptr);
    trace("gdi-ready");
    HWND before=GetForegroundWindow();
    WNDCLASSW hostClass{};hostClass.hInstance=GetModuleHandleW(nullptr);hostClass.lpfnWndProc=DefWindowProcW;hostClass.lpszClassName=L"FixtureRoot";RegisterClassW(&hostClass);
    HWND host=CreateWindowExW(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW|(composited?WS_EX_COMPOSITED:0),hostClass.lpszClassName,L"Offscreen synthetic responsiveness fixture",WS_POPUP,0,0,1200,900,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    if(!host){std::cerr<<"host failed "<<GetLastError()<<std::endl;return 6;}
    auto hook=SetWindowsHookExW(WH_CALLWNDPROC,countMessages,nullptr,GetCurrentThreadId());
    trace("host-ready");
    SynthHome::initialize(host,output,[&](const std::string& destination){if(destination=="people"||destination=="buyer_alerts")SynthCompanion::show(SynthHome::pageHost(),output,destination);});
    HWND workspace=GetParent(SynthHome::pageHost());
    if(!workspace)return 8;
    bool treeComposited=(GetWindowLongPtrW(workspace,GWL_EXSTYLE)&WS_EX_COMPOSITED)!=0;
    if(!composited&&treeComposited)return 9;
    if(composited)SetWindowLongPtrW(workspace,GWL_EXSTYLE,GetWindowLongPtrW(workspace,GWL_EXSTYLE)|WS_EX_COMPOSITED);
    SetWindowPos(workspace,nullptr,0,0,1200,900,SWP_NOZORDER|SWP_NOACTIVATE);
    ShowWindow(workspace,SW_SHOWNOACTIVATE);SynthHome::navigate("people");trace("workspace-ready");
    ULONGLONG start=GetTickCount64(),nextBeat=start;unsigned beats=0,messages=0;ULONGLONG maxDispatch=0;
    while(GetTickCount64()-start<8000){
        MSG msg{};
        if(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){
            auto t=GetTickCount64();if(!SynthHome::routeMessage(msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}maxDispatch=std::max(maxDispatch,GetTickCount64()-t);++messages;
        }else Sleep(1);
        if(GetTickCount64()>=nextBeat){
            for(auto& entry:state.members)if(entry.first=="written_at")entry.second=num(SynthCompanion::now());
            write(output/L"companion_state.json",state);SendMessageW(SynthCompanion::page,WM_TIMER,1,0);++beats;
            if(beats%4==2)SynthHome::navigate("buyer_alerts");
            if(beats%4==3)SynthHome::navigate("people");
            if(beats%4==0)SynthHome::navigate("home");
            if(beats%4==1)SynthHome::navigate("people");
            SetWindowPos(workspace,nullptr,0,0,beats%2?1200:1100,beats%2?900:820,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE);
            nextBeat+=500;
        }
        if(messages>10000||paints>10000)break;
    }
    auto report=obj({{"elapsed_ms",num(double(GetTickCount64()-start))},{"messages",num(messages)},{"paints",num(paints)},{"sizes",num(sizes)},{"commands",num(commands)},{"heartbeats",num(beats)},{"max_dispatch_ms",num(double(maxDispatch))},{"foreground_unchanged",SynthScan::boolean(GetForegroundWindow()==before)},{"gdi_objects",num(GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS))}});
    write(output/L"responsiveness.json",report);std::cout<<encode(report)<<std::endl;
    UnhookWindowsHookEx(hook);SynthCompanion::close();bool closedSelectionSafe=SynthCompanion::chosen().empty()&&SynthCompanion::actionSelection().items.empty();SynthHome::close();DestroyWindow(host);Gdiplus::GdiplusShutdown(token);
    return closedSelectionSafe&&GetForegroundWindow()==before&&beats>=8&&paints<1000&&messages<3000&&maxDispatch<500?0:3;
}
