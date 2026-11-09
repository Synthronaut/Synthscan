// Required visual standards: ../DESIGN.md. Keep text short and controls generous.
type
  TGradientVertex=record X,Y:Integer;Red,Green,Blue,Alpha:Word;end;
  TGradientVertices=array[0..1] of TGradientVertex;
  TGradientRect=record UpperLeft,LowerRight:Cardinal;end;
var
  ModulesPage, ToolsPage: TWizardPage;
  ExtraPage1,ExtraPage2:TWizardPage;
  FeaturePages:array[0..6] of TWizardPage;
  CardIds: array[0..12] of String;
  Cards: array[0..12] of TPanel;
  CardPaint: array[0..12] of TBitmapImage;
  CardButtons: array[0..12] of TBitmapButton;
  CardTitles: array[0..12] of TLabel;
  CardDescriptions: array[0..12] of TLabel;
  CardBadges: array[0..12] of TLabel;
  CardIcons: array[0..12] of TLabel;
  CardSelected: array[0..12] of Boolean;
  SelectionLabels: array[0..6] of TNewStaticText;
  Headings,Subheadings: array[0..6] of TNewStaticText;
  AssuranceTitles,AssuranceBodies: array[0..1] of TLabel;
  PresetButtons: array[0..13] of TBitmapButton;
  NavigationButtons: array[0..2] of TBitmapButton;
  GridColumns,GridRows: Integer;
  CardGridTop: Integer;
  FeaturePageCount:Integer;
  NoticeReserve:Integer;
  LastTextMeasure:String;

function GetSystemMetrics(Index: Integer): Integer;
  external 'GetSystemMetrics@user32.dll stdcall';
function CreateRoundRectRgn(X1,Y1,X2,Y2,W,H: Integer): NativeUInt;
  external 'CreateRoundRectRgn@gdi32.dll stdcall';
function SetWindowRgn(Window,Region: NativeUInt; Redraw: Boolean): Integer;
  external 'SetWindowRgn@user32.dll stdcall';
function SelectClipRgn(DC,Region: NativeUInt): Integer;
  external 'SelectClipRgn@gdi32.dll stdcall';
function DeleteObject(Obj: NativeUInt): Boolean;
  external 'DeleteObject@gdi32.dll stdcall';
function SelectObject(DC,Obj:NativeUInt):NativeUInt;
  external 'SelectObject@gdi32.dll stdcall';
function DrawTextW(DC: NativeUInt; Text: String; Count: Integer;var Bounds: TRect;Flags: Cardinal): Integer;
  external 'DrawTextW@user32.dll stdcall';
function GradientFill(DC:NativeUInt;var Vertices:TGradientVertices;VertexCount:Cardinal;var Mesh:TGradientRect;MeshCount,Mode:Cardinal):Boolean;
  external 'GradientFill@msimg32.dll stdcall';
function PostMessageW(Window:NativeUInt;Msg:Cardinal;WParam:NativeUInt;LParam:NativeInt):Boolean;
  external 'PostMessageW@user32.dll stdcall';

function BlendColor(First,Last: TColor;Position,Total: Integer): TColor;
var R,G,B: Integer;
begin
  R:=(First and 255)+((Last and 255)-(First and 255))*Position div Total;
  G:=((First shr 8) and 255)+(((Last shr 8) and 255)-((First shr 8) and 255))*Position div Total;
  B:=((First shr 16) and 255)+(((Last shr 16) and 255)-((First shr 16) and 255))*Position div Total;
  Result:=R+(G shl 8)+(B shl 16);
end;

procedure PaintPill(Button: TBitmapButton;const Caption: String;Background,Fill,Border,Ink: TColor);
begin
  Button.Caption:=Caption;Button.BackColor:=Background;
  with Button.Bitmap do begin
    Width:=Button.Width-4;Height:=Button.Height-4;
    Canvas.Brush.Color:=Background;Canvas.Pen.Color:=Background;Canvas.Rectangle(0,0,Width,Height);
    Canvas.Brush.Color:=Fill;Canvas.Pen.Color:=Border;Canvas.Pen.Width:=1;
    Canvas.RoundRect(0,0,Width,Height,ScaleX(16),ScaleY(16));
    Canvas.Font.Name:='Segoe UI Semibold';Canvas.Font.PixelsPerInch:=WizardForm.Font.PixelsPerInch;Canvas.Font.Size:=10;Canvas.Font.Color:=Ink;
    Canvas.Brush.Style:=bsClear;
    Canvas.TextOut((Width-Canvas.TextWidth(Caption)) div 2,(Height-Canvas.TextHeight(Caption)) div 2,Caption);
    Canvas.Brush.Style:=bsSolid;
  end;
  Button.Invalidate;
