#pragma once
#include <windows.h>
#include <filesystem>
namespace SynthMissionLog {
void show(HWND parent,const std::filesystem::path& directory);
void close();
}
