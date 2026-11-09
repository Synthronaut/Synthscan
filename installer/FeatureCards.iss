// Required visual standards: ../DESIGN.md. Keep text short and controls generous.
var
  ModulesPage, ToolsPage: TWizardPage;
  CardIds: array[0..13] of String;
  Cards: array[0..13] of TPanel;
  CardPaint: array[0..13] of TBitmapImage;
  CardButtons: array[0..13] of TNewButton;
  CardTitles: array[0..13] of TLabel;
  CardDescriptions: array[0..13] of TLabel;
  CardBadges: array[0..13] of TLabel;
  CardIcons: array[0..13] of TLabel;
  CardSelected: array[0..13] of Boolean;
  SelectionLabels: array[0..1] of TNewStaticText;
  GridColumns,GridRows: Integer;

function GetSystemMetrics(Index: Integer): Integer;
  external 'GetSystemMetrics@user32.dll stdcall';
function CreateRoundRectRgn(X1,Y1,X2,Y2,W,H: Integer): NativeUInt;
  external 'CreateRoundRectRgn@gdi32.dll stdcall';
function SetWindowRgn(Window,Region: NativeUInt; Redraw: Boolean): Integer;
  external 'SetWindowRgn@user32.dll stdcall';

procedure RefreshCards;
var I,Count: Integer; Fill,Border,Ink: TColor;
begin
  Count := 0;
  for I := 0 to 13 do begin
    CardSelected[I] := WizardIsComponentSelected(CardIds[I]);
    if CardSelected[I] then begin
      Count := Count+1; Fill := $00553D22; Border := $00F5DB86; Ink := $00FFFFFF;
      CardButtons[I].Caption := #$2713+' Included';
    end else begin
      Fill := $001E1C1A; Border := $003B3732; Ink := $00827D76;
      CardButtons[I].Caption := 'Not installing';
    end;
    if (I=2) and CardSelected[I] then begin Fill:=$001E2C3A;Border:=$006BC9FF;end;
    Cards[I].Color := Fill;
    with CardPaint[I].Bitmap do begin
      Width := CardPaint[I].Width; Height := CardPaint[I].Height;
      Canvas.Brush.Color := $001D1510; Canvas.Pen.Color := $001D1510;
      Canvas.Rectangle(0,0,Width,Height);
      Canvas.Brush.Color := Fill; Canvas.Pen.Color := Border;
      if CardSelected[I] then Canvas.Pen.Width:=ScaleX(2) else Canvas.Pen.Width:=1;
      if (I=2) and CardSelected[I] then Canvas.Pen.Width:=ScaleX(4);
      Canvas.RoundRect(ScaleX(2),ScaleY(2),Width-ScaleX(2),Height-ScaleY(2),ScaleX(22),ScaleY(22));
      if I=2 then begin
        if CardSelected[I] then Canvas.Brush.Color:=$006BC9FF else Canvas.Brush.Color:=$003B3732;
        Canvas.Pen.Color:=Canvas.Brush.Color;Canvas.Pen.Width:=1;
        Canvas.RoundRect(ScaleX(16),Height-ScaleY(48),Width-ScaleX(16),Height-ScaleY(12),ScaleX(10),ScaleY(10));
        Canvas.Ellipse(ScaleX(12),ScaleY(9),ScaleX(56),ScaleY(52));
      end;
    end;
    CardTitles[I].Font.Color := Ink;
    if CardSelected[I] then begin
      CardIcons[I].Font.Color := $00FFE59A;
      CardDescriptions[I].Font.Color := $00F1DAC3;
      CardBadges[I].Font.Color := $00D1BA9C;
      if I=2 then begin
        CardIcons[I].Font.Color := $001E1B14;
        CardBadges[I].Font.Color := $001E1B14;
      end;
    end else begin
      CardIcons[I].Font.Color := $006B6660;
      CardDescriptions[I].Font.Color := $00736F68;
      CardBadges[I].Font.Color := $006B6660;
    end;
    CardPaint[I].Invalidate;
  end;
  for I:=0 to 1 do SelectionLabels[I].Caption := IntToStr(Count)+' features included  /  Core always included';
end;

