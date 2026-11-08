#pragma once
namespace SCMiner {
// A restored tab's saved size is needed to preserve the nearer screen edge.
inline int resizedOverlayOrigin(int origin,int oldSize,int newSize,int screenStart,int screenEnd){
    return oldSize>0&&2*origin+oldSize>screenStart+screenEnd?origin+oldSize-newSize:origin;
}
}
