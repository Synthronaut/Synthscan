// Offline regression probe, or one passive foreground-game capture. No input.
#include "ScanPanel.h"
#include "Application.h"
#include "RockValuation.h"
#include "ScreenCapture.h"
#include "RockContents.h"
#include "TextLineReader.h"
#include "SynthJson.h"
#include <iostream>
#include <fstream>

int main(int argc,char** argv) {
    if(argc<3)return 2;
    if(std::string(argv[1])=="--hud") {
        if(argc<4)return 2;
        const HWND hwnd=FindWindowW(L"SCMinerGUI",nullptr);DWORD owner=0;if(hwnd)GetWindowThreadProcessId(hwnd,&owner);
        if(!hwnd||owner!=(DWORD)std::strtoul(argv[3],nullptr,10)||!IsWindowVisible(hwnd))return 8;
        RECT rc{};GetClientRect(hwnd,&rc);HDC dc=GetDC(hwnd),mem=CreateCompatibleDC(dc);
        BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=rc.right;bi.bmiHeader.biHeight=-rc.bottom;
        bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
        void* pixels=nullptr;HBITMAP bitmap=CreateDIBSection(dc,&bi,DIB_RGB_COLORS,&pixels,nullptr,0);auto old=SelectObject(mem,bitmap);
        const BOOL printed=PrintWindow(hwnd,mem,PW_CLIENTONLY);bool saved=false;
        if(printed&&pixels)saved=cv::imwrite(argv[2],cv::Mat(rc.bottom,rc.right,CV_8UC4,pixels));
        SelectObject(mem,old);DeleteObject(bitmap);DeleteDC(mem);ReleaseDC(hwnd,dc);return saved?0:9;
    }
    cv::setNumThreads(2);
    if(const char* localization=std::getenv("SYNTHSCAN_TEST_LOCALIZATION"))SCMiner::loadOreNameAliases(localization);
    cv::Mat frame;
    if(std::string(argv[1])=="--capture"||std::string(argv[1])=="--capture-only") {
        auto game=SCMiner::ScreenCapture::gameWindow();DWORD target=0,foreground=0;
        if(game)GetWindowThreadProcessId(game,&target);
        GetWindowThreadProcessId(GetForegroundWindow(),&foreground);
        if(!game||!target||target!=foreground){std::cout<<"Game is not foreground; no capture taken.\n";return 6;}
        auto viewport=SCMiner::ScreenCapture::gameViewport();if(!viewport)return 7;
        SCMiner::ScreenCapture capture;SCMiner::CaptureRegion region;
        region.x=viewport->x;region.y=viewport->y;region.width=viewport->width;region.height=viewport->height;region.autoDetect=false;
        frame=capture.captureRegion(region);
        if(!frame.empty())cv::imwrite(std::string(argv[2])+".png",frame);
        if(std::string(argv[1])=="--capture-only")return frame.empty()?3:0;
    } else frame=cv::imread(argv[1]);
    if(frame.empty())return 3;
    SCMiner::TextLineReader lines;if(!lines.loadEmbedded())return 4;
    SCMiner::OCREngine ocr;SCMiner::OCRConfig cfg;ocr.initialize(cfg);
    SCMiner::GlyphReader glyphs;SCMiner::ScanPanel panel;
    const int passes=std::getenv("SYNTHSCAN_PROBE_PASSES")?std::max(1,std::atoi(std::getenv("SYNTHSCAN_PROBE_PASSES"))):20;
    for(int i=0;i<passes;i++)panel=SCMiner::readScanPanel(frame,ocr,&glyphs,&lines);
    using namespace SynthScan;
    Json out=obj({{"found",SynthScan::boolean(panel.found)},{"mass",num(panel.stats.mass)},{"resistance",num(panel.stats.resistance)},{"instability",num(panel.stats.instability)},{"scu",num(panel.stats.scu)},
      {"ore",str(panel.stats.ore)},{"note",str(panel.note)},{"labels_x",num(panel.labels.x)},
      {"labels_y",num(panel.labels.y)},{"label_scale",num(panel.labelScale)}});
    if(argc>=6){panel.labels={std::atoi(argv[3]),std::atoi(argv[4])};panel.labelScale=std::atof(argv[5]);}
    SCMiner::RockContents contents;SCMiner::readRockContents(frame,panel,panel.stats.ore,lines,contents);
    Json parts=arr();for(auto& p:contents.parts)parts.items.push_back(obj({{"ore",str(p.ore)},{"percent",num(p.percent)},
      {"quality",num(p.quality)},{"share_text",str(p.shareText)},{"name_text",str(p.nameText)},{"quality_text",str(p.qualityText)}}));
    out.members.push_back({"partial",SynthScan::boolean(contents.partial)});out.members.push_back({"estimate_ready",SynthScan::boolean(SCMiner::contentsEstimateReady(contents))});out.members.push_back({"parts",parts});out.members.push_back({"whole",SynthScan::boolean(contents.whole)});out.members.push_back({"contents_note",str(contents.note)});
    auto crop=SCMiner::rockContentsRegion(panel,frame.size());
    if(!crop.empty()) {
        auto moved=panel;moved.labels-=crop.tl();SCMiner::RockContents runtime;
        SCMiner::readRockContents(frame(crop).clone(),moved,panel.stats.ore,lines,runtime);
        out.members.push_back({"runtime_crop_whole",SynthScan::boolean(runtime.whole)});
        out.members.push_back({"runtime_crop_estimate_ready",SynthScan::boolean(SCMiner::contentsEstimateReady(runtime))});
        out.members.push_back({"runtime_crop_note",str(runtime.note)});
        out.members.push_back({"runtime_crop_parts",num(runtime.parts.size())});
    }
    if(const char* cache=std::getenv("SYNTHSCAN_PROBE_PRICE_CACHE")) {
        std::string note;auto prices=SCMiner::Application::loadRockPrices(cache,"4.10.2",note);
        SCMiner::RockValue value;if(prices)value=prices->estimate(panel.stats.scu,contents,"Stanton",2,(long long)std::time(nullptr));
        out.members.push_back({"value",obj({{"scanned",SynthScan::boolean(value.scanned)},{"raw_known",SynthScan::boolean(value.rawKnown)},
            {"raw",num(value.raw)},{"refined_known",SynthScan::boolean(value.refinedKnown)},{"refined_before_fees",num(value.refined)},
            {"player_coverage",num(value.playerCoverage)}})});
    }
    if(std::getenv("SYNTHSCAN_PROBE_CANDIDATES")) {
        Json candidates=arr();auto region=cv::Rect(int(frame.cols*.54),int(frame.rows*.35),int(frame.cols*.30),int(frame.rows*.30));
        auto all=SCMiner::figureLineCandidates(frame,region,20);auto white=SCMiner::whiteFigureLineCandidates(frame,region,20);all.insert(all.end(),white.begin(),white.end());
        for(const auto& f:all) {
            SCMiner::ScanPanel candidate;auto first=lines.read(frame(f.rows[1]));
            bool read=SCMiner::readPanelRows(frame,lines,f.rows,f.values,candidate);
            candidates.items.push_back(obj({{"first",str(first.text)},{"read",SynthScan::boolean(read)},{"note",str(candidate.note)},
                {"x",num(f.rows[1].x)},{"y",num(f.rows[1].y)},{"w",num(f.rows[1].width)},{"h",num(f.rows[1].height)},{"off",num(f.off)}}));
        }
        out.members.push_back({"candidates",candidates});
    }
    if(argc>=10){auto r=cv::Rect(std::atoi(argv[6]),std::atoi(argv[7]),std::atoi(argv[8]),std::atoi(argv[9]))&cv::Rect(0,0,frame.cols,frame.rows);auto line=lines.read(frame(r));out.members.push_back({"line",str(line.text)});out.members.push_back({"certainty",num(line.mean)});}
    std::ofstream file(argv[2]);file<<encode(out);return file.good()?0:5;
}
