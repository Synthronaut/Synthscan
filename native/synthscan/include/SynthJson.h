// SynthScan JSON construction helpers; the upstream parser remains unchanged.
#pragma once
#include "MiniJson.h"
#include <filesystem>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <windows.h>
namespace SynthScan {
using Json=SCMiner::JsonValue;
inline Json str(const std::string& text){Json j;j.kind=Json::Kind::String;j.text=text;return j;}
inline Json num(double value){Json j;if(std::isfinite(value)){j.kind=Json::Kind::Number;j.number=value;}return j;}
inline Json boolean(bool value){Json j;j.kind=Json::Kind::Bool;j.boolean=value;return j;}
inline Json obj(std::initializer_list<std::pair<std::string,Json>> fields={}){Json j;j.kind=Json::Kind::Object;j.members=fields;return j;}
inline Json arr(){Json j;j.kind=Json::Kind::Array;return j;}
inline const Json& field(const Json& value,const char* name){static const Json nil;auto p=value.find(name);return p?*p:nil;}
inline bool flag(const Json& value,const char* name,bool fallback=false){auto p=value.find(name);return p&&p->kind==Json::Kind::Bool?p->boolean:fallback;}
inline std::string quoted(const std::string& text){std::ostringstream s;s<<'"';for(unsigned char c:text){if(c=='"'||c=='\\')s<<'\\'<<c;else if(c<32)s<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c)<<std::dec;else s<<c;}return s.str()+'"';}
inline std::string encode(const Json& j){switch(j.kind){case Json::Kind::Null:return "null";case Json::Kind::Bool:return j.boolean?"true":"false";case Json::Kind::Number:{std::ostringstream s;s<<std::setprecision(17)<<j.number;return s.str();}case Json::Kind::String:return quoted(j.text);case Json::Kind::Array:{std::string s="[";for(auto& v:j.items){if(s.size()>1)s+=',';s+=encode(v);}return s+"]";}case Json::Kind::Object:{std::string s="{";for(auto& v:j.members){if(s.size()>1)s+=',';s+=quoted(v.first)+":"+encode(v.second);}return s+"}";}}return "null";}
// The bridge publishes by replacing the file. A normal MSVC ifstream denies
// deletion while open, intermittently blocking that atomic publication.
inline Json read(const std::filesystem::path& path,size_t limit=32*1024*1024){
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return {};
    LARGE_INTEGER size{};std::string s;bool ok=GetFileSizeEx(file,&size)&&size.QuadPart>=0&&static_cast<unsigned long long>(size.QuadPart)<=limit;
    if(ok){s.resize(size_t(size.QuadPart));DWORD got=0;ok=ReadFile(file,s.data(),DWORD(s.size()),&got,nullptr)&&got==s.size();}
    CloseHandle(file);if(!ok)return {};Json j;std::string why;if(!SCMiner::parseJson(s,j,why))return {};return j;
}
inline bool write(const std::filesystem::path& path,const Json& value){auto tmp=path;tmp+=L".tmp";{std::ofstream f(tmp,std::ios::binary);if(!f)return false;f<<encode(value);f.flush();if(!f)return false;}for(int attempt=0;attempt<5;++attempt){if(MoveFileExW(tmp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return true;DWORD error=GetLastError();if(error!=ERROR_SHARING_VIOLATION&&error!=ERROR_ACCESS_DENIED)return false;Sleep(10);}return false;}
inline std::wstring wide(const std::string& text){int n=MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),nullptr,0);std::wstring w(n,0);if(n)MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),w.data(),n);return w;}
inline std::string utf8(const std::wstring& text){int n=WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),nullptr,0,nullptr,nullptr);std::string s(n,0);if(n)WideCharToMultiByte(CP_UTF8,0,text.data(),int(text.size()),s.data(),n,nullptr,nullptr);return s;}
}