end;

function NavigationTarget(Index:Integer):TNewButton;
begin
  Result:=nil;
  case Index of
    0:Result:=WizardForm.BackButton;
    1:Result:=WizardForm.NextButton;
    2:Result:=WizardForm.CancelButton;
  end;
end;

procedure NavigationClick(Sender:TObject);
var Target:TNewButton;
begin
  Target:=NavigationTarget(TComponent(Sender).Tag);
  // Queue the wizard's own button action after this script callback returns.
  // Calling its event synchronously can re-enter the Pascal interpreter.
  if Target<>nil then if Target.Enabled then PostMessageW(Target.Handle,$00F5,0,0);
end;

procedure SyncNavigation;
var Caption: String;
begin
  NavigationButtons[0].Visible:=WizardForm.BackButton.Visible;NavigationButtons[0].Enabled:=WizardForm.BackButton.Enabled;
  NavigationButtons[1].Visible:=WizardForm.NextButton.Visible;NavigationButtons[1].Enabled:=WizardForm.NextButton.Enabled;
  NavigationButtons[2].Visible:=WizardForm.CancelButton.Visible;NavigationButtons[2].Enabled:=WizardForm.CancelButton.Enabled;
  Caption:=WizardForm.NextButton.Caption;StringChangeEx(Caption,'&','',True);
  PaintPill(NavigationButtons[0],#$2190+'  Back',$001D1510,$002B2118,$005D4833,$00D6C6B1);
  PaintPill(NavigationButtons[1],Caption,$001D1510,$00EDD89A,$00EDD89A,$00291E10);
  PaintPill(NavigationButtons[2],'Cancel',$001D1510,$001D1510,$001D1510,$00B4A493);
end;

procedure RefreshCards;
var I,Count: Integer; Fill,TopFill,Border,Ink: TColor;Clip: NativeUInt;Vertices:TGradientVertices;Mesh:TGradientRect;
begin
  Count := 0;
  for I := 0 to 12 do begin
    CardSelected[I] := WizardIsComponentSelected(CardIds[I]);
    if CardSelected[I] then begin
      Count := Count+1; Fill := $00312114;TopFill:=$004C3825;Border:=$00655038; Ink := $00FFFFFF;
      CardButtons[I].Caption := #$2713+' Included';
    end else begin
      Fill := $001B1816;TopFill:=$0024211E; Border := $003B3732; Ink := $00827D76;
      CardButtons[I].Caption := 'Not installing';
    end;
    if (I=2) and CardSelected[I] then begin Fill:=$00141B24;TopFill:=$00253243;Border:=$006BC9FF;end;
    Cards[I].Color := Fill;
    with CardPaint[I].Bitmap do begin
      Width := CardPaint[I].Width; Height := CardPaint[I].Height;
      Canvas.Brush.Color := $001D1510; Canvas.Pen.Color := $001D1510;
      Canvas.Rectangle(0,0,Width,Height);
      Clip:=CreateRoundRectRgn(ScaleX(2),ScaleY(2),Width-ScaleX(2),Height-ScaleY(2),ScaleX(22),ScaleY(22));
      SelectClipRgn(Canvas.Handle,Clip);
      Canvas.Pen.Width:=1;
      Vertices[0].X:=0;Vertices[0].Y:=0;
      Vertices[0].Red:=(TopFill and 255) shl 8;Vertices[0].Green:=((TopFill shr 8) and 255) shl 8;Vertices[0].Blue:=((TopFill shr 16) and 255) shl 8;Vertices[0].Alpha:=0;
      Vertices[1].X:=Width;Vertices[1].Y:=Height;
      Vertices[1].Red:=(Fill and 255) shl 8;Vertices[1].Green:=((Fill shr 8) and 255) shl 8;Vertices[1].Blue:=((Fill shr 16) and 255) shl 8;Vertices[1].Alpha:=0;
      Mesh.UpperLeft:=0;Mesh.LowerRight:=1;
      if not GradientFill(Canvas.Handle,Vertices,2,Mesh,1,1) then begin Canvas.Brush.Color:=Fill;Canvas.Rectangle(0,0,Width,Height);end;
      SelectClipRgn(Canvas.Handle,0);DeleteObject(Clip);
      Canvas.Brush.Style:=bsClear; Canvas.Pen.Color := Border;Canvas.Pen.Width:=1;
      if (I=2) and CardSelected[I] then Canvas.Pen.Width:=ScaleX(3);
      Canvas.RoundRect(ScaleX(2),ScaleY(2),Width-ScaleX(2),Height-ScaleY(2),ScaleX(22),ScaleY(22));
      Canvas.Brush.Style:=bsSolid;
      if CardSelected[I] and (I<>2) then begin
        Canvas.Pen.Color:=$00D7BB70;Canvas.Pen.Width:=ScaleX(2);
        Canvas.MoveTo(ScaleX(24),ScaleY(3));Canvas.LineTo(Width-ScaleX(24),ScaleY(3));
      end;
      if I=2 then begin
        if CardSelected[I] then Canvas.Brush.Color:=$006BC9FF else Canvas.Brush.Color:=$003B3732;
        Canvas.Pen.Color:=Canvas.Brush.Color;Canvas.Pen.Width:=1;
        if GridColumns=2 then Canvas.RoundRect(ScaleX(16),Height-ScaleY(32),Width-ScaleX(16),Height-ScaleY(8),ScaleX(10),ScaleY(10))
        else Canvas.RoundRect(ScaleX(16),Height-ScaleY(48),Width-ScaleX(16),Height-ScaleY(12),ScaleX(10),ScaleY(10));
        if GridColumns=2 then Canvas.Ellipse(ScaleX(12),ScaleY(4),ScaleX(40),ScaleY(32))
        else Canvas.Ellipse(ScaleX(12),ScaleY(9),ScaleX(56),ScaleY(52));
      end;
    end;
    CardTitles[I].Font.Color := Ink;
    if CardSelected[I] then PaintPill(CardButtons[I],#$2713+' Included',BlendColor(TopFill,Fill,25,CardPaint[I].Height),$00443C20,$007B7950,$00DAF2B2)
    else PaintPill(CardButtons[I],'Not installing',BlendColor(TopFill,Fill,25,CardPaint[I].Height),$002B2723,$00413A33,$00918A82);
    CardButtons[I].Caption:=CardTitles[I].Caption+' — '+CardButtons[I].Caption;
    if CardSelected[I] then begin
      CardIcons[I].Font.Color := $00FFE59A;
      CardDescriptions[I].Font.Color := $00DAC5AE;
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
  for I:=0 to FeaturePageCount-1 do SelectionLabels[I].Caption := IntToStr(Count)+' features included  /  Core always included';
end;

function ContentFits(const Text: String;Font:TFont;Width,Height:Integer): Boolean;
var Bitmap: TBitmap;Bounds:TRect;Measured:Integer;OldFont:NativeUInt;MeasuredText:String;
begin
  Bitmap:=TBitmap.Create;
  try
    MeasuredText:=TrimRight(Text);
    Bitmap.Width:=1;Bitmap.Height:=1;
    OldFont:=SelectObject(Bitmap.Canvas.Handle,Font.Handle);
    Bounds.Left:=0;Bounds.Top:=0;Bounds.Right:=Width;Bounds.Bottom:=0;
    Measured:=DrawTextW(Bitmap.Canvas.Handle,MeasuredText,Length(MeasuredText),Bounds,$00000C10);
    SelectObject(Bitmap.Canvas.Handle,OldFont);
    LastTextMeasure:=' requested='+IntToStr(Width)+'x'+IntToStr(Height)+' measured='+IntToStr(Bounds.Right)+'x'+IntToStr(Bounds.Bottom)+' font='+Font.Name+' '+IntToStr(Font.Size)+' ppi='+IntToStr(Font.PixelsPerInch)+' height='+IntToStr(Font.Height)+' text='+Text;
    Result:=((MeasuredText='') or (Measured>0)) and (Bounds.Bottom<=Height) and (Bounds.Right<=Width);
  finally Bitmap.Free;end;
end;

function TextFits(LabelText:TLabel):Boolean;
begin
  Result:=ContentFits(LabelText.Caption,LabelText.Font,LabelText.Width,LabelText.Height);
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
  for I:=0 to 12 do begin
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
  for I:=0 to 12 do CardSelected[I] := True;
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
  if FeaturePageCount=7 then begin Page:=FeaturePages[Index div 2];Slot:=Index mod 2;end
  else if FeaturePageCount=4 then begin
    if Index<4 then begin Page:=ModulesPage;Slot:=Index;end
    else if Index<8 then begin Page:=ToolsPage;Slot:=Index-4;end
    else if Index<11 then begin Page:=ExtraPage1;Slot:=Index-8;end
    else begin Page:=ExtraPage2;Slot:=Index-11;end;
  end;
  Gap := ScaleX(16); W := (Page.SurfaceWidth-Gap*(GridColumns-1)) div GridColumns;
  H := (Page.SurfaceHeight-ScaleY(CardGridTop+14+NoticeReserve)-Gap*(GridRows-1)) div GridRows;
  X := (Slot mod GridColumns)*(W+Gap); Y := ScaleY(CardGridTop)+(Slot div GridColumns)*(H+Gap);
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
  CardButtons[Index] := TBitmapButton.Create(WizardForm); CardButtons[Index].Parent := Cards[Index];
  CardButtons[Index].SetBounds(W-ScaleX(117),ScaleY(15),ScaleX(99),ScaleY(32));
  CardButtons[Index].Tag := Index; CardButtons[Index].OnClick := @ToggleCard;
  CardButtons[Index].AutoSize:=False;CardButtons[Index].Cursor:=crHandPoint;
  CardButtons[Index].TabStop:=True;
  CardButtons[Index].Hint := Title+' — Space to include or remove'; CardButtons[Index].ShowHint := True;
  CardTitles[Index] := CardLabel(Cards[Index],Title,ScaleX(19),ScaleY(53),W-ScaleX(38),ScaleY(30),16,Index,$00EBFADE);
  CardTitles[Index].Font.Name := 'Bahnschrift';
  CardDescriptions[Index] := CardLabel(Cards[Index],Description,ScaleX(19),ScaleY(86),W-ScaleX(38),H-ScaleY(120),11,Index,$00C3B5A3);
  CardBadges[Index] := CardLabel(Cards[Index],Badge,ScaleX(19),H-ScaleY(28),W-ScaleX(38),ScaleY(19),9,Index,$00B6A184);
  CardBadges[Index].Font.Name := 'Segoe UI Semibold';
  if GridColumns=2 then begin
    CardTitles[Index].Font.Size:=13;
    CardTitles[Index].Top:=ScaleY(36);CardTitles[Index].Height:=ScaleY(22);
    CardDescriptions[Index].Font.Size:=10;
    CardDescriptions[Index].Top:=ScaleY(60);CardDescriptions[Index].Height:=H-ScaleY(88);
    CardIcons[Index].Top:=ScaleY(8);CardIcons[Index].Height:=ScaleY(20);CardIcons[Index].Font.Size:=14;
    CardButtons[Index].Top:=ScaleY(5);CardButtons[Index].Height:=ScaleY(26);
    CardBadges[Index].Font.Size:=8;
  end;
  if Index=2 then CardBadges[Index].Font.Color := $008DCDEE;
end;

procedure PageHeading(Page: TWizardPage; const Title,Subtitle: String; Number: Integer);
var LabelText: TNewStaticText; Button: TBitmapButton;
begin
  LabelText := TNewStaticText.Create(WizardForm); LabelText.Parent := Page.Surface;
  LabelText.AutoSize:=False;
  LabelText.SetBounds(0,0,Page.SurfaceWidth,ScaleY(46)); LabelText.Caption := Title;
  LabelText.Font.Name := 'Bahnschrift'; LabelText.Font.Size := 28; LabelText.Font.Color := $00F4F0E6;
  Headings[Number]:=LabelText;
  if GridColumns=2 then begin LabelText.Font.Size:=24;LabelText.Height:=ScaleY(39);end;
  LabelText := TNewStaticText.Create(WizardForm); LabelText.Parent := Page.Surface;
  LabelText.AutoSize:=False;
  LabelText.SetBounds(0,ScaleY(49),Page.SurfaceWidth,ScaleY(25)); LabelText.Caption := Subtitle;
  LabelText.Font.Size := 12; LabelText.Font.Color := $00C4B7A0;
  Subheadings[Number]:=LabelText;
  if GridColumns=2 then begin LabelText.Top:=ScaleY(42);LabelText.Height:=ScaleY(18);LabelText.Font.Size:=10;end;
  SelectionLabels[Number] := TNewStaticText.Create(WizardForm); SelectionLabels[Number].Parent := Page.Surface;
  SelectionLabels[Number].AutoSize:=False;
  SelectionLabels[Number].SetBounds(0,ScaleY(81),Page.SurfaceWidth div 2,ScaleY(20));
  SelectionLabels[Number].Font.Size := 10; SelectionLabels[Number].Font.Color := $00BCAA88;
  if GridColumns=2 then SelectionLabels[Number].Top:=ScaleY(66);
  Button := TBitmapButton.Create(WizardForm); Button.Parent := Page.Surface;Button.AutoSize:=False;Button.TabStop:=True;
  Button.SetBounds(Page.SurfaceWidth-ScaleX(315),ScaleY(76),ScaleX(100),ScaleY(25));
  if GridColumns=2 then Button.Top:=ScaleY(63);
  Button.Tag := 0; Button.OnClick := @SelectAllCards;Button.Cursor:=crHandPoint;
  PaintPill(Button,'Include all',$001D1510,$00443C20,$007B7950,$00DAF2B2);PresetButtons[Number*2]:=Button;
  Button := TBitmapButton.Create(WizardForm); Button.Parent := Page.Surface;Button.AutoSize:=False;Button.TabStop:=True;
  Button.SetBounds(Page.SurfaceWidth-ScaleX(205),ScaleY(76),ScaleX(205),ScaleY(25));
  if GridColumns=2 then Button.Top:=ScaleY(63);
  Button.Tag := 1; Button.OnClick := @SelectAllCards;Button.Cursor:=crHandPoint;
  PaintPill(Button,'All without screen reading',$001D1510,$002B2118,$005D4833,$00D6C6B1);PresetButtons[Number*2+1]:=Button;
end;

procedure AddAssurance(Page: TWizardPage; const Title,Body: String);
var L: TLabel; Gap,W,H,X,Y,Number: Integer;
begin
  Number:=0;if Page=ToolsPage then Number:=1;
  if FeaturePageCount=4 then begin if Number=0 then Page:=ExtraPage1 else Page:=ExtraPage2;end;
  Gap:=ScaleX(16);W:=(Page.SurfaceWidth-Gap*(GridColumns-1)) div GridColumns;
  H:=(Page.SurfaceHeight-ScaleY(CardGridTop+14+NoticeReserve)-Gap*(GridRows-1)) div GridRows;
  X:=W+Gap;Y:=ScaleY(CardGridTop)+2*(H+Gap);
  if GridColumns=2 then begin X:=W+Gap;Y:=ScaleY(CardGridTop)+H+Gap;end;
  if FeaturePageCount=7 then begin X:=0;Y:=ScaleY(CardGridTop+10)+H;W:=Page.SurfaceWidth;end;
  L:=TLabel.Create(WizardForm);L.Parent:=Page.Surface;L.AutoSize:=False;L.Transparent:=True;L.WordWrap:=True;
  L.SetBounds(X+ScaleX(18),Y+ScaleY(22),W*2+Gap-ScaleX(36),ScaleY(30));
  if FeaturePageCount=7 then begin L.Top:=Y;L.Height:=ScaleY(24);end;
  L.Caption:=Title;L.Font.Name:='Bahnschrift';L.Font.Size:=18;L.Font.Color:=$00F4F0E6;
  if Number=0 then L.Font.Color:=$008DCDEE;
  if GridColumns=2 then begin
    L.Width:=W-ScaleX(36);L.Font.Size:=13;
    if Number=0 then L.Caption:='LOCAL. OPTIONAL.' else L.Caption:='YOUR RECORDS. YOUR PC.';
  end;
  AssuranceTitles[Number]:=L;
  L:=TLabel.Create(WizardForm);L.Parent:=Page.Surface;L.AutoSize:=False;L.Transparent:=True;
  L.SetBounds(X+ScaleX(18),Y+ScaleY(62),W*2+Gap-ScaleX(36),H-ScaleY(70));
  if FeaturePageCount=7 then begin L.Top:=Y+ScaleY(28);L.Height:=ScaleY(NoticeReserve-28);end;
  L.Caption:=Body;L.WordWrap:=True;L.Font.Size:=12;L.Font.Color:=$00C7BBA7;
  if GridColumns=2 then begin
    L.Width:=W-ScaleX(36);L.Font.Size:=10;
    if Number=0 then L.Caption:='Game-window only. No image uploads.'
    else L.Caption:='Local records. No usage tracking.';
  end;
  while (L.Font.Size>10) and not TextFits(L) do L.Font.Size:=L.Font.Size-1;
  AssuranceBodies[Number]:=L;
end;

procedure InitializeWizard;
var W,H,X,Y,I: Integer;SourceButton:TNewButton;
begin
  W:=GetSystemMetrics(0)*88 div 100;H:=GetSystemMetrics(1)*88 div 100;
#ifdef SelectionTestBuild
  W:=StrToIntDef(ExpandConstant('{param:WIDTH|}'),W);H:=StrToIntDef(ExpandConstant('{param:HEIGHT|}'),H);
#endif
  X:=(GetSystemMetrics(0)-W) div 2;Y:=(GetSystemMetrics(1)-H) div 2;
  WizardForm.SetBounds(X,Y,W,H);
  WizardForm.Font.Name:='Segoe UI';WizardForm.Font.Size:=11;
  ModulesPage:=CreateCustomPage(wpSelectComponents,'BUILD YOUR TOOLKIT','01 / 02   •   Your everyday essentials');
  ToolsPage:=CreateCustomPage(ModulesPage.ID,'MAKE IT YOURS','02 / 02   •   More ways to play');
  // Windows can constrain the wizard's requested bounds. Choose the existing
  // paged layout from the space the cards actually receive, including fonts/DPI.
  GridColumns:=3;GridRows:=3;CardGridTop:=104;FeaturePageCount:=2;NoticeReserve:=0;
  if (ModulesPage.SurfaceWidth<ScaleX(1100)) or (ModulesPage.SurfaceHeight<ScaleY(730)) then begin
    GridColumns:=2;GridRows:=2;CardGridTop:=92;FeaturePageCount:=4;
  end;
  if ModulesPage.SurfaceHeight<ScaleY(400) then begin GridRows:=1;FeaturePageCount:=7;NoticeReserve:=80;end;
  WizardForm.WizardBitmapImage.Width:=WizardForm.WelcomePage.Width*28 div 100;
  WizardForm.WelcomeLabel1.Left:=WizardForm.WizardBitmapImage.Width+ScaleX(60);
  WizardForm.WelcomeLabel1.Top:=ScaleY(52);
  WizardForm.WelcomeLabel1.Width:=WizardForm.WelcomePage.Width-WizardForm.WelcomeLabel1.Left-ScaleX(55);
  WizardForm.WelcomeLabel1.AutoSize:=False;
  WizardForm.WelcomeLabel1.Font.Name:='Bahnschrift';WizardForm.WelcomeLabel1.Font.Size:=34;
  WizardForm.WelcomeLabel1.Height:=ScaleY(125);
  WizardForm.WelcomeLabel2.Top:=WizardForm.WelcomeLabel1.Top+ScaleY(150);
  WizardForm.WelcomeLabel2.Left:=WizardForm.WelcomeLabel1.Left;
  WizardForm.WelcomeLabel2.Width:=WizardForm.WelcomeLabel1.Width;
  WizardForm.WelcomeLabel2.AutoSize:=False;WizardForm.WelcomeLabel2.WordWrap:=True;
  WizardForm.WelcomeLabel2.Height:=WizardForm.WelcomePage.Height-WizardForm.WelcomeLabel2.Top-ScaleY(24);
  WizardForm.WelcomeLabel2.Font.Size:=15;
  if GridColumns=2 then begin
    WizardForm.WelcomeLabel1.Top:=ScaleY(28);WizardForm.WelcomeLabel1.Font.Size:=28;WizardForm.WelcomeLabel1.Height:=ScaleY(104);
    WizardForm.WelcomeLabel2.Top:=WizardForm.WelcomeLabel1.Top+ScaleY(120);
    WizardForm.WelcomeLabel2.Height:=WizardForm.WelcomePage.Height-WizardForm.WelcomeLabel2.Top-ScaleY(20);
    WizardForm.WelcomeLabel2.Font.Size:=12;
    WizardForm.WelcomeLabel2.Caption:='Your HUD, game text, mining, crafting and mission records, together.'+#13#10+#13#10+'Choose the features you want. Leave the screen reader off to install without OCR.'+#13#10+#13#10+'Your records stay on this PC.';
  end;
  WizardForm.PageNameLabel.Font.Name:='Bahnschrift';WizardForm.PageNameLabel.Font.Size:=13;
  WizardForm.PageDescriptionLabel.Font.Size:=11;
  WizardForm.NextButton.Width:=ScaleX(126);WizardForm.NextButton.Height:=ScaleY(36);
  WizardForm.NextButton.Left:=WizardForm.CancelButton.Left-ScaleX(142);
  WizardForm.BackButton.Width:=ScaleX(100);WizardForm.BackButton.Height:=ScaleY(36);
  WizardForm.BackButton.Left:=WizardForm.NextButton.Left-ScaleX(116);
  WizardForm.NextButton.Top:=WizardForm.ClientHeight-ScaleY(52);
  WizardForm.BackButton.Top:=WizardForm.NextButton.Top;
  WizardForm.CancelButton.Top:=WizardForm.NextButton.Top;WizardForm.CancelButton.Height:=ScaleY(36);
  for I:=0 to 2 do begin
    case I of
      0:SourceButton:=WizardForm.BackButton;
      1:SourceButton:=WizardForm.NextButton;
      2:SourceButton:=WizardForm.CancelButton;
    end;
    SourceButton.TabStop:=False;
    NavigationButtons[I]:=TBitmapButton.Create(WizardForm);NavigationButtons[I].Parent:=WizardForm;
    NavigationButtons[I].AutoSize:=False;NavigationButtons[I].Cursor:=crHandPoint;
    NavigationButtons[I].TabStop:=True;
    NavigationButtons[I].SetBounds(SourceButton.Left,SourceButton.Top,SourceButton.Width,SourceButton.Height);
    NavigationButtons[I].Tag:=I;NavigationButtons[I].OnClick:=@NavigationClick;
    NavigationButtons[I].BringToFront;
  end;
  FeaturePages[0]:=ModulesPage;FeaturePages[1]:=ToolsPage;
  if FeaturePageCount=4 then begin
    ModulesPage.Description:='01 / 04   •   Your everyday essentials';ToolsPage.Description:='02 / 04   •   Explore your verse';
    ExtraPage1:=CreateCustomPage(ToolsPage.ID,'MAKE EVERY SESSION COUNT','03 / 04   •   Your session tools');
    ExtraPage2:=CreateCustomPage(ExtraPage1.ID,'MAKE IT YOURS','04 / 04   •   The finishing touches');
    FeaturePages[2]:=ExtraPage1;FeaturePages[3]:=ExtraPage2;
    PageHeading(ModulesPage,'Build your essentials.','Only Live Mining Recognition reads the game window, locally.',0);
    PageHeading(ToolsPage,'Find your way around.','Bright means included. Grey means not installing.',1);
    PageHeading(ExtraPage1,'Make every session count.','Your selection carries across all four pages.',2);
    PageHeading(ExtraPage2,'Keep the details close.','Finish your personal toolkit.',3);
  end else if FeaturePageCount=7 then begin
    for I:=2 to 6 do FeaturePages[I]:=CreateCustomPage(FeaturePages[I-1].ID,'BUILD YOUR TOOLKIT',IntToStr(I+1)+' / 07');
    ModulesPage.Description:='01 / 07   •   Your everyday essentials';ToolsPage.Description:='02 / 07   •   Recognition and crafting';
    PageHeading(ModulesPage,'Build your essentials.','Bright means included. Grey means not installing.',0);
    PageHeading(ToolsPage,'See more. Craft more.','The amber card is the only screen reader.',1);
    PageHeading(FeaturePages[2],'Find your way around.','Items, ships and your current session.',2);
    PageHeading(FeaturePages[3],'Know your surroundings.','Your history and familiar faces.',3);
    PageHeading(FeaturePages[4],'Make your time count.','Tools for your next session.',4);
    PageHeading(FeaturePages[5],'Plan your next move.','The right place, at the right time.',5);
    PageHeading(FeaturePages[6],'Keep the details close.','Finish your personal toolkit.',6);
  end else begin
    PageHeading(ModulesPage,'Your verse. Your toolkit.','Bright cards install. Grey cards do not. Click anywhere on a card to switch it.',0);
    PageHeading(ToolsPage,'Make every session count.','Your selection carries across both pages. Grey means not installing.',1);
  end;
  AddCard(0,ModulesPage,0,'synthstrings','SynthStrings + Reputation','Your reputation and owned blueprints, right in the game text.','IN-GAME TEXT  /  ACCOUNT ACCESS',#$E8D4);
  AddCard(1,ModulesPage,1,'mining_tools','Mining Tools','Plan trips, keep a mining diary and manage refinery records.','PLANNING + LOCAL RECORDS',#$E90F);
  AddCard(2,ModulesPage,2,'mining_recognition','Live Mining Recognition','Reads rock details and refinery terminals from the game screen.','!  READS YOUR GAME SCREEN  /  OCR',#$E890);
  CardBadges[2].SetBounds(ScaleX(24),Cards[2].Height-ScaleY(40),Cards[2].Width-ScaleX(48),ScaleY(26));
  CardDescriptions[2].Height:=CardDescriptions[2].Height-ScaleY(20);
  CardBadges[2].Caption:='SCREEN READER  /  READS THE GAME WINDOW';
  CardBadges[2].Font.Size:=11;CardBadges[2].Font.Style:=[fsBold];
  if GridColumns=2 then begin
    CardBadges[2].SetBounds(ScaleX(24),Cards[2].Height-ScaleY(28),Cards[2].Width-ScaleX(48),ScaleY(20));
    CardDescriptions[2].Height:=CardDescriptions[2].Height+ScaleY(12);
    CardDescriptions[2].Caption:='Live rock + refinery screen reading.';
    CardBadges[2].Font.Size:=9;CardBadges[2].Caption:='SCREEN READER (OCR)';
  end;
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
  AddAssurance(ToolsPage,'Your records stay yours.','Blueprints, history, notes and ledgers stay on this Windows account. No SynthScan account, analytics signup or usage beacon. Signed packages and integrity checks protect updates; changing modules keeps your saved records.');
  // Keep a measured gap above each badge, using its final OCR/non-OCR bounds.
  for I:=0 to 12 do CardDescriptions[I].Height:=CardBadges[I].Top-CardDescriptions[I].Top-ScaleY(4);
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
#ifdef ValidationBuild
  WizardForm.WelcomeLabel2.Caption := WizardForm.WelcomeLabel2.Caption+#13#10+#13#10+'ISOLATED TEST: A separate, empty profile. Game-text and permission changes are blocked. Your regular SynthScan records are untouched.';
#endif
  while (WizardForm.WelcomeLabel2.Font.Size>10) and not ContentFits(WizardForm.WelcomeLabel2.Caption,WizardForm.WelcomeLabel2.Font,WizardForm.WelcomeLabel2.Width,WizardForm.WelcomeLabel2.Height) do
    WizardForm.WelcomeLabel2.Font.Size:=WizardForm.WelcomeLabel2.Font.Size-1;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result:=(PageID=wpSelectComponents) or (PageID=wpSelectTasks);
end;

procedure CurPageChanged(CurPageID: Integer);
var IsFeaturePage:Boolean;I:Integer;
begin
  IsFeaturePage:=False;
  for I:=0 to FeaturePageCount-1 do if FeaturePages[I]<>nil then IsFeaturePage:=IsFeaturePage or (CurPageID=FeaturePages[I].ID);
  if IsFeaturePage then begin
    RefreshCards;
    if CurPageID=FeaturePages[FeaturePageCount-1].ID then WizardForm.NextButton.Caption:='Install features'
    else WizardForm.NextButton.Caption:='Continue  '+#$2192;
  end;
  SyncNavigation;
end;
