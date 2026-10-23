#pragma once
#include "SynthJson.h"
#include <functional>
namespace SynthScanDiary {
void initialize(HWND owner,const std::filesystem::path& data,bool testing,std::function<void(SynthScan::Json)> send);
void open();
void update(const SynthScan::Json& model,const SynthScan::Json& result,const std::string& note);
void close();
HWND window();
HWND previewWindow();
}
