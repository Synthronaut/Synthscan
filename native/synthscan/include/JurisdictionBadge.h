#pragma once
#include "SynthJson.h"
#include <gdiplus.h>
#include <algorithm>
#include <cmath>
#include <string>

namespace SynthScan {
struct JurisdictionBadgeModel {
    std::string title, detail;
    int red=149, green=160, blue=173;
    bool armistice=false, monitored=false, pulse=false;
    double changedAt=0;
};

inline JurisdictionBadgeModel jurisdictionBadgeModel(const Json& state, bool joined, double now) {
    JurisdictionBadgeModel result;
    result.title="MONITORING UNKNOWN";
    result.detail="Awaiting zone report · security hostility unknown";
    const auto* record=state.find("jurisdiction");
    if(!joined||!record||record->textOr("session_token")!=state.textOr("session_token"))return result;
    const auto* available=record->find("available");
    if(!available||!available->boolean)return result;
    const auto monitoring=record->textOr("monitoring","unknown");
    result.armistice=record->textOr("armistice")=="inside";
    result.monitored=monitoring=="monitored";
    if(result.armistice){
        result.title="ARMISTICE · COMBAT PROHIBITED";
        result.red=255;result.green=151;result.blue=125;
    }else if(result.monitored){
        result.title="MONITORED SPACE";
        result.red=255;result.green=202;result.blue=95;
    }else if(monitoring=="unmonitored"||monitoring=="down"){
        result.title=monitoring=="down"?"MONITORING DOWN":"UNMONITORED SPACE";
        result.red=98;result.green=204;result.blue=255;
    }
    const auto* observations=record->find("observations");
    const auto* primary=observations?observations->find(result.armistice?"armistice":"monitoring"):nullptr;
    if(!primary&&observations)primary=observations->find("jurisdiction");
    const double at=primary?primary->numberOr("observed_at"):0;
    if(at<=0||now<at)return JurisdictionBadgeModel{"MONITORING UNKNOWN","Awaiting zone report · security hostility unknown"};
    const int age=int(std::min(86400.,now-at));
    result.detail="Last report "+std::to_string(age<60?age:age/60)+(age<60?"s":"m")+" ago";
    if(result.armistice)result.detail+=" · "+std::string(result.monitored?"Monitored":monitoring=="unknown"?"Monitoring unknown":"Monitoring absent");
    auto jurisdiction=record->textOr("jurisdiction");
    if(!jurisdiction.empty())result.detail+=" · "+jurisdiction;
    result.changedAt=record->numberOr("changed_at");
    result.pulse=result.changedAt>0&&now>=result.changedAt&&now-result.changedAt<3;
    return result;
}

inline void drawJurisdictionBadge(Gdiplus::Graphics& g, const JurisdictionBadgeModel& model,
                                 float x,float y,float width,float scale,double now) {
    const float opacity=model.pulse?float(95+65*(1+std::sin((now-model.changedAt)*4.1887902))/2):30.f;
    Gdiplus::SolidBrush background(Gdiplus::Color(BYTE(opacity),BYTE(model.red),BYTE(model.green),BYTE(model.blue)));
    Gdiplus::SolidBrush foreground(Gdiplus::Color(255,BYTE(model.red),BYTE(model.green),BYTE(model.blue)));
    Gdiplus::SolidBrush detail(Gdiplus::Color(255,199,209,220));
    Gdiplus::Pen line(Gdiplus::Color(255,BYTE(model.red),BYTE(model.green),BYTE(model.blue)),1.5f*scale);
    g.FillRectangle(&background,x*scale,y*scale,width*scale,31*scale);
    const float cx=(x+15)*scale,cy=(y+15.5f)*scale;
    if(model.armistice){
        Gdiplus::PointF points[8];
        for(int i=0;i<8;i++){const double a=(i+.5)*3.141592653589793/4;points[i]=Gdiplus::PointF(cx+float(std::cos(a))*10*scale,cy+float(std::sin(a))*10*scale);}
        g.DrawPolygon(&line,points,8);g.DrawLine(&line,cx-5*scale,cy,cx+5*scale,cy);
    }else{
        g.FillEllipse(&foreground,cx-2*scale,cy-2*scale,4*scale,4*scale);
        g.DrawLine(&line,cx,cy,cx,cy+9*scale);
        g.DrawArc(&line,cx-7*scale,cy-7*scale,14*scale,14*scale,205.f,130.f);
        g.DrawArc(&line,cx-11*scale,cy-11*scale,22*scale,22*scale,205.f,130.f);
        if(!model.monitored)g.DrawLine(&line,cx-9*scale,cy+8*scale,cx+9*scale,cy-9*scale);
    }
    Gdiplus::StringFormat format;format.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);format.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);
    Gdiplus::Font title(L"Segoe UI",(width<360?10.5f:12.f)*scale,Gdiplus::FontStyleBold,Gdiplus::UnitPixel);
    Gdiplus::Font detailFont(L"Segoe UI",9*scale,Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);
    auto wideText=[](const std::string& text){int count=MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),nullptr,0);std::wstring value(count,L'\0');MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),value.data(),count);return value;};
    g.DrawString(wideText(model.title).c_str(),-1,&title,Gdiplus::RectF((x+31)*scale,(y+1)*scale,(width-36)*scale,17*scale),&format,&foreground);
    g.DrawString(wideText(model.detail).c_str(),-1,&detailFont,Gdiplus::RectF((x+31)*scale,(y+18)*scale,(width-36)*scale,12*scale),&format,&detail);
}
}