function TextFits(LabelText: TLabel): Boolean;
var Bitmap: TBitmap;Words: TStringList;I,Lines: Integer;Line,Candidate: String;
begin
  Bitmap:=TBitmap.Create;Words:=TStringList.Create;
  try
    Bitmap.Width:=1;Bitmap.Height:=1;Bitmap.Canvas.Font.Assign(LabelText.Font);
    Words.Delimiter:=' ';Words.StrictDelimiter:=True;Words.DelimitedText:=LabelText.Caption;
    Lines:=1;Line:='';
    for I:=0 to Words.Count-1 do begin
      Candidate:=Line;
      if Candidate<>'' then Candidate:=Candidate+' ';
      Candidate:=Candidate+Words[I];
      if (Line<>'') and (Bitmap.Canvas.TextWidth(Candidate)>LabelText.Width) then begin
        Lines:=Lines+1;Line:=Words[I];
      end else Line:=Candidate;
    end;
    Result:=Lines*Bitmap.Canvas.TextHeight('Ag')<=LabelText.Height;
  finally Words.Free;Bitmap.Free;end;
end;

procedure ExplainCard(Index: Integer; const Detail: String);
var Summary: String;OriginalSize: Integer;
begin
  Summary:=CardDescriptions[Index].Caption;
  OriginalSize:=CardDescriptions[Index].Font.Size;
  CardDescriptions[Index].Caption:=Detail;
  CardDescriptions[Index].Font.Size:=13;
  while (CardDescriptions[Index].Font.Size>OriginalSize) and not TextFits(CardDescriptions[Index]) do
    CardDescriptions[Index].Font.Size:=CardDescriptions[Index].Font.Size-1;
  if not TextFits(CardDescriptions[Index]) then begin
    CardDescriptions[Index].Caption:=Summary;CardDescriptions[Index].Font.Size:=OriginalSize;
  end;
end;

procedure SelectCards;
var I: Integer; Chosen: String;
begin
  Chosen := 'core';
  // WizardSelectComponents leaves unspecified components unchanged. Send an
  // explicit exclusion for every off card, otherwise refresh reselects it.
  for I:=0 to 13 do begin
    if CardSelected[I] then Chosen := Chosen+','+CardIds[I]
    else Chosen := Chosen+',!'+CardIds[I];
  end;
  WizardSelectComponents(Chosen); RefreshCards;
end;

procedure ToggleCard(Sender: TObject);
var I: Integer;
begin
  I := TComponent(Sender).Tag;
  CardSelected[I] := not CardSelected[I];
  if (I=2) and CardSelected[2] then CardSelected[1] := True;
  if (I=1) and not CardSelected[1] then CardSelected[2] := False;
  SelectCards;
end;

procedure SelectAllCards(Sender: TObject);
var I: Integer;
begin
  for I:=0 to 13 do CardSelected[I] := True;
  if TComponent(Sender).Tag=1 then CardSelected[2] := False;
  SelectCards;
end;

function CardLabel(Parent: TWinControl; const Text: String; X,Y,W,H,Size,Index: Integer; Color: TColor): TLabel;
begin
  Result := TLabel.Create(WizardForm); Result.Parent := Parent;
  Result.SetBounds(X,Y,W,H); Result.AutoSize := False;
  Result.Caption := Text; Result.WordWrap := True; Result.Transparent := True;
  Result.Font.Name := 'Segoe UI'; Result.Font.Size := Size; Result.Font.Color := Color;
  Result.ShowAccelChar := False; Result.Tag := Index;
  Result.Cursor := crHandPoint; Result.OnClick := @ToggleCard;
end;

