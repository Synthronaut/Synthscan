#pragma once
#include "SynthJson.h"
#include <functional>
namespace SynthScanNav {
void initialize(HWND owner,bool testing,std::function<void(SynthScan::Json)> send);
void open();
void update(const SynthScan::Json& model);
void close();
HWND window();
}
