#pragma once
#include <windows.h>
#include <filesystem>
#include <string>
namespace SynthCompanion {
void prewarm(HWND parent,const std::filesystem::path& directory);
void show(HWND parent,const std::filesystem::path& directory,const std::string& page);
void close();
int stylePreview(const std::filesystem::path& output);
int preview(const std::filesystem::path& directory);
}
