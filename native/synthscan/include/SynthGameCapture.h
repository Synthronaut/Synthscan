#pragma once
#ifdef _WIN32
#include <Windows.h>
#include <opencv2/core.hpp>
#include <memory>
#include <mutex>
#include <string>
namespace SCMiner {
// Captures a verified StarCitizen.exe window surface, never the desktop.
class GameWindowCapture {
public:
    GameWindowCapture();~GameWindowCapture();
    GameWindowCapture(const GameWindowCapture&)=delete;
    cv::Mat grab(HWND game,const cv::Rect& screenRegion);
    void stop();
    bool hdr() const;
    const std::string& error() const;
    double milliseconds() const;
    static bool validGame(HWND window);
private:struct Impl;std::mutex gate;std::unique_ptr<Impl> p;
};
}
#endif
