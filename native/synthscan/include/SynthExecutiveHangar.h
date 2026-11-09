#pragma once
#include <windows.h>
#include <filesystem>
#include <functional>
#include "MiniJson.h"
namespace SynthExecutiveHangar {
void show(HWND parent,std::function<bool(SCMiner::JsonValue)> action);
void update(const SCMiner::JsonValue& inventory,const SCMiner::JsonValue& timing,bool busy,const std::string& note);
void close();
int preview(const std::filesystem::path& directory);
}