procedure AddCard(Index: Integer; Page: TWizardPage; Slot: Integer; const Id,Title,Description,Badge,Icon: String);
var W,H,X,Y,Gap: Integer;
begin
  CardIds[Index] := Id;
  Gap := ScaleX(16); W := (Page.SurfaceWidth-Gap*(GridColumns-1)) div GridColumns;
  H := (Page.SurfaceHeight-ScaleY(118)-Gap*(GridRows-1)) div GridRows;
  X := (Slot mod GridColumns)*(W+Gap); Y := ScaleY(104)+(Slot div GridColumns)*(H+Gap);
  Cards[Index] := TPanel.Create(WizardForm); Cards[Index].Parent := Page.Surface;
  Cards[Index].SetBounds(X,Y,W,H); Cards[Index].BevelOuter := bvNone;
  Cards[Index].StyleElements := []; Cards[Index].Tag := Index;
  Cards[Index].Cursor := crHandPoint; Cards[Index].OnClick := @ToggleCard;
  SetWindowRgn(Cards[Index].Handle,CreateRoundRectRgn(0,0,W,H,ScaleX(22),ScaleY(22)),True);
  CardPaint[Index] := TBitmapImage.Create(WizardForm); CardPaint[Index].Parent := Cards[Index];
  CardPaint[Index].SetBounds(0,0,W,H); CardPaint[Index].Tag := Index;
  CardPaint[Index].Cursor := crHandPoint; CardPaint[Index].OnClick := @ToggleCard;
  CardIcons[Index] := CardLabel(Cards[Index],Icon,ScaleX(19),ScaleY(17),ScaleX(30),ScaleY(32),20,Index,$00F2D177);
  CardIcons[Index].Font.Name := 'Segoe MDL2 Assets';
  CardButtons[Index] := TNewButton.Create(WizardForm); CardButtons[Index].Parent := Cards[Index];
  CardButtons[Index].SetBounds(W-ScaleX(117),ScaleY(15),ScaleX(99),ScaleY(32));
  CardButtons[Index].Tag := Index; CardButtons[Index].OnClick := @ToggleCard;
  CardButtons[Index].Font.Name := 'Segoe UI Semibold'; CardButtons[Index].Font.Size := 10;
  CardButtons[Index].Hint := Title+' — Space to include or remove'; CardButtons[Index].ShowHint := True;
  CardTitles[Index] := CardLabel(Cards[Index],Title,ScaleX(19),ScaleY(53),W-ScaleX(38),ScaleY(30),16,Index,$00EBFADE);
  CardTitles[Index].Font.Name := 'Bahnschrift';
  CardDescriptions[Index] := CardLabel(Cards[Index],Description,ScaleX(19),ScaleY(86),W-ScaleX(38),H-ScaleY(120),11,Index,$00C3B5A3);
  CardBadges[Index] := CardLabel(Cards[Index],Badge,ScaleX(19),H-ScaleY(28),W-ScaleX(38),ScaleY(19),9,Index,$00B6A184);
  CardBadges[Index].Font.Name := 'Segoe UI Semibold';
  if GridColumns=4 then begin
    CardTitles[Index].Font.Size:=13;
    CardDescriptions[Index].Font.Size:=10;
    CardBadges[Index].Font.Size:=8;
  end;
  if Index=2 then CardBadges[Index].Font.Color := $008DCDEE;
end;

procedure PageHeading(Page: TWizardPage; const Title,Subtitle: String; Number: Integer);
var LabelText: TNewStaticText; Button: TNewButton;
begin
  LabelText := TNewStaticText.Create(WizardForm); LabelText.Parent := Page.Surface;
  LabelText.SetBounds(0,0,Page.SurfaceWidth,ScaleY(42)); LabelText.Caption := Title;
  LabelText.Font.Name := 'Bahnschrift'; LabelText.Font.Size := 28; LabelText.Font.Color := $00F4F0E6;
  LabelText := TNewStaticText.Create(WizardForm); LabelText.Parent := Page.Surface;
  LabelText.SetBounds(0,ScaleY(49),Page.SurfaceWidth,ScaleY(25)); LabelText.Caption := Subtitle;
  LabelText.Font.Size := 12; LabelText.Font.Color := $00C4B7A0;
  SelectionLabels[Number] := TNewStaticText.Create(WizardForm); SelectionLabels[Number].Parent := Page.Surface;
  SelectionLabels[Number].SetBounds(0,ScaleY(81),Page.SurfaceWidth div 2,ScaleY(20));
  SelectionLabels[Number].Font.Size := 10; SelectionLabels[Number].Font.Color := $00BCAA88;
  Button := TNewButton.Create(WizardForm); Button.Parent := Page.Surface;
  Button.SetBounds(Page.SurfaceWidth-ScaleX(315),ScaleY(76),ScaleX(100),ScaleY(25));
  Button.Caption := 'Include all'; Button.Tag := 0; Button.OnClick := @SelectAllCards;
  Button := TNewButton.Create(WizardForm); Button.Parent := Page.Surface;
  Button.SetBounds(Page.SurfaceWidth-ScaleX(205),ScaleY(76),ScaleX(205),ScaleY(25));
  Button.Caption := 'All without screen reading'; Button.Tag := 1; Button.OnClick := @SelectAllCards;
