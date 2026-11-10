#pragma once
#include <windows.h>
#include <filesystem>
#include <functional>
#include <string>
#include "SynthJson.h"

namespace SynthWebView {
bool available();
bool active();
bool attach(HWND parent, const std::filesystem::path& dataFolder, const std::string& mode, std::function<void(const SynthScan::Json&)> onCommand);
void setCatalog(const SynthScan::Json& catalog);
void setDesktopState(const SynthScan::Json& desktop);
void pushSnapshot(const std::string& mode, const SynthScan::Json& state, const SynthScan::Json& marketItems, const SynthScan::Json& homeOverview);
void resize(int width, int height);
void detach();
int preview(const std::filesystem::path& directory);
}
