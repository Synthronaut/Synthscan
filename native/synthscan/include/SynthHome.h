#pragma once
#include <windows.h>
#include <filesystem>
#include <functional>
#include <string>
#include "MiniJson.h"
namespace SynthHome {
void initialize(HWND owner,const std::filesystem::path& data,std::function<void(const std::string&)> action);
void update(const SCMiner::JsonValue& overview,const std::string& identity,bool connected);
void show();
void hide();
void close();
bool routeMessage(MSG& message);
bool visible();
}
