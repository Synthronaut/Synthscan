#pragma once
#include <windows.h>
#include <filesystem>
#include <string>
namespace SynthCompanion {
void show(HWND parent,const std::filesystem::path& directory,const std::string& page);
void close();
int preview(const std::filesystem::path& directory);
}
