#pragma once
#include <windows.h>
#include <filesystem>
#include <functional>
#include <string>
#include "MiniJson.h"
namespace SynthFinder {
using Ownership=std::function<int(int,const std::string&)>;
void initialize(HWND owner,const std::filesystem::path& data,Ownership ownership);
void prepare(const SCMiner::JsonValue& library);
void sync(bool visible);
void activationChanged(bool active);
bool key(UINT message,WPARAM value,HWND target);
bool owns(HWND target);
void close();
bool selfTest();
}
