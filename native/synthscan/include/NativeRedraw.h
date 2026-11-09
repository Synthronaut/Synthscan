#pragma once
#include <windows.h>
#include <vector>

namespace NativeRedraw {
// Defer geometry and visibility together. MoveWindow(..., TRUE) paints each
// control synchronously, exposing half-finished layouts and doing duplicate work.
class Layout {
    struct Change {HWND window;int x,y,width,height;UINT flags;};
    HWND parent;std::vector<Change> changes;
public:
    explicit Layout(HWND owner):parent(owner){}
    void place(HWND child,int x,int y,int width,int height,int visible=-1){
        RECT current{};GetWindowRect(child,&current);
        MapWindowPoints(nullptr,parent,reinterpret_cast<POINT*>(&current),2);
        UINT flags=SWP_NOZORDER|SWP_NOACTIVATE|SWP_NOOWNERZORDER;
        if(current.left==x&&current.top==y)flags|=SWP_NOMOVE;
        if(current.right-current.left==width&&current.bottom-current.top==height)flags|=SWP_NOSIZE;
        // IsWindowVisible includes ancestors; use the child's own visibility bit.
        bool shown=(GetWindowLongPtrW(child,GWL_STYLE)&WS_VISIBLE)!=0;
        if(visible>=0&&shown!=bool(visible))flags|=visible?SWP_SHOWWINDOW:SWP_HIDEWINDOW;
        if((flags&(SWP_NOMOVE|SWP_NOSIZE))!=(SWP_NOMOVE|SWP_NOSIZE)||(flags&(SWP_SHOWWINDOW|SWP_HIDEWINDOW)))
            changes.push_back({child,x,y,width,height,flags});
    }
    bool apply(){
        if(changes.empty())return false;
        HDWP deferred=BeginDeferWindowPos(int(changes.size()));
        for(const auto& c:changes){
            if(!deferred)break;
            deferred=DeferWindowPos(deferred,c.window,nullptr,c.x,c.y,c.width,c.height,c.flags);
        }
        if(!deferred||!EndDeferWindowPos(deferred))
            for(const auto& c:changes)SetWindowPos(c.window,nullptr,c.x,c.y,c.width,c.height,c.flags);
        changes.clear();return true;
    }
};
}
