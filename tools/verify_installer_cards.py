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
  if not Condition then RaiseException('Card interaction failed: '+Detail);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var I: Integer; Selector: TNewButton; Report: String;
begin
  if CurStep<>ssInstall then exit;
  Selector:=TNewButton.Create(WizardForm);Selector.Tag:=0;
  for I:=0 to 13 do begin
    SelectAllCards(Selector);
    RequireState(WizardIsComponentSelected(CardIds[I]),'initial included '+CardIds[I]);
    ToggleCard(CardPaint[I]);
    RequireState(not WizardIsComponentSelected(CardIds[I]),'card excludes '+CardIds[I]);
    RequireState(CardButtons[I].Caption='Not installing','off label '+CardIds[I]);
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
  for I:=0 to 13 do
    RequireState(WizardIsComponentSelected(CardIds[I])=(I<>2),'reader-free preset '+CardIds[I]);
  for I:=0 to 13 do
    if WizardIsComponentSelected(CardIds[I]) then ToggleCard(CardPaint[I]);
  RequireState(WizardSelectedComponents(False)='core','Core-only install selection');
  RequireState(SelectionLabels[0].Caption='0 features included  /  Core always included','zero-feature summary');
  Selector.Tag:=0;SelectAllCards(Selector);
  for I:=0 to 13 do RequireState(WizardIsComponentSelected(CardIds[I]),'restore all '+CardIds[I]);
  Report:=ExpandConstant('{param:REPORT|}');
  RequireState(Report<>'','missing report destination');
  RequireState(SaveStringsToUTF8File(Report,['{"passed":true,"feature_cards":14,"event_targets_per_card":6,"dependency_rules":true,"reader_free_preset":true,"page_persistence":true,"core_only":true,"inactive_state_dimmed":true}'],False),'save report');
end;
'''


def verify(output):
    source=(ROOT/'installer/SynthScan-Modular.iss').read_text(encoding='utf-8')
    types=source.split('[Types]',1)[1].split('[Components]',1)[0]
    components=source.split('[Components]',1)[1].split('[Tasks]',1)[0]
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
'''+types+'\n[Components]\n'+components+'\n[Code]\n#include "'+str(ROOT/'installer/FeatureCards.iss')+'"\n'+CHECKS,encoding='utf-8-sig')
        subprocess.run([str(compiler()),'/Q',str(script)],check=True,capture_output=True,text=True)
        subprocess.run([str(folder/'CardTest.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/REPORT='+str(report)],check=True,timeout=60,creationflags=0x08000000)
        value=json.loads(report.read_text(encoding='utf-8-sig'))
        if output:Path(output).write_text(json.dumps(value,indent=2),encoding='utf-8')
        return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    print(json.dumps(verify(args.output),indent=2))
