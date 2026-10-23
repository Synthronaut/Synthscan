// SynthScan native adapter, GPL-3.0-or-later. Upstream copyrights retained in vendor/.
#pragma once
#include "MiniJson.h"
#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>
using J = SCMiner::JsonValue;
inline J j(const std::string& s) { J v; v.kind=J::Kind::String; v.text=s; return v; }
inline J j(const char* s) { return j(std::string(s?s:"")); }
inline J j(double n) { J v; if(std::isfinite(n)){v.kind=J::Kind::Number;v.number=n;} return v; }
inline J j(int n) { return j(double(n)); }
inline J j(bool b) { J v;v.kind=J::Kind::Bool;v.boolean=b;return v; }
inline J object(std::initializer_list<std::pair<std::string,J>> items={}) { J v;v.kind=J::Kind::Object;v.members=items;return v; }
inline J array() { J v;v.kind=J::Kind::Array;return v; }
inline std::string quote(const std::string& s) {
    std::ostringstream o;o<<'"';
    for(unsigned char c:s) {
        if(c=='"'||c=='\\')o<<'\\'<<c;
        else if(c<32)o<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c)<<std::dec;
        else o<<c;
    }
    return o.str()+'"';
}
inline std::string dump(const J& v) {
    std::ostringstream o;o<<std::setprecision(17);
    switch(v.kind) {
        case J::Kind::Null:return "null";
        case J::Kind::Bool:return v.boolean?"true":"false";
        case J::Kind::Number:o<<v.number;return o.str();
        case J::Kind::String:return quote(v.text);
        case J::Kind::Array: {o<<'[';bool first=true;for(auto& x:v.items){if(!first)o<<',';first=false;o<<dump(x);}o<<']';return o.str();}
        case J::Kind::Object: {o<<'{';bool first=true;for(auto& x:v.members){if(!first)o<<',';first=false;o<<quote(x.first)<<':'<<dump(x.second);}o<<'}';return o.str();}
    }
    return "null";
}
inline bool flag(const J& v,const char* key,bool fallback=false) {auto p=v.find(key);return p&&p->kind==J::Kind::Bool?p->boolean:fallback;}
inline const J& member(const J& v,const char* key) {auto p=v.find(key);if(!p)throw std::runtime_error(std::string("Missing ")+key);return *p;}
