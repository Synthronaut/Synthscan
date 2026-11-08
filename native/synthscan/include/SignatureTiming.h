#pragma once
namespace SCMiner {
inline bool signatureReadingExpired(bool automatic,int value,double age){
    return automatic&&value>0&&age>1.5;
}
// Cockpit instruments away from the aiming box need stronger visual proof.
inline bool signatureMarkerContext(bool outsideAim,bool wrongFont,double pin,bool separator,bool independentlyAgreed){
    if(!outsideAim)return true;
    if(wrongFont)return independentlyAgreed&&pin>=.85&&separator;
    return independentlyAgreed||(pin>=.90&&separator);
}
inline double signatureCandidateCost(double toAim,double toPrevious){
    // Continuity breaks close ties; it cannot outweigh a newly aimed marker.
    return toAim+.15*(toPrevious<40?toPrevious:40);
}
// Repair a fleeting weak fragment, never rewrite a clean newly scanned value
// into a previous target's number.
inline bool restoreSignatureFragment(int part,int whole,double age,bool strongCurrent){
    if(strongCurrent||age<0||age>1.5||part<=0||whole<=part)return false;
    if(whole==part*10)return true;
    for(int p=10;p<=100000&&p<=whole;p*=10)if(p>part&&whole%p==part)return true;
    return false;
}
}
