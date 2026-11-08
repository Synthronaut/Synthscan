#pragma once
#include <windows.h>
#include "MiniJson.h"
namespace SynthDirectoryCard {
HWND create(HWND parent,int id,int x,int y,int width,int height);
void update(HWND window,const SCMiner::JsonValue& item,const SCMiner::JsonValue& shops,bool favorite);
}
