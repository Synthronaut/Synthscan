// Native diary editor and local share preview. No browser, account or upload.
#define UNICODE
#define _UNICODE
#include "SynthDiaryUI.h"
#include <commctrl.h>
#include <commdlg.h>
#include <dwmapi.h>
#include <uxtheme.h>
#include <gdiplus.h>
#include <map>
#include <memory>
#include <sstream>
#include <set>
using namespace SynthScan;
namespace SynthScanDiary {
namespace {
HWND parent=nullptr,win=nullptr,list=nullptr,status=nullptr,description=nullptr,preview=nullptr;
HFONT body=nullptr,heading=nullptr;HBRUSH bg=nullptr,card=nullptr;
std::filesystem::path directory;
std::function<void(Json)> send;
Json model,current;std::vector<Json> rows;
std::map<std::string,HWND> edits;
std::unique_ptr<Gdiplus::Bitmap> picture;
bool testing=false,busy=false,dirty=false,pendingSave=false,pendingShare=false;
double scale=1;int offset=0;std::string lastRows,lastOptions,lastResult;
const char* types[]={"scanned","mined","haul","refined","sale","trip"};
const wchar_t* labels[]={L"Rock scanned",L"Rock mined · confirmed",L"Collected haul · confirmed",L"Refined output · confirmed",L"Completed sale · confirmed",L"Trip / memory"};
constexpr COLORREF BG=RGB(20,23,29),CARD=RGB(29,33,41),TEXT=RGB(233,237,241),GOLD=RGB(218,160,79),MUTED=RGB(149,160,173);
int px(int n){return int(n*scale+.5);}
std::wstring text(HWND h){int n=GetWindowTextLengthW(h);std::wstring s(n+1,0);GetWindowTextW(h,s.data(),n+1);s.resize(n);return s;}
std::wstring lines(std::string s){std::wstring out;for(auto c:wide(s)){if(c==L'\n'&&(out.empty()||out.back()!=L'\r'))out+=L'\r';out+=c;}return out;}
HWND ctl(const wchar_t* cls,const wchar_t* label,DWORD style,int x,int y,int w,int h,int id){
    if(std::wstring(cls)==L"BUTTON"&&(style&15)==BS_PUSHBUTTON)style|=BS_OWNERDRAW;
    HWND c=CreateWindowExW(std::wstring(cls)==L"EDIT"?WS_EX_CLIENTEDGE:0,cls,label,WS_CHILD|WS_VISIBLE|WS_TABSTOP|style,px(x),px(y),px(w),px(h),win,(HMENU)INT_PTR(id),GetModuleHandleW(nullptr),nullptr);
    SetWindowTheme(c,L"DarkMode_Explorer",nullptr);SendMessageW(c,WM_SETFONT,(WPARAM)body,TRUE);return c;
}
void message(const std::string& value){if(status)SetWindowTextW(status,wide(value).c_str());}
HWND edit(const char* name,const wchar_t* label,int x,int y,int w,int id,bool multi=false){
    ctl(L"STATIC",label,SS_LEFT,x,y-20,w,18,0);
    HWND h=ctl(L"EDIT",L"",multi?(ES_MULTILINE|ES_AUTOVSCROLL|WS_VSCROLL):ES_AUTOHSCROLL,x,y,w,multi?100:28,id);
    edits[name]=h;SendMessageW(h,EM_SETLIMITTEXT,std::string(name)=="notes"?5000:500,0);return h;
}
bool discard(){return !dirty||testing||MessageBoxW(win,L"Discard the unsaved edits to this diary entry?",L"Unsaved diary entry",MB_YESNO|MB_ICONQUESTION)==IDYES;}
void fill(const Json& entry){
    busy=true;current=entry;
    for(auto& pair:edits){const auto& value=field(entry,pair.first.c_str());std::string s=value.kind==Json::Kind::Number?encode(value):value.text;SetWindowTextW(pair.second,lines(s).c_str());}
    int kind=0;for(int i=0;i<6;i++)if(entry.textOr("kind")==types[i])kind=i;SendDlgItemMessageW(win,430,CB_SETCURSEL,kind,0);
    if(entry.textOr("id").empty()){
        SYSTEMTIME t;GetSystemTime(&t);wchar_t date[40];swprintf_s(date,L"%04d-%02d-%02dT%02d:%02d:%02dZ",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond);SetWindowTextW(edits["occurred_at"],date);
    }
    std::string provenance=entry.textOr("source")+"\n"+entry.textOr("identity")+"\n"+entry.textOr("location_source");
    for(auto& p:field(entry,"parts").items)provenance+="\n"+encode(field(p,"percent"))+"% "+p.textOr("material","Inert")+" · Q"+encode(field(p,"quality"));
    provenance+="\nSave a correction or choose an outcome you can confirm.";
    SetWindowTextW(description,lines(entry.textOr("id").empty()?"New memory. Rock entries use kg; hauls use SCU.\nConfirmed outcomes are entered by you, never inferred from a scan.":provenance).c_str());
    dirty=false;busy=false;
}
Json shareOptions(){return obj({{"name",str(utf8(text(GetDlgItem(win,450))))},{"location",SynthScan::boolean(IsDlgButtonChecked(win,451)==BST_CHECKED)},
    {"crew",SynthScan::boolean(IsDlgButtonChecked(win,452)==BST_CHECKED)},{"notes",SynthScan::boolean(IsDlgButtonChecked(win,453)==BST_CHECKED)},
    {"value",SynthScan::boolean(IsDlgButtonChecked(win,454)==BST_CHECKED)},{"screenshot",SynthScan::boolean(IsDlgButtonChecked(win,455)==BST_CHECKED)}});}
void filters(int page=0){offset=page;send(obj({{"action",str("diary_view")},{"query",str(utf8(text(GetDlgItem(win,401))))},
    {"system",str(SendDlgItemMessageW(win,402,CB_GETCURSEL,0,0)>0?utf8(text(GetDlgItem(win,402))):"")},
    {"patch",str(SendDlgItemMessageW(win,403,CB_GETCURSEL,0,0)>0?utf8(text(GetDlgItem(win,403))):"")},
    {"mode",str(utf8(text(GetDlgItem(win,404))))},{"offset",num(offset)}}));message("Loading diary…");}
bool fileDialog(bool saving,std::wstring& path,bool asText=false){
    wchar_t name[32768]{};if(saving)wcscpy_s(name,asText?L"SynthScan mining memory.txt":L"SynthScan mining memory.png");
    OPENFILENAMEW f{sizeof(f)};f.hwndOwner=win;f.lpstrFile=name;f.nMaxFile=32768;f.lpstrDefExt=saving?(asText?L"txt":L"png"):nullptr;
    f.lpstrFilter=saving?(asText?L"Text summary\0*.txt\0":L"PNG share card\0*.png\0"):L"Screenshot images\0*.png;*.jpg;*.jpeg;*.bmp\0";
    f.Flags=OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST|(saving?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);
    bool result=saving?GetSaveFileNameW(&f)!=FALSE:GetOpenFileNameW(&f)!=FALSE;if(result)path=name;return result;
}
void act(int id){
    if(id==405){filters();return;}if(id==406){filters(std::max(0,offset-200));return;}if(id==407){if(offset+200<model.numberOr("count"))filters(offset+200);return;}
    if(id>=470&&id<476){const auto& records=field(model,"records").items;if(id-470<int(records.size())&&!field(records[id-470],"entry").textOr("id").empty()&&discard())fill(field(records[id-470],"entry"));return;}
    if(id==408){if(discard())fill(obj());return;}
    if(id==409){
        if(dirty){message("Save or discard edits before merging scans.");return;}Json ids=arr();int i=-1;while((i=ListView_GetNextItem(list,i,LVNI_SELECTED))>=0)if(i<int(rows.size()))ids.items.push_back(field(rows[i],"id"));
        if(ids.items.size()<2){message("Ctrl-click two or more scan entries, then Merge scans.");return;}
        send(obj({{"action",str("diary_merge")},{"entry_ids",ids}}));pendingSave=true;return;
    }
    if(id==410){if(current.textOr("id").empty())return;if(!testing&&MessageBoxW(win,L"Delete this diary entry? It will also leave your personal records.",L"Delete memory",MB_YESNO|MB_ICONQUESTION)!=IDYES)return;send(obj({{"action",str("diary_delete")},{"entry_id",field(current,"id")}}));fill(obj());return;}
    if(id==440){
        if(pendingSave){message("A diary save is still being processed.");return;}Json e=obj();if(!current.textOr("id").empty())e.members.push_back({"id",field(current,"id")});
        int kind=int(SendDlgItemMessageW(win,430,CB_GETCURSEL,0,0));e.members.push_back({"kind",str(types[kind>=0&&kind<6?kind:0])});
        for(auto& pair:edits)e.members.push_back({pair.first,str(utf8(text(pair.second)))});
        pendingSave=true;send(obj({{"action",str("diary_save")},{"entry",e}}));message("Saving memory…");return;
    }
    if(id==441){if(testing)return;std::wstring path;if(fileDialog(false,path)){SetWindowTextW(edits["screenshot"],path.c_str());dirty=true;}return;}
    if(id==456||id==457||id==459){
        if(dirty||current.textOr("id").empty()){message("Save the entry before sharing it.");return;}if(pendingShare){message("A share card is being prepared.");return;}
        std::wstring path;if(id!=456&&(testing||!fileDialog(true,path,id==459)))return;
        pendingShare=true;Json c=obj({{"action",str("diary_share")},{"entry_id",field(current,"id")},{"options",shareOptions()}});
        if(!path.empty())c.members.push_back({"destination",str(utf8(path))});send(c);message("Preparing local share preview…");return;
    }
    if(id==458){std::error_code e;write(directory/L"diary_settings.json",obj({{"auto_log",SynthScan::boolean(IsDlgButtonChecked(win,458)==BST_CHECKED)}}));message("Automatic scan logging setting saved.");}
}
LRESULT CALLBACK previewProc(HWND h,UINT m,WPARAM w,LPARAM l){
    if(m==WM_ERASEBKGND)return TRUE;
    if(m==WM_CLOSE){ShowWindow(h,SW_HIDE);return 0;}
    if(m==WM_PAINT||m==WM_PRINTCLIENT||m==WM_PRINT){PAINTSTRUCT ps{};HDC dc=m==WM_PAINT?BeginPaint(h,&ps):(HDC)w;RECT r;GetClientRect(h,&r);FillRect(dc,&r,bg);
        if(picture&&picture->GetLastStatus()==Gdiplus::Ok){float s=std::min(float(r.right-30)/picture->GetWidth(),float(r.bottom-30)/picture->GetHeight());Gdiplus::Graphics g(dc);g.SetInterpolationMode(Gdiplus::InterpolationModeHighQualityBicubic);float width=picture->GetWidth()*s,height=picture->GetHeight()*s;g.DrawImage(picture.get(),(r.right-width)/2,(r.bottom-height)/2,width,height);}if(m==WM_PAINT)EndPaint(h,&ps);return 0;}
    return DefWindowProcW(h,m,w,l);
}
void showPreview(const std::string& path){
    // A file-backed GDI+ bitmap locks the PNG for its lifetime. Copy pixels
    // into memory so the next card can replace preview.png while this is open.
    {Gdiplus::Bitmap source(wide(path).c_str());if(source.GetLastStatus()!=Gdiplus::Ok){message("Could not load the share preview.");return;}
    picture=std::make_unique<Gdiplus::Bitmap>(source.GetWidth(),source.GetHeight(),PixelFormat32bppARGB);Gdiplus::Graphics copy(picture.get());copy.DrawImage(&source,0,0,source.GetWidth(),source.GetHeight());}
    if(!preview){WNDCLASSW c{};c.lpfnWndProc=previewProc;c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"SynthScanDiaryPreview";c.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&c);preview=CreateWindowW(c.lpszClassName,L"SynthScan share preview · local only · nothing uploaded",WS_OVERLAPPEDWINDOW,testing?-32000:CW_USEDEFAULT,testing?-32000:CW_USEDEFAULT,px(800),px(740),win,nullptr,c.hInstance,nullptr);BOOL dark=TRUE;DwmSetWindowAttribute(preview,20,&dark,sizeof(dark));}
    InvalidateRect(preview,nullptr,FALSE);ShowWindow(preview,testing?SW_SHOWNOACTIVATE:SW_SHOW);if(!testing)SetForegroundWindow(preview);
}
LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
    switch(m){
    case WM_CLOSE:if(discard()){fill(current);ShowWindow(h,SW_HIDE);}return 0;
    case WM_COMMAND:{int id=LOWORD(w),code=HIWORD(w);if(!busy&&((id>=420&&id<=439&&code==EN_CHANGE)||(id==430&&code==CBN_SELCHANGE)))dirty=true;act(id);return 0;}
    case WM_NOTIFY:{auto n=reinterpret_cast<NMHDR*>(l);if(n->hwndFrom==list&&n->code==LVN_ITEMCHANGED&&!busy){int i=ListView_GetNextItem(list,-1,LVNI_SELECTED);if(i>=0&&i<int(rows.size())&&!dirty)fill(field(rows[i],"entry"));else if(dirty)message("Unsaved edits: Save entry, or New entry to discard them.");}if(n->hwndFrom==list&&n->code==NM_CUSTOMDRAW){auto d=(NMLVCUSTOMDRAW*)l;if(d->nmcd.dwDrawStage==CDDS_PREPAINT)return CDRF_NOTIFYITEMDRAW;if(d->nmcd.dwDrawStage==CDDS_ITEMPREPAINT){bool chosen=(ListView_GetItemState(list,int(d->nmcd.dwItemSpec),LVIS_SELECTED)&LVIS_SELECTED)!=0;d->clrText=TEXT;d->clrTextBk=chosen?RGB(76,58,32):CARD;d->nmcd.uItemState&=~CDIS_SELECTED;return CDRF_NEWFONT;}}return 0;}
    case WM_DRAWITEM:{auto item=reinterpret_cast<DRAWITEMSTRUCT*>(l);if(item->CtlType!=ODT_BUTTON)break;RECT r=item->rcItem;FillRect(item->hDC,&r,card);SetBkMode(item->hDC,TRANSPARENT);SetTextColor(item->hDC,item->CtlID>=470?GOLD:TEXT);SelectObject(item->hDC,body);InflateRect(&r,-7,-4);auto label=text(item->hwndItem);DrawTextW(item->hDC,label.c_str(),-1,&r,DT_CENTER|DT_VCENTER|DT_WORDBREAK|DT_NOPREFIX);if(item->itemState&ODS_FOCUS)DrawFocusRect(item->hDC,&r);return TRUE;}
    case WM_CTLCOLORBTN:case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:{auto dc=(HDC)w;SetTextColor(dc,TEXT);SetBkColor(dc,m==WM_CTLCOLOREDIT?CARD:BG);return (LRESULT)(m==WM_CTLCOLOREDIT?card:bg);}
    case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(h,&ps);RECT r;GetClientRect(h,&r);FillRect(dc,&r,bg);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,GOLD);SelectObject(dc,heading);const wchar_t* title=L"Mining diary & personal records";TextOutW(dc,px(20),px(17),title,int(wcslen(title)));EndPaint(h,&ps);return 0;}
    }
    return DefWindowProcW(h,m,w,l);
}
void choices(HWND c,const Json& values,const wchar_t* all){
    auto prior=text(c);SendMessageW(c,CB_RESETCONTENT,0,0);SendMessageW(c,CB_ADDSTRING,0,(LPARAM)all);
    for(auto& value:values.items){auto s=wide(value.text);SendMessageW(c,CB_ADDSTRING,0,(LPARAM)s.c_str());}
    int match=int(SendMessageW(c,CB_FINDSTRINGEXACT,-1,(LPARAM)prior.c_str()));SendMessageW(c,CB_SETCURSEL,match>=0?match:0,0);
}
LRESULT CALLBACK headerProc(HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR,DWORD_PTR){
    if(m==WM_ERASEBKGND)return TRUE;
    if(m==WM_PAINT||m==WM_PRINTCLIENT){PAINTSTRUCT ps{};HDC dc=m==WM_PAINT?BeginPaint(h,&ps):(HDC)w;RECT r;GetClientRect(h,&r);FillRect(dc,&r,card);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,MUTED);SelectObject(dc,body);
        for(int i=0;i<Header_GetItemCount(h);i++){RECT cell;Header_GetItemRect(h,i,&cell);wchar_t label[120]{};HDITEMW item{};item.mask=HDI_TEXT;item.pszText=label;item.cchTextMax=120;Header_GetItem(h,i,&item);cell.left+=px(5);DrawTextW(dc,label,-1,&cell,DT_SINGLELINE|DT_VCENTER|DT_NOPREFIX);}if(m==WM_PAINT)EndPaint(h,&ps);return 0;}
    return DefSubclassProc(h,m,w,l);
}
}
void initialize(HWND owner,const std::filesystem::path& data,bool isTesting,std::function<void(Json)> callback){parent=owner;directory=data;testing=isTesting;send=std::move(callback);}
HWND window(){return win;}
HWND previewWindow(){return preview;}
void open(){
    if(!win){
        scale=GetDpiForWindow(parent)/96.0;bg=CreateSolidBrush(BG);card=CreateSolidBrush(CARD);
        body=CreateFontW(-px(14),0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");heading=CreateFontW(-px(25),0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        WNDCLASSW c{};c.lpfnWndProc=proc;c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"SynthScanMiningDiary";c.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&c);
        RECT r{0,0,px(1100),px(810)};DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;AdjustWindowRectEx(&r,style,FALSE,0);
        win=CreateWindowW(c.lpszClassName,L"SynthScan · Mining diary",style,testing?-32000:CW_USEDEFAULT,testing?-32000:CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,parent,nullptr,c.hInstance,nullptr);
        BOOL dark=TRUE;DwmSetWindowAttribute(win,20,&dark,sizeof(dark));SetWindowDisplayAffinity(win,WDA_EXCLUDEFROMCAPTURE);
        ctl(L"STATIC",L"Your discoveries, journeys and confirmed hauls. Share a memory, not a mandatory competition.",SS_LEFT,20,55,800,20,0);
        ctl(L"BUTTON",L"Automatically log settled scans",BS_AUTOCHECKBOX,820,24,265,24,458);CheckDlgButton(win,458,flag(read(directory/L"diary_settings.json"),"auto_log",true)?BST_CHECKED:BST_UNCHECKED);
        for(int i=0;i<6;i++)ctl(L"BUTTON",L"No record yet",BS_PUSHBUTTON,20+i*178,88,166,60,470+i);
        ctl(L"EDIT",L"",ES_AUTOHSCROLL,20,166,300,28,401);SendDlgItemMessageW(win,401,EM_SETCUEBANNER,TRUE,(LPARAM)L"Search material, site, ship, notes or date");
        ctl(L"STATIC",L"Search material, site, ship, notes or date",SS_LEFT,20,148,305,18,0);
        for(int id:{402,403,404})ctl(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,id==402?334:id==403?510:668,166,id==402?162:144,230,id);
        choices(GetDlgItem(win,402),arr(),L"All systems");choices(GetDlgItem(win,403),arr(),L"All patches");
        for(auto s:{L"Recent",L"Rock mass",L"Haul SCU",L"Sale proceeds",L"Quality"})SendDlgItemMessageW(win,404,CB_ADDSTRING,0,(LPARAM)s);SendDlgItemMessageW(win,404,CB_SETCURSEL,0,0);
        ctl(L"BUTTON",L"Apply",BS_PUSHBUTTON,826,166,90,28,405);ctl(L"BUTTON",L"Previous",BS_PUSHBUTTON,928,166,75,28,406);ctl(L"BUTTON",L"Next",BS_PUSHBUTTON,1013,166,65,28,407);
        list=ctl(WC_LISTVIEWW,L"",LVS_REPORT|LVS_SHOWSELALWAYS,20,214,510,276,411);ListView_SetExtendedListViewStyle(list,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER);ListView_SetBkColor(list,CARD);ListView_SetTextBkColor(list,CARD);ListView_SetTextColor(list,TEXT);
        SetWindowSubclass(ListView_GetHeader(list),headerProc,1,0);
        for(int i=0;i<3;i++){LVCOLUMNW col{};col.mask=LVCF_TEXT|LVCF_WIDTH;col.cx=px(i==0?220:140);const wchar_t* names[]={L"Memory",L"Outcome",L"Location"};col.pszText=const_cast<wchar_t*>(names[i]);ListView_InsertColumn(list,i,&col);}
        description=ctl(L"EDIT",L"",ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL,20,502,510,95,412);
        ctl(L"BUTTON",L"New entry",BS_PUSHBUTTON,20,610,135,30,408);ctl(L"BUTTON",L"Merge scans",BS_PUSHBUTTON,168,610,175,30,409);ctl(L"BUTTON",L"Delete entry",BS_PUSHBUTTON,356,610,174,30,410);
        ctl(L"STATIC",L"Share as (optional name)",SS_LEFT,20,657,230,18,0);ctl(L"EDIT",L"",ES_AUTOHSCROLL,250,651,280,28,450);
        for(int i=0;i<5;i++){const wchar_t* names[]={L"Site",L"Crew",L"Notes",L"Sale value",L"Screenshot"};ctl(L"BUTTON",names[i],BS_AUTOCHECKBOX,20+i*104,692,104,25,451+i);}
        ctl(L"BUTTON",L"Preview card",BS_PUSHBUTTON,20,742,160,32,456);ctl(L"BUTTON",L"Save PNG…",BS_PUSHBUTTON,194,742,160,32,457);ctl(L"BUTTON",L"Save text…",BS_PUSHBUTTON,368,742,162,32,459);
        edit("title",L"Memory title",550,233,528,420);ctl(L"STATIC",L"Outcome",SS_LEFT,550,270,240,18,0);ctl(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_VSCROLL,550,290,240,220,430);
        for(auto label:labels)SendDlgItemMessageW(win,430,CB_ADDSTRING,0,(LPARAM)label);
        edit("occurred_at",L"Date/time · ISO with timezone",806,290,272,421);
        edit("material",L"Material / main ore",550,345,246,422);edit("mass_kg",L"Rock mass · kg",812,345,126,423);edit("quality",L"Quality · 0–1000",952,345,126,424);
        edit("system",L"System",550,400,246,425);edit("location",L"Moon / belt / site",812,400,266,426);
        edit("ship",L"Ship",550,455,246,427);edit("patch",L"Game patch",812,455,266,428);
        edit("scu",L"Haul / output · SCU",550,510,246,429);edit("proceeds",L"Confirmed sale · aUEC",812,510,266,431);
        edit("crew",L"Crew / shared haul credit",550,565,528,432);edit("notes",L"Your story",550,620,528,433,true);
        ctl(L"BUTTON",L"Choose screenshot…",BS_PUSHBUTTON,550,732,180,28,441);edits["screenshot"]=ctl(L"EDIT",L"",ES_AUTOHSCROLL|ES_READONLY,742,732,336,28,434);
        ctl(L"BUTTON",L"Save entry",BS_PUSHBUTTON,550,770,528,30,440);
        status=ctl(L"STATIC",L"Local diary. Share exports never upload anything.",SS_LEFT,20,782,510,22,0);
        ctl(L"STATIC",L"",SS_LEFT,20,196,510,17,413);
        fill(obj());
    }
    lastRows.clear();lastOptions.clear();update(model,obj(),"");
    if(testing)ShowWindow(win,SW_SHOWNOACTIVATE);else{ShowWindow(win,SW_SHOW);SetForegroundWindow(win);filters();}
}
void update(const Json& value,const Json& result,const std::string& note){
    model=value;if(!win)return;
    busy=true;
    std::string options=encode(field(model,"systems"))+encode(field(model,"patches"));if(options!=lastOptions){lastOptions=options;choices(GetDlgItem(win,402),field(model,"systems"),L"All systems");choices(GetDlgItem(win,403),field(model,"patches"),L"All patches");}
    const auto& records=field(model,"records").items;for(int i=0;i<6;i++){std::string title=i<int(records.size())?records[i].textOr("label")+"\n"+records[i].textOr("value"):"No record yet";SetDlgItemTextW(win,470+i,wide(title).c_str());}
    auto revision=encode(field(model,"revision"))+encode(field(model,"offset"))+encode(field(model,"rows"));
    if(revision!=lastRows){lastRows=revision;std::set<std::string> selected;int old=-1;while((old=ListView_GetNextItem(list,old,LVNI_SELECTED))>=0)if(old<int(rows.size()))selected.insert(rows[old].textOr("id"));rows=field(model,"rows").items;ListView_DeleteAllItems(list);
        for(int i=0;i<int(rows.size());i++){auto name=wide(rows[i].textOr("name")),kind=wide(rows[i].textOr("kind")),location=wide(rows[i].textOr("category"));LVITEMW item{};item.mask=LVIF_TEXT;item.iItem=i;item.pszText=name.data();ListView_InsertItem(list,&item);ListView_SetItemText(list,i,1,kind.data());ListView_SetItemText(list,i,2,location.data());if(selected.count(rows[i].textOr("id")))ListView_SetItemState(list,i,LVIS_SELECTED,LVIS_SELECTED);}
        if(!dirty&&!pendingSave)for(auto& row:rows)if(row.textOr("id")==current.textOr("id")){fill(field(row,"entry"));break;}
    }
    busy=false;
    SetDlgItemTextW(win,413,wide(std::to_string(int(model.numberOr("count")))+" memories · showing "+std::to_string(rows.empty()?0:int(model.numberOr("offset"))+1)+"–"+std::to_string(int(model.numberOr("offset"))+int(rows.size()))).c_str());
    EnableWindow(GetDlgItem(win,406),model.numberOr("offset")>0);EnableWindow(GetDlgItem(win,407),model.numberOr("offset")+200<model.numberOr("count"));
    auto key=result.textOr("command_id");if(!key.empty()&&key!=lastResult){lastResult=key;if(flag(result,"error")){pendingSave=false;pendingShare=false;}if(pendingSave&&!field(result,"entry").textOr("id").empty()){pendingSave=false;fill(field(result,"entry"));}if(pendingShare&&!result.textOr("preview").empty()){pendingShare=false;showPreview(result.textOr("preview"));}message(result.textOr("note"));}
    if(!note.empty())message(note);
    if(note.find("Invalid")!=std::string::npos||note.find("Enter ")!=std::string::npos||note.find("needs ")!=std::string::npos||note.find("Choose ")!=std::string::npos||note.find("Date/time")!=std::string::npos||note.find("Quality")!=std::string::npos){pendingSave=false;pendingShare=false;}
}
void close(){if(preview)DestroyWindow(preview);preview=nullptr;picture.reset();if(win)DestroyWindow(win);win=nullptr;if(body)DeleteObject(body);if(heading)DeleteObject(heading);if(bg)DeleteObject(bg);if(card)DeleteObject(card);edits.clear();}
}