end;

procedure AddAssurance(Page: TWizardPage; const Title,Body: String);
var L: TNewStaticText; Gap,W,H,X,Y: Integer;
begin
  Gap:=ScaleX(16);W:=(Page.SurfaceWidth-Gap*(GridColumns-1)) div GridColumns;
  H:=(Page.SurfaceHeight-ScaleY(118)-Gap*(GridRows-1)) div GridRows;
  X:=W+Gap;Y:=ScaleY(104)+2*(H+Gap);
  if GridColumns=4 then begin X:=3*(W+Gap);Y:=ScaleY(104)+H+Gap;end;
  L:=TNewStaticText.Create(WizardForm);L.Parent:=Page.Surface;
  L.SetBounds(X+ScaleX(18),Y+ScaleY(22),W*2+Gap-ScaleX(36),ScaleY(30));
  L.Caption:=Title;L.Font.Name:='Bahnschrift';L.Font.Size:=18;L.Font.Color:=$008DCDEE;
  if GridColumns=4 then begin
    L.Width:=W-ScaleX(36);L.Font.Size:=13;
    if Page=ModulesPage then L.Caption:='LOCAL. OPTIONAL.' else L.Caption:='YOUR RECORDS. YOUR PC.';
  end;
  L:=TNewStaticText.Create(WizardForm);L.Parent:=Page.Surface;
  L.SetBounds(X+ScaleX(18),Y+ScaleY(62),W*2+Gap-ScaleX(36),H-ScaleY(70));
  L.Caption:=Body;L.WordWrap:=True;L.Font.Size:=12;L.Font.Color:=$00C7BBA7;
  if GridColumns=4 then begin
    L.Width:=W-ScaleX(36);L.Font.Size:=10;
    if Page=ModulesPage then L.Caption:='Game-window only. Local recognition. No frame uploads. Focus-loss pause. Leave it off to keep OCR uninstalled.'
    else L.Caption:='Local records. No analytics signup. Verified update packages. Change your modules and keep your saved progress.';
  end;
end;

