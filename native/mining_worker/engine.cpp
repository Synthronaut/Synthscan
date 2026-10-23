// SynthScan adapter, GPL-3.0-or-later.
// Marker acceptance is adapted from upstream DevTools::runPipelineOnFiles and
// Application::processScanWithGUI. Original source and attribution: vendor/UPSTREAM.json.
#include "engine.h"
#include <algorithm>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <stdexcept>
using namespace SCMiner;
using Clock=std::chrono::steady_clock;
static J rect(const cv::Rect& r) {return object({{"x",j(r.x)},{"y",j(r.y)},{"width",j(r.width)},{"height",j(r.height)}});}
Engine::Engine() {
    cv::setNumThreads(2);
    templates=glyphs.loadTemplates("./glyphs");
    if(templates<=0||!lines.loadEmbedded())throw std::runtime_error("Embedded mining readers failed to load");
}
J Engine::analyze(int value) {
    J result=array();
    for(const auto& r:analyzer.analyzeSignature(value)) {
        if(r.difference>=1)continue;
        const char* category=r.category==SignalCategory::ShipMining?"ship_mining":r.category==SignalCategory::ROCMining?"roc":r.category==SignalCategory::FPSMining?"hand":"salvage";
        result.items.push_back(object({{"name",j(r.name)},{"count",j(r.clusterSize)},{"category",j(category)},
            {"difference",j(r.difference)},{"in_scope",j(r.inSelectedSystem)},{"combination",j(r.combination)}}));
        if(result.items.size()>=16)break;
    }
    return result;
}
J Engine::marker(const cv::Mat& frame,bool cropped) {
    cv::Rect whole(0,0,frame.cols,frame.rows),area=whole;
    cv::Point aim(frame.cols/2,frame.rows/2);
    if(!cropped&&frame.rows>=540) {
        // Application::defaultAimBox: HUD scales with height, not screen width.
        int width=std::max(40,int(std::lround(frame.rows*352.0/1440)));
        int height=std::max(20,int(std::lround(frame.rows*180.0/1440)));
        int margin=std::max(50,int(std::lround(frame.rows*250.0/1440)));
        aim.y=int(std::lround(frame.rows*475.0/1440));
        area=cv::Rect(aim.x-width/2-margin,aim.y-height/2-margin,width+2*margin,height+2*margin)&whole;
        // Follow the last accepted region; return to the aim area after misses.
        if(lastMarker.area()>0&&misses<3) {
            int pad=std::max(80,lastMarker.height*6);
            area=(cv::Rect(lastMarker.x-pad,lastMarker.y-pad,lastMarker.width+2*pad,lastMarker.height+2*pad)&area);
        }
    }
    if(area.area()<=0)return J();
    auto single=[&](int v){return analyzer.isSingleSignature(v);};
    auto sum=[&](int v){return analyzer.isKnownSignature(v);};
    auto known=[&](int v){return analyzer.explainsExactly(v);};
    auto table=analyzer.knownSignatures();
    cv::Mat search=frame(area);
    std::vector<cv::Rect> labels=cropped?std::vector<cv::Rect>{cv::Rect(0,0,search.cols,search.rows)}:capture.locateSignatureLabels(search,12);
    std::stable_sort(labels.begin(),labels.end(),[&](const auto& a,const auto& b){return cv::norm(a.tl()+cv::Point(a.width/2,a.height/2)+area.tl()-aim)<cv::norm(b.tl()+cv::Point(b.width/2,b.height/2)+area.tl()-aim);});
    struct Retry{cv::Rect label;GlyphReader::Reading reading;};std::vector<Retry> retry;
    int value=0,nearest=3;std::string method;double certainty=0,pin=0;cv::Rect where;
    for(const auto& label:labels) {
        GlyphReader::Reading read;
        cv::Rect hint;
        if(!cropped)if(auto row=capture.rowOf(label))hint=*row-label.tl();
        auto glyph=glyphs.read(search(label),&read,single,&table,sum,hint.area()>0?&hint:nullptr,nearest-->0);
        if(glyph) {
            std::string name;int count=0;
            const bool one=analyzer.isExactMatch(*glyph,name,count);
            const bool mixed=!one&&analyzer.isKnownSignature(*glyph);
            if(GlyphReader::goodEnough(read)&&(one||(mixed&&GlyphReader::wellPinned(read))||(read.unknown&&GlyphReader::strictlyGood(read)))
                &&!GlyphReader::ambiguousValue(read,sum,GlyphReader::ambiguityLead())) {
                value=*glyph;method="glyphs";certainty=read.mean/100;pin=read.pinScore;where=label+area.tl();
                const auto opinion=lines.judge(search,label.tl(),read,value,known);
                if(opinion.verdict==TextLineReader::Verdict::Differs){value=opinion.value;method="neural_override";certainty=opinion.line.mean;}
                break;
            }
        }
        if(read.markerLikely&&read.pinScore>=GlyphReader::OCR_MIN_PIN&&read.digitBox.area()>0&&retry.size()<2)retry.push_back({label,read});
    }
    if(!value)for(const auto& trial:retry) {
        auto opinion=lines.judge(search,trial.label.tl(),trial.reading,std::nullopt,known);
        if(opinion.verdict!=TextLineReader::Verdict::Reads)continue;
        value=opinion.value;method="neural";certainty=opinion.line.mean;pin=trial.reading.pinScore;where=trial.label+area.tl();break;
    }
    if(!value){misses++;pending=0;repeats=0;return J();}
    auto now=Clock::now();
    if(value==pending&&now-lastAt<std::chrono::seconds(3))repeats++;else{pending=value;repeats=1;}
    lastAt=now;lastMarker=where;misses=0;
    return object({{"value",j(value)},{"accepted",j(repeats>=2)},{"repeats",j(repeats)},
                   {"method",j(method)},{"ocr_confidence",j(certainty)},{"pin_score",j(pin)},
                   {"box",rect(where)},{"candidates",analyze(value)}});
}
J Engine::scan(const cv::Mat& frame,const J& req) {
    if(frame.empty())throw std::runtime_error("Empty image");
    if(frame.size()!=lastFrame) {
        lastFrame=frame.size();lastMarker={};pending=repeats=misses=0;steadier.forget();
    }
    GlyphReader::setHudScale(flag(req,"cropped")?1.0:double(frame.rows)/GlyphReader::REFERENCE_VIEWPORT_HEIGHT);
    J out=object({{"marker",flag(req,"marker",true)?marker(frame,flag(req,"cropped")):J()}});
    if(flag(req,"panel")) {
        auto panel=readScanPanel(frame,ocr,&glyphs,&lines);
        RockStats rock=panel.stats;bool settled=false;
        if(panel.found&&!panel.figures[0].likeness.empty())settled=steadier.add(panel,rock);
        else settled=panel.found&&panel.figuresRead>=3&&rock.mass>0;
        J body=object({{"found",j(panel.found)},{"settled",j(settled)},{"figures_read",j(panel.figuresRead)},{"box",rect(panel.box)}});
        if(settled) {
            body.members.push_back({"stats",object({{"mass",j(rock.mass)},{"resistance",j(rock.resistance)},{"resistance_adjusted",j(rock.resistanceAdjusted)},
                {"instability",j(rock.instability)},{"scu",j(rock.scu)},{"ore",j(rock.ore)}})});
            if(flag(req,"contents")) {
                RockContents contents;readRockContents(frame,panel,rock.ore,lines,contents);J parts=array();
                for(const auto& p:contents.parts)parts.items.push_back(object({{"ore",j(p.ore)},{"inert",j(p.inert)},{"percent",j(p.percent)},{"quality",j(p.quality)}}));
                body.members.push_back({"contents",object({{"whole",j(contents.whole)},{"sum",j(contents.sum)},{"parts",parts}})});
            }
            if(auto fit=req.find("fit")) {
                J inputs=*fit;
                inputs.members.push_back({"rock",object({{"mass",j(rock.mass)},{"resistance",j(rock.resistance)},
                    {"instability",j(rock.instability)},{"resistance_adjusted",j(rock.resistanceAdjusted)},
                    {"distance",j(fit->numberOr("distance"))}})});
                try{out.members.push_back({"advice",advice(inputs)});}
                catch(const std::exception& error){out.members.push_back({"advice_error",j(error.what())});}
            }
        }
        out.members.push_back({"panel",body});
    }
    if(flag(req,"loadout")) {
        SeenLoadout fit;readSeenLoadout(frame,lines,fit);J modules=array();for(auto m:fit.modules)modules.items.push_back(j(m->id));
        out.members.push_back({"loadout",object({{"complete",j(fit.complete())},{"laser",j(fit.laser?fit.laser->id:"")},{"modules",modules}})});
    }
    if(flag(req,"refinery")) {
        auto bars=findRefineryBars(frame);auto screen=readRefineryScreen(frame,bars,lines);J panels=array();
        for(const auto& p:screen.panels){J rows=array();for(const auto& r:p.rows)rows.items.push_back(object({{"material",j(r.material)},{"quality",j(r.quality)},{"yield_cscu",j(r.yield)}}));
            const char* status=p.kind==RefineryBar::Band::Completed?"completed":p.kind==RefineryBar::Band::Processing?"processing":"setup";
            panels.items.push_back(object({{"number",j(p.order)},{"status",j(status)},{"whole",j(p.whole())},{"seconds",j(p.seconds)},{"method",j(p.method)},{"rows",rows}}));}
        out.members.push_back({"refinery",object({{"station_text",j(screen.stationText)},{"panels",panels}})});
    }
    return out;
}
J Engine::request(const J& req) {
    const auto op=req.textOr("op");
    if(op=="hello")return object({{"schema",j(1)},{"engine",j("SynthScan Native Mining")},{"templates",j(templates)},{"neural_ready",j(lines.ready())}});
    if(op=="hardware")return hardware();
    if(op=="advice")return advice(req);
    if(op=="analyze")return analyze(int(req.numberOr("value")));
    const auto next=req.textOr("session");
    if(next!=session){session=next;pending=repeats=misses=0;lastMarker={};steadier.forget();}
    analyzer.setSystemFilter(req.textOr("system"));analyzer.setPlaceFilter(req.textOr("place"));
    auto ground=req.textOr("ground");analyzer.setGround(ground=="space"?SignatureAnalyzer::Ground::Space:ground=="surface"?SignatureAnalyzer::Ground::Surface:SignatureAnalyzer::Ground::Unknown);
    if(op=="scan_file") {
        // OpenCV's Windows narrow filename overload cannot open Unicode paths.
        std::ifstream file(std::filesystem::u8path(req.textOr("path")),std::ios::binary|std::ios::ate);
        const auto size=file.tellg();
        if(!file||size<=0||size>128*1024*1024)throw std::runtime_error("Frame file is missing, empty or too large");
        std::vector<unsigned char> bytes(static_cast<size_t>(size));file.seekg(0);
        if(!file.read(reinterpret_cast<char*>(bytes.data()),size))throw std::runtime_error("Could not read frame file");
        return scan(cv::imdecode(bytes,cv::IMREAD_COLOR),req);
    }
    if(op=="scan_live") {
        HWND game=ScreenCapture::gameWindow();
        if(!game||GetForegroundWindow()!=game)return object({{"inactive",j(true)}});
        auto view=ScreenCapture::gameViewport();if(!view)return object({{"inactive",j(true)}});
        CaptureRegion region;region.x=view->x;region.y=view->y;region.width=view->width;region.height=view->height;region.autoDetect=false;
        auto taken=std::chrono::system_clock::now();
        auto out=scan(capture.captureRegion(region),req);
        out.members.push_back({"observed_at",j(std::chrono::duration<double>(taken.time_since_epoch()).count())});return out;
    }
    throw std::runtime_error("Unknown operation");
}
