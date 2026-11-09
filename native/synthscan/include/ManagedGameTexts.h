#pragma once
#ifdef _WIN32
#include "AppPaths.h"
#include "SynthJson.h"
#include <windows.h>
#include <vector>
namespace SCMiner {
struct ManagedTextResult {bool written=false;std::string note;};
inline std::wstring textArg(const std::wstring& value){std::wstring out=L"\"";size_t slashes=0;for(auto c:value){if(c==L'\\'){++slashes;continue;}if(c==L'"'){out.append(slashes*2+1,L'\\');out+=c;}else{out.append(slashes,L'\\');out+=c;}slashes=0;}out.append(slashes*2,L'\\');return out+L'"';}
inline ManagedTextResult managedGameText(const std::wstring& action,const std::filesystem::path& game,const std::vector<bool>& owned={}){
    using namespace SynthScan;auto program=AppPaths::program();auto runtime=read(program/L"native_runtime.json");auto root=std::filesystem::u8path(runtime.textOr("workspace"));auto python=wide(runtime.textOr("pythonw"));
    if(python.empty()||!std::filesystem::is_regular_file(root/L"game_text_lifecycle.py"))return {false,"Open Setup to prepare managed SynthStrings; no game files were changed"};
    auto data=AppPaths::data();std::error_code error;auto calls=data/L"game_text/calls";std::filesystem::create_directories(calls,error);
    auto result=calls/(std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetCurrentThreadId())+L"-"+std::to_wstring(GetTickCount64())+L".json");
    std::wstring bits;for(bool value:owned)bits+=value?L'1':L'0';
    std::wstring command=textArg(python)+L" -I -B "+textArg((root/L"game_text_lifecycle.py").wstring())+L" "+action+L" --game "+textArg(game.wstring())+L" --profile "+textArg(data.wstring())+L" --native "+textArg((program/L"SynthScan.exe").wstring())+L" --owned "+textArg(bits)+L" --result "+textArg(result.wstring());
    STARTUPINFOW startup{sizeof(startup)};PROCESS_INFORMATION process{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW|BELOW_NORMAL_PRIORITY_CLASS,nullptr,root.c_str(),&startup,&process))return {false,"Could not start the managed text writer; game files unchanged"};
    CloseHandle(process.hThread);DWORD waited=WaitForSingleObject(process.hProcess,330000);CloseHandle(process.hProcess);
    if(waited!=WAIT_OBJECT_0)return {false,"Text preparation is still pending; inspect Setup before retrying"};
    auto value=read(result,128*1024);std::filesystem::remove(result,error);auto written=value.find("written");return {written&&written->boolean,value.textOr("note","Managed text writer did not return a result")};
}
}
#endif
