#pragma once
#include "SynthJson.h"
#include "FinderLayout.h"
#include "HudTheme.h"
#include <gdiplus.h>
#include <functional>
#include <algorithm>
#include <cmath>
#include <vector>
#include <filesystem>
#include <iomanip>
#include <sstream>

// Paint-only content. No window, capture, focus or transparency changes.
namespace FinderCards {
using namespace SynthScan;
inline const Gdiplus::Color Ink=HudTheme::Text,Muted=HudTheme::Muted,Accent=HudTheme::modeAccent(4),Card(255,24,26,30),Green(255,92,215,162),Red(255,245,127,130);
struct Link {Gdiplus::RectF rect;std::string url;};
inline std::string money(double value){std::ostringstream out;out<<std::fixed<<std::setprecision(0)<<value;auto s=out.str();for(int at=int(s.size())-3;at>0;at-=3)s.insert(at,",");return s;}
inline std::string quantity(double value){std::ostringstream out;out<<std::setprecision(6)<<value;return out.str();}
struct Canvas {
    Gdiplus::Graphics& g;float width,scale,pad=12,clipTop=0,clipBottom=100000;std::vector<Link> links;
    float inner()const{return width-2*pad*scale;}
    float left()const{return pad*scale;}
    void box(float x,float y,float w,float h){
        float d=12*scale;Gdiplus::GraphicsPath p;p.AddArc(x,y,d,d,180,90);p.AddArc(x+w-d,y,d,d,270,90);p.AddArc(x+w-d,y+h-d,d,d,0,90);p.AddArc(x,y+h-d,d,d,90,90);p.CloseFigure();Gdiplus::SolidBrush brush(Card);g.FillPath(&brush,&p);
    }
    void line(const std::string& value,float x,float y,float w,float size,Gdiplus::Color color,bool bold=false){
        Gdiplus::Font f(L"Segoe UI",size*scale,bold?Gdiplus::FontStyleBold:Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::StringFormat fmt;fmt.SetFormatFlags(Gdiplus::StringFormatFlagsNoWrap);fmt.SetTrimming(Gdiplus::StringTrimmingEllipsisCharacter);Gdiplus::SolidBrush brush(color);auto text=wide(value);g.DrawString(text.c_str(),-1,&f,Gdiplus::RectF(x,y,w,(size+7)*scale),&fmt,&brush);
    }
    float text(const std::string& value,float x,float y,float w,float size,Gdiplus::Color color,bool bold=false){
        Gdiplus::Font f(L"Segoe UI",size*scale,bold?Gdiplus::FontStyleBold:Gdiplus::FontStyleRegular,Gdiplus::UnitPixel);Gdiplus::StringFormat fmt;Gdiplus::RectF bounds;auto string=wide(value);g.MeasureString(string.c_str(),-1,&f,Gdiplus::RectF(x,y,w,10000),&fmt,&bounds);Gdiplus::SolidBrush brush(color);g.DrawString(string.c_str(),-1,&f,Gdiplus::RectF(x,y,w,bounds.Height+2),&fmt,&brush);return bounds.Height;
    }
    float heading(const std::string& label,float y){line(label,left()+2*scale,y,inner(),10,Accent,true);return y+24*scale;}
    float note(const std::string& label,float y){return y+text(label,left()+4*scale,y,inner()-8*scale,10,Muted)+8*scale;}
    float shops(const Json& view,float y){
        y=heading("WHERE TO BUY",y);const auto& rows=field(view,"rows").items;double low=0,high=0;
        for(const auto& row:rows){double price=row.numberOr("price");if(std::isfinite(price)&&price>0){if(!low||price<low)low=price;high=std::max(high,price);}}
        if(rows.empty())y=note(flag(view,"error")?"Shop lookup unavailable. Retrying automatically.":"No retail purchase locations reported for this item.",y);
        for(const auto& row:rows){
            float x=left(),w=inner(),right=x+w-182*scale;box(x,y,w,84*scale);
            Gdiplus::Pen pin(Accent,1.5f*scale);g.DrawEllipse(&pin,x+12*scale,y+12*scale,9*scale,9*scale);g.DrawLine(&pin,x+13*scale,y+20*scale,x+16.5f*scale,y+27*scale);g.DrawLine(&pin,x+20*scale,y+20*scale,x+16.5f*scale,y+27*scale);
            line(row.textOr("shop","Shop"),x+32*scale,y+9*scale,w-224*scale,14,Ink,true);
            line(row.textOr("place","Location not reported"),x+12*scale,y+34*scale,w-204*scale,12,Ink);
            line(row.textOr("reported_label")+" · "+row.textOr("patch_label"),x+12*scale,y+62*scale,w-204*scale,9,flag(row,"different_patch")?Accent:Muted);
            auto deal=FinderLayout::compare(row.numberOr("price"),low,high);auto color=deal==FinderLayout::Deal::Lowest?Green:deal==FinderLayout::Deal::Higher?Red:Accent;
            line(money(row.numberOr("price")),right,y+6*scale,170*scale,23,color,true);line("aUEC / each",right+2*scale,y+35*scale,168*scale,10,Muted);
            line(deal==FinderLayout::Deal::Lowest?"LOWEST LISTED PRICE":deal==FinderLayout::Deal::Higher?"+"+money(row.numberOr("price")-low)+" vs lowest":"LISTED PURCHASE PRICE",right+2*scale,y+62*scale,168*scale,9,color,true);y+=94*scale;
        }
        auto checked=view.textOr("checked_label");if(!checked.empty())y=note("UEX · checked "+checked+(flag(view,"stale")?" · cached / overdue":""),y);
        if(!rows.empty())y=note("Community-reported prices · stock is not guaranteed",y);
        if(flag(view,"error")&&!rows.empty())y=note("Refresh unavailable · retaining the last successful lookup",y);
        return y+5*scale;
    }
    float market(const Json& view,float y,int selectedQuality){
        auto message=view.textOr("message");if(!message.empty())y=note(message,y);
        for(const auto& section:field(view,"sections").items){
            y=heading(section.textOr("operation")=="sell"?"SELLER ASKS":"BUY REQUESTS",y);
            for(const auto& summary:field(section,"summaries").items){
                bool reliable=flag(summary,"reliable");auto grade=selectedQuality?"Q"+std::to_string(selectedQuality):summary.numberOr("quality")>0?"Q"+std::to_string(int(summary.numberOr("quality"))):"Quality unspecified";
                box(left(),y,inner(),reliable?88*scale:58*scale);
                line(grade+" · per "+summary.textOr("unit"),left()+12*scale,y+8*scale,inner()-24*scale,11,Muted,true);
                if(reliable){
                    line(money(summary.numberOr("low"))+" – "+money(summary.numberOr("high"))+" aUEC",left()+12*scale,y+29*scale,inner()-24*scale,21,Accent,true);
                    line("Median "+money(summary.numberOr("median"))+" · "+std::to_string(int(summary.numberOr("count")))+" comparable ads · middle 50%",left()+12*scale,y+63*scale,inner()-24*scale,10,Muted);
                }else line("Only "+std::to_string(int(summary.numberOr("count")))+" comparable ads · no reliable estimate",left()+12*scale,y+30*scale,inner()-24*scale,12,Ink);
                y+=(reliable?98:68)*scale;
            }
            if(field(section,"offers").items.empty())y=note("No matching comparable advertisements.",y);
            for(const auto& offer:field(section,"offers").items){
                float x=left(),w=inner(),right=x+w-182*scale;box(x,y,w,84*scale);
                line(offer.textOr("title"),x+12*scale,y+9*scale,w-204*scale,13,Ink,true);
                std::string grade=offer.numberOr("quality")>0?"Q"+std::to_string(int(offer.numberOr("quality"))):"Quality unspecified";
                auto place=offer.textOr("location");line(grade+(place.empty()?"":" · "+place),x+12*scale,y+35*scale,w-204*scale,11,Ink);
                line("Updated "+offer.textOr("updated_label"),x+12*scale,y+62*scale,w-204*scale,9,Muted);
                line(money(offer.numberOr("price")),right,y+6*scale,170*scale,23,Accent,true);line("aUEC / "+offer.textOr("unit"),right+2*scale,y+35*scale,168*scale,10,Muted);
                line("OPEN LISTING ↗",right+2*scale,y+62*scale,168*scale,9,Accent,true);
                if(y>=clipTop&&y+84*scale<=clipBottom)links.push_back({{x,y,w,84*scale},offer.textOr("url")});y+=94*scale;
            }
            if(section.numberOr("rejected")>0)y=note(std::to_string(int(section.numberOr("rejected")))+" implausible-price or mixed-quality ads excluded",y);
            if(section.numberOr("total")>10)y=note("Showing 10 of "+std::to_string(int(section.numberOr("total")))+" comparable ads",y);
        }
        if(flag(view,"limited"))y=note("UEX listing limit reached · partial view",y);
        auto checked=view.textOr("checked_label");if(!checked.empty())y=note("UEX · checked "+checked+(flag(view,"stale")?" · cached / overdue":""),y);
        return note("Advertisements, not confirmed sales · listing patch is not supplied by UEX",y);
    }
    float mounts(const Json& row,float y){
        const auto& ship=field(row,"ship_stats");const auto& ports=field(ship,"hardpoints");const auto& groups=field(ports,"groups").items;if(groups.empty())return y;
        y=heading("COMPONENT SLOTS & WEAPON MOUNTS",y+8*scale);float cell=(inner()-10*scale)/2;
        for(size_t i=0;i<groups.size();++i){const auto& part=groups[i];float x=left()+(i%2)*(cell+10*scale),top=y+(i/2)*59*scale;box(x,top,cell,51*scale);int minimum=std::max(1,int(part.numberOr("minimum"))),maximum=int(part.numberOr("maximum"));auto size=minimum==maximum?"S"+std::to_string(maximum):"S"+std::to_string(minimum)+"–S"+std::to_string(maximum);
            line(part.textOr("label"),x+10*scale,top+5*scale,cell-20*scale,10,Muted,true);line(std::to_string(int(part.numberOr("count")))+" × "+size,x+10*scale,top+23*scale,cell-20*scale,18,Accent,true);
        }
        y+=((groups.size()+1)/2)*59*scale;y=note("Stock mounts / turrets · required tags may limit swaps · "+ship.textOr("patch"),y);
        if(ports.textOr("status")=="partial")y=note("Some mount limits unavailable; only resolved slots shown",y);return y;
    }
    float blueprints(const Json& row,float y,const std::function<int(int,const std::string&)>& ownership){
        const auto& blueprints=field(row,"finder_blueprints").items;
        if(blueprints.empty())return row.textOr("kind")=="Ship"||row.textOr("kind")=="Vehicle"?y:note("No creation blueprint recorded in this catalog.",y+6*scale);
        for(const auto& bp:blueprints){
            y=heading("CRAFTING BLUEPRINT",y+8*scale);y+=text(bp.textOr("name"),left()+4*scale,y,inner()-8*scale,15,Ink,true)+5*scale;
            int state=ownership?ownership(int(bp.numberOr("reference_index",-1)),bp.textOr("reference_name")):-1;bool starter=flag(bp,"known_from_start");
            y+=text(starter?"Available by default":state==1?"✓ Recorded as obtained":state==2?"Possibly obtained · not confirmed":"Not recorded as obtained",left()+4*scale,y,inner()-8*scale,11,starter||state==1?Green:Muted)+12*scale;
            line("MATERIALS",left()+4*scale,y,inner(),10,Muted,true);y+=22*scale;
            if(field(bp,"materials").items.empty())y=note("Recipe inputs not recorded.",y);
            for(const auto& material:field(bp,"materials").items){
                box(left(),y,inner(),46*scale);line(material.textOr("material"),left()+10*scale,y+5*scale,inner()-180*scale,13,Ink,true);line(quantity(material.numberOr("amount"))+" "+material.textOr("unit"),left()+inner()-160*scale,y+5*scale,150*scale,14,Accent,true);
                auto quality=material.numberOr("min_quality");line(quality>0?"Minimum Q"+std::to_string(int(quality)):"Any quality",left()+10*scale,y+27*scale,inner()-20*scale,10,Muted);y+=53*scale;
            }
            if(!flag(bp,"recipe_verified"))y=note("Older recipe reference · verify inputs in game",y);
            if(!starter&&state!=1){
                y=heading("UNLOCK MISSIONS",y+5*scale);if(field(bp,"missions").items.empty())y=note("No known mission source in this catalog.",y);
                for(const auto& mission:field(bp,"missions").items){
                    y+=text(mission.textOr("title"),left()+4*scale,y,inner()-8*scale,13,Ink,true)+3*scale;y=note(mission.textOr("faction")+" · "+mission.textOr("system")+" · "+mission.textOr("standing"),y);
                }
                y=note("Source: "+bp.textOr("unlock_source","Reference data")+" · pools do not guarantee a particular reward",y);
            }
        }return y;
    }
};
// Raster-only QA: exercises the production painters without creating windows or
// injecting input, so it is safe to run while the player has the game open.
inline bool selfTest(const std::filesystem::path& preview={}){
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;if(Gdiplus::GdiplusStartup(&token,&input,nullptr)!=Gdiplus::Ok)return false;
    bool ok=true;
    {
        auto save=[&](Gdiplus::Bitmap& bitmap,const wchar_t* filename){
            if(preview.empty())return true;
            std::filesystem::create_directories(preview);UINT count=0,bytes=0;Gdiplus::GetImageEncodersSize(&count,&bytes);std::vector<BYTE> memory(bytes);auto encoders=reinterpret_cast<Gdiplus::ImageCodecInfo*>(memory.data());
            if(Gdiplus::GetImageEncoders(count,bytes,encoders)!=Gdiplus::Ok)return false;
            for(UINT i=0;i<count;++i)if(std::wstring(encoders[i].MimeType)==L"image/png")return bitmap.Save((preview/filename).c_str(),&encoders[i].Clsid,nullptr)==Gdiplus::Ok;return false;
        };
        Json shops=obj({{"rows",arr()},{"checked_label",str("synthetic preview")}});
        for(int i=0;i<2;++i){auto row=obj({{"shop",str(i?"New Deal · Lorville":"New Deal · Orison")},{"place",str(i?"Hurston · Lorville":"Crusader · Orison")},{"price",num(i?28009800:29484000)},{"reported_label",str("Synthetic quote")},{"patch_label",str("test fixture")}});shops.members[0].second.items.push_back(row);}
        Gdiplus::Bitmap bitmap(544,680,PixelFormat32bppPARGB);Gdiplus::Graphics g(&bitmap);g.Clear(Gdiplus::Color(255,15,16,19));g.SetTextRenderingHint(Gdiplus::TextRenderingHintAntiAliasGridFit);Canvas c{g,544,1};
        c.line("Crusader M2 Hercules · HUD preview",12,10,520,19,Ink,true);float y=c.shops(shops,48);
        auto groups=arr();for(auto pair:{std::pair<const char*,int>{"Shields",2},{"Quantum drive",1},{"Power plants",2},{"Coolers",2},{"Guns",2},{"Turret guns",6}})groups.items.push_back(obj({{"label",str(pair.first)},{"count",num(pair.second)},{"minimum",num(pair.first==std::string("Guns")?5:pair.first==std::string("Turret guns")?4:3)},{"maximum",num(pair.first==std::string("Guns")?5:pair.first==std::string("Turret guns")?4:3)}}));
        auto ship=obj({{"ship_stats",obj({{"patch",str("synthetic test layout")},{"hardpoints",obj({{"status",str("ready")},{"groups",groups}})}})}});y=c.mounts(ship,y);ok=ok&&y>300&&y<680&&save(bitmap,L"finder_hud_shops.png");
        auto summaries=arr();summaries.items.push_back(obj({{"unit",str("piece")},{"quality",num(975)},{"count",num(8)},{"reliable",SynthScan::boolean(true)},{"low",num(750000)},{"high",num(1250000)},{"median",num(950000)}}));
        auto offers=arr();offers.items.push_back(obj({{"title",str("Afarite · Q975")},{"quality",num(975)},{"price",num(950000)},{"unit",str("piece")},{"location",str("Stanton")},{"updated_label",str("synthetic preview")},{"url",str("https://uexcorp.space/marketplace/")}}));
        auto sections=arr();sections.items.push_back(obj({{"operation",str("sell")},{"summaries",summaries},{"offers",offers}}));auto market=obj({{"sections",sections},{"checked_label",str("synthetic preview")}});
        Gdiplus::Bitmap marketBitmap(544,430,PixelFormat32bppPARGB);Gdiplus::Graphics mg(&marketBitmap);mg.Clear(Gdiplus::Color(255,15,16,19));mg.SetTextRenderingHint(Gdiplus::TextRenderingHintAntiAliasGridFit);Canvas mc{mg,544,1};mc.line("Afarite · player-market HUD preview",12,10,520,19,Ink,true);auto bottom=mc.market(market,48,975);ok=ok&&bottom>200&&bottom<430&&mc.links.size()==1&&save(marketBitmap,L"finder_hud_market.png");
        auto materials=arr();materials.items.push_back(obj({{"material",str("Copper")},{"amount",num(2.5)},{"unit",str("SCU")},{"min_quality",num(900)}}));materials.items.push_back(obj({{"material",str("Iron")},{"amount",num(.75)},{"unit",str("SCU")}}));
        auto missions=arr();missions.items.push_back(obj({{"title",str("Example reward mission")},{"faction",str("Example faction")},{"system",str("Stanton")},{"standing",str("Neutral")}}));auto blueprints=arr();blueprints.items.push_back(obj({{"name",str("Example component · synthetic recipe")},{"materials",materials},{"missions",missions},{"recipe_verified",SynthScan::boolean(true)},{"unlock_source",str("Synthetic preview")}}));auto item=obj({{"kind",str("Component")},{"finder_blueprints",blueprints}});
        Gdiplus::Bitmap recipeBitmap(544,480,PixelFormat32bppPARGB);Gdiplus::Graphics rg(&recipeBitmap);rg.Clear(Gdiplus::Color(255,15,16,19));rg.SetTextRenderingHint(Gdiplus::TextRenderingHintAntiAliasGridFit);Canvas rc{rg,544,1};auto recipeBottom=rc.blueprints(item,10,[](int,const std::string&){return 0;});ok=ok&&recipeBottom>200&&recipeBottom<480&&save(recipeBitmap,L"finder_hud_blueprints.png");
    }
    Gdiplus::GdiplusShutdown(token);return ok;
}
}
