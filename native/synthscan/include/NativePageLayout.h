#pragma once
#include "WorkspaceLayout.h"
#include <windows.h>
#include <commctrl.h>
#include <vector>
#include <string>

namespace NativePageLayout {
// Retain original control geometry once. Resizing never recreates editors or
// modifies their contents, selections, checkboxes or scroll positions.
class Controls {
    struct Control {HWND window;int id;WorkspaceLayout::Box box;};
    std::vector<Control> controls;
public:
    void capture(HWND parent,double scale){
        controls.clear();
        for(HWND child=GetWindow(parent,GW_CHILD);child;child=GetWindow(child,GW_HWNDNEXT)){
            RECT rect{};GetWindowRect(child,&rect);MapWindowPoints(nullptr,parent,reinterpret_cast<POINT*>(&rect),2);
            int height=rect.bottom-rect.top;wchar_t type[64]{};GetClassNameW(child,type,64);
            if(std::wstring(type)==L"ComboBox"){RECT drop{};if(SendMessageW(child,CB_GETDROPPEDCONTROLRECT,0,reinterpret_cast<LPARAM>(&drop)))height=drop.bottom-drop.top;}
            controls.push_back({child,GetDlgCtrlID(child),{int(rect.left/scale+.5),int(rect.top/scale+.5),int((rect.right-rect.left)/scale+.5),int(height/scale+.5)}});
        }
    }
    template<class Layout> void apply(HWND parent,double scale,Layout layout){
        RECT client{};GetClientRect(parent,&client);
        for(const auto& control:controls)if(IsWindow(control.window)){
            auto box=layout(control.box,control.id,int(client.right/scale+.5),int(client.bottom/scale+.5));
            MoveWindow(control.window,int(box.x*scale+.5),int(box.y*scale+.5),int(box.width*scale+.5),int(box.height*scale+.5),TRUE);
        }
        InvalidateRect(parent,nullptr,FALSE);
    }
    void clear(){controls.clear();}
};
}
