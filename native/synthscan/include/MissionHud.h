#pragma once
#include "SynthJson.h"
#include "HudTheme.h"
#include <iomanip>
namespace SynthScan::MissionHud {
inline std::string amount(const Json& value,bool sign=false){
    if(value.kind!=Json::Kind::Number)return "—";
    std::ostringstream out;out<<std::fixed<<std::setprecision(value.number==std::floor(value.number)?0:2)<<value.number;
    std::string s=out.str();auto dot=s.find('.');int stop=int(dot==std::string::npos?s.size():dot);
    for(int at=stop-3;at>0&&s[at-1]!='-';at-=3)s.insert(size_t(at),",");
    return sign&&value.number>0?"+"+s:s;
}
inline std::string duration(double seconds){
    if(!std::isfinite(seconds)||seconds<0)return "Start unknown";
    int total=int(seconds),hours=total/3600;std::ostringstream out;
    if(hours)out<<hours<<":";out<<std::setfill('0')<<std::setw(2)<<(total/60)%60<<":"<<std::setw(2)<<total%60;return out.str();
}
inline void draw(Gdiplus::Graphics& g,float width,float scale,int tab,const Json& model,const Json& fallback,double now,bool fresh,bool previewTabs=false){
    using namespace Gdiplus;const float logical=width/scale;
    Color accent=HudTheme::modeAccent(2),green(255,103,213,154),red(255,239,108,116);
    auto text=[&](const std::string& value,float x,float y,float size,Color color,float span=0){
        Font font(L"Segoe UI",size*scale,FontStyleRegular,UnitPixel);SolidBrush brush(color);StringFormat format;
        format.SetFormatFlags(StringFormatFlagsNoWrap);format.SetTrimming(StringTrimmingEllipsisCharacter);
        g.DrawString(wide(value).c_str(),-1,&font,RectF(x*scale,y*scale,(span>0?span:logical-x-12)*scale,25*scale),&format,&brush);
    };
    text("MISSIONS",10,8,12,accent);
    const auto& completion=field(model,"latest_completion");
    if(previewTabs){const char* labels[]={"Active","aUEC","Reputation","Runs"};float cell=(logical-32)/4;
        for(int i=0;i<4;++i){SolidBrush fill(i==tab?Color(255,31,65,52):Color(255,29,36,46));g.FillRectangle(&fill,(10+i*(cell+4))*scale,42*scale,cell*scale,24*scale);text(labels[i],20+i*(cell+4),45,11,i==tab?accent:HudTheme::Muted,cell-12);}}
    if(!fresh&&tab!=0){text("Ledger connection unavailable",10,91,17,HudTheme::Text);text("Saved records remain in Mission & Wallet Log.",10,125,12,HudTheme::Muted);return;}
    if(tab==0){
        const auto& active=field(model,"active");bool have=fresh&&!active.textOr("id").empty();
        if(fresh&&!have&&!completion.textOr("id").empty()){
            text(now-completion.numberOr("at")<90?"JUST COMPLETED":"LAST COMPLETED",10,80,11,accent);
            text(completion.textOr("title"),10,104,16,HudTheme::Text);
            text("FINISHED IN  "+completion.textOr("duration","Start unknown"),10,134,20,accent);
            const auto& lines=field(completion,"lines").items;
            for(size_t i=0;i<std::min(size_t(7),lines.size());++i)text(lines[i].text,10,172+float(i)*20,11,HudTheme::Text);
            text(completion.textOr("time")+" · observed changes correlated with completion",10,322,10,HudTheme::Muted);return;
        }
        text(have?active.textOr("title"):fallback.textOr("title","No active contract observed"),10,80,16,HudTheme::Text);
        const auto& start=field(active,"accepted_log_at");bool timed=have&&start.kind==Json::Kind::Number&&now>=start.number;
        text(timed?"ELAPSED  "+duration(now-start.number):"ELAPSED  Start unknown",10,109,20,timed?accent:HudTheme::Muted);
        text(have?"Accepted → now · wall time":"Awaiting a logged acceptance for the selected contract",10,139,10,HudTheme::Muted);
        const auto& lines=field(have?active:fallback,"lines").items;
        for(size_t i=0;i<std::min(size_t(7),lines.size());++i)text(lines[i].text,10,164+float(i)*20,11,HudTheme::Text);
        text("Listed rewards / party splits are estimates",10,322,10,HudTheme::Muted);return;
    }
    if(tab==1){
        const auto& wallet=field(model,"wallet");
        text("OBSERVED IN  "+amount(field(wallet,"incoming")),10,82,15,green,logical/2-14);
        text("OBSERVED OUT  "+amount(field(wallet,"outgoing")),logical/2,82,15,red,logical/2-12);
        text("Last balance: "+amount(field(wallet,"balance"))+" aUEC · current session",10,111,11,HudTheme::Muted);
        const auto& entries=field(wallet,"entries").items;
        if(entries.empty())text("No aUEC changes observed this session",10,163,13,HudTheme::Muted);
        for(size_t i=0;i<entries.size()&&i<4;++i){auto& row=entries[i];float y=151+float(i)*39;
            text(row.textOr("label"),10,y,12,HudTheme::Text,logical-150);text(amount(field(row,"delta"),true),logical-132,y,14,row.numberOr("delta")<0?red:green,120);
            const auto& orgs=field(row,"reward_organizations").items;
            text(row.textOr("time")+" · "+(row.textOr("classification_source")=="Mission completion correlation"?(orgs.empty()?std::string("mission window"):orgs.front().text)+" · correlated":std::string("net balance change")),10,y+19,10,HudTheme::Muted);}
    }else if(tab==2){
        bool completed=!completion.textOr("id").empty();
        text(completed?"LAST COMPLETION · "+amount(field(completion,"rep_observed"),true)+" OBSERVED REP":"REPUTATION CHANGES · CURRENT SESSION",10,82,12,completed?accent:HudTheme::Muted);
        if(completed)text("Base "+amount(field(completion,"rep_base"))+" · "+amount(field(completion,"participants"))+" participants · "+completion.textOr("comparison"),10,105,10,HudTheme::Muted);
        const auto& entries=field(field(model,"reputation"),"entries").items;
        if(entries.empty())text("No reputation changes observed this session",10,149,13,HudTheme::Muted);
        for(size_t i=0;i<entries.size()&&i<4;++i){auto& row=entries[i];float y=(completed?135:113)+float(i)*42;
            text(row.textOr("label"),10,y,12,HudTheme::Text,logical-130);text(amount(field(row,"delta"),true),logical-112,y,16,row.numberOr("delta")<0?red:green,100);
            text(row.textOr("time")+" · "+amount(field(row,"before"))+" → "+amount(field(row,"after")),10,y+20,10,HudTheme::Muted);}
    }else{
        text("RECENT MISSION OUTCOMES · SAVED HISTORY",10,82,11,HudTheme::Muted);
        const auto& runs=field(model,"runs").items;
        if(runs.empty())text("Completed or ended contracts will appear here",10,131,13,HudTheme::Muted);
        for(size_t i=0;i<runs.size()&&i<4;++i){auto& row=runs[i];float y=111+float(i)*45;
            text(row.textOr("title"),10,y,12,HudTheme::Text,logical-135);text(row.textOr("duration","Start unknown"),logical-123,y,15,accent,112);
            text(row.textOr("status")+" · aUEC Δ "+amount(field(row,"money"),true)+" · rep Δ "+amount(field(row,"rep"),true),10,y+20,10,HudTheme::Muted);}
    }
    text(flag(model,"recording")?"Net observations; intervening transactions may be combined":"Collection paused · saved observations",10,322,10,HudTheme::Muted);
}
}
