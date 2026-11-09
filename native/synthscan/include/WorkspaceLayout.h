#pragma once
#include <algorithm>
#include <array>

// Logical pixels. Fonts keep their normal size while data areas use spare space.
namespace WorkspaceLayout {
struct Box {int x,y,width,height;};
struct History {
    std::array<Box,5> labels,filters;
    Box results,previous,next,count,detail,csv,json,timezone,notes,saveNote,name,nameButton,minutes,cooldown,status;
};
inline History history(int width,int height){
    width=std::max(860,width);height=std::max(650,height);
    const int content=width-40,region=std::clamp(content/5,170,220),date=std::clamp(content/7,145,180);
    const int query=content-region-date*2-64-48;
    History out{};int x=20;int widths[]{query,region,date,date,64};
    for(int i=0;i<5;i++){out.labels[i]={x,112,widths[i],20};out.filters[i]={x,134,widths[i],i==1?220:30};x+=widths[i]+12;}
    int nameY=height-72,notesY=nameY-86,detailHeight=std::clamp(height/7,100,170),detailY=notesY-detailHeight-12,pagingY=detailY-38;
    out.results={20,178,content,pagingY-190};
    out.previous={20,pagingY,130,28};out.next={162,pagingY,130,28};out.count={308,pagingY+3,content-288,24};
    out.detail={100,detailY,width-120,detailHeight};out.csv={20,detailY,70,30};out.json={20,detailY+40,70,30};out.timezone={20,detailY+80,75,40};
    out.notes={100,notesY,width-312,70};out.saveNote={width-200,notesY,180,32};
    out.name={20,nameY,content-520,30};out.nameButton={width-528,nameY,170,30};out.minutes={width-346,nameY,60,30};out.cooldown={width-274,nameY,254,30};
    out.status={20,height-28,content,22};return out;
}
inline Box diary(Box box,int id,int width,int height){
    const int dx=std::max(0,width-1100),dy=std::max(0,height-810),left=510+dx/2,right=528+dx-dx/2;
    if(id>=470&&id<=475){int cell=(1060+dx)/6;box.x=20+(id-470)*cell;box.width=cell-12;return box;}
    if(box.y<214){
        if(id==460||id==458)box.x+=dx;
        else if(box.y>=148){box.x=20+(box.x-20)*(1060+dx)/1060;box.width=box.width*(1060+dx)/1060;}
        else if(box.width>=800)box.width+=dx;
        return box;
    }
    if(box.x>=550){
        box.x=550+dx/2+(box.x-550)*right/528;box.width=box.width*right/528;
        if(id==433)box.height+=dy;
        if(box.y>=732)box.y+=dy;
    }else{
        if(id==411){box.width=left;box.height+=dy;return box;}
        if(box.y>=502)box.y+=dy;
        int index=id==408?0:id==409?1:id==410?2:id==456?0:id==457?1:id==459?2:-1;
        if(index>=0){int cell=(left-24)/3;box.x=20+index*(cell+12);box.width=cell;}
        else if(id>=451&&id<=455){int cell=left/5;box.x=20+(id-451)*cell;box.width=cell;}
        else if(id==450)box.width=left-230;
        else if(box.width>=500)box.width=left;
    }
    return box;
}
inline Box bookmarks(Box box,int id,int width,int height){
    const int dx=std::max(0,width-900),dy=std::max(0,height-660),left=310+dx/3;
    if(id==704)return {20,295,left,220+dy};
    if(id==705)return {40+left,295,width-left-60,220+dy};
    if(id>=710&&id<=712){int cell=(width-70)/3;return {20+(id-710)*(cell+15),202,cell,34};}
    if(id>=713&&id<=716){int cell=(width-85)/4;return {20+(id-713)*(cell+15),532+dy,cell,32};}
    if(id==717)return box;
    if(box.y>=532)box.y+=dy;
    if(box.x>=440){box.x+=dx/2;if(id!=703)box.width+=dx-dx/2;}
    else if(id==701||box.y==95)box.width+=dx/2;
    else if(box.width>=800)box.width+=dx;
    return box;
}
}
