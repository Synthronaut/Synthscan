#ifdef SYNTHSCAN_NO_SCREEN_READING
// Standard edition: deliberately no Windows Graphics Capture or desktop duplication.
#include "SynthGameCapture.h"
#include "DxgiCapture.h"
#include <filesystem>
#include <cmath>
namespace SCMiner {
struct GameWindowCapture::Impl {};
GameWindowCapture::GameWindowCapture():p(std::make_unique<Impl>()){}
GameWindowCapture::~GameWindowCapture()=default;
void GameWindowCapture::stop(){}
bool GameWindowCapture::hdr()const{return false;}
const std::string& GameWindowCapture::error()const{static const std::string value="Standard edition: screen reading is not installed";return value;}
double GameWindowCapture::milliseconds()const{return 0;}
cv::Mat GameWindowCapture::grab(HWND,const cv::Rect&){return {};}
bool GameWindowCapture::validGame(HWND target){
    if(!target||!IsWindow(target)||!IsWindowVisible(target)||IsIconic(target))return false;
    wchar_t cls[64]{};if(!GetClassNameW(target,cls,64)||wcscmp(cls,L"CryENGINE"))return false;
    DWORD pid=0;GetWindowThreadProcessId(target,&pid);HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);if(!process)return false;
    wchar_t path[32768]{};DWORD length=32768;bool ok=QueryFullProcessImageNameW(process,0,path,&length)!=FALSE;CloseHandle(process);
    return ok&&_wcsicmp(std::filesystem::path(path).filename().c_str(),L"StarCitizen.exe")==0;
}
DxgiCapture::~DxgiCapture()=default;
cv::Mat DxgiCapture::grab(const cv::Rect&){return {};}
std::string DxgiCapture::rawStats()const{return {};}
namespace {

// How long to wait for a new desktop frame. A still screen produces none at
// all, which is not an error - the copy already held is still what is on
// screen - so this only has to be short enough not to stall the scan.
constexpr UINT ACQUIRE_TIMEOUT_MS = 16;

// scRGB is linear light with 1.0 at SDR white (80 nits). Where the picture
// sits on that scale, measured with --capture on this game in HDR:
//
//     median 0.25   p90 0.44   p99 4.62   p99.9 5.31   max 5.75
//
// The world - terrain, sky - lives below half of SDR white. The HUD and its
// markers live at four to six times it, which matches the 400 nits Star
// Citizen reports. The two are decades apart in light, and everything worth
// reading is in the upper group.
//
// Treating 1.0 as white, with a shoulder above it into the last ten display
// levels, puts digits on 253 and the plate under them on 244 - nine levels
// apart where the reader needs forty - and no frame reads (0 of 108). So
// white goes where the HUD is, and only what is brighter gets compressed.
constexpr float TONE_WHITE = 4.0f;        // the scRGB level that becomes white
constexpr float TONE_SHOULDER_AT = 0.8f;  // where the curve starts to bend
constexpr float TONE_SHOULDER_RATE = 3.0f;

float toneMap(float linear) {
    if (linear <= 0.0f) return 0.0f;   // scRGB allows negatives for wide gamut
    const float t = linear / TONE_WHITE;
    if (t <= TONE_SHOULDER_AT) return t;
    // Never quite reaches 1.0, so a sun or a lamp above the HUD level still
    // separates instead of collapsing into one flat white the way GDI leaves it
    return TONE_SHOULDER_AT + (1.0f - TONE_SHOULDER_AT) *
           (1.0f - std::exp(-(t - TONE_SHOULDER_AT) * TONE_SHOULDER_RATE));
}

// The reader was tuned on GDI captures, which are sRGB-encoded. Duplication's
// float buffer is linear, so it has to be encoded back or every mid-tone would
// land too dark and the digit thresholds would all be wrong.
float encodeSrgb(float linear) {
    if (linear <= 0.0031308f) return linear * 12.92f;
    return 1.055f * std::pow(linear, 1.0f / 2.4f) - 0.055f;
}

}  // namespace

std::vector<unsigned char> DxgiCapture::makeToneCurve() {
    std::vector<unsigned char> toneCurve_(65536);

    // Decode every half-float bit pattern once, through OpenCV rather than by

    // hand: it gets the denormals and infinities right, which a quick shift-
    // and-mask version does not.
    cv::Mat bits(1, 65536, CV_16UC1);
    for (int i = 0; i < 65536; i++) bits.at<unsigned short>(0, i) = static_cast<unsigned short>(i);
    cv::Mat halves(1, 65536, CV_16FC1, bits.data);
    cv::Mat floats;
    halves.convertTo(floats, CV_32F);

    for (int i = 0; i < 65536; i++) {
        float v = floats.at<float>(0, i);
        if (!std::isfinite(v)) v = (v > 0.0f) ? 1.0f : 0.0f;   // inf / NaN
        const float encoded = encodeSrgb((std::min)(toneMap(v), 1.0f));
        toneCurve_[i] = static_cast<unsigned char>(
            std::lround((std::min)((std::max)(encoded, 0.0f), 1.0f) * 255.0f));
    }
    return toneCurve_;
}

}

#endif
