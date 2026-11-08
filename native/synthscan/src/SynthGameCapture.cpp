#ifdef _WIN32
#include "SynthGameCapture.h"
#include "DxgiCapture.h"
#include <dwmapi.h>
#include <windows.graphics.capture.interop.h>
#include <windows.graphics.directx.direct3d11.interop.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Graphics.Capture.h>
#include <winrt/Windows.Graphics.DirectX.Direct3D11.h>
#include <d3d11.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <mutex>
#include <chrono>
#include <opencv2/imgproc.hpp>
#include <filesystem>

namespace SCMiner {
using Microsoft::WRL::ComPtr;
using namespace winrt::Windows::Graphics;
using namespace winrt::Windows::Graphics::Capture;
using namespace winrt::Windows::Graphics::DirectX;
struct GameWindowCapture::Impl {
    HWND window=nullptr;DWORD pid=0;HMONITOR monitor=nullptr;bool hdr=false;
    std::string error;double ms=0;
    ComPtr<ID3D11Device> device;ComPtr<ID3D11DeviceContext> context;
    ComPtr<ID3D11Texture2D> staging;
    winrt::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice runtimeDevice{nullptr};
    GraphicsCaptureItem item{nullptr};Direct3D11CaptureFramePool pool{nullptr};GraphicsCaptureSession session{nullptr};
    struct Frames {std::mutex mutex;Direct3D11CaptureFrame latest{nullptr};ULONGLONG at=0;};
    std::shared_ptr<Frames> frames;winrt::event_token arrival{};
    void close(){
        if(pool){try{pool.FrameArrived(arrival);}catch(...){} }
        if(session){try{session.Close();}catch(...){}session=nullptr;}
        if(pool){try{pool.Close();}catch(...){}pool=nullptr;}
        frames.reset();item=nullptr;runtimeDevice=nullptr;staging.Reset();context.Reset();device.Reset();window=nullptr;pid=0;
    }
    bool init(HWND target){
        close();
        // Balance initialization on the calling thread, tolerating an existing STA.
        struct Apartment {HRESULT hr=RoInitialize(RO_INIT_MULTITHREADED);~Apartment(){if(SUCCEEDED(hr))RoUninitialize();}};
        static thread_local Apartment apartment;
        if(FAILED(apartment.hr)&&apartment.hr!=RPC_E_CHANGED_MODE)winrt::check_hresult(apartment.hr);
        if(!GraphicsCaptureSession::IsSupported()){error="Window capture is not supported; desktop fallback is disabled.";return false;}
        window=target;GetWindowThreadProcessId(target,&pid);monitor=MonitorFromWindow(target,MONITOR_DEFAULTTONEAREST);
        hdr=false;ComPtr<IDXGIFactory1> factory;
        if(SUCCEEDED(CreateDXGIFactory1(IID_PPV_ARGS(&factory))))for(UINT a=0;;++a){
            ComPtr<IDXGIAdapter1> adapter;if(factory->EnumAdapters1(a,&adapter)==DXGI_ERROR_NOT_FOUND)break;
            for(UINT o=0;;++o){ComPtr<IDXGIOutput> output;if(adapter->EnumOutputs(o,&output)==DXGI_ERROR_NOT_FOUND)break;
                ComPtr<IDXGIOutput6> newer;if(SUCCEEDED(output.As(&newer))){DXGI_OUTPUT_DESC1 d{};if(SUCCEEDED(newer->GetDesc1(&d))&&d.Monitor==monitor)hdr=d.ColorSpace==DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;}
            }
        }
        winrt::check_hresult(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,nullptr,0,D3D11_SDK_VERSION,&device,nullptr,&context));
        ComPtr<IDXGIDevice> dxgi;winrt::check_hresult(device.As(&dxgi));winrt::com_ptr<IInspectable> inspectable;
        winrt::check_hresult(CreateDirect3D11DeviceFromDXGIDevice(dxgi.Get(),inspectable.put()));
        runtimeDevice=inspectable.as<winrt::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice>();
        auto interop=winrt::get_activation_factory<GraphicsCaptureItem,IGraphicsCaptureItemInterop>();
        winrt::check_hresult(interop->CreateForWindow(target,winrt::guid_of<GraphicsCaptureItem>(),winrt::put_abi(item)));
        pool=Direct3D11CaptureFramePool::CreateFreeThreaded(runtimeDevice,hdr?DirectXPixelFormat::R16G16B16A16Float:DirectXPixelFormat::B8G8R8A8UIntNormalized,3,item.Size());
        frames=std::make_shared<Frames>();std::weak_ptr<Frames> weak=frames;
        arrival=pool.FrameArrived([weak](auto const& sender,auto const&){
            try{auto frame=sender.TryGetNextFrame();if(!frame)return;if(auto state=weak.lock()){std::lock_guard<std::mutex> lock(state->mutex);state->latest=frame;state->at=GetTickCount64();}}catch(...){}
        });
        session=pool.CreateCaptureSession(item);session.IsCursorCaptureEnabled(false);session.StartCapture();error="Waiting for a fresh Star Citizen frame";return true;
    }
};
GameWindowCapture::GameWindowCapture():p(std::make_unique<Impl>()){}
GameWindowCapture::~GameWindowCapture(){stop();}
void GameWindowCapture::stop(){std::lock_guard<std::mutex> lock(gate);p->close();}
bool GameWindowCapture::hdr()const{return p->hdr;}
const std::string& GameWindowCapture::error()const{return p->error;}
double GameWindowCapture::milliseconds()const{return p->ms;}
bool GameWindowCapture::validGame(HWND target){
    if(!target||!IsWindow(target)||!IsWindowVisible(target)||IsIconic(target))return false;
    wchar_t cls[64]{};if(!GetClassNameW(target,cls,64)||wcscmp(cls,L"CryENGINE"))return false;
    DWORD pid=0;GetWindowThreadProcessId(target,&pid);HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);if(!process)return false;
    wchar_t path[32768]{};DWORD length=32768;bool ok=QueryFullProcessImageNameW(process,0,path,&length)!=FALSE;CloseHandle(process);
    return ok&&_wcsicmp(std::filesystem::path(path).filename().c_str(),L"StarCitizen.exe")==0;
}
cv::Mat GameWindowCapture::grab(HWND game,const cv::Rect& requested){
    std::lock_guard<std::mutex> lock(gate);auto started=std::chrono::steady_clock::now();
    if(requested.width<1||requested.height<1||requested.width>16384||requested.height>16384)return {};
    if(!validGame(game)){p->close();p->error="Waiting for the verified StarCitizen.exe window";return {};}
    DWORD pid=0;GetWindowThreadProcessId(game,&pid);
    try{
        if(game!=p->window||pid!=p->pid||MonitorFromWindow(game,MONITOR_DEFAULTTONEAREST)!=p->monitor)if(!p->init(game))return {};
        Direct3D11CaptureFrame frame{nullptr};ULONGLONG at=0;
        {std::lock_guard<std::mutex> lock(p->frames->mutex);frame=p->frames->latest;at=p->frames->at;}
        if(!frame)for(int i=0;i<20&&!frame;++i){Sleep(5);std::lock_guard<std::mutex> lock(p->frames->mutex);frame=p->frames->latest;at=p->frames->at;}
        if(!frame||!at||GetTickCount64()-at>500){p->error="Waiting for a fresh Star Citizen frame";return {};}
        auto size=frame.ContentSize();auto surface=frame.Surface().as<Windows::Graphics::DirectX::Direct3D11::IDirect3DDxgiInterfaceAccess>();
        ComPtr<ID3D11Texture2D> texture;winrt::check_hresult(surface->GetInterface(IID_PPV_ARGS(&texture)));
        D3D11_TEXTURE2D_DESC source{};texture->GetDesc(&source);
        if(size.Width!=int(source.Width)||size.Height!=int(source.Height)){
            auto format=p->hdr?DirectXPixelFormat::R16G16B16A16Float:DirectXPixelFormat::B8G8R8A8UIntNormalized;
            p->pool.Recreate(p->runtimeDevice,format,3,size);p->error="Game window resized; waiting for a fresh frame";return {};
        }
        RECT outer{},client{};if(FAILED(DwmGetWindowAttribute(game,DWMWA_EXTENDED_FRAME_BOUNDS,&outer,sizeof(outer))))GetWindowRect(game,&outer);
        GetClientRect(game,&client);POINT origin{};ClientToScreen(game,&origin);
        cv::Rect bounds(origin.x,origin.y,client.right,client.bottom);auto clipped=requested&bounds;
        if(clipped.empty()){p->error="Selected capture region is outside Star Citizen";return {};}
        cv::Rect roi(clipped.x-outer.left,clipped.y-outer.top,clipped.width,clipped.height);roi&=cv::Rect(0,0,size.Width,size.Height);
        if(roi.empty())return {};
        D3D11_TEXTURE2D_DESC d=source;d.Width=roi.width;d.Height=roi.height;d.MipLevels=d.ArraySize=1;d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;d.MiscFlags=0;
        D3D11_TEXTURE2D_DESC previous{};if(p->staging)p->staging->GetDesc(&previous);
        if(!p->staging||previous.Width!=d.Width||previous.Height!=d.Height||previous.Format!=d.Format){p->staging.Reset();winrt::check_hresult(p->device->CreateTexture2D(&d,nullptr,&p->staging));}
        D3D11_BOX box{UINT(roi.x),UINT(roi.y),0,UINT(roi.x+roi.width),UINT(roi.y+roi.height),1};
        p->context->CopySubresourceRegion(p->staging.Get(),0,0,0,0,texture.Get(),0,&box);
        D3D11_MAPPED_SUBRESOURCE mapped{};winrt::check_hresult(p->context->Map(p->staging.Get(),0,D3D11_MAP_READ,0,&mapped));
        cv::Mat bgr;
        if(p->hdr){
            static const auto curve=DxgiCapture::makeToneCurve();bgr.create(roi.height,roi.width,CV_8UC3);
            for(int y=0;y<roi.height;++y){const auto* src=reinterpret_cast<const unsigned short*>(static_cast<unsigned char*>(mapped.pData)+y*mapped.RowPitch);auto* dst=bgr.ptr<unsigned char>(y);for(int x=0;x<roi.width;++x){dst[0]=curve[src[2]];dst[1]=curve[src[1]];dst[2]=curve[src[0]];src+=4;dst+=3;}}
        }else{cv::Mat bgra(roi.height,roi.width,CV_8UC4,mapped.pData,mapped.RowPitch);cv::cvtColor(bgra,bgr,cv::COLOR_BGRA2BGR);}
        p->context->Unmap(p->staging.Get(),0);
        cv::Mat result(requested.height,requested.width,CV_8UC3,cv::Scalar());
        bgr.copyTo(result(cv::Rect(clipped.x-requested.x,clipped.y-requested.y,bgr.cols,bgr.rows)));
        p->error.clear();p->ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();return result;
    }catch(const winrt::hresult_error& e){p->close();p->error="Game-window capture unavailable ("+std::to_string(unsigned(e.code()))+"); desktop fallback is disabled.";return {};}
}
}
#endif
