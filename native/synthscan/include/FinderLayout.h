#pragma once
#include "SynthJson.h"
#include <algorithm>
#include <cmath>
#include <string>

namespace FinderLayout {
struct Box {int x,y,width,height;};
struct Layout {Box query,type,category,results,details;int actions,footer;bool sideBySide;};
inline Layout calculate(int width,int height){
    width=std::max(720,width);height=std::max(650,height);
    const int content=width-40,query=content-404;
    Layout out{{20,112,query,28},{32+query,112,150,200},{194+query,112,230,250},{},{},height-64,height-25,width>=1250};
    if(out.sideBySide){
        const int left=content*36/100;
        out.results={20,155,left,height-237};out.details={40+left,155,content-left-20,height-237};
    }else{
        const int listHeight=std::clamp((height-100)*26/100,150,240);
        out.results={20,155,content,listHeight};out.details={20,171+listHeight,content,height-253-listHeight};
    }
    return out;
}
enum class Deal {Neutral,Lowest,Higher};
inline Deal compare(double value,double lowest,double highest){
    if(!std::isfinite(value)||!std::isfinite(lowest)||!std::isfinite(highest)||lowest<=0||highest<=lowest||value<=0)return Deal::Neutral;
    return value<=lowest?Deal::Lowest:Deal::Higher;
}

struct ShipHangarInfo {
    std::string hangar;      // "Small (S)", "Medium (M)", "Large (L)", "Extra Large (XL)", "Extra Small (XS)", "Capital / Docking", "Vehicle Bay / XS"
    std::string sizeLabel;   // "Size 2", "Size 3", etc.
    double length = 0;       // meters
    double width = 0;
    double height = 0;
    int size = 0;
    bool isShip = false;
    bool isGround = false;
};

inline ShipHangarInfo classifyShipHangar(const SynthScan::Json& row) {
    using namespace SynthScan;
    ShipHangarInfo info;
    auto kind = row.textOr("kind");
    auto category = row.textOr("category");
    info.isShip = (kind == "Ship");
    info.isGround = (kind == "Vehicle" || category == "Ground vehicles");
    if (!info.isShip && !info.isGround) return info;

    const auto& ship = field(row, "ship_stats");
    const auto& overview = field(row, "ship_overview");
    info.size = int(ship.numberOr("size", 0));
    info.length = overview.numberOr("length", 0);
    info.width = overview.numberOr("width", 0);
    info.height = overview.numberOr("height", 0);

    if (info.size > 0) {
        info.sizeLabel = "Size " + std::to_string(info.size);
    }

    if (info.isGround) {
        info.hangar = "Vehicle Bay / XS";
        if (info.sizeLabel.empty()) info.sizeLabel = "Ground";
        return info;
    }

    if (info.size == 1) {
        info.hangar = "Extra Small (XS)";
    } else if (info.size == 2) {
        info.hangar = "Small (S)";
    } else if (info.size == 3) {
        info.hangar = "Medium (M)";
    } else if (info.size == 4) {
        info.hangar = "Large (L)";
    } else if (info.size == 5) {
        info.hangar = "Extra Large (XL)";
    } else if (info.size >= 6) {
        info.hangar = "Capital / Docking";
    } else if (info.length > 0) {
        if (info.length < 14) {
            info.hangar = "Extra Small (XS)";
            info.size = 1;
            info.sizeLabel = "Size 1 (est.)";
        } else if (info.length <= 28.5) {
            info.hangar = "Small (S)";
            info.size = 2;
            info.sizeLabel = "Size 2 (est.)";
        } else if (info.length <= 50) {
            info.hangar = "Medium (M)";
            info.size = 3;
            info.sizeLabel = "Size 3 (est.)";
        } else if (info.length <= 75) {
            info.hangar = "Large (L)";
            info.size = 4;
            info.sizeLabel = "Size 4 (est.)";
        } else if (info.length <= 160) {
            info.hangar = "Extra Large (XL)";
            info.size = 5;
            info.sizeLabel = "Size 5 (est.)";
        } else {
            info.hangar = "Capital / Docking";
            info.size = 6;
            info.sizeLabel = "Size 6+ (est.)";
        }
    } else {
        info.hangar = "Unspecified";
    }
    return info;
}
}
