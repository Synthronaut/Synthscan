#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>

// No shell expansion, PATH lookup, administrator prompt, or external Python.
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR arguments,int) {
    wchar_t filename[32768]{};
    if(!GetModuleFileNameW(nullptr,filename,32768))return 1;
    std::wstring root(filename);root.resize(root.find_last_of(L"\\/"));
    std::wstring python=root+L"\\runtime\\pythonw.exe";
    std::wstring command=L"\""+python+L"\" -I -B \""+root+L"\\app_launcher.py\" "+arguments;
    STARTUPINFOW startup{sizeof(startup)};PROCESS_INFORMATION process{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,
                       nullptr,root.c_str(),&startup,&process)) {
        MessageBoxW(nullptr,L"SynthScan is missing required files. Run the SynthScan installer again to repair the installation. Your player records will be kept.",L"SynthScan needs repair",MB_OK|MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    if(std::wstring(arguments).find(L"--uninstall")!=std::wstring::npos) {
        WaitForSingleObject(process.hProcess,15000);DWORD code=1;GetExitCodeProcess(process.hProcess,&code);CloseHandle(process.hProcess);return int(code);
    }
    CloseHandle(process.hProcess);return 0;
}
