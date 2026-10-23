// SynthScan adapter, GPL-3.0-or-later; reads/calculations in vendor/ are unmodified.
#pragma once
#include "json_support.h"
#include "GlyphReader.h"
#include "TextLineReader.h"
#include "SignatureAnalyzer.h"
#include "ScreenCapture.h"
#include "ScanPanel.h"
#include "RockContents.h"
#include "LoadoutReader.h"
#include "RefineryTerminal.h"
#include <chrono>
class Engine {
public:
    Engine();
    J request(const J& request);
private:
    SCMiner::GlyphReader glyphs;
    SCMiner::TextLineReader lines;
    SCMiner::SignatureAnalyzer analyzer;
    SCMiner::ScreenCapture capture;
    SCMiner::OCREngine ocr;
    SCMiner::PanelSteadier steadier;
    int templates=0,pending=0,repeats=0,misses=0;
    std::string session;
    cv::Rect lastMarker;
    cv::Size lastFrame;
    std::chrono::steady_clock::time_point lastAt{};
    J analyze(int value);
    J scan(const cv::Mat& frame,const J& req);
    J marker(const cv::Mat& frame,bool cropped);
};
J hardware();
J advice(const J& request);
