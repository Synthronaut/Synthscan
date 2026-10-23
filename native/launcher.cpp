#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>

// No shell expansion, PATH lookup, administrator prompt, or external Python.
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int) {
    wchar_t filename[32768]{};
    if(!GetModuleFileNameW(nullptr,filename,32768))return 1;
    std::wstring root(filename);root.resize(root.find_last_of(L"\\/"));
    std::wstring python=root+L"\\runtime\\pythonw.exe";
    std::wstring command=L"\""+python+L"\" -I \""+root+L"\\app_launcher.py\"";
    STARTUPINFOW startup{sizeof(startup)};PROCESS_INFORMATION process{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,
                       nullptr,root.c_str(),&startup,&process)) {
        MessageBoxW(nullptr,L"Extract the entire SynthScan ZIP first, then open SynthScan.exe. The bundled runtime must stay beside it.",L"SynthScan",MB_OK|MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);CloseHandle(process.hProcess);return 0;
}
