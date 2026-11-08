#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>

// No shell expansion, PATH lookup, administrator prompt, or external Python.
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR arguments,int) {
    wchar_t filename[32768]{};
    if(!GetModuleFileNameW(nullptr,filename,32768))return 1;
    std::wstring root(filename);root.resize(root.find_last_of(L"\\/"));
    std::wstring runtimeRoot=root,extra;
    const bool health=std::wstring(arguments).find(L"--update-health")!=std::wstring::npos;
    bool recovery=!health&&GetFileAttributesW((root+L"\\activation_pending.txt").c_str())!=INVALID_FILE_ATTRIBUTES;
    HANDLE pointer=CreateFileW((root+L"\\active_version.txt").c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(pointer!=INVALID_HANDLE_VALUE){
        char token[72]{};DWORD got=0;LARGE_INTEGER size{};
        bool valid=GetFileSizeEx(pointer,&size)&&size.QuadPart>=64&&size.QuadPart<=70&&ReadFile(pointer,token,71,&got,nullptr);CloseHandle(pointer);
        for(unsigned i=0;i<64&&valid;i++)valid=(token[i]>='0'&&token[i]<='9')||(token[i]>='a'&&token[i]<='f');
        for(unsigned i=64;i<got&&valid;i++)valid=token[i]=='\r'||token[i]=='\n';
        if(valid&&!recovery){
            std::wstring version;for(unsigned i=0;i<64;i++)version+=wchar_t(token[i]);
            runtimeRoot=root+L"\\versions\\"+version;
            auto attributes=GetFileAttributesW(runtimeRoot.c_str());
            if(attributes==INVALID_FILE_ATTRIBUTES||!(attributes&FILE_ATTRIBUTE_DIRECTORY)||(attributes&FILE_ATTRIBUTE_REPARSE_POINT)){runtimeRoot=root;recovery=true;}
        }else if(!valid)recovery=true;
    }
    if(recovery){runtimeRoot=root;extra=L" --recover-update";}
    std::wstring python=runtimeRoot+L"\\runtime\\pythonw.exe";
    std::wstring command=L"\""+python+L"\" -I -B \""+runtimeRoot+L"\\app_launcher.py\" "+arguments+extra;
    STARTUPINFOW startup{sizeof(startup)};PROCESS_INFORMATION process{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,
                       nullptr,runtimeRoot.c_str(),&startup,&process)) {
        MessageBoxW(nullptr,L"SynthScan is missing required files. Run the SynthScan installer again to repair the installation. Your player records will be kept.",L"SynthScan needs repair",MB_OK|MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    if(std::wstring(arguments).find(L"--uninstall")!=std::wstring::npos) {
        WaitForSingleObject(process.hProcess,15000);DWORD code=1;GetExitCodeProcess(process.hProcess,&code);CloseHandle(process.hProcess);return int(code);
    }
    CloseHandle(process.hProcess);return 0;
}
