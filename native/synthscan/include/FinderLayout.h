#pragma once
#include <algorithm>
#include <cmath>
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
}
