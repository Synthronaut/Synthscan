#include "SynthPrivacy.h"
#include "SynthPages.h"
#include "SynthJson.h"
#include "SynthCapturePrivacy.h"
#include "ScreenCapture.h"
#include <gdiplus.h>
#include <commdlg.h>
#include <memory>

namespace SynthPrivacy { namespace {
using namespace SynthScan;
HWND window=nullptr;HFONT font=nullptr;HBRUSH bg=nullptr;std::filesystem::path data;
SCMiner::ScreenCapture capture;cv::Mat preview;std::wstring message;float scale=1;
const COLORREF BACK=RGB(15,16,19),INK=RGB(238,239,241),CYAN=RGB(98,204,255);
void label(int id,const wchar_t* text,int x,int y,int width,int height,DWORD style=SS_LEFT){auto h=CreateWindowExW(0,L"STATIC",text,WS_CHILD|WS_VISIBLE|style,int(x*scale),int(y*scale),int(width*scale),int(height*scale),window,(HMENU)INT_PTR(id),nullptr,nullptr);SendMessageW(h,WM_SETFONT,(WPARAM)font,TRUE);}
void button(int id,const wchar_t* text,int x,int y,int width,DWORD style=BS_OWNERDRAW){auto h=CreateWindowExW(0,L"BUTTON",text,WS_CHILD|WS_VISIBLE|WS_TABSTOP|style,int(x*scale),int(y*scale),int(width*scale),int(34*scale),window,(HMENU)INT_PTR(id),nullptr,nullptr);SendMessageW(h,WM_SETFONT,(WPARAM)font,TRUE);}
bool accountAllowed(){auto p=read(data/L"capture_privacy.json",4096);return flag(p,"account_access",false);}
void status(){
    if(!SynthEdition::screenReading){SetDlgItemTextW(window,10,L"STANDARD · SCREEN READING NOT INSTALLED");SetDlgItemTextW(window,11,message.c_str());return;}
    auto policy=CapturePrivacy::policy();SetDlgItemTextW(window,1,policy.paused?L"Resume capture":L"Pause capture");
    std::wstring state=policy.paused?L"CAPTURE PAUSED":!SCMiner::ScreenCapture::gameWindow()?L"WAITING FOR STAR CITIZEN":L"GAME WINDOW ONLY · LOCAL OCR";
    SetDlgItemTextW(window,10,state.c_str());SetDlgItemTextW(window,11,message.c_str());
}
void layout(){
    if(!window)return;auto child=GetWindow(window,GW_CHILD);while(child){auto next=GetWindow(child,GW_HWNDNEXT);DestroyWindow(child);child=next;}
    RECT r{};GetClientRect(window,&r);scale=std::max(.7f,GetDpiForWindow(window)/96.f);int width=int(r.right/scale);
    label(0,L"Privacy & capture",24,18,width-48,34);label(10,L"",24,64,width-48,26);
    label(0,L"Only the verified StarCitizen.exe window is captured. OCR stays on this PC.\r\nDesktop capture fallback and automatic image saving are disabled.",24,104,width-48,52);
    button(1,L"Pause capture",24,170,180);button(3,L"Preview game capture",218,170,220);button(5,L"Clear preview",452,170,150);
    button(2,L"Pause when I leave the game",24,220,width-48,BS_AUTOCHECKBOX);SendDlgItemMessageW(window,2,BM_SETCHECK,CapturePrivacy::policy().pauseUnfocused?BST_CHECKED:BST_UNCHECKED,0);
    button(6,L"Allow game-account features: missions, reputation and Citizens",24,264,width-48,BS_AUTOCHECKBOX);SendDlgItemMessageW(window,6,BM_SETCHECK,accountAllowed()?BST_CHECKED:BST_UNCHECKED,0);
    label(0,L"Account features use the game's existing session credential directly with CIG.\r\nThis permission is separate from screen reading. No password is requested.",24,306,width-48,52);
    label(11,L"",24,365,width-48,44);button(4,L"Save this preview as PNG…",24,414,260);EnableWindow(GetDlgItem(window,4),!preview.empty());
    label(0,L"Preview is kept in memory only and cleared when you leave this page.\r\nOnly Save writes an image. No automatic screenshot upload is provided.",24,462,width-48,50);
    if(!SynthEdition::screenReading){
        for(int id:{1,2,3,4,5})ShowWindow(GetDlgItem(window,id),SW_HIDE);
        // Replace capture explanation while preserving the account permission.
        auto h=GetWindow(window,GW_CHILD);while(h){int id=GetDlgCtrlID(h);RECT rr{};GetWindowRect(h,&rr);MapWindowPoints(nullptr,window,reinterpret_cast<POINT*>(&rr),2);if(id==0&&(rr.top==int(104*scale)||rr.top==int(462*scale)))ShowWindow(h,SW_HIDE);h=GetWindow(h,GW_HWNDNEXT);}
        label(20,L"This edition has no screen capture provider, capture packages or OCR models.\r\nScreen reading cannot be enabled in Settings. Install Full explicitly to add it.",24,104,width-48,72);
    }
    status();InvalidateRect(window,nullptr,FALSE);
}
LRESULT CALLBACK proc(HWND hwnd,UINT msg,WPARAM w,LPARAM l){
    if(msg==WM_SIZE){layout();return 0;}
    if(msg==WM_SHOWWINDOW&&!w){capture.releaseWindowCapture();preview.release();message.clear();EnableWindow(GetDlgItem(hwnd,4),FALSE);return 0;}
    if(msg==WM_TIMER){if(!IsWindowVisible(hwnd)){capture.releaseWindowCapture();preview.release();message.clear();EnableWindow(GetDlgItem(hwnd,4),FALSE);}else status();return 0;}
    if(msg==WM_ERASEBKGND)return 1;
    if(msg==WM_CTLCOLORSTATIC||msg==WM_CTLCOLORBTN){SetTextColor((HDC)w,INK);SetBkColor((HDC)w,BACK);return (LRESULT)bg;}
    if(msg==WM_DRAWITEM){auto d=(DRAWITEMSTRUCT*)l;HBRUSH b=CreateSolidBrush(d->itemState&ODS_SELECTED?RGB(28,63,82):RGB(28,31,37));FillRect(d->hDC,&d->rcItem,b);DeleteObject(b);SetBkMode(d->hDC,TRANSPARENT);SetTextColor(d->hDC,CYAN);SelectObject(d->hDC,font);wchar_t text[160]{};GetWindowTextW(d->hwndItem,text,160);DrawTextW(d->hDC,text,-1,&d->rcItem,DT_CENTER|DT_VCENTER|DT_SINGLELINE);return TRUE;}
    if(msg==WM_COMMAND){
        int id=LOWORD(w);
        if(id==1){auto p=CapturePrivacy::policy();p.paused=!p.paused;CapturePrivacy::set(p);capture.releaseWindowCapture();preview.release();message=p.paused?L"Screen reading is paused across capture features.":L"Capture resumed for Star Citizen only.";status();InvalidateRect(hwnd,nullptr,FALSE);}
        if(id==2){auto p=CapturePrivacy::policy();p.pauseUnfocused=SendDlgItemMessageW(hwnd,2,BM_GETCHECK,0,0)==BST_CHECKED;CapturePrivacy::set(p);}
        if(id==6){auto p=read(data/L"capture_privacy.json",4096);if(p.kind!=Json::Kind::Object)p=obj({{"schema",num(1)}});bool allow=SendDlgItemMessageW(hwnd,6,BM_GETCHECK,0,0)==BST_CHECKED;bool found=false;for(auto& pair:p.members)if(pair.first=="account_access"){pair.second=SynthScan::boolean(allow);found=true;}if(!found)p.members.push_back({"account_access",SynthScan::boolean(allow)});write(data/L"capture_privacy.json",p);message=allow?L"Game-account features enabled.":L"Account requests disabled. An already-running request may finish.";status();}
        if(id==3){preview=capture.captureScreen();if(preview.empty()&&SCMiner::ScreenCapture::gameWindow()&&!CapturePrivacy::policy().paused)preview=capture.captureScreen();capture.releaseWindowCapture();message=preview.empty()?wide(capture.captureNote()):L"This is the game-window image available to screen readers. It has not been saved.";EnableWindow(GetDlgItem(hwnd,4),!preview.empty());status();InvalidateRect(hwnd,nullptr,FALSE);}
        if(id==5){capture.releaseWindowCapture();preview.release();EnableWindow(GetDlgItem(hwnd,4),FALSE);message=L"Preview cleared from this page.";status();InvalidateRect(hwnd,nullptr,FALSE);}
        if(id==4&&!preview.empty()){
            wchar_t name[32768]=L"SynthScan-game-capture.png";OPENFILENAMEW file{sizeof(file)};file.hwndOwner=hwnd;file.lpstrFilter=L"PNG image\0*.png\0\0";file.lpstrFile=name;file.nMaxFile=32768;file.lpstrDefExt=L"png";file.Flags=OFN_OVERWRITEPROMPT|OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST;
            if(GetSaveFileNameW(&file)){std::vector<unsigned char> png;if(cv::imencode(".png",preview,png)){std::ofstream out(std::filesystem::path(name),std::ios::binary);out.write((char*)png.data(),png.size());message=out?L"Preview saved to your chosen file. Review it before sharing.":L"Could not save this preview.";status();}}
        }
        return 0;
    }
    if(msg==WM_PAINT){PAINTSTRUCT ps;HDC dc=BeginPaint(hwnd,&ps);RECT r{};GetClientRect(hwnd,&r);FillRect(dc,&r,bg);
        if(!preview.empty()){
            int y=int(530*scale),available=r.bottom-y-int(18*scale);if(available>20){
                cv::Mat image;float factor=std::min(float(r.right-48*scale)/preview.cols,float(available)/preview.rows);cv::resize(preview,image,{},factor,factor,cv::INTER_AREA);cv::cvtColor(image,image,cv::COLOR_BGR2BGRA);
                BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=image.cols;info.bmiHeader.biHeight=-image.rows;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
                SetDIBitsToDevice(dc,int(24*scale),y,image.cols,image.rows,0,0,0,image.rows,image.data,&info,DIB_RGB_COLORS);
            }
        }EndPaint(hwnd,&ps);return 0;
    }
    return DefWindowProcW(hwnd,msg,w,l);
}
}
void show(HWND parent,const std::filesystem::path& directory){
    data=directory;if(!window){WNDCLASSW c{};c.hInstance=GetModuleHandleW(nullptr);c.lpszClassName=L"SynthScanPrivacy";c.lpfnWndProc=proc;c.hCursor=LoadCursor(nullptr,IDC_ARROW);RegisterClassW(&c);bg=CreateSolidBrush(BACK);font=CreateFontW(-MulDiv(17,int(GetDpiForWindow(parent)),96),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");window=CreateWindowExW(WS_EX_CONTROLPARENT,c.lpszClassName,L"Privacy & capture",WS_CHILD|WS_CLIPCHILDREN,0,0,900,800,parent,nullptr,c.hInstance,nullptr);SetTimer(window,1,500,nullptr);layout();}
    SynthPages::mount(window);ShowWindow(window,SW_SHOW);status();
}
void close(){capture.releaseWindowCapture();preview.release();if(window){KillTimer(window,1);DestroyWindow(window);window=nullptr;}if(font){DeleteObject(font);font=nullptr;}if(bg){DeleteObject(bg);bg=nullptr;}}
}
