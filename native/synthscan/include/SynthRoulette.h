#pragma once
#include <Windows.h>
#include <filesystem>
#include <functional>
#include <string>

namespace SynthRoulette {
using NavigateFn = std::function<void(const std::string& kind, int bpIndex, const std::wstring& target)>;
void show(HWND parent, const std::filesystem::path& directory,
          std::function<bool(int)> isOwnedFn = {},
          std::function<bool(int)> isWantedFn = {},
          NavigateFn onNavigateFn = {});
void close();
}
