#include "SynthItemIcons.h"
#include <gdiplus.h>
#include <vector>
namespace SynthItemIcons {
namespace {
void draw(Gdiplus::Graphics& g,FinderItems::Icon icon){
    using namespace Gdiplus;using I=FinderItems::Icon;
    Color color(255,134,195,221);
    if(icon==I::Ammo||icon==I::Blueprint)color=Color(255,225,186,112);
    if(icon==I::Commodity||icon==I::Consumable)color=Color(255,119,201,166);
    if(icon==I::Collectible||icon==I::Clothing||icon==I::Paint)color=Color(255,186,164,218);
    Pen p(color,1.6f);p.SetLineJoin(LineJoinRound);p.SetStartCap(LineCapRound);p.SetEndCap(LineCapRound);
    auto line=[&](float x,float y,float xx,float yy){g.DrawLine(&p,x,y,xx,yy);};
    auto path=[&](std::initializer_list<PointF> points,bool closed=true){std::vector<PointF> v(points);if(closed)g.DrawPolygon(&p,v.data(),int(v.size()));else g.DrawLines(&p,v.data(),int(v.size()));};
    switch(icon){
    case I::Ship:path({{12,3},{15,10},{21,16},{15,15},{14,20},{12,18},{10,20},{9,15},{3,16},{9,10}});line(12,8,12,13);break;
    case I::Vehicle:path({{4,8},{15,8},{20,13},{20,17},{4,17}});g.DrawEllipse(&p,5.f,15.f,4.f,4.f);g.DrawEllipse(&p,15.f,15.f,4.f,4.f);line(13,9,15,13);line(4,13,19,13);break;
    case I::Collectible:g.DrawEllipse(&p,5.f,3.f,14.f,11.f);path({{8,14},{8,17},{6,20},{18,20},{16,17},{16,14}},false);line(12,5,12,11);line(9,8,15,8);break;
    case I::Armor:path({{8,4},{16,4},{19,8},{17,13},{17,19},{7,19},{7,13},{5,8}});path({{9,8},{15,8},{14,14},{12,16},{10,14}});line(5,8,9,8);line(15,8,19,8);break;
    case I::Clothing:path({{8,4},{10,6},{14,6},{16,4},{21,8},{18,12},{16,10},{16,20},{8,20},{8,10},{6,12},{3,8}});break;
    case I::Gun:path({{3,8},{19,8},{19,12},{12,12},{10,19},{6,19},{7,12},{3,12}});line(19,10,22,10);line(11,13,14,13);break;
    case I::Ammo:for(float x:{6.f,14.f}){path({{x,9},{x+2,4},{x+4,9},{x+4,20},{x,20}});line(x,16,x+4,16);}break;
    case I::ShipGun:path({{3,10},{7,7},{12,7},{14,10},{14,15},{6,15},{3,13}});line(14,10,22,10);line(14,13,22,13);line(8,15,8,20);line(5,20,12,20);break;
    case I::Component:g.DrawRectangle(&p,6.f,6.f,12.f,12.f);g.DrawRectangle(&p,9.f,9.f,6.f,6.f);for(float x:{8.f,12.f,16.f}){line(x,3,x,6);line(x,18,x,21);line(3,x,6,x);line(18,x,21,x);}break;
    case I::Commodity:path({{12,3},{20,9},{17,20},{7,20},{4,9}});path({{12,3},{8,10},{12,20},{16,10},{12,3}},false);line(4,9,20,9);break;
    case I::Consumable:path({{9,3},{15,3},{15,7},{18,10},{18,20},{6,20},{6,10},{9,7}});line(9,13,15,13);line(12,10,12,16);break;
    case I::Blueprint:path({{5,3},{15,3},{19,7},{19,21},{5,21}});path({{15,3},{15,7},{19,7}},false);g.DrawRectangle(&p,8.f,10.f,8.f,5.f);line(8,18,14,18);break;
    case I::Paint:path({{12,3},{19,11},{19,15},{16,20},{8,20},{5,15},{5,11}});line(8,14,8,16);line(8,16,10,18);break;
    case I::Container:path({{4,7},{12,3},{20,7},{20,18},{12,22},{4,18}});path({{4,7},{12,11},{20,7}},false);line(12,11,12,22);break;
    default:path({{7,4},{17,4},{20,9},{20,17},{15,21},{8,21},{4,16},{4,8}});line(9,9,15,9);line(9,13,15,13);line(9,17,13,17);break;
    }
}
}
HIMAGELIST create(UINT dpi){
    const int size=MulDiv(24,dpi,96);HIMAGELIST result=ImageList_Create(size,size,ILC_COLOR32|ILC_MASK,int(FinderItems::Icon::Count),1);ImageList_SetBkColor(result,CLR_NONE);
    for(int i=0;i<int(FinderItems::Icon::Count);++i){
        BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=size;info.bmiHeader.biHeight=-size;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;void* pixels=nullptr;
        HBITMAP bitmap=CreateDIBSection(nullptr,&info,DIB_RGB_COLORS,&pixels,nullptr,0);
        if(bitmap){
            {Gdiplus::Bitmap surface(size,size,size*4,PixelFormat32bppPARGB,static_cast<BYTE*>(pixels));Gdiplus::Graphics g(&surface);g.Clear(Gdiplus::Color(0,0,0,0));g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.ScaleTransform(size/24.f,size/24.f);draw(g,FinderItems::Icon(i));g.Flush();}
            HBITMAP mask=CreateBitmap(size,size,1,1,nullptr);HDC dc=CreateCompatibleDC(nullptr);auto old=SelectObject(dc,mask);
            auto data=static_cast<unsigned char*>(pixels);for(int y=0;y<size;++y)for(int x=0;x<size;++x)SetPixelV(dc,x,y,data[(y*size+x)*4+3]?RGB(0,0,0):RGB(255,255,255));
            SelectObject(dc,old);DeleteDC(dc);ImageList_Add(result,bitmap,mask);DeleteObject(mask);DeleteObject(bitmap);
        }
    }
    return result;
}
}
