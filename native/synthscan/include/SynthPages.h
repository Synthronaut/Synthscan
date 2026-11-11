#pragma once
#include <windows.h>
namespace SynthPages {
void initialize(HWND main);
void place(int x,int y,int width,int height,bool visible);
void mount(HWND page,int cropTop=0);
void release(HWND page);
void hide();
void close();
bool contains(HWND page);
HWND host();
HWND current();
HWND daylightPage();
unsigned generation();
void advanceGeneration();
void beginTransition();
void endTransition();
void scrollTo(int y);
}
