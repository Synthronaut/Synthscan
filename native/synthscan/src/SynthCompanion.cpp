#define UNICODE
#define _UNICODE
#include "SynthCompanion.h"
#include "SynthJson.h"
#include "SynthPages.h"
#include "SynthGlass.h"
#include <commctrl.h>
#include <uxtheme.h>
#include <shellapi.h>
#include <gdiplus.h>
#include <algorithm>
#include <ctime>
#include <chrono>
#include <cstdlib>
#include <cctype>
#include <cstring>

namespace SynthCompanion {
namespace {
using namespace SynthScan;
HWND page=nullptr;HFONT font=nullptr;std::filesystem::path folder;
std::string mode,lastState,selected,selectedWatch;Json model;
std::vector<Json> people,items,notices;bool filling=false;double lastLoad=0;
std::vector<std::string> selectedIds;
std::string peopleView;
bool showMatches=false;
HBRUSH background=CreateSolidBrush(RGB(14,18,25)),editBackground=CreateSolidBrush(RGB(25,29,36));
double now(){return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
HWND child(int id){return GetDlgItem(page,id);}
std::string text(int id){int size=GetWindowTextLengthW(child(id));std::wstring value(size+1,L'\0');GetWindowTextW(child(id),value.data(),size+1);value.resize(size);return utf8(value);}
void label(int id,const std::string& value){SetWindowTextW(child(id),wide(value).c_str());}
std::string buttonIcon(int id){switch(id){case 502:return "search";case 503:case 539:return "refresh";case 515:case 541:case 545:return "clear";case 513:return "friend";case 514:case 520:return "invite";case 512:return "check";case 517:case 521:return "tag";case 522:return "diary";default:return "";}}
void drawPersonRow(Gdiplus::Graphics& g,Gdiplus::RectF r,const std::vector<std::wstring>& fields,const std::vector<float>& widths,bool selected,bool hot,Gdiplus::Color relationship,bool focused=false){
    g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintAntiAliasGridFit);
    Gdiplus::SolidBrush base(SynthGlass::Base);g.FillRectangle(&base,r);
    if(selected||hot)SynthGlass::panel(g,{r.X+4,r.Y+3,r.Width-8,r.Height-6},selected,hot,8);
    SynthGlass::checkbox(g,{r.X+13,r.Y+(r.Height-16)/2,16,16},selected,hot);
    SynthGlass::rounded(g,{r.X+40,r.Y+(r.Height-24)/2,24,24},Gdiplus::Color(255,30,37,49),8);
    SynthGlass::icon(g,"people",{r.X+44,r.Y+(r.Height-16)/2,16,16},relationship);
    float x=r.X;
    for(size_t i=0;i<fields.size()&&i<widths.size();++i){
        float left=x+(i==0?74:12),width=widths[i]-(i==0?80:22);
        if(i==1&&!fields[i].empty()){
            Gdiplus::Font tagFont(L"Segoe UI",11.5f,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
            Gdiplus::RectF measured;g.MeasureString(fields[i].c_str(),-1,&tagFont,Gdiplus::PointF(0,0),&measured);
            bool org=fields[i]==L"Org";
            float chip=std::min(width,measured.Width+24.f);SynthGlass::rounded(g,{left,r.Y+(r.Height-22)/2,chip,22},org?Gdiplus::Color(255,64,35,16):Gdiplus::Color(255,37,43,55),7,org?Gdiplus::Color(160,255,145,40):Gdiplus::Color(35,173,190,213));
            SynthGlass::text(g,fields[i],{left+9,r.Y,chip-18,r.Height},11.5f,org?Gdiplus::Color(255,255,145,40):Gdiplus::Color(255,184,196,215));
        }else SynthGlass::text(g,fields[i],{left,r.Y,width,r.Height},i==0?13.f:11.5f,i==0?SynthGlass::Ink:(i==3?relationship:SynthGlass::Muted),i==0&&selected);
        x+=widths[i];
    }
    if(focused){Gdiplus::Pen pen(Gdiplus::Color(90,167,208,209),1);Gdiplus::GraphicsPath path;SynthGlass::shape(path,{r.X+4,r.Y+3,r.Width-8,r.Height-6},8);g.DrawPath(&pen,&path);}
}
void drawHeader(const DRAWITEMSTRUCT& item){
    Gdiplus::Graphics g(item.hDC);auto r=item.rcItem;Gdiplus::LinearGradientBrush bg(Gdiplus::Point(r.left,r.top),Gdiplus::Point(r.left,r.bottom+1),Gdiplus::Color(255,27,34,45),Gdiplus::Color(255,22,28,38));g.FillRectangle(&bg,Gdiplus::RectF(float(r.left),float(r.top),float(r.right-r.left),float(r.bottom-r.top)));
    wchar_t title[180]{};HDITEMW col{};col.mask=HDI_TEXT;col.pszText=title;col.cchTextMax=180;Header_GetItem(item.hwndItem,item.itemID,&col);
    SynthGlass::text(g,title,{float(r.left+(item.itemID==0?74:12)),float(r.top),float(r.right-r.left-(item.itemID==0?80:20)),float(r.bottom-r.top)},11,SynthGlass::Muted);
    Gdiplus::Pen rule(Gdiplus::Color(35,173,190,213));g.DrawLine(&rule,float(r.left),float(r.bottom-1),float(r.right),float(r.bottom-1));
}
void backdrop(Gdiplus::Graphics& g,float w,float h){
    g.Clear(SynthGlass::Base);SynthGlass::ambient(g,{0,0,w,h});if(mode=="people")SynthGlass::panel(g,{0,h-229,w,218},false,false,13);
}
void controlBackdrop(Gdiplus::Graphics& g,HWND hwnd){
    RECT r{},parent{};GetWindowRect(hwnd,&r);MapWindowPoints(nullptr,page,reinterpret_cast<POINT*>(&r),2);GetClientRect(page,&parent);auto state=g.Save();g.TranslateTransform(-float(r.left),-float(r.top));backdrop(g,float(parent.right),float(parent.bottom));g.Restore(state);
}
LRESULT CALLBACK glassControlProc(HWND hwnd,UINT message,WPARAM wp,LPARAM lp,UINT_PTR,DWORD_PTR kind){
    if(message==WM_MOUSEMOVE){if(!GetPropW(hwnd,L"SynthGlass.Hot")){SetPropW(hwnd,L"SynthGlass.Hot",HANDLE(1));InvalidateRect(hwnd,nullptr,FALSE);TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);}}
    if(message==WM_MOUSELEAVE){RemovePropW(hwnd,L"SynthGlass.Hot");InvalidateRect(hwnd,nullptr,FALSE);}
    if(message==WM_SETFOCUS||message==WM_KILLFOCUS)InvalidateRect(hwnd,nullptr,FALSE);
    if(kind&&message==WM_ERASEBKGND)return 1;
    if(kind&&(message==WM_PAINT||message==WM_PRINTCLIENT)){
        PAINTSTRUCT ps{};HDC dc=message==WM_PAINT?BeginPaint(hwnd,&ps):reinterpret_cast<HDC>(wp);RECT rc{};GetClientRect(hwnd,&rc);Gdiplus::Graphics g(dc);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
        Gdiplus::RectF r(0,0,float(rc.right),float(rc.bottom));controlBackdrop(g,hwnd);bool hot=GetPropW(hwnd,L"SynthGlass.Hot")!=nullptr;
        wchar_t title[512]{};GetWindowTextW(hwnd,title,512);
        if(kind==1){SynthGlass::panel(g,{1,1,r.Width-2,r.Height-2},false,hot,9);SynthGlass::text(g,title,{13,0,r.Width-42,r.Height},13);
            Gdiplus::Pen pen(SynthGlass::Muted,1.5f);float x=r.Width-21,y=r.Height/2;g.DrawLine(&pen,x-4,y-2,x,y+2);g.DrawLine(&pen,x,y+2,x+4,y-2);
        }else if(kind==4){
            if(GetDlgCtrlID(hwnd)==590){Gdiplus::Font f(L"Segoe UI",11,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::SolidBrush ink(SynthGlass::Muted);g.DrawString(title,-1,&f,r,nullptr,&ink);}
            else SynthGlass::text(g,title,r,GetDlgCtrlID(hwnd)==506||GetDlgCtrlID(hwnd)==518?11.f:12.f,SynthGlass::Muted);
        }else{bool checked=SendMessageW(hwnd,BM_GETCHECK,0,0)==BST_CHECKED;SynthGlass::checkbox(g,{2,(r.Height-18)/2,18,18},checked,hot);SynthGlass::text(g,title,{29,0,r.Width-29,r.Height},12,SynthGlass::Muted);}
        if(GetFocus()==hwnd){Gdiplus::Pen focus(Gdiplus::Color(120,148,198,202));Gdiplus::GraphicsPath outline;SynthGlass::shape(outline,{1,1,r.Width-2,r.Height-2},8);g.DrawPath(&focus,&outline);}
        if(message==WM_PAINT)EndPaint(hwnd,&ps);return 0;
    }
    if(kind==1&&(message==CB_SETCURSEL||message==CB_SHOWDROPDOWN)){auto value=DefSubclassProc(hwnd,message,wp,lp);InvalidateRect(hwnd,nullptr,FALSE);return value;}
    if(kind==2&&message==BM_SETCHECK){auto value=DefSubclassProc(hwnd,message,wp,lp);InvalidateRect(hwnd,nullptr,FALSE);return value;}
    if(message==WM_NCDESTROY){RemovePropW(hwnd,L"SynthGlass.Hot");RemoveWindowSubclass(hwnd,glassControlProc,2);}
    return DefSubclassProc(hwnd,message,wp,lp);
}
int hoveredPerson=-1;
LRESULT CALLBACK peopleListProc(HWND hwnd,UINT message,WPARAM wp,LPARAM lp,UINT_PTR,DWORD_PTR){
    if((message==WM_LBUTTONDOWN||message==WM_LBUTTONDBLCLK)&&!(wp&(MK_CONTROL|MK_SHIFT))){
        LVHITTESTINFO hit{};hit.pt={(short)LOWORD(lp),(short)HIWORD(lp)};int row=ListView_SubItemHitTest(hwnd,&hit);RECT box{};
        if(row>=0&&ListView_GetItemRect(hwnd,row,&box,LVIR_BOUNDS)&&hit.pt.x>=box.left+5&&hit.pt.x<box.left+35){SetFocus(hwnd);auto state=ListView_GetItemState(hwnd,row,LVIS_SELECTED);ListView_SetItemState(hwnd,row,state?0:LVIS_SELECTED,LVIS_SELECTED);ListView_SetSelectionMark(hwnd,row);SetPropW(hwnd,L"SynthGlass.CheckClick",HANDLE(1));return 0;}
    }
    if(message==WM_LBUTTONUP&&GetPropW(hwnd,L"SynthGlass.CheckClick")){RemovePropW(hwnd,L"SynthGlass.CheckClick");return 0;}

    if(message==WM_DRAWITEM){auto item=reinterpret_cast<DRAWITEMSTRUCT*>(lp);if(item->CtlType==ODT_HEADER){drawHeader(*item);return TRUE;}}
    if(message==WM_MOUSEMOVE||message==WM_MOUSELEAVE){
        if(message==WM_MOUSELEAVE)RemovePropW(hwnd,L"SynthGlass.CheckClick");
        int next=-1;if(message==WM_MOUSEMOVE){LVHITTESTINFO hit{};hit.pt={(short)LOWORD(lp),(short)HIWORD(lp)};next=ListView_SubItemHitTest(hwnd,&hit);TRACKMOUSEEVENT track{sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);}
        if(next!=hoveredPerson){int old=hoveredPerson;hoveredPerson=next;if(old>=0)ListView_RedrawItems(hwnd,old,old);if(next>=0)ListView_RedrawItems(hwnd,next,next);}
    }
    if(message==WM_NCDESTROY){hoveredPerson=-1;RemoveWindowSubclass(hwnd,peopleListProc,1);}
    return DefSubclassProc(hwnd,message,wp,lp);
}
void control(const wchar_t* cls,int id,const wchar_t* title,DWORD style=0){
    if(id==508)style|=LVS_OWNERDRAWFIXED;
    if(cls==std::wstring(L"COMBOBOX"))style|=CBS_OWNERDRAWFIXED|CBS_HASSTRINGS;
    if(cls==std::wstring(L"BUTTON")&&(style&15)==BS_PUSHBUTTON)style|=BS_OWNERDRAW;
    HWND h=CreateWindowExW(0,cls,title,WS_CHILD|WS_VISIBLE|style,0,0,10,24,page,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);
    if(id==508){SetWindowSubclass(h,peopleListProc,1,0);HIMAGELIST rows=ImageList_Create(1,36,ILC_COLOR32,1,1);ListView_SetImageList(h,rows,LVSIL_SMALL);}
    if(cls==std::wstring(L"COMBOBOX"))SetWindowSubclass(h,glassControlProc,2,1);
    if(cls==std::wstring(L"STATIC"))SetWindowSubclass(h,glassControlProc,2,4);
    if(cls==std::wstring(L"BUTTON"))SetWindowSubclass(h,glassControlProc,2,(style&15)==BS_AUTOCHECKBOX?2:0);
    if(cls==std::wstring(L"EDIT"))SendMessageW(h,EM_SETMARGINS,EC_LEFTMARGIN|EC_RIGHTMARGIN,MAKELPARAM(12,10));
    SetWindowTheme(h,L"DarkMode_Explorer",nullptr);SendMessageW(h,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);
    if(cls==std::wstring(L"COMBOBOX"))SendMessageW(h,CB_SETITEMHEIGHT,WPARAM(-1),26);
    if(cls==std::wstring(WC_LISTVIEWW)){ListView_SetExtendedListViewStyle(h,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER);ListView_SetBkColor(h,RGB(14,18,25));ListView_SetTextBkColor(h,RGB(14,18,25));ListView_SetTextColor(h,RGB(234,240,247));}
}
void column(int id,int index,const wchar_t* title,int width){LVCOLUMNW c{};c.mask=LVCF_TEXT|LVCF_WIDTH;c.pszText=const_cast<wchar_t*>(title);c.cx=width;ListView_InsertColumn(child(id),index,&c);if(id==508){auto header=ListView_GetHeader(child(id));HDITEMW column{};column.mask=HDI_FORMAT;Header_GetItem(header,index,&column);column.fmt|=HDF_OWNERDRAW;Header_SetItem(header,index,&column);}}
void cell(int id,int row,int col,const std::string& value){auto wideValue=wide(value);if(col==0){LVITEMW item{};item.mask=LVIF_TEXT;item.iItem=row;item.pszText=wideValue.data();ListView_InsertItem(child(id),&item);}else ListView_SetItemText(child(id),row,col,wideValue.data());}
std::string age(double stamp){if(stamp<=0)return "not checked";int seconds=int(std::max(0.,now()-stamp));return seconds<60?std::to_string(seconds)+"s ago":std::to_string(seconds/60)+"m ago";}
COLORREF personColor(const Json& person){return flag(person,"is_self")?RGB(193,157,255):flag(person,"in_party")?RGB(116,183,255):flag(person,"is_friend")?RGB(121,225,158):RGB(234,240,247);}
bool fresh(){return model.numberOr("owner_pid")==GetCurrentProcessId()&&now()>=model.numberOr("written_at")&&now()-model.numberOr("written_at")<15;}
void queue(Json command){
    if(!fresh()){label(590,"Companion services unavailable. Please wait for a fresh update.");return;}
    static unsigned sequence=0;char id[90];sprintf_s(id,"%020llu-%010lu-%08u",GetTickCount64(),GetCurrentProcessId(),++sequence);
    command.members.push_back({"id",str(id)});command.members.push_back({"owner_pid",num(GetCurrentProcessId())});command.members.push_back({"at",num(now())});command.members.push_back({"session_token",field(model,"session_token")});
    std::error_code error;std::filesystem::create_directories(folder/L"companion_commands",error);
    if(!write(folder/L"companion_commands"/(std::wstring(id,id+strlen(id))+L".json"),command))label(590,"Could not save the action. Please try again.");
    else label(590,"Working…");
}
void layout(){
    if(!page)return;RECT r{};GetClientRect(page,&r);int w=std::max(620,int(r.right)),h=std::max(580,int(r.bottom));
    auto place=[&](int id,int x,int y,int width,int height=34){
        HWND h=child(id);wchar_t cls[30]{};GetClassNameW(h,cls,30);if(std::wstring(cls)==L"Edit"){MoveWindow(h,x+2,y+8,width-4,height-14,TRUE);}else MoveWindow(h,x,y,width,height,TRUE);
    };
    place(501,0,8,w-(mode=="people"?364:292));if(mode=="people")place(523,w-352,8,64);place(502,w-280,8,130);place(503,w-140,8,130);
    if(mode=="people"){
        place(504,0,50,210,150);place(505,222,50,150);place(519,384,50,w-384,34);place(506,0,84,w,22);
        place(508,0,116,w,h-344);place(516,0,h-207,215,210);place(517,227,h-207,112);place(518,351,h-207,w-351,24);
        place(509,0,h-164,32);place(510,40,h-164,w-348);
        place(511,w-298,h-164,145);place(512,w-145,h-164,135);
        place(513,0,h-116,120);place(514,128,h-116,130);place(520,266,h-116,108);place(521,382,h-116,100);place(515,490,h-116,120);
        place(590,0,h-69,w-152,60);place(522,w-140,h-69,140);
        int available=w-GetSystemMetrics(SM_CXVSCROLL);int first=std::max(200,(available-320)*55/100),tags=std::max(120,available-first-320);
        ListView_SetColumnWidth(child(508),0,first);ListView_SetColumnWidth(child(508),1,tags);ListView_SetColumnWidth(child(508),2,72);ListView_SetColumnWidth(child(508),3,118);ListView_SetColumnWidth(child(508),4,130);
    }else{
        place(504,0,47,w,22);place(530,0,73,w-10,200);place(531,0,115,70);place(532,74,115,67);
        place(533,152,115,105);place(534,263,115,90);place(535,363,115,40);place(536,407,115,w-547);place(537,w-130,115,120);
        place(538,0,155,w,h-418);place(539,0,h-249,130);place(540,142,h-249,120);place(541,274,h-249,125);place(546,411,h-249,130);
        place(542,0,h-209,w,20);place(543,0,h-184,w,99);place(544,0,h-74,175);place(545,187,h-74,130);place(590,0,h-36,w,28);
        ListView_SetColumnWidth(child(538),0,std::max(155,w-450));ListView_SetColumnWidth(child(543),0,std::max(260,w-200));
    }
}
std::vector<Json> chosen(){
    std::vector<Json> result;int at=-1;
    while((at=ListView_GetNextItem(child(508),at,LVNI_SELECTED))>=0)if(size_t(at)<people.size()&&!flag(people[size_t(at)],"is_self"))result.push_back(people[size_t(at)]);
    return result;
}
Json playerIds(const std::vector<Json>& rows){Json ids=arr();for(const auto& p:rows)ids.items.push_back(field(p,"id"));return ids;}
std::vector<Json> inviteCandidates(bool org){
    std::vector<Json> result;
    for(const auto& p:org?field(model,"rows").items:chosen())if(!flag(p,"is_self")&&!flag(p,"in_party")&&(!org||flag(p,"is_org")))result.push_back(p);
    return result;
}
LRESULT CALLBACK recipientsProcedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_NCCREATE)SetWindowLongPtrW(hwnd,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(reinterpret_cast<CREATESTRUCTW*>(lp)->lpCreateParams));
    auto result=reinterpret_cast<int*>(GetWindowLongPtrW(hwnd,GWLP_USERDATA));
    if(message==DM_GETDEFID)return MAKELRESULT(IDCANCEL,DC_HASDEFID);
    if(message==WM_COMMAND&&(LOWORD(wp)==IDOK||LOWORD(wp)==IDCANCEL)){if(result)*result=LOWORD(wp);DestroyWindow(hwnd);return 0;}
    if(message==WM_CLOSE){if(result)*result=IDCANCEL;DestroyWindow(hwnd);return 0;}
    return DefWindowProcW(hwnd,message,wp,lp);
}
bool showRecipients(const std::vector<Json>& rows,bool report=false,const std::filesystem::path& previewPath={}){
    WNDCLASSW cls{};cls.lpfnWndProc=recipientsProcedure;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanRecipientsPopup";cls.hCursor=LoadCursor(nullptr,IDC_ARROW);cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);RegisterClassW(&cls);
    HWND owner=GetAncestor(page,GA_ROOT);RECT bounds{};GetWindowRect(owner,&bounds);int result=0;
    HWND dialog=CreateWindowExW(WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT,cls.lpszClassName,report?L"Party invitation results":L"Confirm party invitations",WS_POPUP|WS_CAPTION|WS_SYSMENU,
        bounds.left+std::max(0,int(bounds.right-bounds.left-650)/2),bounds.top+std::max(0,int(bounds.bottom-bounds.top-490)/2),650,490,owner,nullptr,cls.hInstance,&result);
    if(!dialog)return false;
    auto add=[&](const wchar_t* type,int id,const std::wstring& title,DWORD style,int x,int y,int w,int h){auto control=CreateWindowExW(0,type,title.c_str(),WS_CHILD|WS_VISIBLE|style,x,y,w,h,dialog,reinterpret_cast<HMENU>(INT_PTR(id)),cls.hInstance,nullptr);SendMessageW(control,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return control;};
    add(L"STATIC",601,report?L"Invitation receipts and skipped players. Sent means awaiting acceptance.":wide("Invite "+std::to_string(rows.size())+" player(s)? Shard and party membership will be rechecked."),0,12,12,610,36);
    auto list=add(WC_LISTVIEWW,602,L"",WS_TABSTOP|LVS_REPORT,12,50,610,340);ListView_SetExtendedListViewStyle(list,LVS_EX_FULLROWSELECT|LVS_EX_DOUBLEBUFFER);
    int col=0;for(const auto* title:{L"Player",L"Result",L"Details"}){LVCOLUMNW c{};c.mask=LVCF_TEXT|LVCF_WIDTH;c.pszText=const_cast<wchar_t*>(title);c.cx=col==0?180:col==1?115:650;ListView_InsertColumn(list,col++,&c);}
    int row=0;for(const auto& p:rows){auto handle=wide(p.textOr("handle")),outcome=wide(p.textOr("outcome","Invite")),detail=wide(p.textOr("detail"));LVITEMW item{};item.mask=LVIF_TEXT;item.iItem=row;item.pszText=handle.data();ListView_InsertItem(list,&item);ListView_SetItemText(list,row,1,outcome.data());ListView_SetItemText(list,row,2,detail.data());row++;}
    auto cancel=add(L"BUTTON",IDCANCEL,report?L"Close":L"Cancel",WS_TABSTOP|BS_DEFPUSHBUTTON,502,405,120,30);
    if(!report)add(L"BUTTON",IDOK,L"Send invitations",WS_TABSTOP,350,405,140,30);
    if(previewPath.empty()){EnableWindow(owner,FALSE);ShowWindow(dialog,SW_SHOW);SetFocus(cancel);}
    else {
        // Isolated fixture: render and cancel without showing or sending anything.
        RECT bounds{};GetWindowRect(dialog,&bounds);RECT client{0,0,bounds.right-bounds.left,bounds.bottom-bounds.top};HDC dc=GetWindowDC(dialog),memory=CreateCompatibleDC(dc);HBITMAP bitmap=CreateCompatibleBitmap(dc,client.right,client.bottom);auto old=SelectObject(memory,bitmap);
        FillRect(memory,&client,(HBRUSH)(COLOR_WINDOW+1));SendMessageW(dialog,WM_PRINT,reinterpret_cast<WPARAM>(memory),PRF_CLIENT|PRF_CHILDREN|PRF_ERASEBKGND|PRF_NONCLIENT);
        const CLSID png={0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};bool saved;
        {Gdiplus::Bitmap image(bitmap,nullptr);saved=image.Save(previewPath.c_str(),&png,nullptr)==Gdiplus::Ok;}
        wchar_t first[100]{};ListView_GetItemText(list,0,0,first,100);
        write(previewPath.parent_path()/L"confirmation_validation.json",obj({{"rendered",SynthScan::boolean(saved)},{"exact_recipient_count",SynthScan::boolean(ListView_GetItemCount(list)==int(rows.size()))},
            {"first_handle_matches",SynthScan::boolean(!rows.empty()&&utf8(first)==rows.front().textOr("handle"))},{"scrollable",SynthScan::boolean(ListView_GetCountPerPage(list)>0&&ListView_GetCountPerPage(list)<int(rows.size()))},
            {"cancel_is_default",SynthScan::boolean(LOWORD(SendMessageW(dialog,DM_GETDEFID,0,0))==IDCANCEL)},{"stays_modal",SynthScan::boolean(!(GetWindowLongPtrW(dialog,GWL_STYLE)&WS_CHILD)&&GetParent(dialog)==owner)}}));
        SelectObject(memory,old);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(dialog,dc);PostMessageW(dialog,WM_COMMAND,IDCANCEL,0);
    }
    MSG msg{};while(IsWindow(dialog)){int received=GetMessageW(&msg,nullptr,0,0);if(received<=0){DestroyWindow(dialog);if(received==0)PostQuitMessage(int(msg.wParam));break;}if(!IsDialogMessageW(dialog,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    if(previewPath.empty()){EnableWindow(owner,TRUE);SetActiveWindow(owner);}return result==IDOK;
}
void selection(){
    std::vector<std::string> ids;int at=-1;while((at=ListView_GetNextItem(child(508),at,LVNI_SELECTED))>=0)if(size_t(at)<people.size())ids.push_back(people[size_t(at)].textOr("id"));
    const bool changed=ids!=selectedIds;
    if(changed){selectedIds=ids;selected=ids.empty()?"":ids.front();
        auto rows=chosen();label(510,ids.size()==1&&!rows.empty()?rows.front().textOr("tag"):"");SendMessageW(child(511),BM_SETCHECK,ids.size()==1&&!rows.empty()&&flag(rows.front(),"alert")?BST_CHECKED:BST_UNCHECKED,0);}
    auto rows=chosen();const bool enabled=fresh()&&!model.textOr("session_token").empty()&&!rows.empty();
    EnableWindow(child(512),enabled);EnableWindow(child(515),enabled);EnableWindow(child(521),enabled);EnableWindow(child(511),enabled&&selectedIds.size()==1);
    EnableWindow(child(513),enabled&&rows.size()==1&&!flag(model,"social_busy"));EnableWindow(child(514),enabled&&!flag(model,"social_busy"));
    EnableWindow(child(520),fresh()&&!model.textOr("session_token").empty()&&!inviteCandidates(true).empty()&&!flag(model,"social_busy"));EnableWindow(child(522),!field(model,"batch_results").items.empty());
    label(512,rows.size()>1?"Add tags to all":"Save tag");label(514,rows.size()>1?"Invite selected…":"Invite to party…");std::string summary=std::to_string(selectedIds.size())+" selected";int shown=0;for(const auto& p:people)if(std::find(selectedIds.begin(),selectedIds.end(),p.textOr("id"))!=selectedIds.end()){summary+=shown++?", ":": ";summary+=p.textOr("handle");if(shown==3)break;}if(selectedIds.size()>3)summary+=" +"+std::to_string(selectedIds.size()-3);label(518,summary);
    if(changed)InvalidateRect(child(508),nullptr,FALSE);
}
std::string normalizedQuery(std::string query){
    auto first=query.find_first_not_of(" \t\r\n"),last=query.find_last_not_of(" \t\r\n");
    if(first==std::string::npos)return "";query=query.substr(first,last-first+1);
    std::transform(query.begin(),query.end(),query.begin(),[](unsigned char c){return char(std::tolower(c));});return query;
}
void renderPeople(){
    auto query=normalizedQuery(text(501));
    int source=int(SendMessageW(child(504),CB_GETCURSEL,0,0));bool tagged=SendMessageW(child(505),BM_GETCHECK,0,0)==BST_CHECKED;
    std::vector<Json> candidates;
    if(source==2){for(const auto& pair:field(model,"tags").members){auto p=pair.second;p.members.push_back({"id",str(pair.first)});p.members.push_back({"tag",field(pair.second,"label")});candidates.push_back(p);}}
    else if(source!=1||(!query.empty()&&query==normalizedQuery(model.textOr("search_query"))))candidates=field(model,source==1?"search":"rows").items;
    SendMessageW(child(501),EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(source==1?L"Enter an RSI handle, then click Find player":L"Filter this list by handle or tag"));
    const std::string view=model.textOr("session_token")+"|"+std::to_string(source)+"|"+query+"|"+(tagged?"1":"0");
    const bool resetView=view!=peopleView;
    std::vector<Json> nextPeople;
    for(const auto& p:candidates){auto hay=p.textOr("handle")+" "+p.textOr("tag");std::transform(hay.begin(),hay.end(),hay.begin(),[](unsigned char c){return char(std::tolower(c));});if(!query.empty()&&hay.find(query)==std::string::npos)continue;if(tagged&&p.textOr("tag").empty())continue;
        nextPeople.push_back(p);
    }
    bool rowsChanged=resetView||nextPeople.size()!=people.size();
    if(!rowsChanged)for(size_t i=0;i<people.size();i++)if(encode(nextPeople[i])!=encode(people[i])){rowsChanged=true;break;}
    if(rowsChanged){
        HWND list=child(508);const int top=ListView_GetTopIndex(list),horizontal=GetScrollPos(list,SB_HORZ);
        RECT topRect{};const bool haveTop=!resetView&&top>=0&&size_t(top)<people.size()&&ListView_GetItemRect(list,top,&topRect,LVIR_BOUNDS);
        std::string anchor;
        if(haveTop){
            // If the top player leaves, retain the next surviving neighbour.
            // Insertions above the viewport must not move the player being read.
            auto survives=[&](const std::string& id){return std::any_of(nextPeople.begin(),nextPeople.end(),[&](const Json& p){return p.textOr("id")==id;});};
            for(size_t i=size_t(top);i<people.size();i++)if(survives(people[i].textOr("id"))){anchor=people[i].textOr("id");break;}
            if(anchor.empty())for(int i=top-1;i>=0;i--)if(survives(people[size_t(i)].textOr("id"))){anchor=people[size_t(i)].textOr("id");break;}
        }
        const int focused=ListView_GetNextItem(list,-1,LVNI_FOCUSED);
        const auto focusedId=focused>=0&&size_t(focused)<people.size()?people[size_t(focused)].textOr("id"):"";
        const int mark=ListView_GetSelectionMark(list);const auto markId=!resetView&&mark>=0&&size_t(mark)<people.size()?people[size_t(mark)].textOr("id"):"";
        filling=true;hoveredPerson=-1;SendMessageW(list,WM_SETREDRAW,FALSE,0);ListView_DeleteAllItems(list);
        auto previousSelection=resetView?std::vector<std::string>{}:selectedIds;
        people=std::move(nextPeople);peopleView=view;int focusedAt=-1,anchorAt=-1;
        for(size_t i=0;i<people.size();i++){
            const auto& p=people[i];const int row=int(i);
            cell(508,row,0,p.textOr("handle"));cell(508,row,1,p.textOr("tag"));cell(508,row,2,flag(p,"alert")?"On":"Off");cell(508,row,3,p.textOr("relationship","Unknown"));cell(508,row,4,source==1?"Handle search":source==2?"Saved tag":"Shard group");
            if(std::find(previousSelection.begin(),previousSelection.end(),p.textOr("id"))!=previousSelection.end())ListView_SetItemState(list,row,LVIS_SELECTED,LVIS_SELECTED);
            if(p.textOr("id")==markId)ListView_SetSelectionMark(list,row);
            if(p.textOr("id")==focusedId)focusedAt=row;if(p.textOr("id")==anchor)anchorAt=row;
        }
        if(focusedAt>=0)ListView_SetItemState(list,focusedAt,LVIS_FOCUSED,LVIS_FOCUSED);
        SendMessageW(list,WM_SETREDRAW,TRUE,0);
        if(haveTop&&anchorAt>=0){RECT rect{};if(ListView_GetItemRect(list,anchorAt,&rect,LVIR_BOUNDS))ListView_Scroll(list,0,rect.top-topRect.top);}
        if(!resetView)ListView_Scroll(list,horizontal-GetScrollPos(list,SB_HORZ),0);
        InvalidateRect(list,nullptr,FALSE);filling=false;
    }
    selection();
    std::string status=!fresh()?"Services unavailable":model.textOr("session_token").empty()?"Join a shard to load people":std::to_string(field(model,"rows").items.size())+" reported shard members · "+age(model.numberOr("roster_at"));
    if(source==1){
        bool matching=!query.empty()&&query==normalizedQuery(model.textOr("search_query"));
        status=matching?(flag(model,"search_busy")?"Searching handles…":std::to_string(people.size())+" result(s) for “"+model.textOr("search_query")+"”"):(query.empty()?"Enter a handle, then click Find player.":"Click Find player to look up “"+text(501)+"”. Previous results are hidden.");
    }
    if(source!=1&&flag(model,"roster_loading"))status+=" · refreshing";if(source!=1&&!model.textOr("roster_error").empty())status+=" · "+model.textOr("roster_error");label(506,status);
    label(590,model.textOr("status")+"\r\nTagged-player alerts report list appearances; the first snapshot stays quiet."+
        ((!flag(model,"friends_known")||!flag(model,"party_known"))?"\r\nFriend / party status is checking or unavailable; unconfirmed rows stay neutral.":""));
}
void catalog(){
    auto catalog=read(folder/L"finder_market_index.json",8*1024*1024);std::string filter=text(501);std::transform(filter.begin(),filter.end(),filter.begin(),[](unsigned char c){return char(std::tolower(c));});
    int previous=int(SendMessageW(child(530),CB_GETCURSEL,0,0));double selectedId=previous>=0&&size_t(previous)<items.size()?items[previous].numberOr("id"):0;
    items.clear();for(const auto& pair:field(catalog,"items").members){auto name=pair.second.textOr("name");std::transform(name.begin(),name.end(),name.begin(),[](unsigned char c){return char(std::tolower(c));});if(filter.empty()||name.find(filter)!=std::string::npos)items.push_back(pair.second);}
    std::sort(items.begin(),items.end(),[](const Json& a,const Json& b){return a.textOr("name")<b.textOr("name");});if(items.size()>500)items.resize(500);
    SendMessageW(child(530),CB_RESETCONTENT,0,0);int chosen=0,index=0;for(const auto& item:items){auto name=wide(item.textOr("name"));SendMessageW(child(530),CB_ADDSTRING,0,reinterpret_cast<LPARAM>(name.c_str()));if(item.numberOr("id")==selectedId)chosen=index;index++;}SendMessageW(child(530),CB_SETCURSEL,chosen,0);
    label(504,items.empty()?"Market catalog is loading. Try a material name shortly.":"Select the exact item · watches check every 30 minutes · quality 0 means any");
}
void renderMarket(){
    filling=true;ListView_DeleteAllItems(child(538));int i=0,selectedAt=-1;
    for(const auto& watch:field(model,"watches").items){cell(538,i,0,watch.textOr("name"));cell(538,i,1,watch.numberOr("quality")?"Q"+std::to_string(int(watch.numberOr("quality"))):"Any");
        cell(538,i,2,watch.numberOr("minimum_price")?std::to_string(int(watch.numberOr("minimum_price")))+" / "+watch.textOr("unit"):"Any price");cell(538,i,3,std::to_string(field(watch,"matches").items.size()));
        cell(538,i,4,!flag(watch,"enabled")?"Paused":!watch.textOr("error").empty()?"Refresh unavailable":age(watch.numberOr("checked_at")));if(watch.textOr("id")==selectedWatch)selectedAt=i;i++;
    }if(selectedAt>=0)ListView_SetItemState(child(538),selectedAt,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);
    notices=field(model,"notifications").items;
    if(showMatches){notices.clear();for(const auto& watch:field(model,"watches").items)if(watch.textOr("id")==selectedWatch)for(const auto& offer:field(watch,"matches").items){auto row=offer;row.members.push_back({"title",str("BUY REQUEST")});row.members.push_back({"detail",str(std::to_string(int(offer.numberOr("price")))+" UEC / "+offer.textOr("unit")+" · "+offer.textOr("location"))});row.members.push_back({"at",field(offer,"renewed")});notices.push_back(row);}}
    label(542,showMatches?"Current matching buy requests — select one to open its UEX advertisement":"Recent HUD notices — buyer matches and tagged-player appearances");
    label(546,showMatches?"Show notices":"Show matches");
    ListView_DeleteAllItems(child(543));i=0;for(const auto& notice:notices){cell(543,i,0,notice.textOr("title")+" · "+notice.textOr("detail"));cell(543,i,1,age(notice.numberOr("at")));i++;}
    label(590,model.textOr("status"));filling=false;
}
void refresh(bool force=false){
    auto next=read(folder/L"companion_state.json",8*1024*1024);auto serialized=encode(next);bool changed=serialized!=lastState;
    model=next;lastState=serialized;
    if(mode=="people"){if(changed||force)renderPeople();else selection();}
    else if(changed||force){renderMarket();if(force||items.empty())catalog();}
}
void createControls(){
    filling=true;
    for(HWND h=GetWindow(page,GW_CHILD);h;){HWND next=GetWindow(h,GW_HWNDNEXT);DestroyWindow(h);h=next;}
    selected.clear();selectedIds.clear();selectedWatch.clear();
    people.clear();peopleView.clear();
    control(L"EDIT",501,L"",WS_TABSTOP|ES_AUTOHSCROLL);SendMessageW(child(501),EM_SETCUEBANNER,TRUE,reinterpret_cast<LPARAM>(mode=="people"?L"Filter names/tags or enter an RSI handle":L"Search UEX materials or items"));
    if(mode=="people")control(L"BUTTON",523,L"Clear",WS_TABSTOP);
    control(L"BUTTON",502,mode=="people"?L"Find player":L"Find material",WS_TABSTOP);
    control(L"BUTTON",503,mode=="people"?L"Refresh shard":L"Refresh buyers",WS_TABSTOP);
    if(mode=="people"){
        control(L"COMBOBOX",504,L"",WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL);for(const auto* s:{L"Shard members",L"Handle search results",L"Saved player tags"})SendMessageW(child(504),CB_ADDSTRING,0,reinterpret_cast<LPARAM>(s));SendMessageW(child(504),CB_SETCURSEL,0,0);
        control(L"BUTTON",505,L"Tagged only",WS_TABSTOP|BS_AUTOCHECKBOX);control(L"STATIC",506,L"Loading player list…");control(WC_LISTVIEWW,508,L"",WS_TABSTOP|LVS_REPORT|LVS_SHOWSELALWAYS);
        control(L"STATIC",519,L"You: Purple · Friend: Green · Party: Blue");
        column(508,0,L"PLAYER",240);column(508,1,L"TAGS",180);column(508,2,L"ALERTS",80);column(508,3,L"RELATIONSHIP",125);column(508,4,L"SOURCE",120);
        control(L"STATIC",509,L"Tags");control(L"EDIT",510,L"",WS_TABSTOP|ES_AUTOHSCROLL);SendMessageW(child(510),EM_SETLIMITTEXT,240,0);
        control(L"COMBOBOX",516,L"",WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL);for(const auto* tag:{L"Aggressive",L"Trader",L"Friendly",L"Org",L"Org Affiliate",L"Crew",L"Buyer",L"Avoid"})SendMessageW(child(516),CB_ADDSTRING,0,reinterpret_cast<LPARAM>(tag));SendMessageW(child(516),CB_SETCURSEL,0,0);
        control(L"BUTTON",517,L"Add tag",WS_TABSTOP);control(L"STATIC",518,L"Or type custom tags, separated by commas");
        control(L"BUTTON",511,L"Alert on appearance",WS_TABSTOP|BS_AUTOCHECKBOX);control(L"BUTTON",512,L"Save tag",WS_TABSTOP);
        control(L"BUTTON",513,L"Add friend…",WS_TABSTOP);control(L"BUTTON",514,L"Invite to party…",WS_TABSTOP);control(L"BUTTON",515,L"Remove tags",WS_TABSTOP);
        control(L"BUTTON",520,L"Invite org…",WS_TABSTOP);control(L"BUTTON",521,L"Mark org",WS_TABSTOP);control(L"BUTTON",522,L"Invite results",WS_TABSTOP);
    }else{
        control(L"STATIC",504,L"Checks every 30 minutes");control(L"COMBOBOX",530,L"",WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL);
        control(L"STATIC",531,L"Quality");control(L"EDIT",532,L"1000",WS_TABSTOP|ES_NUMBER);control(L"STATIC",533,L"Minimum UEC");control(L"EDIT",534,L"",WS_TABSTOP|ES_AUTOHSCROLL);
        control(L"STATIC",535,L"/ unit");control(L"EDIT",536,L"unit",WS_TABSTOP|ES_AUTOHSCROLL);control(L"BUTTON",537,L"Watch buyers",WS_TABSTOP);
        control(WC_LISTVIEWW,538,L"",WS_TABSTOP|LVS_REPORT|LVS_SINGLESEL|LVS_SHOWSELALWAYS);column(538,0,L"Material / item",230);column(538,1,L"Quality",70);column(538,2,L"Minimum",130);column(538,3,L"Matches",65);column(538,4,L"Last check",150);
        control(L"BUTTON",539,L"Refresh now",WS_TABSTOP);control(L"BUTTON",540,L"Pause / resume",WS_TABSTOP);control(L"BUTTON",541,L"Remove watch",WS_TABSTOP);
        control(L"BUTTON",546,L"Show matches",WS_TABSTOP);
        control(L"STATIC",542,L"Recent HUD notices — buyer matches and tagged-player appearances");control(WC_LISTVIEWW,543,L"",WS_TABSTOP|LVS_REPORT|LVS_SINGLESEL|LVS_SHOWSELALWAYS);column(543,0,L"Notification",500);column(543,1,L"Observed",140);
        control(L"BUTTON",544,L"Open selected UEX ad",WS_TABSTOP);control(L"BUTTON",545,L"Dismiss notices",WS_TABSTOP);
    }control(L"STATIC",590,L"Loading…");filling=false;layout();refresh(true);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_SIZE){layout();return 0;}if(message==WM_TIMER){refresh();return 0;}
    if(message==WM_ERASEBKGND)return 1;
    if(message==WM_PAINT||message==WM_PRINTCLIENT){
        PAINTSTRUCT ps{};HDC dc=message==WM_PAINT?BeginPaint(hwnd,&ps):reinterpret_cast<HDC>(wp);Gdiplus::Graphics g(dc);RECT bounds{};GetClientRect(hwnd,&bounds);backdrop(g,float(bounds.right),float(bounds.bottom));g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
        for(int id:{501,510,532,534,536}){auto h=child(id);if(!h)continue;RECT r{};GetWindowRect(h,&r);MapWindowPoints(nullptr,hwnd,reinterpret_cast<POINT*>(&r),2);SynthGlass::panel(g,{float(r.left-2),float(r.top-8),float(r.right-r.left+4),float(r.bottom-r.top+14)},false,GetFocus()==h,9);}
        if(message==WM_PAINT)EndPaint(hwnd,&ps);return 0;
    }
    if(message==WM_CTLCOLORSTATIC||message==WM_CTLCOLOREDIT){SetTextColor((HDC)wp,RGB(234,240,247));SetBkColor((HDC)wp,message==WM_CTLCOLOREDIT?RGB(25,29,36):RGB(14,18,25));return reinterpret_cast<LRESULT>(message==WM_CTLCOLOREDIT?editBackground:background);}
    if(message==WM_CTLCOLORLISTBOX){SetTextColor((HDC)wp,RGB(234,240,247));SetBkColor((HDC)wp,RGB(25,29,36));return reinterpret_cast<LRESULT>(editBackground);}
    if(message==WM_MEASUREITEM){auto item=reinterpret_cast<MEASUREITEMSTRUCT*>(lp);if(item->CtlType==ODT_LISTVIEW&&item->CtlID==508){item->itemHeight=40;return TRUE;}if(item->CtlType==ODT_COMBOBOX){item->itemHeight=34;return TRUE;}}
    if(message==WM_DRAWITEM){auto item=reinterpret_cast<DRAWITEMSTRUCT*>(lp);
        if(item->CtlType==ODT_LISTVIEW&&item->CtlID==508&&item->itemID<people.size()){
            const auto& p=people[item->itemID];std::vector<std::wstring> values;std::vector<float> widths;
            for(int col=0;col<5;++col){wchar_t value[512]{};ListView_GetItemText(item->hwndItem,item->itemID,col,value,512);values.push_back(value);widths.push_back(float(ListView_GetColumnWidth(item->hwndItem,col)));}
            auto state=ListView_GetItemState(item->hwndItem,item->itemID,LVIS_SELECTED|LVIS_FOCUSED);Gdiplus::Graphics g(item->hDC);auto r=item->rcItem;RECT client{},first{};GetClientRect(item->hwndItem,&client);ListView_GetSubItemRect(item->hwndItem,item->itemID,0,LVIR_BOUNDS,&first);r.left=first.left;int total=0;for(float width:widths)total+=int(width);r.right=std::max(client.right,r.left+total);g.SetClip(Gdiplus::Rect(0,0,client.right,client.bottom),Gdiplus::CombineModeIntersect);
            COLORREF color=personColor(p);drawPersonRow(g,{float(r.left),float(r.top),float(r.right-r.left),float(r.bottom-r.top)},values,widths,(state&LVIS_SELECTED)!=0,int(item->itemID)==hoveredPerson,Gdiplus::Color(255,GetRValue(color),GetGValue(color),GetBValue(color)),(state&LVIS_FOCUSED)&&GetFocus()==item->hwndItem);return TRUE;
        }
        if(item->CtlType==ODT_COMBOBOX){
            Gdiplus::Graphics g(item->hDC);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);Gdiplus::SolidBrush base(SynthGlass::Base);auto r=item->rcItem;g.FillRectangle(&base,Gdiplus::RectF(float(r.left),float(r.top),float(r.right-r.left),float(r.bottom-r.top)));
            bool selected=(item->itemState&ODS_SELECTED)!=0;if(selected)SynthGlass::panel(g,{float(r.left+3),float(r.top+2),float(r.right-r.left-6),float(r.bottom-r.top-4)},true,false,7);
            std::wstring value=L"Choose…";if(item->itemID!=UINT(-1)){int n=int(SendMessageW(item->hwndItem,CB_GETLBTEXTLEN,item->itemID,0));if(n>=0){value.assign(size_t(n)+1,0);SendMessageW(item->hwndItem,CB_GETLBTEXT,item->itemID,reinterpret_cast<LPARAM>(value.data()));value.resize(n);}}
            SynthGlass::text(g,value,{float(r.left+13),float(r.top),float(r.right-r.left-26),float(r.bottom-r.top)},12.5f);return TRUE;
        }
        if(item->CtlType==ODT_BUTTON){Gdiplus::Graphics g(item->hDC);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);wchar_t value[160]{};GetWindowTextW(item->hwndItem,value,160);const auto& r=item->rcItem;
            controlBackdrop(g,item->hwndItem);
            SynthGlass::button(g,{float(r.left),float(r.top),float(r.right-r.left),float(r.bottom-r.top)},value,buttonIcon(item->CtlID),GetPropW(item->hwndItem,L"SynthGlass.Hot")!=nullptr,(item->itemState&ODS_SELECTED)!=0,(item->itemState&ODS_DISABLED)!=0);return TRUE;}
    }
    if(message==WM_NOTIFY&&!filling){auto header=reinterpret_cast<NMHDR*>(lp);
        if(header->code==LVN_ITEMCHANGED){if(header->idFrom==508)selection();if(header->idFrom==538){int at=ListView_GetNextItem(child(538),-1,LVNI_SELECTED);const auto& watches=field(model,"watches").items;selectedWatch=at>=0&&size_t(at)<watches.size()?watches[at].textOr("id"):"";}}
    }
    if(message==WM_COMMAND&&!filling){int id=LOWORD(wp),event=HIWORD(wp);
        if(id==501&&event==EN_CHANGE){if(mode=="people"){if(text(501).empty()&&SendMessageW(child(504),CB_GETCURSEL,0,0)==1)SendMessageW(child(504),CB_SETCURSEL,0,0);renderPeople();}else catalog();return 0;}
        if(id==523&&event==BN_CLICKED){SendMessageW(child(504),CB_SETCURSEL,0,0);label(501,"");renderPeople();return 0;}
        if((id==504&&event==CBN_SELCHANGE)||(id==505&&event==BN_CLICKED)){renderPeople();return 0;}
        if(event!=BN_CLICKED)return 0;
        if(id==502){if(mode=="people"){SendMessageW(child(504),CB_SETCURSEL,1,0);queue(obj({{"action",str("search")},{"query",str(text(501))}}));renderPeople();}else catalog();}
        if(id==503||id==539)queue(obj({{"action",str(mode=="people"?"refresh_people":"refresh_market")}}));
        if(id==512||id==515){auto rows=chosen();if(rows.size()>1)queue(obj({{"action",str("tag_many")},{"player_ids",playerIds(rows)},{"label",str(id==515?"":text(510))},{"clear_tags",SynthScan::boolean(id==515)}}));else if(!rows.empty())queue(obj({{"action",str("tag")},{"player_id",field(rows.front(),"id")},{"label",str(id==515?"":text(510))},{"alert",SynthScan::boolean(SendMessageW(child(511),BM_GETCHECK,0,0)==BST_CHECKED)}}));}
        if(id==521)queue(obj({{"action",str("mark_org")},{"player_ids",playerIds(chosen())}}));
        if(id==520||(id==514&&chosen().size()>1)){auto rows=inviteCandidates(id==520);auto session=model.textOr("session_token");if(rows.empty())label(590,"No eligible players to invite.");else if(showRecipients(rows)){if(session!=model.textOr("session_token"))label(590,"Session changed. Review the recipients again.");else queue(obj({{"action",str("party_many")},{"player_ids",playerIds(rows)},{"org_only",SynthScan::boolean(id==520)},{"confirmed",SynthScan::boolean(true)}}));}}
        if(id==522)showRecipients(field(model,"batch_results").items,true);
        if(id==517){wchar_t value[80]{};int at=int(SendMessageW(child(516),CB_GETCURSEL,0,0));if(at>=0){SendMessageW(child(516),CB_GETLBTEXT,at,reinterpret_cast<LPARAM>(value));auto existing=text(510);if(!existing.empty())existing+=", ";label(510,existing+utf8(value));}}
        if(id==513||(id==514&&chosen().size()==1)){auto recipients=chosen();auto p=recipients.begin();if(p!=recipients.end()){
            auto prompt=wide(std::string(id==513?"Send a friend request to ":"Send a party invitation to ")+p->textOr("handle")+"?");
            auto session=model.textOr("session_token");auto recipient=field(*p,"id");
            if(MessageBoxW(page,prompt.c_str(),L"Confirm player",MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)==IDYES){if(session!=model.textOr("session_token"))label(590,"Session changed. Select the player again.");else queue(obj({{"action",str(id==513?"friend":"party")},{"player_id",recipient},{"confirmed",SynthScan::boolean(true)}}));}}}
        if(id==537){int at=int(SendMessageW(child(530),CB_GETCURSEL,0,0));auto q=text(532),p=text(534);char* end=nullptr;double price=p.empty()?0:std::strtod(p.c_str(),&end);
            if(at<0||size_t(at)>=items.size()||q.empty()||q.find_first_not_of("0123456789")!=std::string::npos||q.size()>4||(!p.empty()&&(!end||*end))){label(590,"Choose an item and enter a whole-number quality and valid minimum price.");return 0;}
            queue(obj({{"action",str("add_watch")},{"item_id",field(items[at],"id")},{"quality",num(std::atoi(q.c_str()))},{"price",num(price)},{"unit",str(text(536))}}));}
        if(id==540||id==541)queue(obj({{"action",str(id==540?"toggle_watch":"remove_watch")},{"watch_id",str(selectedWatch)}}));
        if(id==545)queue(obj({{"action",str("dismiss_notices")}}));
        if(id==546){showMatches=!showMatches;renderMarket();}
        if(id==544){int at=ListView_GetNextItem(child(543),-1,LVNI_SELECTED);if(at>=0&&size_t(at)<notices.size()){auto url=notices[at].textOr("url");if(url.rfind("https://uexcorp.space/marketplace/item/info/",0)==0&&url.find_first_of("\r\n\t ")==std::string::npos)ShellExecuteW(page,L"open",wide(url).c_str(),nullptr,nullptr,SW_SHOWNORMAL);}}
        return 0;
    }return DefWindowProcW(hwnd,message,wp,lp);
}
}
void show(HWND parent,const std::filesystem::path& directory,const std::string& name){
    folder=directory;bool changed=mode!=name;mode=name;
    if(!page){WNDCLASSW cls{};cls.lpfnWndProc=procedure;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"SynthScanCompanion";cls.hCursor=LoadCursor(nullptr,IDC_ARROW);cls.hbrBackground=background;RegisterClassW(&cls);
        font=CreateFontW(-14,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
        page=CreateWindowExW(WS_EX_CONTROLPARENT,cls.lpszClassName,L"SynthScan companion",WS_CHILD|WS_CLIPCHILDREN|WS_CLIPSIBLINGS,0,0,620,580,parent,nullptr,cls.hInstance,nullptr);changed=true;SetTimer(page,1,1000,nullptr);}
    if(changed)createControls();SynthPages::mount(page);ShowWindow(page,SW_SHOW);
}
void close(){if(page){KillTimer(page,1);DestroyWindow(page);}page=nullptr;if(font)DeleteObject(font);font=nullptr;}
int stylePreview(const std::filesystem::path& output){
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;if(Gdiplus::GdiplusStartup(&token,&input,nullptr)!=Gdiplus::Ok)return 2;
    int result=2;{
        Gdiplus::Bitmap bitmap(1240,840,PixelFormat32bppARGB);Gdiplus::Graphics g(&bitmap);g.Clear(SynthGlass::Base);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);SynthGlass::ambient(g,{0,0,1240,840});
        SynthGlass::panel(g,{14,14,196,812},false,false,18);
        SynthGlass::rounded(g,{31,33,36,36},Gdiplus::Color(255,35,52,64),11);SynthGlass::icon(g,"directory",{38,40,22,22});SynthGlass::text(g,L"SynthScan",{79,33,120,35},20,SynthGlass::Ink,true);
        SynthGlass::text(g,L"YOUR VERSE, CONNECTED",{33,79,170,20},9,SynthGlass::Muted);
        const std::vector<std::pair<std::wstring,std::string>> nav={{L"Home","home"},{L"Item & Ship Finder","directory"},{L"People","people"},{L"Server History","servers"},{L"Blueprint Library","blueprints"},{L"Mining Planner","planner"},{L"Mining Diary","diary"},{L"Refinery","refinery"},{L"Piracy","hud_piracy"},{L"Day/Night Forecast","daylight"},{L"Automatic Acceptance","acceptance"},{L"Personal Notes","notes"},{L"Settings","settings"}};
        float ny=120;for(const auto& n:nav){bool on=n.second=="people";if(on)SynthGlass::panel(g,{24,ny,176,37},true,false,10);SynthGlass::icon(g,n.second,{37,ny+10,17,17},on?SynthGlass::Accent:SynthGlass::Muted);SynthGlass::text(g,n.first,{66,ny,128,37},11.5f,on?SynthGlass::Ink:SynthGlass::Muted,on);ny+=45;}
        SynthGlass::text(g,L"People",{242,30,600,45},30,SynthGlass::Ink,true);SynthGlass::text(g,L"A familiar face in a very large universe.",{243,79,700,24},13,SynthGlass::Muted);
        SynthGlass::panel(g,{242,123,561,38},false,false,10);SynthGlass::icon(g,"search",{255,133,18,18});SynthGlass::text(g,L"Filter this list by handle or tag",{285,123,500,38},13,SynthGlass::Muted);
        SynthGlass::button(g,{814,123,72,38},L"Clear","");SynthGlass::button(g,{896,123,139,38},L"Find player","search");SynthGlass::button(g,{1045,123,166,38},L"Refresh shard","refresh");
        SynthGlass::panel(g,{242,177,220,36});SynthGlass::text(g,L"Shard members   \u2304",{257,177,198,36},13);SynthGlass::checkbox(g,{480,186,18,18},false);SynthGlass::text(g,L"Tagged only",{509,177,120,36},12,SynthGlass::Muted);
        SynthGlass::text(g,L"128 MEMBERS  /  LIVE SHARD",{242,225,500,24},10,SynthGlass::Muted);
        std::vector<float> widths={300,230,85,170,184};const wchar_t* names[]={L"PLAYER",L"TAGS",L"ALERTS",L"RELATIONSHIP",L"SOURCE"};float x=242;
        for(int i=0;i<5;i++){SynthGlass::text(g,names[i],{x+(i?12:74),266,widths[i]-24,28},10,SynthGlass::Muted);x+=widths[i];}
        const std::vector<std::vector<std::wstring>> rows={{L"A_PLAYER_LIKE_TO_PLAY",L"Crew, Friendly",L"On",L"Party",L"Shard group"},{L"Nova Drift",L"Trader",L"Off",L"Friend",L"Shard group"},{L"Orion Atlas",L"Org Affiliate",L"On",L"Org",L"Shard group"},{L"Pilot Wildflower",L"",L"Off",L"—",L"Shard group"},{L"Starlight Echo",L"Friendly",L"Off",L"Friend",L"Shard group"},{L"Wanderer",L"",L"Off",L"—",L"Shard group"},{L"Cassiopeia",L"Crew",L"On",L"Party",L"Shard group"}};
        for(size_t i=0;i<rows.size();++i)drawPersonRow(g,{242,300+float(i)*42,969,40},rows[i],widths,i==0||i==2,i==3,i==0||i==6?Gdiplus::Color(255,116,183,255):i==1||i==4?Gdiplus::Color(255,121,225,158):SynthGlass::Muted,i==0);
        SynthGlass::panel(g,{242,615,969,180},false,false,14);SynthGlass::text(g,L"2 SELECTED",{259,625,180,25},10,SynthGlass::Accent,true);SynthGlass::text(g,L"A_PLAYER_LIKE_TO_PLAY, Orion Atlas",{440,625,744,25},12,SynthGlass::Muted);
        SynthGlass::panel(g,{259,663,192,36});SynthGlass::text(g,L"Friendly   \u2304",{273,663,163,36},13);SynthGlass::button(g,{463,663,116,36},L"Add tag","tag");SynthGlass::panel(g,{592,663,402,36});SynthGlass::text(g,L"Crew, Friendly",{606,663,375,36},13);SynthGlass::button(g,{1007,663,184,36},L"Add tags to all","check");
        SynthGlass::button(g,{259,716,160,36},L"Add friend…","friend");SynthGlass::button(g,{430,716,160,36},L"Invite selected…","invite");SynthGlass::button(g,{601,716,160,36},L"Mark org","tag");SynthGlass::button(g,{772,716,160,36},L"Remove tags","clear");SynthGlass::text(g,L"Ctrl-click or Shift-click to select multiple people",{259,761,900,24},11,SynthGlass::Muted);
        CLSID png{0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};result=bitmap.Save(output.c_str(),&png,nullptr)==Gdiplus::Ok?0:2;
    }Gdiplus::GdiplusShutdown(token);return result;
}
int preview(const std::filesystem::path& directory){
    std::filesystem::create_directories(directory);
    if(std::filesystem::exists(directory/L"companion_private.json"))return 2;
    auto at=now();Json rows=arr();
    rows.items.push_back(obj({{"id",str("demo-one")},{"handle",str("DemoPilot")},{"tag",str("Friendly, Trader, Org")},{"is_org",SynthScan::boolean(true)},{"alert",SynthScan::boolean(true)},{"is_friend",SynthScan::boolean(true)},{"relationship",str("Friend")}}));
    rows.items.push_back(obj({{"id",str("demo-two")},{"handle",str("DemoZebra")},{"tag",str("Org Affiliate")},{"is_org",SynthScan::boolean(true)},{"alert",SynthScan::boolean(false)},{"is_friend",SynthScan::boolean(true)},{"in_party",SynthScan::boolean(true)},{"relationship",str("Party + Friend")}}));
    rows.items.push_back(obj({{"id",str("demo-self")},{"handle",str("YourPilot")},{"is_self",SynthScan::boolean(true)},{"is_org",SynthScan::boolean(true)},{"is_friend",SynthScan::boolean(true)},{"in_party",SynthScan::boolean(true)},{"relationship",str("You")}}));
    Json watches=arr();watches.items.push_back(obj({{"id",str("demo-watch")},{"name",str("Carinite (Pure)")},{"quality",num(1000)},{"minimum_price",num(0)},{"enabled",SynthScan::boolean(true)},{"checked_at",num(at-60)},{"matches",arr()}}));
    write(directory/L"companion_state.json",obj({{"owner_pid",num(GetCurrentProcessId())},{"written_at",num(at)},{"session_token",str("synthetic-fixture")},
          {"rows",rows},{"search",arr()},{"roster_at",num(at-12)},{"friends_known",SynthScan::boolean(true)},{"party_known",SynthScan::boolean(true)},
          {"status",str("Synthetic preview — no game queries or outgoing requests")},{"watches",watches},{"notifications",arr()}}));
    write(directory/L"finder_market_index.json",obj({{"items",obj({{"5011",obj({{"id",num(5011)},{"name",str("Carinite (Pure)")}})}})}}));
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;Gdiplus::GdiplusStartup(&token,&input,nullptr);
    auto before=GetForegroundWindow();HWND parent=CreateWindowExW(WS_EX_NOACTIVATE,L"STATIC",L"SynthScan preview",WS_POPUP,0,0,900,700,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    SynthPages::initialize(parent);SynthPages::place(0,0,900,700,true);
    const CLSID png={0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};
    bool saved=true;
    bool tagRoute=false,watchRoute=false,heartbeatScroll=false,relationshipScroll=false,membershipScroll=false,removedAnchor=false,filterReset=false,draftPreserved=false;
    bool multiPreserved=false,markOrgRoute=false,bulkTagRoute=false,orgRecipients=false,confirmationCancelled=false;
    const bool relationshipColors=personColor(rows.items[0])==RGB(121,225,158)&&personColor(rows.items[1])==RGB(116,183,255)&&personColor(rows.items[2])==RGB(193,157,255)&&personColor(obj())==RGB(234,240,247);
    std::string scrollDiagnostics;
    for(const auto* name:{"people","buyer_alerts"}){
        show(SynthPages::host(),directory,name);MoveWindow(page,0,0,900,700,TRUE);layout();refresh(true);
        if(mode=="people"){
            // Exercise actual ListView scrolling and selection under heartbeat and
            // roster changes. These are isolated fixture records, never live users.
            Json savedModel=model,many=arr();
            for(int i=0;i<240;i++){char handle[40];sprintf_s(handle,"Pilot %03d",i);many.items.push_back(obj({{"id",str("fixture-"+std::to_string(i))},{"handle",str(handle)},{"tag",str("Friendly")}}));}
            auto put=[&](const char* key,const Json& value){for(auto& pair:model.members)if(pair.first==key){pair.second=value;return;}model.members.push_back({key,value});};
            auto heartbeat=[&](){write(directory/L"companion_state.json",model);refresh();};
            put("rows",many);heartbeat();HWND list=child(508);
            ListView_SetColumnWidth(list,0,600);ListView_SetColumnWidth(list,1,400);
            ListView_SetItemState(list,3,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);ListView_SetItemState(list,7,LVIS_SELECTED,LVIS_SELECTED);ListView_SetSelectionMark(list,3);selection();label(510,"Trader, unsaved draft");
            ListView_Scroll(list,120,1800);const int top=ListView_GetTopIndex(list),horizontal=GetScrollPos(list,SB_HORZ);
            const auto anchor=people[size_t(top)].textOr("id");RECT original{};ListView_GetItemRect(list,top,&original,LVIR_BOUNDS);
            for(int beat=0;beat<3;beat++){put("written_at",num(now()));put("status",str("Fixture heartbeat "+std::to_string(beat)));heartbeat();}
            RECT after{};ListView_GetItemRect(list,ListView_GetTopIndex(list),&after,LVIR_BOUNDS);
            heartbeatScroll=top>10&&ListView_GetTopIndex(list)==top&&after.top==original.top&&GetScrollPos(list,SB_HORZ)==horizontal;
            many.items[3].members.push_back({"is_friend",SynthScan::boolean(true)});many.items[3].members.push_back({"relationship",str("Friend")});put("rows",many);heartbeat();
            ListView_GetItemRect(list,ListView_GetTopIndex(list),&after,LVIR_BOUNDS);
            relationshipScroll=people[size_t(ListView_GetTopIndex(list))].textOr("id")==anchor&&after.top==original.top&&GetScrollPos(list,SB_HORZ)==horizontal&&selected=="fixture-3";
            many.items.insert(many.items.begin(),obj({{"id",str("new-fixture")},{"handle",str("A newly reported player")}}));put("rows",many);heartbeat();
            const int insertedTop=ListView_GetTopIndex(list);ListView_GetItemRect(list,insertedTop,&after,LVIR_BOUNDS);
            membershipScroll=people[size_t(insertedTop)].textOr("id")==anchor&&after.top==original.top&&GetScrollPos(list,SB_HORZ)==horizontal&&selected=="fixture-3";
            int selectionMark=ListView_GetSelectionMark(list);
            multiPreserved=selectedIds==std::vector<std::string>{"fixture-3","fixture-7"}&&chosen().size()==2&&selectionMark>=0&&people[size_t(selectionMark)].textOr("id")=="fixture-3";
            scrollDiagnostics="anchor "+anchor+" -> "+people[size_t(insertedTop)].textOr("id")+"; y "+std::to_string(original.top)+" -> "+std::to_string(after.top)+"; horizontal "+std::to_string(horizontal)+" -> "+std::to_string(GetScrollPos(list,SB_HORZ))+"; selected "+selected;
            draftPreserved=text(510)=="Trader, unsaved draft";
            const auto nextAnchor=people[size_t(insertedTop+1)].textOr("id");many.items.erase(many.items.begin()+insertedTop);put("rows",many);heartbeat();
            removedAnchor=people[size_t(ListView_GetTopIndex(list))].textOr("id")==nextAnchor;
            SetWindowTextW(child(501),L"Pilot");filterReset=ListView_GetTopIndex(list)==0;
            model=savedModel;SetWindowTextW(child(501),L"");write(directory/L"companion_state.json",model);refresh(true);layout();
            auto org=inviteCandidates(true);orgRecipients=org.size()==1&&org.front().textOr("id")=="demo-one";
            std::vector<Json> confirmationRows;for(int i=0;i<40;i++)confirmationRows.push_back(obj({{"handle",str("Demo org pilot "+std::to_string(i+1))}}));
            // Exercise the visible-home page capture hook, entirely offscreen.
            SetWindowPos(parent,nullptr,-32000,-32000,0,0,SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE);ShowWindow(parent,SW_SHOWNOACTIVATE);auto mounted=SynthPages::current();
            confirmationCancelled=!showRecipients(confirmationRows,false,directory/L"confirmation.png")&&SynthPages::current()==mounted;ShowWindow(parent,SW_HIDE);
        }
        HDC dc=GetDC(page),memory=CreateCompatibleDC(dc);HBITMAP bitmap=CreateCompatibleBitmap(dc,900,700);auto previous=SelectObject(memory,bitmap);
        SendMessageW(page,WM_PRINT,reinterpret_cast<WPARAM>(memory),PRF_CLIENT|PRF_CHILDREN|PRF_ERASEBKGND|PRF_NONCLIENT);
        // Native edit/combobox controls skip text painting under a hidden parent.
        // Render their actual current text explicitly for this offscreen fixture.
        for(int id:{501,504,510,516,530,532,534,536}){
            HWND h=child(id);if(!h)continue;wchar_t cls[48]{};GetClassNameW(h,cls,48);
            if(std::wstring(cls)!=L"Edit"&&std::wstring(cls)!=L"ComboBox")continue;
            RECT rect{};GetWindowRect(h,&rect);MapWindowPoints(nullptr,page,reinterpret_cast<POINT*>(&rect),2);
            if(std::wstring(cls)==L"ComboBox")rect.bottom=rect.top+26;
            FillRect(memory,&rect,editBackground);FrameRect(memory,&rect,(HBRUSH)GetStockObject(GRAY_BRUSH));rect.left+=6;
            SetBkMode(memory,TRANSPARENT);SetTextColor(memory,RGB(234,240,247));SelectObject(memory,font);
            auto value=wide(text(id));DrawTextW(memory,value.c_str(),-1,&rect,DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS);
        }
        {Gdiplus::Bitmap image(bitmap,nullptr);saved=saved&&image.Save((directory/std::filesystem::u8path(std::string(name)+".png")).c_str(),&png,nullptr)==Gdiplus::Ok;}
        SelectObject(memory,previous);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(page,dc);
        if(mode=="people"){
            ListView_SetItemState(child(508),0,LVIS_SELECTED|LVIS_FOCUSED,LVIS_SELECTED|LVIS_FOCUSED);selection();
            SendMessageW(page,WM_COMMAND,MAKEWPARAM(517,BN_CLICKED),0);SendMessageW(page,WM_COMMAND,MAKEWPARAM(512,BN_CLICKED),0);
            ListView_SetItemState(child(508),1,LVIS_SELECTED,LVIS_SELECTED);selection();
            SendMessageW(page,WM_COMMAND,MAKEWPARAM(521,BN_CLICKED),0);label(510,"Friendly");SendMessageW(page,WM_COMMAND,MAKEWPARAM(512,BN_CLICKED),0);
        }else SendMessageW(page,WM_COMMAND,MAKEWPARAM(537,BN_CLICKED),0);
    }
    for(const auto& entry:std::filesystem::directory_iterator(directory/L"companion_commands")){
        auto command=read(entry.path());
        if(command.numberOr("owner_pid")!=GetCurrentProcessId())continue;
        tagRoute=tagRoute||(command.textOr("action")=="tag"&&command.textOr("player_id")=="demo-one"&&command.textOr("label").find("Aggressive")!=std::string::npos);
        const auto& ids=field(command,"player_ids").items;bool two=ids.size()==2&&encode(ids[0])==encode(str("demo-one"))&&encode(ids[1])==encode(str("demo-two"));
        markOrgRoute=markOrgRoute||(command.textOr("action")=="mark_org"&&two);
        bulkTagRoute=bulkTagRoute||(command.textOr("action")=="tag_many"&&two&&command.textOr("label")=="Friendly");
        watchRoute=watchRoute||(command.textOr("action")=="add_watch"&&command.numberOr("quality")==1000&&command.numberOr("item_id")==5011);
    }
    write(directory/L"ui_validation.json",obj({{"tag_command",SynthScan::boolean(tagRoute)},{"buyer_watch_command",SynthScan::boolean(watchRoute)},
        {"people_heartbeat_keeps_scroll",SynthScan::boolean(heartbeatScroll)},{"people_membership_keeps_anchor_and_selection",SynthScan::boolean(membershipScroll)},
        {"people_relationship_refresh_keeps_scroll",SynthScan::boolean(relationshipScroll)},
        {"people_removed_anchor_keeps_neighbour",SynthScan::boolean(removedAnchor)},{"people_filter_resets_intentionally",SynthScan::boolean(filterReset)},
        {"people_unsaved_tags_preserved",SynthScan::boolean(draftPreserved)},{"self_purple_party_blue_friend_green_priority",SynthScan::boolean(relationshipColors)},
        {"multi_selection_and_range_anchor_preserved",SynthScan::boolean(multiPreserved)},{"mark_org_command",SynthScan::boolean(markOrgRoute)},
        {"bulk_tag_command",SynthScan::boolean(bulkTagRoute)},{"org_recipients_exclude_self_and_party",SynthScan::boolean(orgRecipients)},{"recipient_confirmation_cancelled",SynthScan::boolean(confirmationCancelled)},{"outgoing_requests_sent",num(0)}}));
    write(directory/L"scroll_diagnostics.json",obj({{"details",str(scrollDiagnostics)}}));
    close();SynthPages::close();DestroyWindow(parent);Gdiplus::GdiplusShutdown(token);
    return saved&&tagRoute&&watchRoute&&heartbeatScroll&&relationshipScroll&&membershipScroll&&removedAnchor&&filterReset&&draftPreserved&&relationshipColors&&multiPreserved&&markOrgRoute&&bulkTagRoute&&orgRecipients&&confirmationCancelled&&GetForegroundWindow()==before?0:3;
}
}
