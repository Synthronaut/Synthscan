#pragma once
#include "SynthJson.h"
#include <opencv2/imgcodecs.hpp>
namespace FrameTransfer {
// A short-lived, pagefile-backed mapping. No image filename or disk write.
class Lease {
    HANDLE mapping=nullptr;void* view=nullptr;size_t size=0;ULONGLONG until=0;
public:
    std::string name;
    ~Lease(){clear();}
    void clear(){if(view){SecureZeroMemory(view,size);UnmapViewOfFile(view);}if(mapping)CloseHandle(mapping);mapping=nullptr;view=nullptr;size=0;until=0;name.clear();}
    SynthScan::Json create(const cv::Mat& frame){
        clear();std::vector<unsigned char> png;if(!cv::imencode(".png",frame,png)||png.empty()||png.size()>32*1024*1024)return {};
        GUID id{};if(FAILED(CoCreateGuid(&id)))return {};wchar_t guid[40]{};StringFromGUID2(id,guid,40);
        name="Local\\SynthScan.Fabricator."+std::to_string(GetCurrentProcessId())+"."+SynthScan::utf8(guid);
        size=png.size();mapping=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,DWORD(size),SynthScan::wide(name).c_str());
        if(!mapping){clear();return {};}
        view=MapViewOfFile(mapping,FILE_MAP_WRITE,0,0,size);if(!view){clear();return {};}
        memcpy(view,png.data(),size);SecureZeroMemory(png.data(),png.size());until=GetTickCount64()+90000;
        return SynthScan::obj({{"frame_name",SynthScan::str(name)},{"frame_size",SynthScan::num(double(size))}});
    }
    void expire(const std::filesystem::path& directory){if(!view)return;auto ack=SynthScan::read(directory/L"fabricator_frame_ack.json",1024);if(ack.textOr("frame_name")==name||GetTickCount64()>=until)clear();}
};
}
