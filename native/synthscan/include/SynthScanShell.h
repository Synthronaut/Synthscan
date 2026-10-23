// SynthScan application services around the preserved native mining interface.
#pragma once
#include <string>
#include <functional>
namespace SCMiner {class MinerGUI;struct RockStats;struct RockContents;}
namespace Gdiplus {class Graphics;}
namespace SynthScan {
bool begin(bool automatic);
bool automatic();
bool gameAvailable();
bool piracyMode();
bool piracyDetails();
int piracyHeight();
int activityFooterHeight();
bool questingMode();
bool activityMode();
void drawQuesting(Gdiplus::Graphics& g,float width,float height,float scale);
bool hudLocked();
void drawPiracy(Gdiplus::Graphics& g,float width,float height,float scale);
void attach(SCMiner::MinerGUI* gui,std::function<bool(const std::string&)> confirm);
void shutdown();
void workspace(int tab=0);
int sessionHeight();
void drawSession(Gdiplus::Graphics& g,float width,float top,float height,float scale);
int uiTest(const std::string& directory);
void observeMiningRock(const SCMiner::RockStats& rock,const SCMiner::RockContents* contents,
                       const std::string& system,const std::string& place,const std::string& ship,int version);
void endMiningRock();
}
