#pragma once
#include <Windows.h>
#include <filesystem>
namespace SynthPrivacy {
void show(HWND parent,const std::filesystem::path& directory);
void close();
}
