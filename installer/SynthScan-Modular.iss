#ifndef Payload
  #error Module payload directory is required
#endif
#ifndef Output
  #define Output "output"
#endif
#ifndef AppVersion
  #error Release version is required
#endif

[Setup]
#ifdef ValidationBuild
AppId={{6278A3F4-6738-4AE9-84CF-12B477780C30}
AppName=SynthScan Validation
DefaultDirName={localappdata}\Programs\SynthScan-Validation
DefaultGroupName=SynthScan Validation
#else
AppId={{6278A3F4-6738-4AE9-84CF-12B477780C20}
AppName=SynthScan
DefaultDirName={localappdata}\Programs\SynthScan
DefaultGroupName=SynthScan
#endif
AppVersion={#AppVersion}
AppPublisher=Synthronaut
AppPublisherURL=https://github.com/Synthronaut/Synthscan
AppSupportURL=https://github.com/Synthronaut/Synthscan/issues
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
WizardStyle=modern dark polar includetitlebar hidebevels
WizardBackColor=#10151D
WizardSizePercent=150,150
WizardImageFile=branding\welcome.bmp
WizardSmallImageFile=branding\mark.bmp
WizardImageBackColor=#10151D
WizardSmallImageBackColor=#10151D
WizardImageStretch=yes
SetupIconFile=..\assets\branding\SynthScan-Blue.ico
UninstallDisplayIcon={app}\SynthScan.exe
OutputDir={#Output}
#ifdef ValidationBuild
OutputBaseFilename=SynthScan-Validation-Setup-Windows-x64
#else
OutputBaseFilename=SynthScan-Setup-Windows-x64
#endif
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
#ifdef SelectionReserve
ExtraDiskSpaceRequired={#SelectionReserve}
#endif

[Types]
Name: "complete"; Description: "All features (recommended)"
Name: "custom"; Description: "Choose my features"; Flags: iscustom

[Components]
Name: "core"; Description: "SynthScan Core - app, local records, verified updates and recovery"; Types: complete custom; Flags: fixed
Name: "synthstrings"; Description: "SynthStrings & Reputation - in-game labels and owned blueprint markers"; Types: complete
Name: "mining_tools"; Description: "Mining Tools - planner, diary, rock bookmarks and refinery records"; Types: complete
Name: "mining_recognition"; Description: "Live Mining Recognition [SCREEN READING] - signatures, rock details and refinery imports"; Types: complete
Name: "blueprints"; Description: "Crafting & Blueprints - library, recipes, quality and acquisition details"; Types: complete
Name: "item_finder"; Description: "Item & Ship Finder - equipment, locations and market information"; Types: complete
Name: "server_hud"; Description: "Server HUD - region, shard and supported background measurements (no OCR)"; Types: complete
Name: "server_history"; Description: "Server History - visits, timestamps, hopping history and notes"; Types: complete
Name: "people"; Description: "People - player lists, tags, relationships and alerts"; Types: complete
Name: "piracy"; Description: "Piracy - manual timer and available log reports (no OCR)"; Types: complete
Name: "missions"; Description: "Missions & Ledger - contracts, durations, wallet and reputation changes"; Types: complete
Name: "hangars"; Description: "Hangars & Compboards - five-light schedule and local board inventory (no OCR)"; Types: complete
Name: "daylight"; Description: "Day/Night Forecast - plan daylight at your destination"; Types: complete
Name: "acceptance"; Description: "Automatic Acceptance [AUTOMATED INPUT] - optional helper, off until enabled"; Types: complete

[Tasks]
#ifdef ValidationBuild
Name: "startup"; Description: "Start this separate test copy with RSI Launcher"; Flags: unchecked
Name: "desktop"; Description: "Create a SynthScan Validation desktop shortcut"; Flags: unchecked
#else
Name: "startup"; Description: "Open SynthScan automatically with RSI Launcher"; Flags: checkedonce
Name: "desktop"; Description: "Create a desktop shortcut"; Flags: checkedonce
#endif

[Files]
Source: "{#Payload}\core\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\synthscan-modules.json"; DestDir: "{tmp}\SynthScanComponents"; Flags: deleteafterinstall
Source: "{#Payload}\SynthScan-module-core.zip"; DestDir: "{tmp}\SynthScanComponents"; Flags: deleteafterinstall
#include Payload + "\installer-components.iss"

[InstallDelete]
Type: files; Name: "{app}\active_version.txt"
Type: files; Name: "{app}\activation_pending.txt"

[Icons]
Name: "{group}\SynthScan"; Filename: "{app}\SynthScan.exe"
Name: "{group}\Setup and reputation status"; Filename: "{app}\SynthScan.exe"; Parameters: "--status"
#ifdef ValidationBuild
Name: "{autodesktop}\SynthScan Validation"; Filename: "{app}\SynthScan.exe"; Tasks: desktop
Name: "{userstartup}\SynthScan Validation Watcher"; Filename: "{app}\SynthScan.exe"; Parameters: "--watch"; Tasks: startup
#else
Name: "{autodesktop}\SynthScan"; Filename: "{app}\SynthScan.exe"; Tasks: desktop
Name: "{userstartup}\SynthScan Game Watcher"; Filename: "{app}\SynthScan.exe"; Parameters: "--watch"; Tasks: startup
#endif

[Run]
Filename: "{app}\SynthScan.exe"; Description: "Open SynthScan and prepare my game"; Check: InstallationReady; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\SynthScan.exe"; Parameters: "--uninstall --profile-dir ""{code:SelectedProfile}"""; Flags: runhidden waituntilterminated; RunOnceId: "SynthScanCleanup"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\versions"
Type: files; Name: "{app}\active_version.txt"
Type: files; Name: "{app}\activation_pending.txt"
Type: files; Name: "{app}\dist\native\native_runtime.json"
Type: files; Name: "{app}\dist\native\workspace_library.json"
Type: files; Name: "{app}\launch_target.json"
Type: files; Name: "{app}\validation-install.txt"

[Messages]
WelcomeLabel1=Less friction.%nMore Star Citizen.
WelcomeLabel2=SynthScan brings the information you need into one place, so you can spend more time playing.%n%n  •  Clear, movable HUDs for the way you play%n  •  Reputation and owned blueprints where they matter%n  •  Mining, crafting and mission planning together%n  •  Your records, kept on your PC%n%nBuild your own toolkit. Everything starts included; switch off whatever you don't need.
SelectComponentsDesc=Choose the features to install. Unchecked features are not installed. Live Mining Recognition is the only screen-reading add-on.
SelectComponentsLabel2=Screen reading processes the Star Citizen window locally; it does not upload screenshots. Server HUD, hangars, blueprints, reputation and piracy work without it. Recognition needs Mining Tools.
FinishedHeadingLabel=SynthScan is ready
FinishedLabelNoIcons=Your selected features are installed and verified. Open SynthScan to find your game and prepare local reference data.%n%nSynthStrings can require one game restart after setup. Your records stay in AppData, outside the game folder.

[Code]
var
  Ready: Boolean;
  PreviousInventory: String;

#include "FeatureCards.iss"

function InstallationReady: Boolean;
begin
  Result := Ready;
end;

function SelectedProfile(Param: String): String;
begin
  Result := ExpandConstant('{param:SYNTHSCANPROFILE|}');
#ifdef ValidationBuild
  if Result = '' then Result := ExpandConstant('{localappdata}\SynthScan-Validation\native');
#else
  if Result = '' then Result := GetEnv('SYNTHSCAN_DATA_DIR');
  if Result = '' then Result := ExpandConstant('{localappdata}\SynthScan\native');
#endif
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Processes: Variant;
  Locator: Variant;
  Services: Variant;
begin
  Result := '';
#ifndef ValidationBuild
  if CheckForMutexes('Local\SynthScan.Native.App') then begin
    Result := 'Please exit SynthScan before installing. Your records will be kept.';
    exit;
  end;
#endif
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Services := Locator.ConnectServer('', 'root\CIMV2');
    Processes := Services.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''StarCitizen.exe''');
    if Processes.Count > 0 then
      Result := 'Please close Star Citizen before installing. SynthScan will never close or control the game for you.';
  except
    Result := 'Windows could not verify that the game is closed. Close Star Citizen, then retry the installer.';
  end;
  if Result = '' then begin
    PreviousInventory := ExpandConstant('{tmp}\synthscan-previous-integrity.json');
    if FileExists(ExpandConstant('{app}\release_integrity.json')) then
      FileCopy(ExpandConstant('{app}\release_integrity.json'), PreviousInventory, False);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectComponents) and WizardIsComponentSelected('mining_recognition') and not WizardIsComponentSelected('mining_tools') then begin
    WizardSelectComponents(WizardSelectedComponents(False) + ',mining_tools');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Args: String;
begin
  if CurStep = ssPostInstall then begin
#ifdef ValidationBuild
    if not SaveStringsToUTF8File(ExpandConstant('{app}\validation-install.txt'), [SelectedProfile('')], False) then
      RaiseException('Could not establish the isolated test profile. Installation stopped before setup.');
#endif
    Args := '-I -B "' + ExpandConstant('{app}\module_setup.py') + '" --root "' + ExpandConstant('{app}') + '" --profile "' + SelectedProfile('') + '" --offline "' + ExpandConstant('{tmp}\SynthScanComponents') + '" --selected "' + WizardSelectedComponents(False) + '"';
    if FileExists(PreviousInventory) then Args := Args + ' --previous-inventory "' + PreviousInventory + '"';
    Ready := Exec(ExpandConstant('{app}\runtime\pythonw.exe'), Args, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
    if not Ready then
      RaiseException('SynthScan could not verify the selected installation. Your player records were kept. Run the installer again; details are in AppData\Local\SynthScan\native\module_install_error.json.');
  end;
end;
