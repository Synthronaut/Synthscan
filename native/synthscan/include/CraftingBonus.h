#pragma once
// A positive bonus means an improvement. The multiplier remains the literal
// stat change, including decreases to recoil, fuel use and other lower-is-better stats.
inline double craftingBonusPercent(double factor,int better){return (factor-1.0)*100.0*(better==1?-1.0:1.0);}
