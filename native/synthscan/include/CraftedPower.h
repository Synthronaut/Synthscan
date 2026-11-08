#pragma once
#include <cmath>
#include <cstdio>
#include <string>

namespace SCMiner {
// One final item bonus. Material contributions are already combined by the
// game; integrity does not enter the mining-power calculation.
inline bool parseCraftedPower(const std::string& text,float& value) {
    size_t first=text.find_first_not_of(" \t\r\n");
    if(first==std::string::npos){value=0;return true;}
    size_t last=text.find_last_not_of(" \t\r\n");
    if(text[last]=='%'){
        if(last==first)return false;
        last=text.find_last_not_of(" \t",last-1);
    }
    size_t at=first;double sign=1,result=0,place=0.1;bool point=false,digit=false;
    if(text[at]=='-'||text[at]=='+'){sign=text[at]=='-'?-1:1;at++;}
    if(last-at>16)return false;
    for(;at<=last;at++){
        const char c=text[at];
        if(c=='.'&&!point){point=true;continue;}
        if(c<'0'||c>'9')return false;
        digit=true;
        if(point){result+=(c-'0')*place;place*=0.1;}else result=result*10+c-'0';
    }
    result*=sign;
    if(!digit||!std::isfinite(result)||result< -50||result>100)return false;
    value=float(result);return true;
}

inline std::string craftedPowerText(float value) {
    char buffer[48];std::snprintf(buffer,sizeof(buffer),"%.4f",value);
    std::string out=buffer;
    while(out.size()>1&&out.back()=='0')out.pop_back();
    if(!out.empty()&&out.back()=='.')out.pop_back();
    return out=="-0"?"0":out;
}
}
