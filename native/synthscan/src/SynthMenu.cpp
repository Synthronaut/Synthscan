#include "SynthMenu.h"
#include <deque>
#include <string>
#include <algorithm>

namespace SynthMenus {
namespace {
struct Item {std::wstring text;bool separator=false,submenu=false;};
bool active=false;HFONT font=nullptr;float scale=1;
HBRUSH background=CreateSolidBrush(RGB(24,26,30));
void prepare(HMENU menu,std::deque<Item>& storage){
    MENUINFO info{sizeof(info)};info.fMask=MIM_BACKGROUND;info.hbrBack=background;SetMenuInfo(menu,&info);
    for(int i=0;i<GetMenuItemCount(menu);i++){
        wchar_t text[1024]{};MENUITEMINFOW item{sizeof(item)};item.fMask=MIIM_FTYPE|MIIM_STRING|MIIM_SUBMENU;
        item.dwTypeData=text;item.cch=1023;if(!GetMenuItemInfoW(menu,i,TRUE,&item))continue;
        std::wstring label=text;for(size_t at;(at=label.find(L"&&"))!=std::wstring::npos;)label.replace(at,2,L"&");
        storage.push_back({label,(item.fType&MFT_SEPARATOR)!=0,item.hSubMenu!=nullptr});
        MENUITEMINFOW paint{sizeof(paint)};paint.fMask=MIIM_FTYPE|MIIM_DATA;
        paint.fType=item.fType|MFT_OWNERDRAW;paint.dwItemData=reinterpret_cast<ULONG_PTR>(&storage.back());
        SetMenuItemInfoW(menu,i,TRUE,&paint);if(item.hSubMenu)prepare(item.hSubMenu,storage);
    }
}
}
int track(HMENU menu,UINT flags,int x,int y,int reserved,HWND owner,const RECT* exclude){
    std::deque<Item> storage;prepare(menu,storage);scale=GetDpiForWindow(owner)/96.f;
    font=CreateFontW(-int(12*scale),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
    active=true;int selected=TrackPopupMenu(menu,flags,x,y,reserved,owner,exclude);active=false;
    DeleteObject(font);font=nullptr;return selected;
}
bool message(UINT message,WPARAM,LPARAM l,LRESULT& result){
    if(!active||!l)return false;
    if(message==WM_MEASUREITEM){
        auto item=reinterpret_cast<MEASUREITEMSTRUCT*>(l);if(item->CtlType!=ODT_MENU||!item->itemData)return false;
        auto& data=*reinterpret_cast<Item*>(item->itemData);HDC dc=GetDC(nullptr);auto old=SelectObject(dc,font);SIZE size{};
        GetTextExtentPoint32W(dc,data.text.c_str(),int(data.text.size()),&size);SelectObject(dc,old);ReleaseDC(nullptr,dc);
        item->itemHeight=UINT((data.separator?9:31)*scale);item->itemWidth=UINT(std::max(int(210*scale),int(size.cx)+int(66*scale)));
        result=TRUE;return true;
    }
    if(message==WM_DRAWITEM){
        auto item=reinterpret_cast<DRAWITEMSTRUCT*>(l);if(item->CtlType!=ODT_MENU||!item->itemData)return false;
        const auto& data=*reinterpret_cast<Item*>(item->itemData);bool selected=(item->itemState&ODS_SELECTED)!=0,disabled=(item->itemState&(ODS_DISABLED|ODS_GRAYED))!=0;
        HBRUSH fill=selected?CreateSolidBrush(RGB(46,50,58)):background;FillRect(item->hDC,&item->rcItem,fill);if(selected)DeleteObject(fill);
        if(data.separator){HPEN pen=CreatePen(PS_SOLID,1,RGB(44,47,54));auto old=SelectObject(item->hDC,pen);int y=(item->rcItem.top+item->rcItem.bottom)/2;MoveToEx(item->hDC,item->rcItem.left+int(12*scale),y,nullptr);LineTo(item->hDC,item->rcItem.right-int(12*scale),y);SelectObject(item->hDC,old);DeleteObject(pen);}
        else{
            SetBkMode(item->hDC,TRANSPARENT);SetTextColor(item->hDC,disabled?RGB(100,106,116):selected?RGB(238,178,70):RGB(238,239,241));auto old=SelectObject(item->hDC,font);
            RECT text=item->rcItem;text.left+=int(31*scale);text.right-=int(26*scale);DrawTextW(item->hDC,data.text.c_str(),-1,&text,DT_SINGLELINE|DT_VCENTER|DT_LEFT|DT_NOPREFIX);
            RECT mark=item->rcItem;mark.left+=int(10*scale);mark.right=mark.left+int(15*scale);
            if(item->itemState&ODS_CHECKED)DrawTextW(item->hDC,L"✓",-1,&mark,DT_SINGLELINE|DT_VCENTER|DT_LEFT);
            if(data.submenu){mark=item->rcItem;mark.left=mark.right-int(18*scale);DrawTextW(item->hDC,L"›",-1,&mark,DT_SINGLELINE|DT_VCENTER|DT_LEFT);}
            SelectObject(item->hDC,old);
        }
        result=TRUE;return true;
    }
    return false;
}
}
