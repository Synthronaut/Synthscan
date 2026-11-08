#include "SynthDirectoryCard.h"
#include "SynthJson.h"
#include <gdiplus.h>
#include <windowsx.h>
#include <algorithm>
#include <map>
#include <uxtheme.h>

namespace SynthDirectoryCard {
namespace {
using namespace SynthScan;
struct Model {Json item,shops;bool favorite=false;int scroll=0,total=0;};
std::map<HWND,Model> models;
const Gdiplus::Color BG(255,19,22,28),CARD(255,27,31,38),INK(255,237,240,244),MUTED(255,151,163,178),GOLD(255,238,178,70),LINE(255,48,56,68);
void text(Gdiplus::Graphics& g,const std::string& value,float x,float y,float width,float height,float size,Gdiplus::Color color,bool bold=false){
    Gdiplus::Font font(L"Segoe UI",size,bold?Gdiplus::FontStyleBold:Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    Gdiplus::SolidBrush brush(color);Gdiplus::StringFormat format;format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);
    g.DrawString(wide(value).c_str(),-1,&font,Gdiplus::RectF(x,y,width,height),&format,&brush);
}
void rounded(Gdiplus::Graphics& g,float x,float y,float width,float height){
    Gdiplus::GraphicsPath p;float d=16;p.AddArc(x,y,d,d,180,90);p.AddArc(x+width-d,y,d,d,270,90);p.AddArc(x+width-d,y+height-d,d,d,0,90);p.AddArc(x,y+height-d,d,d,90,90);p.CloseFigure();
    Gdiplus::SolidBrush b(CARD);g.FillPath(&b,&p);Gdiplus::Pen pen(LINE);g.DrawPath(&pen,&p);
}
std::string price(double value){std::ostringstream out;out<<std::fixed<<std::setprecision(0)<<value;auto result=out.str();for(int at=int(result.size())-3;at>0;at-=3)result.insert(at,",");return result;}
void paint(HWND window){
    PAINTSTRUCT ps{};HDC dc=BeginPaint(window,&ps);RECT r{};GetClientRect(window,&r);auto& m=models[window];
    if(r.right>0&&r.bottom>0){
        Gdiplus::Bitmap bitmap(r.right,r.bottom,PixelFormat32bppPARGB);Gdiplus::Graphics g(&bitmap);g.Clear(BG);
        float scale=GetDpiForWindow(window)/96.f;g.ScaleTransform(scale,scale);g.TranslateTransform(0,-float(m.scroll));g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);
        float width=r.right/scale,pad=16,y=12;
        if(m.item.textOr("name").empty())text(g,"Select an item to see prices and places to buy it.",pad,y,width-32,40,14,MUTED);
        else {
            text(g,m.item.textOr("name"),pad,y,width-200,30,21,INK,true);
            text(g,m.favorite?"FAVORITE  ·  "+m.item.textOr("kind"):m.item.textOr("kind"),width-180,y+5,164,22,11,GOLD,true);
            text(g,"WHERE TO BUY",pad,y+35,200,20,10,MUTED,true);
            text(g,"UEX CORP · IN-GAME SHOPS",width-228,y+35,212,20,10,MUTED);
            y+=62;
            const auto& rows=field(m.shops,"rows").items;
            if(!m.item.textOr("item_id").empty()){
                if(rows.empty()){
                    std::string message=flag(m.shops,"loading")?"Checking shop prices…":flag(m.shops,"error")?"Shop lookup unavailable. Retrying automatically.":"No retail listings reported for this item.";
                    rounded(g,pad,y,width-32,61);text(g,message,pad+16,y+12,width-64,24,14,INK);
                    text(g,flag(m.shops,"loading")?"Prices and locations will appear here.":"UEX listings do not confirm current shop stock.",pad+16,y+36,width-64,18,11,MUTED);y+=73;
                }
                for(const auto& row:rows){
                    rounded(g,pad,y,width-32,88);
                    Gdiplus::Pen pin(GOLD,1.7f);g.DrawEllipse(&pin,pad+16,y+19,12.f,12.f);g.DrawLine(&pin,pad+17,y+29,pad+22,y+38);g.DrawLine(&pin,pad+27,y+29,pad+22,y+38);
                    text(g,row.textOr("shop"),pad+42,y+10,width-306,25,16,INK,true);
                    text(g,row.textOr("place"),pad+42,y+37,width-306,22,12,MUTED);
                    text(g,price(row.numberOr("price")),width-238,y+10,202,30,23,GOLD,true);
                    text(g,"aUEC / each",width-236,y+43,200,18,11,MUTED);
                    text(g,row.textOr("reported_label")+"  ·  "+row.textOr("patch_label"),pad+42,y+64,width-100,18,10,flag(row,"different_patch")?GOLD:MUTED);
                    y+=98;
                }
                auto checked=m.shops.textOr("checked_label");
                if(!checked.empty()){text(g,"Checked "+checked+(flag(m.shops,"stale")?" · cached / refresh overdue":""),pad,y,width-32,19,10,MUTED);y+=22;}
                if(!rows.empty()){text(g,"Community-reported prices · current stock is not guaranteed",pad,y,width-32,19,10,MUTED);y+=26;}
                if(flag(m.shops,"error")&&!rows.empty()){text(g,"Refresh unavailable · showing the last successful lookup",pad,y,width-32,20,11,GOLD);y+=25;}
            }
            auto notes=m.item.textOr("detail");
            if(!notes.empty()){
                text(g,"ITEM DETAILS",pad,y,width-32,20,10,MUTED,true);y+=24;
                Gdiplus::Font f(L"Segoe UI",12,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::RectF bounds;auto value=wide(notes);
                g.MeasureString(value.c_str(),-1,&f,Gdiplus::RectF(pad,y,width-32,100000),&bounds);
                text(g,notes,pad,y,width-32,bounds.Height+8,12,MUTED);y+=bounds.Height+16;
            }
        }
        m.total=int(y+10);int height=int(r.bottom/scale);m.scroll=std::clamp(m.scroll,0,std::max(0,m.total-height));
        SCROLLINFO si{sizeof(si),SIF_RANGE|SIF_PAGE|SIF_POS};si.nMax=m.total-1;si.nPage=height;si.nPos=m.scroll;SetScrollInfo(window,SB_VERT,&si,TRUE);
        Gdiplus::Graphics screen(dc);screen.DrawImage(&bitmap,0,0);
    }
    EndPaint(window,&ps);
}
LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_PAINT){paint(window);return 0;}if(message==WM_ERASEBKGND)return 1;
    if(message==WM_SIZE){InvalidateRect(window,nullptr,FALSE);return 0;}
    if(message==WM_MOUSEWHEEL||message==WM_VSCROLL||message==WM_KEYDOWN){
        auto& m=models[window];int change=0;SCROLLINFO si{sizeof(si),SIF_ALL};GetScrollInfo(window,SB_VERT,&si);
        if(message==WM_MOUSEWHEEL)change=-GET_WHEEL_DELTA_WPARAM(wp)/WHEEL_DELTA*42;
        else if(message==WM_KEYDOWN){if(wp==VK_DOWN)change=28;else if(wp==VK_UP)change=-28;else if(wp==VK_NEXT)change=int(si.nPage)-24;else if(wp==VK_PRIOR)change=24-int(si.nPage);else return DefWindowProcW(window,message,wp,lp);}
        else switch(LOWORD(wp)){case SB_LINEUP:change=-28;break;case SB_LINEDOWN:change=28;break;case SB_PAGEUP:change=-int(si.nPage);break;case SB_PAGEDOWN:change=si.nPage;break;case SB_THUMBTRACK:change=si.nTrackPos-m.scroll;break;}
        m.scroll=std::clamp(m.scroll+change,0,std::max(0,m.total-int(si.nPage)));InvalidateRect(window,nullptr,FALSE);return 0;
    }
    if(message==WM_LBUTTONDOWN)SetFocus(window);
    if(message==WM_NCDESTROY)models.erase(window);
    return DefWindowProcW(window,message,wp,lp);
}
}
HWND create(HWND parent,int id,int x,int y,int width,int height){
    WNDCLASSW cls{};cls.lpfnWndProc=procedure;cls.hInstance=GetModuleHandleW(nullptr);cls.hCursor=LoadCursor(nullptr,IDC_ARROW);cls.lpszClassName=L"SynthScanDirectoryCard";RegisterClassW(&cls);
    HWND window=CreateWindowExW(0,cls.lpszClassName,L"Item purchase details",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_VSCROLL,x,y,width,height,parent,reinterpret_cast<HMENU>(INT_PTR(id)),cls.hInstance,nullptr);
    SetWindowTheme(window,L"DarkMode_Explorer",nullptr);return window;
}
void update(HWND window,const SCMiner::JsonValue& item,const SCMiner::JsonValue& shops,bool favorite){
    if(!window)return;auto& m=models[window];if(m.item.textOr("id")!=item.textOr("id"))m.scroll=0;m.item=item;m.shops=shops;m.favorite=favorite;
    SetWindowTextW(window,wide(item.textOr("name")+" · "+shops.textOr("text")).c_str());InvalidateRect(window,nullptr,FALSE);
}
}
