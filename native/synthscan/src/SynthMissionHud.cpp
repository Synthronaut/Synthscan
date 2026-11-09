// Bitmap-only fixture: no windows, capture, account queries or input events.
#include "MissionHud.h"
#include <filesystem>
namespace SynthScan {
int missionHudPreview(const std::filesystem::path& output){
    Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;
    if(Gdiplus::GdiplusStartup(&token,&input,nullptr)!=Gdiplus::Ok)return 2;
    int result=2;{
        Json lines=arr();for(auto value:{"Objective: Deliver supplies to the outpost","Listed payout: 30,000 aUEC","Accepted participants: 3","Equal-split estimate: 10,000 aUEC each","Example Organization / Standing: +300 base rep","Equal-split estimate: +100 rep each"})lines.items.push_back(str(value));
        Json money=arr();money.items={obj({{"label",str("Mission · Demo supply delivery")},{"delta",num(10000)},{"classification_source",str("Mission completion correlation")},{"time",str("11-09 18:42:10")}}),obj({{"label",str("repairs · player classified")},{"delta",num(-1750)},{"time",str("11-09 18:31:08")}})};
        Json rep=arr();rep.items={obj({{"label",str("Example Organization")},{"delta",num(50)},{"before",num(1000)},{"after",num(1050)},{"time",str("11-09 18:42:11")}}),obj({{"label",str("Example Guild / Affinity")},{"delta",num(-25)},{"time",str("11-09 18:20:04")}})};
        Json runs=arr();runs.items={obj({{"title",str("Demo supply delivery")},{"duration",str("08:32")},{"status",str("Complete")},{"money",num(10000)},{"rep",num(50)}}),obj({{"title",str("Demo investigation")},{"duration",str("Start unknown")},{"status",str("Abandoned")}})};
        auto model=obj({{"recording",boolean(true)},{"active",obj({{"id",str("synthetic")},{"title",str("Demo · Supply delivery")},{"accepted_log_at",num(1000)},{"lines",lines}})},
                        {"wallet",obj({{"incoming",num(10000)},{"outgoing",num(1750)},{"balance",num(1234567)},{"entries",money}})},
                        {"reputation",obj({{"entries",rep}})},{"runs",runs}});
        Json completedLines=arr();for(auto value:{"Observed rep: +50 · configured base: 250","Accepted participants: 5","Example Organization: 1,000 → 1,050","Example Organization: Matches 1/5 split","Observed aUEC: +10,000"})completedLines.items.push_back(str(value));
        model.members.push_back({"latest_completion",obj({{"id",str("demo-finished")},{"title",str("Demo · Supply delivery")},{"at",num(1500)},{"time",str("11-09 18:42:11")},{"duration",str("08:32")},{"rep_observed",num(50)},{"rep_base",num(250)},{"participants",num(5)},{"comparison",str("Matches 1/5 split")},{"lines",completedLines}})});
        for(auto& field:model.members)if(field.first=="active")field.second=obj();
        Gdiplus::Bitmap bitmap(1260,760,PixelFormat32bppARGB);Gdiplus::Graphics g(&bitmap);g.Clear(HudTheme::Bottom);
        for(int tab=0;tab<4;++tab){auto saved=g.Save();g.TranslateTransform(float((tab%2)*630),float((tab/2)*380));
            Gdiplus::SolidBrush background(HudTheme::Top);g.FillRectangle(&background,5.f,5.f,620.f,360.f);
            MissionHud::draw(g,620,1,tab,model,Json{},1512,true,true);g.Restore(saved);}
        CLSID png{0x557cf406,0x1a04,0x11d3,{0x9a,0x73,0x00,0x00,0xf8,0x1e,0xf3,0x2e}};
        result=bitmap.Save(output.c_str(),&png,nullptr)==Gdiplus::Ok?0:2;
    }Gdiplus::GdiplusShutdown(token);return result;
}
}
