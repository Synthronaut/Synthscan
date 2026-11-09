"""Exercise production Inno card handlers without installing files or input.

The silent harness uses the real component definitions and card code. It calls
their event handlers internally; it never sends mouse/keyboard input, launches
the game, creates an app directory or registers an uninstall entry.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build_installer import compiler

ROOT=Path(__file__).resolve().parents[1]
CHECKS=r'''
procedure RequireState(Condition: Boolean; const Detail: String);
begin
  if not Condition then begin
    SaveStringsToUTF8File(ExpandConstant('{param:REPORT|}'),['FAILED: '+Detail+LastTextMeasure],False);
    RaiseException('Card interaction failed: '+Detail);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var I: Integer; Selector,SourceButton: TNewButton; Report: String;
begin
  if CurStep<>ssInstall then exit;
  Selector:=TNewButton.Create(WizardForm);Selector.Tag:=0;
  for I:=0 to 2 do begin
    case I of
      0:SourceButton:=WizardForm.BackButton;
      1:SourceButton:=WizardForm.NextButton;
      2:SourceButton:=WizardForm.CancelButton;
    end;
    RequireState(NavigationTarget(I)=SourceButton,'navigation route');
    RequireState(NavigationButtons[I].TabStop,'keyboard navigation target');
  end;
  RequireState(ContentFits(WizardForm.WelcomeLabel1.Caption,WizardForm.WelcomeLabel1.Font,WizardForm.WelcomeLabel1.Width,WizardForm.WelcomeLabel1.Height),'welcome heading fits');
  RequireState(ContentFits(WizardForm.WelcomeLabel2.Caption,WizardForm.WelcomeLabel2.Font,WizardForm.WelcomeLabel2.Width,WizardForm.WelcomeLabel2.Height),'welcome body fits');
  for I:=0 to 1 do begin
    RequireState(ContentFits(Headings[I].Caption,Headings[I].Font,Headings[I].Width,Headings[I].Height),'page heading fits');
    RequireState(ContentFits(Subheadings[I].Caption,Subheadings[I].Font,Subheadings[I].Width,Subheadings[I].Height),'page subtitle fits');
    RequireState(not AssuranceBodies[I].AutoSize,'bounded assurance body');
    RequireState(not AssuranceTitles[I].AutoSize,'bounded assurance heading');
    RequireState(TextFits(AssuranceBodies[I]),'wrapped assurance body');
    RequireState(TextFits(AssuranceTitles[I]),'wrapped assurance heading');
    RequireState(AssuranceBodies[I].Left+AssuranceBodies[I].Width<=AssuranceBodies[I].Parent.ClientWidth,'assurance right edge');
    RequireState(AssuranceBodies[I].Top+AssuranceBodies[I].Height<=AssuranceBodies[I].Parent.ClientHeight,'assurance bottom edge');
  end;
  for I:=2 to FeaturePageCount-1 do begin
    RequireState(ContentFits(Headings[I].Caption,Headings[I].Font,Headings[I].Width,Headings[I].Height),'extra page heading fits');
    RequireState(ContentFits(Subheadings[I].Caption,Subheadings[I].Font,Subheadings[I].Width,Subheadings[I].Height),'extra page subtitle fits');
  end;
  for I:=0 to 12 do begin
    SelectAllCards(Selector);
    RequireState(WizardIsComponentSelected(CardIds[I]),'initial included '+CardIds[I]);
    RequireState(TextFits(CardDescriptions[I]),'readable description '+CardIds[I]);
    RequireState(TextFits(CardTitles[I]),'readable title '+CardIds[I]);
    RequireState(TextFits(CardBadges[I]),'readable badge '+CardIds[I]);
    RequireState(Cards[I].Left+Cards[I].Width<=Cards[I].Parent.ClientWidth,'card right edge '+CardIds[I]);
    RequireState(Cards[I].Top+Cards[I].Height<=Cards[I].Parent.ClientHeight,'card bottom edge '+CardIds[I]);
    ToggleCard(CardPaint[I]);
    RequireState(not WizardIsComponentSelected(CardIds[I]),'card excludes '+CardIds[I]);
    RequireState(Pos('Not installing',CardButtons[I].Caption)>0,'off label '+CardIds[I]);
    RequireState(Pos(CardTitles[I].Caption,CardButtons[I].Caption)>0,'accessible feature name '+CardIds[I]);
    RequireState(CardTitles[I].Font.Color=$00827D76,'dim title '+CardIds[I]);
    RequireState(CardDescriptions[I].Font.Color=$00736F68,'dim body '+CardIds[I]);
    ToggleCard(CardButtons[I]);
    RequireState(WizardIsComponentSelected(CardIds[I]),'button includes '+CardIds[I]);
    RequireState(CardTitles[I].Font.Color=$00FFFFFF,'bright title '+CardIds[I]);
    ToggleCard(CardTitles[I]);
    RequireState(not WizardIsComponentSelected(CardIds[I]),'title excludes '+CardIds[I]);
    ToggleCard(CardDescriptions[I]);
    RequireState(WizardIsComponentSelected(CardIds[I]),'description includes '+CardIds[I]);
    ToggleCard(CardBadges[I]);
    RequireState(not WizardIsComponentSelected(CardIds[I]),'badge excludes '+CardIds[I]);
    ToggleCard(CardIcons[I]);
    RequireState(WizardIsComponentSelected(CardIds[I]),'icon includes '+CardIds[I]);
  end;
  SelectAllCards(Selector);ToggleCard(CardPaint[1]);
  RequireState(not WizardIsComponentSelected('mining_tools'),'mining off');
  RequireState(not WizardIsComponentSelected('mining_recognition'),'dependent reader off');
  ToggleCard(CardPaint[2]);
  RequireState(WizardIsComponentSelected('mining_tools'),'reader restores dependency');
  RequireState(WizardIsComponentSelected('mining_recognition'),'reader restored');
  Selector.Tag:=1;SelectAllCards(Selector);
  CurPageChanged(ToolsPage.ID);CurPageChanged(ModulesPage.ID);
  for I:=0 to 12 do
    RequireState(WizardIsComponentSelected(CardIds[I])=(I<>2),'reader-free preset '+CardIds[I]);
  for I:=0 to 12 do
    if WizardIsComponentSelected(CardIds[I]) then ToggleCard(CardPaint[I]);
  RequireState(WizardSelectedComponents(False)='core','Core-only install selection');
  RequireState(SelectionLabels[0].Caption='0 features included  /  Core always included','zero-feature summary');
  Selector.Tag:=0;SelectAllCards(Selector);
  for I:=0 to 12 do RequireState(WizardIsComponentSelected(CardIds[I]),'restore all '+CardIds[I]);
  Report:=ExpandConstant('{param:REPORT|}');
  RequireState(Report<>'','missing report destination');
  RequireState(SaveStringsToUTF8File(Report,['{"passed":true,"feature_cards":13,"event_targets_per_card":6,"dependency_rules":true,"reader_free_preset":true,"page_persistence":true,"core_only":true,"inactive_state_dimmed":true}'],False),'save report');
end;
'''


def verify(output):
    source=(ROOT/'installer/SynthScan-Modular.iss').read_text(encoding='utf-8')
    types=source.split('[Types]',1)[1].split('[Components]',1)[0]
    components=source.split('[Components]',1)[1].split('[Tasks]',1)[0]
    messages=source.split('[Messages]',1)[1].split('[Code]',1)[0]
    with tempfile.TemporaryDirectory(prefix='SynthScan-card-tests-') as temporary:
        folder=Path(temporary);report=folder/'result.json'
        script=folder/'cards.iss'
        script.write_text('''[Setup]
AppName=SynthScan Card Interaction Test
AppVersion=1
AppId=SynthScan-Card-Interaction-Test
DefaultDirName={tmp}\\SynthScan-card-test
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
WizardStyle=modern dark polar includetitlebar hidebevels
WizardBackColor=#10151D
WizardSizePercent=150,150
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir='''+str(folder)+'''
OutputBaseFilename=CardTest
[Types]
'''+types+'\n[Components]\n'+components+'\n[Messages]\n'+messages+'\n[Code]\n#include "'+str(ROOT/'installer/FeatureCards.iss')+'"\n'+CHECKS,encoding='utf-8-sig')
        compiled=subprocess.run([str(compiler()),'/Q','/DSelectionTestBuild=1','/DValidationBuild=1',str(script)],capture_output=True,text=True)
        if compiled.returncode:raise ValueError(compiled.stdout+compiled.stderr)
        cases=[]
        for width,height in ((2240,1222),(1680,945),(1152,648)):
            report.unlink(missing_ok=True)
            process=subprocess.Popen([str(folder/'CardTest.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/WIDTH='+str(width),'/HEIGHT='+str(height),'/REPORT='+str(report)],creationflags=0x08000000)
            try:code=process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=0x08000000)
                raise
            if code:raise ValueError(str((width,height))+': '+(report.read_text(encoding='utf-8-sig') if report.exists() else 'No report'))
            value=json.loads(report.read_text(encoding='utf-8-sig'));value.update(width=width,height=height);cases.append(value)
        value=dict(passed=True,resolutions=cases)
        if output:Path(output).write_text(json.dumps(value,indent=2),encoding='utf-8')
        return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    print(json.dumps(verify(args.output),indent=2))
