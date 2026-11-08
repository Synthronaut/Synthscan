#pragma once
#include "MiningAdvice.h"
#include <cmath>

namespace SCMiner {
// Mass alone is not a target ID. In particular, two rocks may have equal mass
// but different composition/volume. Missing OCR is never evidence for reusing
// a different mass, even when just one numeral differs.
inline bool sameContentsTarget(const RockStats& a, const RockStats& b) {
    if (!std::isfinite(a.mass) || !std::isfinite(b.mass) || a.mass <= 0 || b.mass <= 0) return false;
    if (!a.ore.empty() && !b.ore.empty() && a.ore != b.ore) return false;
    const bool volumes = std::isfinite(a.scu) && std::isfinite(b.scu) && a.scu > 0 && b.scu > 0;
    const bool volumeAgrees = volumes && std::abs(a.scu-b.scu) <= 0.015f;
    if (volumes && !volumeAgrees) return false;
    if (std::abs(a.mass-b.mass) <= .5f) return true;
    // A small digit-reading wobble can retain confirmation only when the
    // independently printed two-decimal SCU figure agrees.
    return volumeAgrees && std::abs(a.mass-b.mass) <= std::max(1.0f, a.mass*.001f);
}
}
