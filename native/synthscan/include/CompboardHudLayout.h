#pragma once

namespace CompboardHud {
struct Rect {int x,y,width,height;};
inline Rect control(int id,int width=430){
    if(id==31930)return {width-178,8,64,20};
    if(id>=31931&&id<=31944)return {width-((id-31931)%2?48:136),96+26*((id-31931)/2),26,22};
    return {18+126*(id-31945),288,118,22};
}
inline const wchar_t* caption(int id,bool inventory){
    return id==31930?(inventory?L"Timer":L"Boards"):id==31945?L"+ full set":id==31946?L"Use full set":id==31947?L"Undo last use":(id-31931)%2?L"+":L"−";
}
}
