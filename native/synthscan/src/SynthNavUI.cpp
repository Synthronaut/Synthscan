// Explicitly armed field test. No game keystrokes, hidden GPS or autopilot.
#define UNICODE
#define _UNICODE
#include "SynthNavUI.h"
#include <commdlg.h>
#include <dwmapi.h>
#include <uxtheme.h>
#include <sstream>
#include <iomanip>
using namespace SynthScan;
namespace SynthScanNav {
namespace {
HWND parent=nullptr,win=nullptr;HFONT font=nullptr,title=nullptr;HBRUSH bg=nullptr,input=nullptr;
Json model;std::function<void(Json)> send;bool testing=false,busy=false;double scale=1;
std::string bodyKey,markKey;
constexpr COLORREF BG=RGB(20,23,29),CARD=RGB(29,33,41),TEXT=RGB(233,237,241),GOLD=RGB(218,160,79);
int px(int n){return int(n*scale+.5);}
std::string text(int id){HWND h=GetDlgItem(win,id);int n=GetWindowTextLengthW(h);std::wstring s(n+1,0);GetWindowTextW(h,s.data(),n+1);s.resize(n);return utf8(s);}
void label(int id,std::string s){std::wstring w;for(auto c:wide(s)){if(c==L'\n')w+=L'\r';w+=c;}SetDlgItemTextW(win,id,w.c_str());}
HWND ctl(const wchar_t* cls,const wchar_t* text,DWORD style,int x,int y,int w,int h,int id){
 if(std::wstring(cls)==L"BUTTON")style|=BS_OWNERDRAW;
 HWND c=CreateWindowExW(std::wstring(cls)==L"EDIT"?WS_EX_CLIENTEDGE:0,cls,text,WS_CHILD|WS_VISIBLE|WS_TABSTOP|style,px(x),px(y),px(w),px(h),win,(HMENU)INT_PTR(id),GetModuleHandleW(nullptr),nullptr);
 SetWindowTheme(c,L"DarkMode_Explorer",nullptr);SendMessageW(c,WM_SETFONT,(WPARAM)font,TRUE);return c;
}
bool pathDialog(bool save,std::wstring& path){
 wchar_t name[32768]=L"SynthScan rock bookmark.json";OPENFILENAMEW f{sizeof(f)};f.hwndOwner=win;f.lpstrFile=name;f.nMaxFile=32768;f.lpstrDefExt=L"json";f.lpstrFilter=L"Rock bookmark\0*.json\0";f.Flags=OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST|(save?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);
 bool ok=save?GetSaveFileNameW(&f)!=FALSE:GetOpenFileNameW(&f)!=FALSE;if(ok)path=name;return ok;
}
void act(int id){
 if(id>=710&&id<=712){int i=int(SendDlgItemMessageW(win,701,CB_GETCURSEL,0,0));const auto& bodies=field(model,"bodies").items;
  if(i<0||i>=int(bodies.size()))return;
  send(obj({{"action",str("nav_arm")},{"body_id",field(bodies[i],"id")},{"role",str(id==710?"mark":id==711?"check":"current")},{"name",str(text(702))},{"stand_off_m",str(text(703))}}));return;}
 if(id==713){send(obj({{"action",str("nav_cancel")}}));return;}
 if(id==714||id==715){std::wstring path;if(!testing&&pathDialog(id==714,path))send(obj({{"action",str(id==714?"nav_export":"nav_import")},{"path",str(utf8(path))}}));return;}
 if(id==716){if(testing||MessageBoxW(win,L"Delete the selected bookmark?",L"Delete bookmark",MB_YESNO|MB_ICONQUESTION)==IDYES)send(obj({{"action",str("nav_delete")}}));return;}
}
LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
 if(m==WM_DRAWITEM){auto d=(DRAWITEMSTRUCT*)l;RECT r=d->rcItem;FillRect(d->hDC,&r,input);SetBkMode(d->hDC,TRANSPARENT);SetTextColor(d->hDC,(d->itemState&ODS_DISABLED)?RGB(120,128,138):TEXT);SelectObject(d->hDC,font);wchar_t caption[200]{};GetWindowTextW(d->hwndItem,caption,200);DrawTextW(d->hDC,caption,-1,&r,DT_CENTER|DT_VCENTER|DT_SINGLELINE);if(d->itemState&ODS_FOCUS){InflateRect(&r,-3,-3);DrawFocusRect(d->hDC,&r);}return TRUE;}
 if(m==WM_CLOSE){ShowWindow(h,SW_HIDE);return 0;}
 if(m==WM_COMMAND){int id=LOWORD(w);if(id==704&&HIWORD(w)==LBN_SELCHANGE&&!busy){int i=int(SendDlgItemMessageW(h,704,LB_GETCURSEL,0,0));const auto& marks=field(model,"marks").items;if(i>=0&&i<int(marks.size()))send(obj({{"action",str("nav_select")},{"bookmark_id",field(marks[i],"id")}}));}else if(HIWORD(w)==BN_CLICKED)act(id);return 0;}
 if(m==WM_CTLCOLORSTATIC||m==WM_CTLCOLOREDIT||m==WM_CTLCOLORLISTBOX){SetTextColor((HDC)w,TEXT);SetBkColor((HDC)w,m==WM_CTLCOLORSTATIC?BG:CARD);return (LRESULT)(m==WM_CTLCOLORSTATIC?bg:input);}
 if(m==WM_ERASEBKGND)return TRUE;
 if(m==WM_PAINT){PAINTSTRUCT ps;HDC dc=BeginPaint(h,&ps);RECT r;GetClientRect(h,&r);FillRect(dc,&r,bg);SelectObject(dc,title);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,GOLD);const wchar_t* s=L"Rock bookmarks · field test";TextOutW(dc,px(20),px(16),s,int(wcslen(s)));EndPaint(h,&ps);return 0;}
 return DefWindowProcW(h,m,w,l);
}
}
void initialize(HWND owner,bool test,std::function<void(Json)> callback){parent=owner;testing=test;send=std::move(callback);}
HWND window(){return win;}
void open(){
 if(!win){scale=GetDpiForWindow(parent)/96.;bg=CreateSolidBrush(BG);input=CreateSolidBrush(CARD);font=CreateFontW(-px(14),0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");title=CreateFontW(-px(25),0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
 WNDCLASSW c{};c.lpfnWndProc=proc;c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"SynthScanRockNavigation";c.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&c);DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;RECT r{0,0,px(900),px(660)};AdjustWindowRect(&r,style,FALSE);
 win=CreateWindowW(c.lpszClassName,L"SynthScan · Rock bookmarks",style,testing?-32000:CW_USEDEFAULT,testing?-32000:CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,parent,nullptr,c.hInstance,nullptr);BOOL dark=TRUE;DwmSetWindowAttribute(win,20,&dark,sizeof(dark));SetWindowDisplayAffinity(win,WDA_EXCLUDEFROMCAPTURE);
 ctl(L"STATIC",L"Save where you are parked. The saved point is your ship, not the scanned rock.",0,20,57,850,23,0);
 ctl(L"STATIC",L"Body / coordinate model",0,20,95,370,20,0);ctl(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,20,119,400,350,701);
 ctl(L"STATIC",L"Bookmark name",0,440,95,300,20,0);ctl(L"EDIT",L"Rock / station test",ES_AUTOHSCROLL,440,119,440,28,702);SendDlgItemMessageW(win,702,EM_SETLIMITTEXT,200,0);
 ctl(L"STATIC",L"Distance from ship to rock · meters (uncertainty)",0,20,162,460,20,0);ctl(L"EDIT",L"0",ES_AUTOHSCROLL,500,158,120,28,703);SendDlgItemMessageW(win,703,EM_SETLIMITTEXT,10,0);
 ctl(L"BUTTON",L"1  Arm new bookmark",BS_PUSHBUTTON,20,202,265,34,710);ctl(L"BUTTON",L"2  Arm stationary check",BS_PUSHBUTTON,300,202,280,34,711);ctl(L"BUTTON",L"3  Arm current fix",BS_PUSHBUTTON,595,202,285,34,712);
 ctl(L"STATIC",L"After arming, type /showlocation in game chat. For step 2, stay parked for at least 30 seconds.",0,20,250,860,35,0);
 ctl(L"LISTBOX",L"",LBS_NOTIFY|WS_VSCROLL,20,295,310,220,704);
 ctl(L"EDIT",L"Waiting for the session service…",ES_MULTILINE|ES_READONLY|WS_VSCROLL,350,295,530,220,705);
 ctl(L"BUTTON",L"Cancel capture",BS_PUSHBUTTON,20,532,180,32,713);ctl(L"BUTTON",L"Export exact location…",BS_PUSHBUTTON,215,532,230,32,714);ctl(L"BUTTON",L"Import bookmark…",BS_PUSHBUTTON,460,532,230,32,715);ctl(L"BUTTON",L"Delete",BS_PUSHBUTTON,705,532,175,32,716);
 ctl(L"STATIC",L"",0,20,579,860,65,706);
 }
 bodyKey.clear();markKey.clear();update(model);ShowWindow(win,testing?SW_SHOWNOACTIVATE:SW_SHOW);if(!testing)SetForegroundWindow(win);
}
void update(const Json& value){model=value;if(!win)return;busy=true;
 auto key=encode(field(model,"bodies"));if(key!=bodyKey){bodyKey=key;auto prior=text(701);SendDlgItemMessageW(win,701,CB_RESETCONTENT,0,0);int selected=0,i=0;for(auto& b:field(model,"bodies").items){auto s=b.textOr("system")+" · "+b.textOr("name");SendDlgItemMessageW(win,701,CB_ADDSTRING,0,(LPARAM)wide(s).c_str());if(s==prior)selected=i;i++;}SendDlgItemMessageW(win,701,CB_SETCURSEL,selected,0);}
 key=encode(field(model,"marks"))+model.textOr("selected");if(key!=markKey){markKey=key;SendDlgItemMessageW(win,704,LB_RESETCONTENT,0,0);int i=0;for(auto& m:field(model,"marks").items){auto s=wide(m.textOr("name")+" · "+m.textOr("body_id"));SendDlgItemMessageW(win,704,LB_ADDSTRING,0,(LPARAM)s.c_str());if(m.textOr("id")==model.textOr("selected")){SendDlgItemMessageW(win,704,LB_SETCURSEL,i,0);int j=0;for(auto& b:field(model,"bodies").items){if(b.textOr("id")==m.textOr("body_id"))SendDlgItemMessageW(win,701,CB_SETCURSEL,j,0);j++;}}i++;}}
 std::ostringstream s;s<<std::fixed<<std::setprecision(1);const Json* selected=nullptr;for(auto& m:field(model,"marks").items)if(m.textOr("id")==model.textOr("selected"))selected=&m;
 if(selected){s<<selected->textOr("name")<<"\n"<<selected->textOr("body_id")<<"\nShard: "<<field(*selected,"fix").textOr("full_shard_id")<<"\nShip-to-rock uncertainty: "<<selected->numberOr("stand_off_m")<<" m\n";const auto& check=field(*selected,"rotation_check");if(check.kind==Json::Kind::Object)s<<"Stationary error: "<<check.numberOr("error_m")<<" m\n";}
 const auto& g=field(model,"guidance");if(!g.textOr("unavailable").empty())s<<"\n"<<g.textOr("unavailable");else if(g.kind==Json::Kind::Object){s<<"\nRange: "<<g.numberOr("distance_m")<<" m · fix age "<<g.numberOr("fix_age_s")<<" s\n";if(field(g,"bearing_deg").kind==Json::Kind::Number)s<<"Bearing: "<<g.numberOr("bearing_deg")<<"°\nHeight difference: "<<g.numberOr("target_height_delta_m")<<" m\n";s<<g.textOr("status");}
 if(!selected)s<<"Choose a model and arm a new bookmark.\n\nSpace tests measure range only; no cockpit bearing.\nSurface models use a community reference and require a stationary check.\n\nFresh fixes expire after 15 seconds. No continuous position feed or automatic quantum route yet.";
 label(705,s.str());label(706,model.textOr("message","Session service starting…"));busy=false;
}
void close(){if(win)DestroyWindow(win);win=nullptr;if(font)DeleteObject(font);if(title)DeleteObject(title);if(bg)DeleteObject(bg);if(input)DeleteObject(input);}
}
