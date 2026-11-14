#pragma once
#include <windows.h>
#include <gdiplus.h>
#include <string>
#include <algorithm>
namespace SynthGlass {
using namespace Gdiplus;
inline const Color Ink(255,232,239,244),Muted(255,142,157,173),Accent(255,161,205,208),Base(255,14,18,25);
inline void ambient(Graphics& g,RectF r){
    GraphicsPath glow;glow.AddEllipse(r.X+r.Width*.30f,r.Y-r.Height*.42f,r.Width*.95f,r.Height*.9f);
    PathGradientBrush light(&glow);light.SetCenterColor(Color(28,100,137,170));Color edge(0,100,137,170);INT count=1;light.SetSurroundColors(&edge,&count);g.FillPath(&light,&glow);
}
inline void shape(GraphicsPath& p,RectF r,float radius){
    float d=std::min(radius*2,std::min(r.Width,r.Height));if(d<=0)return;
    p.AddArc(r.X,r.Y,d,d,180,90);p.AddArc(r.GetRight()-d,r.Y,d,d,270,90);p.AddArc(r.GetRight()-d,r.GetBottom()-d,d,d,0,90);p.AddArc(r.X,r.GetBottom()-d,d,d,90,90);p.CloseFigure();
}
inline void rounded(Graphics& g,RectF r,Color fill,float radius=10,Color border=Color(0,0,0,0)){
    GraphicsPath p;shape(p,r,radius);SolidBrush b(fill);g.FillPath(&b,&p);if(border.GetA()){Pen pen(border,1);g.DrawPath(&pen,&p);}
}
inline void panel(Graphics& g,RectF r,bool selected=false,bool hot=false,float radius=10){
    GraphicsPath p;shape(p,r,radius);
    LinearGradientBrush fill(PointF(r.X,r.Y),PointF(r.X,r.GetBottom()+1),selected?Color(242,38,57,64):hot?Color(240,35,44,57):Color(238,28,35,47),selected?Color(238,27,43,49):Color(232,19,25,35));g.FillPath(&fill,&p);
    Pen edge(selected?Color(160,148,198,202):hot?Color(80,174,193,219):Color(40,174,193,219),1);g.DrawPath(&edge,&p);
    Pen sheen(Color(selected?35:18,255,255,255),1);g.DrawLine(&sheen,r.X+radius,r.Y+1,r.GetRight()-radius,r.Y+1);
}
inline void text(Graphics& g,const std::wstring& value,RectF r,float size=13,Color color=Ink,bool bold=false){
    Font f(L"Segoe UI",size,bold?FontStyleBold:FontStyleRegular,UnitPixel);
    SolidBrush b(color);StringFormat fmt;fmt.SetLineAlignment(StringAlignmentCenter);fmt.SetFormatFlags(StringFormatFlagsNoWrap);fmt.SetTrimming(StringTrimmingEllipsisCharacter);g.DrawString(value.c_str(),-1,&f,r,&fmt,&b);
}
inline void icon(Graphics& g,const std::string& name,RectF box,Color color=Accent){
    auto saved=g.Save();g.TranslateTransform(box.X,box.Y);g.ScaleTransform(box.Width/24.f,box.Height/24.f);
    Pen p(color,1.5f);p.SetStartCap(LineCapRound);p.SetEndCap(LineCapRound);p.SetLineJoin(LineJoinRound);
    auto line=[&](float a,float b,float c,float d){g.DrawLine(&p,a,b,c,d);};
    if(name=="people"||name=="friend"||name=="invite"){g.DrawEllipse(&p,8.f,3.f,8.f,8.f);g.DrawArc(&p,5.f,12.f,14.f,13.f,180.f,180.f);if(name=="invite"){line(19,5,19,11);line(16,8,22,8);}else if(name=="people"){g.DrawArc(&p,1.f,6.f,6.f,6.f,90.f,180.f);g.DrawArc(&p,0.f,14.f,8.f,8.f,180.f,100.f);}}
    else if(name=="search"){g.DrawEllipse(&p,4.f,3.f,12.f,12.f);line(15,14,21,20);}
    else if(name=="refresh"){g.DrawArc(&p,4.f,4.f,16.f,16.f,40.f,285.f);line(20,3,20,9);line(14,9,20,9);}
    else if(name=="clear"){line(7,7,17,17);line(17,7,7,17);}
    else if(name=="check"){line(5,12,10,17);line(10,17,20,6);}
    else if(name=="tag"){line(3,4,13,4);line(13,4,21,12);line(21,12,12,21);line(12,21,3,12);line(3,12,3,4);g.DrawEllipse(&p,6.f,7.f,2.f,2.f);}
    else if(name=="home"){line(3,11,12,3);line(12,3,21,11);line(6,10,6,21);line(6,21,18,21);line(18,21,18,10);line(10,21,10,15);line(10,15,14,15);line(14,15,14,21);}
    else if(name=="servers"){for(int y:{4,12}){GraphicsPath r;shape(r,{3.f,float(y),18.f,7.f},2);g.DrawPath(&p,&r);line(6,float(y+3),7,float(y+3));line(15,float(y+3),18,float(y+3));}}
    else if(name=="daylight"){g.DrawEllipse(&p,7.f,7.f,10.f,10.f);line(12,1,12,4);line(12,20,12,23);line(1,12,4,12);line(20,12,23,12);line(4,4,6,6);line(18,18,20,20);line(4,20,6,18);line(18,6,20,4);}
    else if(name=="hud_piracy"){g.DrawEllipse(&p,5.f,3.f,14.f,14.f);g.DrawEllipse(&p,8.f,8.f,2.f,3.f);g.DrawEllipse(&p,14.f,8.f,2.f,3.f);line(8,21,16,21);line(10,17,10,21);line(14,17,14,21);}
    else if(name=="planner"||name=="mining"){line(4,7,17,4);line(17,4,22,8);line(12,6,7,21);line(10,9,17,17);}
    else if(name=="directory"){g.DrawEllipse(&p,3.f,3.f,18.f,18.f);line(12,6,15,12);line(15,12,9,18);line(9,18,12,6);}
    else if(name=="executive_hangar"){line(3,21,3,8);line(3,8,12,3);line(12,3,21,8);line(21,8,21,21);line(3,21,21,21);line(7,21,7,11);line(7,11,17,11);line(17,11,17,21);line(12,11,12,21);}
    else if(name=="settings"){g.DrawEllipse(&p,8.f,8.f,8.f,8.f);for(int i=0;i<8;++i){auto t=g.Save();g.TranslateTransform(12.f,12.f);g.RotateTransform(float(i*45));line(0,-9,0,-7);g.Restore(t);}}
    else if(name=="refinery"){line(9,3,15,3);line(10,3,10,10);line(14,3,14,10);line(10,10,4,21);line(4,21,20,21);line(20,21,14,10);line(7,16,17,16);}
    else if(name=="roulette"||name=="fate_roulette"){g.DrawEllipse(&p,3.f,3.f,18.f,18.f);line(12,3,12,21);line(3,12,21,12);line(5.6f,5.6f,18.4f,18.4f);line(5.6f,18.4f,18.4f,5.6f);g.DrawEllipse(&p,9.f,9.f,6.f,6.f);}
    else {GraphicsPath r;shape(r,{5,3,14,18},3);g.DrawPath(&p,&r);line(9,8,15,8);line(9,12,15,12);line(9,16,13,16);}
    g.Restore(saved);
}
inline void checkbox(Graphics& g,RectF r,bool checked,bool hot=false){panel(g,r,checked,hot,4);if(checked)icon(g,"check",{r.X+2,r.Y+2,r.Width-4,r.Height-4},Ink);}
inline void button(Graphics& g,RectF r,const std::wstring& title,const std::string& glyph,bool hot=false,bool down=false,bool disabled=false){
    panel(g,{r.X+1,r.Y+1,r.Width-2,r.Height-2},down,hot,9);float x=r.X+11;
    if(!glyph.empty()){icon(g,glyph,{x,r.Y+(r.Height-18)/2,18,18},disabled?Muted:Accent);x+=26;}
    text(g,title,{x,r.Y,r.GetRight()-x-8,r.Height},12.5f,disabled?Color(255,94,108,124):Ink);
}
}
