#pragma once

namespace SCMiner {
// Only these explicit controls may receive clicks while another app has focus.
inline bool overlayButtonId(int id) {
    if(id>=31930&&id<=31947)return true; // Hangars inventory controls
    switch (id) {
    case 1002: case 1011: case 1017: case 1021:
    case 31810: case 31811: case 31813: case 31814:
    case 31815: case 31817: case 31818: case 31819:
    case 31920: case 31921: case 31922: case 31923: return true;
    default: return false;
    }
}
inline bool overlayPointerInteractive(bool appActive, bool overButton,
                                      bool cursorVisible, bool mouseAlreadyDown,
                                      bool ownButtonCapture) {
    return appActive || ownButtonCapture ||
        (overButton && cursorVisible && !mouseAlreadyDown);
}
// Used instead of the standard BUTTON focus/capture behavior in passive mode.
struct OverlayButtonPress {
    bool down = false;
    void begin() { down = true; }
    void cancel() { down = false; }
    bool release(bool inside) {
        const bool click = down && inside;
        down = false;
        return click;
    }
};
}
