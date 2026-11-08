#pragma once
#include <windows.h>
namespace SynthMenus {
int track(HMENU menu,UINT flags,int x,int y,int reserved,HWND owner,const RECT* exclude);
bool message(UINT message,WPARAM w,LPARAM l,LRESULT& result);
}
