#pragma once
#include <Windows.h>
#include <filesystem>

namespace SynthRoulette {
void show(HWND parent, const std::filesystem::path& directory);
void close();
}
