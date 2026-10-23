// GPL-3.0-or-later. Adapter around unmodified MiningAdvice.h; multi-head power
// and strongest-first selection adapted from MinerGUI.cpp (upstream Ravaxx).
#include "engine.h"
#include "MiningAdvice.h"
#include <stdexcept>
using namespace SCMiner;
J hardware() {
    J lasers=array(),modules=array(),gadgets=array(),ships=array();
    for(const auto& l:MINING_LASERS)lasers.items.push_back(object({{"id",j(l.id)},{"name",j(l.name)},{"size",j(int(l.size))},{"slots",j(int(l.slots))},
        {"power",j(l.fracture)},{"full_range",j(l.fullRange)},{"zero_range",j(l.zeroRange)}}));
    for(const auto& m:MINING_MODULES)modules.items.push_back(object({{"id",j(m.id)},{"name",j(m.name)},{"active",j(m.active)}}));
    for(const auto& g:MINING_GADGETS)gadgets.items.push_back(object({{"id",j(g.id)},{"name",j(g.name)},{"description",j(g.blurb)}}));
    for(const auto& s:MINING_SHIPS)ships.items.push_back(object({{"id",j(s.id)},{"name",j(s.name)},{"heads",j(int(s.heads))},{"size",j(int(s.size))},{"fixed_laser",j(s.fixedLaser)}}));
    return object({{"lasers",lasers},{"modules",modules},{"gadgets",gadgets},{"ships",ships}});
}
J advice(const J& req) {
    const auto& r=member(req,"rock");RockStats rock;
    rock.mass=float(r.numberOr("mass"));rock.resistance=float(r.numberOr("resistance"));
    rock.instability=float(r.numberOr("instability"));rock.distance=float(r.numberOr("distance"));
    rock.resistanceAdjusted=flag(r,"resistance_adjusted");
    if(rock.mass<=0||rock.mass>10000000||rock.resistance<0||rock.resistance>100||rock.instability<0||rock.distance<0||rock.distance>100000)
        throw std::runtime_error("Rock values outside supported range");
    const auto ship=shipById(req.textOr("ship").c_str());
    if(!ship)throw std::runtime_error("Choose a known mining ship");
    const auto& inputs=member(req,"heads");
    if(inputs.kind!=J::Kind::Array||inputs.items.empty()||inputs.items.size()>size_t(ship->heads))throw std::runtime_error("Invalid head count");
    std::vector<MiningLoadout> heads;std::vector<int> slots;
    for(const auto& input:inputs.items) {
        double rawSlot=input.numberOr("slot",double(heads.size()+1));
        if(!std::isfinite(rawSlot)||std::floor(rawSlot)!=rawSlot||rawSlot<1||rawSlot>ship->heads)throw std::runtime_error("Invalid crew head slot");
        int slot=int(rawSlot);
        if(slot<1||slot>ship->heads||std::find(slots.begin(),slots.end(),slot)!=slots.end())throw std::runtime_error("Invalid crew head slot");
        slots.push_back(slot);
        MiningLoadout h;h.laser=laserById(input.textOr("laser").c_str());
        if(!h.laser||!laserFits(*h.laser,*ship))throw std::runtime_error("Laser does not fit ship");
        h.craftedPower=float(input.numberOr("crafted_power"));
        if(h.craftedPower< -50||h.craftedPower>100)throw std::runtime_error("Crafted power outside supported range");
        if(auto mods=input.find("modules")) {
            if(mods->kind!=J::Kind::Array||mods->items.size()>size_t(h.laser->slots))throw std::runtime_error("Too many modules");
            for(const auto& id:mods->items) {
                auto m=moduleById(id.text.c_str());if(!m)throw std::runtime_error("Unknown module");h.modules.push_back(m);
            }
        }
        heads.push_back(h);
    }
    bool actives=flag(req,"actives");
    float factor=0;for(const auto& h:heads)factor+=outputOf(h,0,actives).resistance/100;
    float own=rockOwnResistance(rock.resistance,rock.resistanceAdjusted,factor/heads.size());
    const auto gadgetId=req.textOr("gadget");
    const auto gadget=gadgetId.empty()?nullptr:gadgetById(gadgetId.c_str());
    if(!gadgetId.empty()&&!gadget)throw std::runtime_error("Unknown gadget");
    float adjusted=own*(gadget?1+gadget->resistance/100:1);
    J results=array();std::vector<std::pair<float,int>> order;
    float total=0,bestSafety=-1;int safest=-1;
    for(size_t i=0;i<heads.size();i++) {
        auto output=outputOf(heads[i],rock.distance,actives);
        float through=output.atRange*resistanceLetsThrough(adjusted,output.resistance);
        total+=through;order.push_back({through,int(i)});
        auto throttle=throttleFor(rock.mass,heads[i].laser,through);
        const float share=throttle.toHold/100;
        if(through>0&&share<=BREAK_EDGE&&share>=heads[i].laser->throttleMin) {
            float centered=1-std::fabs(share-.6f)/.6f;
            float safety=output.window*(.5f+.5f*std::max(0.f,centered));
            if(safety>bestSafety){bestSafety=safety;safest=int(i);}
        }
        results.items.push_back(object({{"head",j(slots[i])},{"laser",j(heads[i].laser->name)},{"power_through",j(through)},
            {"hold_percent",through>0?j(throttle.toHold):J()},{"possible",j(throttle.possible)},{"overpowered",j(throttle.overpowered)},
            {"window",j(output.window)},{"instability",j(output.instability)},{"full_range",j(heads[i].laser->fullRange)}}));
    }
    // Same ordering and 10% power reserve used by MinerGUI::fewestHeadsNeeded.
    std::sort(order.begin(),order.end(),[&](auto a,auto b){
        if(std::fabs(a.first-b.first)>1)return a.first>b.first;
        return outputOf(heads[a.second],rock.distance,actives).window>outputOf(heads[b.second],rock.distance,actives).window;
    });
    float needed=rock.mass*BREAK_DECAY_PER_MASS,have=0;J selected=array();
    for(auto [power,index]:order) {
        if(power<=0)continue;
        selected.items.push_back(j(slots[index]));have+=power;
        if(needed/have<=BREAK_COMFORTABLE)break;
    }
    bool comfortable=have>0&&needed/have<=BREAK_COMFORTABLE;
    if(!comfortable)selected.items.clear();
    int preferred=safest>=0?safest:0;
    MiningLoadout adviceFit=heads[preferred];
    if(!actives)adviceFit.modules=countedModules(adviceFit,false);
    BreakBalance balance;balance.needs=needed;balance.ownResistance=own;
    balance.powerThrough=[&](float resistance){
        if(safest>=0){auto one=outputOf(heads[safest],rock.distance,actives);return one.atRange*resistanceLetsThrough(resistance,one.resistance);}
        float through=0;for(const auto& h:heads){auto one=outputOf(h,rock.distance,actives);through+=one.atRange*resistanceLetsThrough(resistance,one.resistance);}return through;
    };
    auto goal=advise(rock,adviceFit,&balance);
    return object({{"heads",results},{"selected_heads",selected},{"comfortable",j(comfortable)},
        {"safest_single_head",safest>=0?j(slots[safest]):J()},{"selected_hold_percent",comfortable?j(100*needed/have):J()},
        {"possible",j(total>0&&needed/total<=1)},{"combined_hold_percent",total>0?j(100*needed/total):J()},
        {"suggested_gadget",j(goal.gadget?goal.gadget->name:"")},{"gadget_reason",j(goal.because)},
        {"actives_included",j(actives)},{"distance_metres",j(rock.distance)},
        {"assumptions",j("Estimate: upstream resistance curve and linear distance falloff; zero distance means full-power range. Configured active modules are included only when selected.")}});
}