procedure InitializeWizard;
var W,H,X,Y: Integer;
begin
  W:=GetSystemMetrics(0)*88 div 100;H:=GetSystemMetrics(1)*88 div 100;
  X:=(GetSystemMetrics(0)-W) div 2;Y:=(GetSystemMetrics(1)-H) div 2;
  WizardForm.SetBounds(X,Y,W,H);
  GridColumns:=3;GridRows:=3;
  if H<ScaleY(760) then begin GridColumns:=4;GridRows:=2;end;
  WizardForm.Font.Name:='Segoe UI';WizardForm.Font.Size:=11;
  WizardForm.WizardBitmapImage.Width:=WizardForm.WelcomePage.Width*28 div 100;
  WizardForm.WelcomeLabel1.Left:=WizardForm.WizardBitmapImage.Width+ScaleX(60);
  WizardForm.WelcomeLabel1.Top:=ScaleY(52);
  WizardForm.WelcomeLabel1.Width:=WizardForm.WelcomePage.Width-WizardForm.WelcomeLabel1.Left-ScaleX(55);
  WizardForm.WelcomeLabel1.Font.Name:='Bahnschrift';WizardForm.WelcomeLabel1.Font.Size:=34;
  WizardForm.WelcomeLabel1.Height:=ScaleY(125);
  WizardForm.WelcomeLabel2.Top:=WizardForm.WelcomeLabel1.Top+ScaleY(150);
  WizardForm.WelcomeLabel2.Left:=WizardForm.WelcomeLabel1.Left;
  WizardForm.WelcomeLabel2.Width:=WizardForm.WelcomeLabel1.Width;
  WizardForm.WelcomeLabel2.Height:=WizardForm.WelcomePage.Height-WizardForm.WelcomeLabel2.Top-ScaleY(24);
  WizardForm.WelcomeLabel2.Font.Size:=15;
  if GridColumns=4 then WizardForm.WelcomeLabel2.Font.Size:=12;
  WizardForm.PageNameLabel.Font.Name:='Bahnschrift';WizardForm.PageNameLabel.Font.Size:=13;
  WizardForm.PageDescriptionLabel.Font.Size:=11;
  WizardForm.NextButton.Width:=ScaleX(126);WizardForm.NextButton.Height:=ScaleY(36);
  WizardForm.NextButton.Left:=WizardForm.CancelButton.Left-ScaleX(142);
  WizardForm.BackButton.Width:=ScaleX(100);WizardForm.BackButton.Height:=ScaleY(36);
  WizardForm.BackButton.Left:=WizardForm.NextButton.Left-ScaleX(116);
  WizardForm.NextButton.Top:=WizardForm.ClientHeight-ScaleY(52);
  WizardForm.BackButton.Top:=WizardForm.NextButton.Top;
  WizardForm.CancelButton.Top:=WizardForm.NextButton.Top;WizardForm.CancelButton.Height:=ScaleY(36);
  ModulesPage:=CreateCustomPage(wpSelectComponents,'BUILD YOUR TOOLKIT','01 / 02   •   Your everyday essentials');
  ToolsPage:=CreateCustomPage(ModulesPage.ID,'MAKE IT YOURS','02 / 02   •   More ways to play');
  PageHeading(ModulesPage,'Your verse. Your toolkit.','Bright cards install. Grey cards do not. Click anywhere on a card to switch it.',0);
  PageHeading(ToolsPage,'Make every session count.','Your selection carries across both pages. Grey means not installing.',1);
  AddCard(0,ModulesPage,0,'synthstrings','SynthStrings + Reputation','Your reputation and owned blueprints, right in the game text.','IN-GAME TEXT  /  ACCOUNT ACCESS',#$E8D4);
  AddCard(1,ModulesPage,1,'mining_tools','Mining Tools','Plan trips, keep a mining diary and manage refinery records.','PLANNING + LOCAL RECORDS',#$E90F);
  AddCard(2,ModulesPage,2,'mining_recognition','Live Mining Recognition','Reads rock details and refinery terminals from the game screen.','!  READS YOUR GAME SCREEN  /  OCR',#$E890);
  CardBadges[2].SetBounds(ScaleX(24),Cards[2].Height-ScaleY(40),Cards[2].Width-ScaleX(48),ScaleY(26));
  CardDescriptions[2].Height:=CardDescriptions[2].Height-ScaleY(20);
  CardBadges[2].Caption:='SCREEN READER  /  READS THE GAME WINDOW';
  CardBadges[2].Font.Size:=11;CardBadges[2].Font.Style:=[fsBold];
  if GridColumns=4 then begin CardBadges[2].Font.Size:=9;CardBadges[2].Caption:='SCREEN READER (OCR)';end;
  AddCard(3,ModulesPage,3,'blueprints','Crafting + Blueprints','Your collection, recipes, quality effects and acquisition routes.','LIBRARY + CRAFTING',#$E8F1);
  AddCard(4,ModulesPage,4,'item_finder','Item + Ship Finder','Find equipment, ships, shops and public market information.','SEARCH + PUBLIC PRICES',#$E721);
  AddCard(5,ModulesPage,5,'server_hud','Server HUD','A clear, permanent region and shard ribbon above the action.','BACKGROUND DATA  /  NO OCR',#$E9D9);
  AddCard(6,ModulesPage,6,'server_history','Server History','Remember where you played, and spot repeat shard visits.','YOUR SESSION TIMELINE',#$E81C);
  AddAssurance(ModulesPage,'Only the amber mining card reads your screen.','Screen reading (OCR) turns game-window text into mining data. It runs on your PC: no image uploads, no desktop capture, and focus-loss pause by default. Switch that card off to keep capture/OCR components uninstalled. All other cards work without screen reading.');
  AddCard(7,ToolsPage,0,'people','People','Tag players, manage relationships and set appearance alerts.','ACCOUNT ACCESS',#$E716);
  AddCard(8,ToolsPage,1,'piracy','Piracy','Keep a wait timer and review available game-log reports.','NO OCR  /  NOT A CATCH DETECTOR',#$E7BA);
  AddCard(9,ToolsPage,2,'missions','Missions + Ledger','Follow contracts, completion times, money and reputation changes.','ACCOUNT ACCESS',#$E9D5);
  AddCard(10,ToolsPage,3,'hangars','Hangars + Compboards','Executive hangar timing and your saved compboard sets.','COMMUNITY SCHEDULE ESTIMATES',#$E7C1);
  AddCard(11,ToolsPage,4,'daylight','Day / Night Forecast','Check destination lighting before you head out.','DESTINATION PLANNING',#$E706);
  AddCard(12,ToolsPage,5,'acceptance','Automatic Acceptance','An optional helper for incoming game notifications.','AUTOMATED INPUT  /  OFF UNTIL ENABLED',#$E73E);
  AddCard(13,ToolsPage,6,'notes','Personal Notes','Keep the details worth remembering, close at hand.','LOCAL NOTEBOOK',#$E70B);
  AddAssurance(ToolsPage,'Your records stay yours.','Blueprints, history, notes and ledgers stay on this Windows account. No SynthScan account, analytics signup or usage beacon. Signed packages and integrity checks protect updates; changing modules keeps your saved records.');
  ExplainCard(0,'Make the game menus work harder for you. Add verified reputation beside organizations, show owned blueprint markers in supported mission text, and shorten distracting labels. Managed backups and patch checks protect your existing game text.');
  ExplainCard(1,'Turn a mining trip into a plan. Find material locations and overlaps, keep a diary of standout rocks and hauls, bookmark coordinates, and manage manual refinery records. Planning and saved records work without screen reading.');
  ExplainCard(2,'Let the rock tell you what it is worth. Reads visible signatures, mass, composition and quality for a clearer rock breakdown and ore-value estimate. Also supports refinery-terminal imports. This is the only feature that captures the game window.');
  ExplainCard(3,'Know what you can build and what to chase next. Browse your blueprint collection, mark older unlocks as owned, review recipes and material-quality effects, and find supported mission unlocks. Keep crafting information together in one library.');
  ExplainCard(4,'Spend less time hunting through tabs. Search items, ships and equipment, compare available shop locations and public prices, and inspect useful item details. Public price information needs no UEX token.');
  ExplainCard(5,'Keep your session identity in sight. A compact permanent ribbon shows your region, shard identity and supported background readings, with quick access to the activity HUD. Get clearer session context without a screen-reading dependency.');
  ExplainCard(6,'Make server hopping less of a guessing game. Look back through timestamped shard visits, spot servers you have already tried, and keep session notes. History reflects your own recorded visits, not the lifetime of a server.');
  ExplainCard(7,'Put familiar names in context. Browse reported shard members, search handles, add player tags and relationships, and enable optional appearance alerts. Friend and party actions stay separate from passive information.');
  ExplainCard(8,'Keep your piracy session organized. Use a manual waiting timer and review interdiction-related reports that appear in the game log. It works without OCR; the available reports do not identify every catch.');
  ExplainCard(9,'See what your time earned. Follow supported contracts, compare configured rewards with observed outcomes, track completion times, and review money and verified reputation changes in your local ledger. Unknown changes remain visible.');
  ExplainCard(10,'Arrive with a plan and the right boards. Keep the five-light executive hangar estimate in view, count your compboards and complete sets, and record a set used for a claim. Timings refresh from community data and are clearly labeled as estimates.');
  ExplainCard(11,'Choose your destination before choosing your moment. Select a system, body and supported location to forecast daylight, sunrise and sunset. Use it to plan a trip or operation; special event instances may need separate verification.');
  ExplainCard(12,'Miss fewer fleeting notifications. An opt-in helper can respond to supported incoming requests with your configured game key. It starts off, and sends input only when enabled and the game is focused. No screen reading is required.');
  ExplainCard(13,'Keep the details that never fit in a waypoint. Save routes, plans, reminders and session notes in your local notebook. Your notes remain on this Windows account and are kept when you remove the feature.');
#ifdef ValidationBuild
  WizardForm.WelcomeLabel2.Caption := WizardForm.WelcomeLabel2.Caption+#13#10+#13#10+'ISOLATED TEST: A separate, empty profile. Game-text and permission changes are blocked. Your regular SynthScan records are untouched.';
#endif
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result:=PageID=wpSelectComponents;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID=ModulesPage.ID) or (CurPageID=ToolsPage.ID) then begin
    RefreshCards;
    WizardForm.NextButton.Caption:='Continue  '+#$2192;
  end;
end;
