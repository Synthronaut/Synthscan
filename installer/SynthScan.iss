#ifndef Payload
  #error Payload directory is required
#endif
#ifndef Output
  #define Output "output"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0-alpha.11"
#endif
#ifndef Edition
  #define Edition "full"
#endif
#if Edition == "standard"
  #define EditionName "Standard"
  #define EditionSuffix "-Standard"
  #define EditionGuid "6278A3F4-6738-4AE9-84CF-12B477780C21"
#else
  #define EditionName "Full"
  #define EditionSuffix ""
  #define EditionGuid "6278A3F4-6738-4AE9-84CF-12B477780C20"
#endif
[Setup]
#if Edition == "standard"
AppId={{6278A3F4-6738-4AE9-84CF-12B477780C21}
#else
AppId={{6278A3F4-6738-4AE9-84CF-12B477780C20}
#endif
AppName=SynthScan {#EditionName}
AppVersion={#AppVersion}
AppPublisher=Synthronaut
AppPublisherURL=https://github.com/Synthronaut/Synthscan
AppSupportURL=https://github.com/Synthronaut/Synthscan/issues
DefaultDirName={localappdata}\Programs\SynthScan{#EditionSuffix}
DefaultGroupName=SynthScan {#EditionName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=yes
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=..\native\synthscan\resources\synthscan.ico
UninstallDisplayIcon={app}\SynthScan.exe
OutputDir={#Output}
OutputBaseFilename=SynthScan-{#EditionName}-Setup-Windows-x64
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "startup"; Description: "Launch SynthScan automatically when Star Citizen starts"; Flags: checkedonce
Name: "desktop"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\active_version.txt"
Type: files; Name: "{app}\activation_pending.txt"

[Icons]
Name: "{group}\SynthScan {#EditionName}"; Filename: "{app}\SynthScan.exe"
Name: "{group}\Setup and reputation status"; Filename: "{app}\SynthScan.exe"; Parameters: "--status"
Name: "{autodesktop}\SynthScan {#EditionName}"; Filename: "{app}\SynthScan.exe"; Tasks: desktop
Name: "{userstartup}\SynthScan Game Watcher"; Filename: "{app}\SynthScan.exe"; Parameters: "--watch"; Tasks: startup

[Run]
Filename: "{app}\SynthScan.exe"; Description: "Open SynthScan and set up my game"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\SynthScan.exe"; Parameters: "--uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "SynthScanCleanup"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\versions"
Type: files; Name: "{app}\active_version.txt"
Type: files; Name: "{app}\activation_pending.txt"
Type: files; Name: "{app}\dist\native\native_runtime.json"
Type: files; Name: "{app}\dist\native\workspace_library.json"
Type: files; Name: "{app}\launch_target.json"

[Messages]
#if Edition == "standard"
WelcomeLabel2=Standard installs SynthScan without screen reading. Mining recognition, DisplayInfo readings and screen imports are not installed. Finder, People, reputation, log-based server information and manual planning remain available. Updates preserve Standard; adding screen reading requires explicitly installing Full.
#else
WelcomeLabel2=Full includes local game-window screen reading for mining recognition, DisplayInfo readings and screen imports. Capture can be paused in Privacy & capture. Choose the separate Standard installer if you do not want screen-reading components installed.
#endif
