#define UNICODE
#define _UNICODE
#define PSAPI_VERSION 2
#include "SynthWebView.h"
#include "AppPaths.h"
#include <unknwn.h>
#include <objidl.h>
#include <bcrypt.h>
#include <psapi.h>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <set>
#include <vector>

namespace SynthWebView {
namespace {
using namespace SynthScan;

struct ICoreWebView2Environment;
struct ICoreWebView2Controller;
struct ICoreWebView2;
struct ICoreWebView2Settings;
struct ICoreWebView2WebMessageReceivedEventArgs;

struct COREWEBVIEW2_COLOR { BYTE A; BYTE R; BYTE G; BYTE B; };
struct EventRegistrationToken { __int64 value; };

MIDL_INTERFACE("4e8a3389-c9d8-4bd2-b6b5-124fee6cc14d")
ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Environment* createdEnvironment) = 0;
};

MIDL_INTERFACE("6c4819f3-c9b7-4260-8127-c9f5bde7f68c")
ICoreWebView2CreateCoreWebView2ControllerCompletedHandler : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Controller* createdController) = 0;
};

MIDL_INTERFACE("57213f19-00e6-49fa-8e07-898ea01ecbd2")
ICoreWebView2WebMessageReceivedEventHandler : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender, ICoreWebView2WebMessageReceivedEventArgs* args) = 0;
};

MIDL_INTERFACE("697e05e9-8d8f-45fa-96f4-8ffe1ededaf5")
ICoreWebView2CapturePreviewCompletedHandler : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode) = 0;
};

MIDL_INTERFACE("0f99a40c-e962-4207-9e92-e3d542eff849")
ICoreWebView2WebMessageReceivedEventArgs : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE get_Source(LPWSTR* source) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_WebMessageAsJson(LPWSTR* webMessageAsJson) = 0;
    virtual HRESULT STDMETHODCALLTYPE TryGetWebMessageAsString(LPWSTR* webMessageAsString) = 0;
};

MIDL_INTERFACE("e562e4f0-d7fa-43ac-8d71-c05150499f00")
ICoreWebView2Settings : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE get_IsScriptEnabled(BOOL* isScriptEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsScriptEnabled(BOOL isScriptEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_AreDefaultScriptDialogsEnabled(BOOL* areDefaultScriptDialogsEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_AreDefaultScriptDialogsEnabled(BOOL areDefaultScriptDialogsEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_IsWebMessageEnabled(BOOL* isWebMessageEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsWebMessageEnabled(BOOL isWebMessageEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_AreDevToolsEnabled(BOOL* areDevToolsEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_AreDevToolsEnabled(BOOL areDevToolsEnabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_AreDefaultContextMenusEnabled(BOOL* enabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_AreDefaultContextMenusEnabled(BOOL enabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_AreHostObjectsAllowed(BOOL* allowed) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_AreHostObjectsAllowed(BOOL allowed) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_IsZoomControlEnabled(BOOL* enabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsZoomControlEnabled(BOOL enabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_IsBuiltInErrorPageEnabled(BOOL* enabled) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsBuiltInErrorPageEnabled(BOOL enabled) = 0;
};

MIDL_INTERFACE("76eceacb-0462-4d94-ac83-423a6793775e")
ICoreWebView2 : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE get_Settings(ICoreWebView2Settings** settings) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Source(LPWSTR* uri) = 0;
    virtual HRESULT STDMETHODCALLTYPE Navigate(LPCWSTR uri) = 0;
    virtual HRESULT STDMETHODCALLTYPE NavigateToString(LPCWSTR htmlContent) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_NavigationStarting(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_NavigationStarting(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_ContentLoading(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_ContentLoading(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_SourceChanged(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_SourceChanged(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_HistoryChanged(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_HistoryChanged(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_NavigationCompleted(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_NavigationCompleted(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_FrameNavigationStarting(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_FrameNavigationStarting(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_FrameNavigationCompleted(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_FrameNavigationCompleted(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_ScriptDialogOpening(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_ScriptDialogOpening(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_PermissionRequested(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_PermissionRequested(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_ProcessFailed(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_ProcessFailed(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE AddScriptToExecuteOnDocumentCreated(LPCWSTR javaScript, IUnknown* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE RemoveScriptToExecuteOnDocumentCreated(LPCWSTR id) = 0;
    virtual HRESULT STDMETHODCALLTYPE ExecuteScript(LPCWSTR javaScript, IUnknown* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE CapturePreview(int imageFormat, IStream* imageStream, IUnknown* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE Reload() = 0;
    virtual HRESULT STDMETHODCALLTYPE PostWebMessageAsJson(LPCWSTR webMessageAsJson) = 0;
    virtual HRESULT STDMETHODCALLTYPE PostWebMessageAsString(LPCWSTR webMessageAsString) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_WebMessageReceived(ICoreWebView2WebMessageReceivedEventHandler* handler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_WebMessageReceived(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE CallDevToolsProtocolMethod(LPCWSTR methodName, LPCWSTR parametersAsJson, IUnknown* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_BrowserProcessId(UINT32* value) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_CanGoBack(BOOL* canGoBack) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_CanGoForward(BOOL* canGoForward) = 0;
    virtual HRESULT STDMETHODCALLTYPE GoBack() = 0;
    virtual HRESULT STDMETHODCALLTYPE GoForward() = 0;
    virtual HRESULT STDMETHODCALLTYPE GetDevToolsProtocolEventReceiver(LPCWSTR eventName, IUnknown** receiver) = 0;
    virtual HRESULT STDMETHODCALLTYPE Stop() = 0;
    virtual HRESULT STDMETHODCALLTYPE add_NewWindowRequested(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_NewWindowRequested(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_DocumentTitleChanged(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_DocumentTitleChanged(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_DocumentTitle(LPWSTR* title) = 0;
    virtual HRESULT STDMETHODCALLTYPE AddHostObjectToScript(LPCWSTR name, VARIANT* object) = 0;
    virtual HRESULT STDMETHODCALLTYPE RemoveHostObjectFromScript(LPCWSTR name) = 0;
    virtual HRESULT STDMETHODCALLTYPE OpenDevToolsWindow() = 0;
    virtual HRESULT STDMETHODCALLTYPE add_ContainsFullScreenElementChanged(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_ContainsFullScreenElementChanged(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_ContainsFullScreenElement(BOOL* containsFullScreenElement) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_WebResourceRequested(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_WebResourceRequested(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE AddWebResourceRequestedFilter(LPCWSTR uri, int resourceContext) = 0;
    virtual HRESULT STDMETHODCALLTYPE RemoveWebResourceRequestedFilter(LPCWSTR uri, int resourceContext) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_WindowCloseRequested(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_WindowCloseRequested(EventRegistrationToken token) = 0;
};

MIDL_INTERFACE("9E8F0CF8-E670-4B5E-B2BC-73E061E3184C")
ICoreWebView2_2 : public ICoreWebView2 {
    virtual HRESULT STDMETHODCALLTYPE add_WebResourceResponseReceived(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_WebResourceResponseReceived(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE NavigateWithWebResourceRequest(IUnknown* request) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_DOMContentLoaded(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_DOMContentLoaded(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_CookieManager(IUnknown** cookieManager) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Environment(ICoreWebView2Environment** environment) = 0;
};

MIDL_INTERFACE("A0D6DF20-3B92-416D-AA0C-437A9C727857")
ICoreWebView2_3 : public ICoreWebView2_2 {
    virtual HRESULT STDMETHODCALLTYPE TrySuspend(IUnknown* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE Resume() = 0;
    virtual HRESULT STDMETHODCALLTYPE get_IsSuspended(BOOL* isSuspended) = 0;
    virtual HRESULT STDMETHODCALLTYPE SetVirtualHostNameToFolderMapping(LPCWSTR hostName, LPCWSTR folderPath, int accessKind) = 0;
    virtual HRESULT STDMETHODCALLTYPE ClearVirtualHostNameToFolderMapping(LPCWSTR hostName) = 0;
};

MIDL_INTERFACE("4d00c0d1-9434-4eb6-8078-8697a560334f")
ICoreWebView2Controller : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE get_IsVisible(BOOL* isVisible) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsVisible(BOOL isVisible) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Bounds(RECT* bounds) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_Bounds(RECT bounds) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_ZoomFactor(double* zoomFactor) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_ZoomFactor(double zoomFactor) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_ZoomFactorChanged(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_ZoomFactorChanged(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE SetBoundsAndZoomFactor(RECT bounds, double zoomFactor) = 0;
    virtual HRESULT STDMETHODCALLTYPE MoveFocus(int reason) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_MoveFocusRequested(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_MoveFocusRequested(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_GotFocus(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_GotFocus(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_LostFocus(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_LostFocus(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_AcceleratorKeyPressed(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_AcceleratorKeyPressed(EventRegistrationToken token) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_ParentWindow(HWND* parentWindow) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_ParentWindow(HWND parentWindow) = 0;
    virtual HRESULT STDMETHODCALLTYPE NotifyParentWindowPositionChanged() = 0;
    virtual HRESULT STDMETHODCALLTYPE Close() = 0;
    virtual HRESULT STDMETHODCALLTYPE get_CoreWebView2(ICoreWebView2** coreWebView2) = 0;
};

MIDL_INTERFACE("c979903e-d4ca-4228-92eb-47ee3fa96eab")
ICoreWebView2Controller2 : public ICoreWebView2Controller {
    virtual HRESULT STDMETHODCALLTYPE get_DefaultBackgroundColor(COREWEBVIEW2_COLOR* backgroundColor) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_DefaultBackgroundColor(COREWEBVIEW2_COLOR backgroundColor) = 0;
};

MIDL_INTERFACE("b96d755e-0319-4e92-a296-23436f46a1fc")
ICoreWebView2Environment : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE CreateCoreWebView2Controller(HWND parentWindow, ICoreWebView2CreateCoreWebView2ControllerCompletedHandler* handler) = 0;
    virtual HRESULT STDMETHODCALLTYPE CreateWebResourceResponse(IStream* content, int statusCode, LPCWSTR reasonPhrase, LPCWSTR headers, IUnknown** response) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_BrowserVersionString(LPWSTR* versionInfo) = 0;
    virtual HRESULT STDMETHODCALLTYPE add_NewBrowserVersionAvailable(IUnknown* eventHandler, EventRegistrationToken* token) = 0;
    virtual HRESULT STDMETHODCALLTYPE remove_NewBrowserVersionAvailable(EventRegistrationToken token) = 0;
};

typedef HRESULT (STDAPICALLTYPE *CreateWebViewEnvironmentWithOptionsInternal_t)(
    bool checkRunningInstance, int runtimeType, PCWSTR userDataFolder, IUnknown* environmentOptions,
    ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler* handler);

std::wstring findWebView2Dll() {
    for (HKEY root : {HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER}) {
        for (const wchar_t* subkey : {
            L"SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            L"Software\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        }) {
            wchar_t loc[512]{}, pv[128]{};
            DWORD szLoc = sizeof(loc), szPv = sizeof(pv);
            if (RegGetValueW(root, subkey, L"location", RRF_RT_REG_SZ, nullptr, loc, &szLoc) == ERROR_SUCCESS &&
                RegGetValueW(root, subkey, L"pv", RRF_RT_REG_SZ, nullptr, pv, &szPv) == ERROR_SUCCESS) {
                std::filesystem::path p = std::filesystem::path(loc) / pv / L"EBWebView\\x64\\EmbeddedBrowserWebView.dll";
                if (std::filesystem::exists(p)) return p.wstring();
            }
        }
    }
    return L"";
}

std::filesystem::path findUiDistFolder() {
    std::error_code ec;
    auto prog = SCMiner::AppPaths::program();
    std::vector<std::filesystem::path> candidates = {
        prog.parent_path().parent_path() / L"ui" / L"dist",
        prog.parent_path() / L"ui" / L"dist",
        prog / L"ui" / L"dist",
    };
    Json runtime = read(prog / L"native_runtime.json");
    auto ws = runtime.textOr("workspace");
    if (!ws.empty()) {
        candidates.push_back(std::filesystem::u8path(ws) / L"ui" / L"dist");
    }
    for (const auto& c : candidates) {
        if (std::filesystem::exists(c / L"index.html", ec)) {
            return std::filesystem::canonical(c, ec);
        }
    }
    return {};
}

std::string generateBridgeToken() {
    unsigned char bytes[16]{};
    BCryptGenRandom(nullptr, bytes, sizeof(bytes), BCRYPT_USE_SYSTEM_PREFERRED_RNG);
    char hex[33]{};
    for (int i = 0; i < 16; ++i) {
        sprintf_s(hex + i * 2, 3, "%02x", bytes[i]);
    }
    return std::string(hex, 32);
}

bool allowedAction(const std::string& action) {
    static const std::set<std::string> allowed = {
        "search", "refresh_people", "refresh_market",
        "stage_people", "unstage_people", "clear_actions", "stage_tag",
        "tag", "tag_many",
        "friend", "friend_many", "party", "party_many",
        "pause_invites", "resume_invites", "cancel_invites",
        "add_watch", "toggle_watch", "remove_watch", "dismiss_notices",
        "open_uex_ad", "navigate",
        "daylight_preferences", "daylight_observe", "daylight_refresh",
        "piracy_toggle_wait", "piracy_reset_wait", "piracy_log_pull", "piracy_delete_pull",
        "mission_view", "mission_classify", "mission_export"
    };
    return allowed.count(action) > 0;
}

bool validateCommandObject(const Json& command) {
    if (command.kind != Json::Kind::Object) return false;
    auto action = command.textOr("action");
    if (!allowedAction(action)) return false;
    if (action == "friend" || action == "friend_many" || action == "party" || action == "party_many") {
        if (!flag(command, "confirmed")) return false;
        if (action == "friend_many" || action == "party_many") {
            const auto& ids = field(command, "player_ids").items;
            if (ids.empty() || ids.size() > 50) return false;
        }
    }
    if (action == "stage_people") {
        const auto& ids = field(command, "player_ids").items;
        if (ids.empty() || ids.size() > 50) return false;
    }
    if (action == "open_uex_ad") {
        auto url = command.textOr("url");
        if (url.rfind("https://uexcorp.space/marketplace/item/info/", 0) != 0 ||
            url.find_first_of("\r\n\t ") != std::string::npos) {
            return false;
        }
    }
    return true;
}

HWND g_parent = nullptr;
ICoreWebView2Controller* g_controller = nullptr;
ICoreWebView2* g_webview = nullptr;
bool g_initializing = false;
bool g_uiReady = false;
std::string g_bridgeToken;
double g_lastClientSeq = 0;
unsigned g_rejectedMessages = 0;
std::function<void(const Json&)> g_onCommand;
std::string g_pendingMode = "people";
Json g_pendingState;
Json g_pendingMarketItems;
Json g_pendingHome;
Json g_pendingDaylight;
Json g_pendingPiracy;
Json g_pendingMission;
Json g_suiteResult;
bool g_hasSuiteResult = false;
std::wstring g_initialUrl = L"https://synthscan.local/index.html";

void sendSnapshotMessage() {
    if (!g_webview || !g_uiReady) return;
    Json envelope = obj({
        {"kind", str("snapshot")},
        {"bridge_token", str(g_bridgeToken)},
        {"mode", str(g_pendingMode)},
        {"state", g_pendingState},
        {"market_items", g_pendingMarketItems},
        {"home", g_pendingHome},
        {"daylight", g_pendingDaylight},
        {"piracy", g_pendingPiracy},
        {"mission", g_pendingMission}
    });
    auto payload = wide(encode(envelope));
    g_webview->PostWebMessageAsJson(payload.c_str());
}

class WebMessageHandler : public ICoreWebView2WebMessageReceivedEventHandler {
    ULONG ref = 1;
public:
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == __uuidof(ICoreWebView2WebMessageReceivedEventHandler)) {
            *ppv = static_cast<ICoreWebView2WebMessageReceivedEventHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++ref; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG r = --ref; if (!r) delete this; return r; }
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs* args) override {
        LPWSTR src = nullptr;
        if (FAILED(args->get_Source(&src)) || !src) {
            ++g_rejectedMessages;
            return S_OK;
        }
        std::wstring origin(src);
        CoTaskMemFree(src);
        if (origin.rfind(L"https://synthscan.local/", 0) != 0) {
            ++g_rejectedMessages;
            return S_OK;
        }
        LPWSTR rawJson = nullptr;
        if (FAILED(args->get_WebMessageAsJson(&rawJson)) || !rawJson) {
            ++g_rejectedMessages;
            return S_OK;
        }
        std::string utf8Json = utf8(rawJson);
        CoTaskMemFree(rawJson);

        Json message;
        std::string err;
        if (!SCMiner::parseJson(utf8Json, message, err) || message.kind != Json::Kind::Object) {
            ++g_rejectedMessages;
            return S_OK;
        }

        auto kind = message.textOr("kind");
        if (kind == "ui_ready") {
            g_uiReady = true;
            sendSnapshotMessage();
            return S_OK;
        }
        if (kind == "suite_result") {
            g_suiteResult = field(message, "result");
            g_hasSuiteResult = true;
            return S_OK;
        }
        if (kind == "command") {
            if (message.textOr("bridge_token") != g_bridgeToken || g_bridgeToken.empty()) {
                ++g_rejectedMessages;
                return S_OK;
            }
            double seq = message.numberOr("client_seq", 0);
            if (seq <= g_lastClientSeq) {
                ++g_rejectedMessages;
                return S_OK;
            }
            const auto& cmd = field(message, "command");
            if (!validateCommandObject(cmd)) {
                ++g_rejectedMessages;
                return S_OK;
            }
            g_lastClientSeq = seq;
            if (g_onCommand) {
                g_onCommand(cmd);
            }
            return S_OK;
        }
        ++g_rejectedMessages;
        return S_OK;
    }
};

class ControllerCompletedHandler : public ICoreWebView2CreateCoreWebView2ControllerCompletedHandler {
    ULONG ref = 1;
    HWND target;
    std::filesystem::path distFolder;
public:
    ControllerCompletedHandler(HWND h, std::filesystem::path f) : target(h), distFolder(std::move(f)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == __uuidof(ICoreWebView2CreateCoreWebView2ControllerCompletedHandler)) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++ref; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG r = --ref; if (!r) delete this; return r; }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Controller* controller) override {
        g_initializing = false;
        if (FAILED(errorCode) || !controller || target != g_parent || !IsWindow(target)) {
            return S_OK;
        }
        g_controller = controller;
        g_controller->AddRef();

        ICoreWebView2Controller2* c2 = nullptr;
        if (SUCCEEDED(g_controller->QueryInterface(__uuidof(ICoreWebView2Controller2), (void**)&c2)) && c2) {
            c2->put_DefaultBackgroundColor({255, 14, 18, 25});
            c2->Release();
        }

        RECT bounds{};
        GetClientRect(target, &bounds);
        g_controller->put_Bounds(bounds);
        bool visible = IsWindowVisible(target) != 0;
        g_controller->put_IsVisible(visible ? TRUE : FALSE);

        if (SUCCEEDED(g_controller->get_CoreWebView2(&g_webview)) && g_webview) {
            ICoreWebView2Settings* settings = nullptr;
            if (SUCCEEDED(g_webview->get_Settings(&settings)) && settings) {
                settings->put_AreDefaultContextMenusEnabled(FALSE);
                settings->put_AreHostObjectsAllowed(FALSE);
                settings->put_AreDevToolsEnabled(FALSE);
                settings->put_IsBuiltInErrorPageEnabled(FALSE);
                settings->Release();
            }
            ICoreWebView2_3* wv3 = nullptr;
            if (SUCCEEDED(g_webview->QueryInterface(__uuidof(ICoreWebView2_3), (void**)&wv3)) && wv3) {
                wv3->SetVirtualHostNameToFolderMapping(L"synthscan.local", distFolder.wstring().c_str(), 0);
                wv3->Release();
            }
            EventRegistrationToken tok{};
            g_webview->add_WebMessageReceived(new WebMessageHandler(), &tok);
            g_webview->Navigate(g_initialUrl.c_str());
        }
        return S_OK;
    }
};

class EnvironmentCompletedHandler : public ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler {
    ULONG ref = 1;
    HWND target;
    std::filesystem::path distFolder;
public:
    EnvironmentCompletedHandler(HWND h, std::filesystem::path f) : target(h), distFolder(std::move(f)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == __uuidof(ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler)) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++ref; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG r = --ref; if (!r) delete this; return r; }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, ICoreWebView2Environment* env) override {
        if (FAILED(errorCode) || !env || target != g_parent || !IsWindow(target)) {
            g_initializing = false;
            return S_OK;
        }
        env->CreateCoreWebView2Controller(target, new ControllerCompletedHandler(target, distFolder));
        return S_OK;
    }
};

class CapturePreviewHandler : public ICoreWebView2CapturePreviewCompletedHandler {
    ULONG ref = 1;
    bool* doneFlag;
    HRESULT* outHr;
public:
    CapturePreviewHandler(bool* d, HRESULT* h) : doneFlag(d), outHr(h) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == __uuidof(ICoreWebView2CapturePreviewCompletedHandler)) {
            *ppv = static_cast<ICoreWebView2CapturePreviewCompletedHandler*>(this);
            AddRef(); return S_OK;
        }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++ref; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG r = --ref; if (!r) delete this; return r; }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode) override {
        if (outHr) *outHr = errorCode;
        if (doneFlag) *doneFlag = true;
        return S_OK;
    }
};

} // namespace

bool available() {
    return !findWebView2Dll().empty() && !findUiDistFolder().empty();
}

bool active() {
    return g_controller != nullptr || g_initializing;
}

bool attach(HWND parent, const std::filesystem::path& dataFolder, const std::string& mode, std::function<void(const Json&)> onCommand) {
    if (!parent || !IsWindow(parent)) return false;
    g_pendingMode = mode;
    g_onCommand = std::move(onCommand);
    if (g_parent == parent && (g_controller || g_initializing)) {
        sendSnapshotMessage();
        return true;
    }
    detach();
    auto dllPath = findWebView2Dll();
    auto distFolder = findUiDistFolder();
    if (dllPath.empty() || distFolder.empty()) return false;

    static HMODULE webviewModule = nullptr;
    static CreateWebViewEnvironmentWithOptionsInternal_t createEnv = nullptr;
    if (!webviewModule) {
        webviewModule = LoadLibraryExW(dllPath.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (webviewModule) {
            createEnv = reinterpret_cast<CreateWebViewEnvironmentWithOptionsInternal_t>(
                GetProcAddress(webviewModule, "CreateWebViewEnvironmentWithOptionsInternal"));
        }
    }
    if (!createEnv) return false;

    g_parent = parent;
    g_initializing = true;
    g_uiReady = false;
    g_bridgeToken = generateBridgeToken();
    g_lastClientSeq = 0;

    std::error_code ec;
    auto udf = dataFolder / L"webview2_cache";
    std::filesystem::create_directories(udf, ec);

    HRESULT hr = createEnv(true, 0, udf.wstring().c_str(), nullptr, new EnvironmentCompletedHandler(parent, distFolder));
    if (FAILED(hr)) {
        g_initializing = false;
        g_parent = nullptr;
        return false;
    }
    return true;
}

void pushSnapshot(const std::string& mode, const Json& state, const Json& marketItems, const Json& homeOverview, const Json& daylight, const Json& piracy, const Json& mission) {
    g_pendingMode = mode;
    g_pendingState = state;
    g_pendingMarketItems = marketItems;
    g_pendingHome = homeOverview;
    g_pendingDaylight = daylight;
    g_pendingPiracy = piracy;
    g_pendingMission = mission;
    sendSnapshotMessage();
}

void resize(int width, int height) {
    if (!g_controller) return;
    RECT bounds{0, 0, std::max(1, width), std::max(1, height)};
    g_controller->put_Bounds(bounds);
    if (g_parent) {
        bool visible = IsWindowVisible(g_parent) != 0;
        g_controller->put_IsVisible(visible ? TRUE : FALSE);
    }
}

void detach() {
    if (g_controller) {
        g_controller->Close();
        g_controller->Release();
        g_controller = nullptr;
    }
    if (g_webview) {
        g_webview->Release();
        g_webview = nullptr;
    }
    g_parent = nullptr;
    g_initializing = false;
    g_uiReady = false;
    g_bridgeToken.clear();
    g_lastClientSeq = 0;
}

int preview(const std::filesystem::path& directory) {
    if (std::filesystem::exists(directory / L"companion_private.json")) return 2;
    std::filesystem::create_directories(directory);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    auto beforeForeground = GetForegroundWindow();
    HWND hostWindow = CreateWindowExW(
        WS_EX_NOACTIVATE, L"STATIC", L"SynthScan WebView2 Preview", WS_POPUP,
        -32000, -32000, 1240, 840, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!hostWindow) return 2;
    ShowWindow(hostWindow, SW_SHOWNOACTIVATE);

    auto t0 = std::chrono::steady_clock::now();
    g_hasSuiteResult = false;
    g_suiteResult = {};
    g_initialUrl = L"https://synthscan.local/index.html?suite=roster500";

    std::vector<Json> receivedCommands;
    if (!attach(hostWindow, directory / L"wv2_profile", "people", [&](const Json& cmd) {
        receivedCommands.push_back(cmd);
    })) {
        DestroyWindow(hostWindow);
        return 2;
    }

    auto pumpUntil = [](auto predicate, DWORD timeoutMs) {
        DWORD start = GetTickCount();
        while (!predicate() && GetTickCount() - start < timeoutMs) {
            MSG msg{};
            while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
            Sleep(5);
        }
        return predicate();
    };

    bool suiteDone = pumpUntil([]() { return g_hasSuiteResult; }, 12000);
    double startupMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();

    // Now test normal live UI mode, authenticated command routing, forged token rejection, and PNG capture
    g_initialUrl = L"https://synthscan.local/index.html";
    g_uiReady = false;
    if (g_webview) {
        g_webview->Navigate(g_initialUrl.c_str());
    }
    bool liveReady = pumpUntil([]() { return g_uiReady; }, 8000);

    double nowSec = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    Json demoRows = arr();
    demoRows.items.push_back(obj({
        {"id", str("demo-self")}, {"handle", str("YourPilot")},
        {"tag", str("Org")}, {"is_self", SynthScan::boolean(true)}, {"is_org", SynthScan::boolean(true)},
        {"in_party", SynthScan::boolean(true)}, {"is_friend", SynthScan::boolean(true)}, {"on_shard", SynthScan::boolean(true)},
        {"relationship", str("You")}
    }));
    demoRows.items.push_back(obj({
        {"id", str("demo-one")}, {"handle", str("DemoPilot")},
        {"tag", str("Friendly, Trader, Org, Friend")}, {"is_org", SynthScan::boolean(true)},
        {"is_friend", SynthScan::boolean(true)}, {"on_shard", SynthScan::boolean(true)}, {"relationship", str("Friend")}
    }));
    demoRows.items.push_back(obj({
        {"id", str("demo-two")}, {"handle", str("Cassiopeia")},
        {"tag", str("Crew, Org Affiliate")}, {"is_org", SynthScan::boolean(true)},
        {"in_party", SynthScan::boolean(true)}, {"is_friend", SynthScan::boolean(true)}, {"on_shard", SynthScan::boolean(true)},
        {"relationship", str("Party + Friend")}
    }));
    Json state = obj({
        {"owner_pid", num(GetCurrentProcessId())},
        {"written_at", num(nowSec)},
        {"session_token", str("synthetic-webview-session")},
        {"rows", demoRows},
        {"action_people", arr()},
        {"friends_known", SynthScan::boolean(true)},
        {"party_known", SynthScan::boolean(true)},
        {"status", str("WebView2 synthetic verification — zero live game queries")}
    });
    pushSnapshot("people", state, arr(), obj({}));
    pumpUntil([]() { return false; }, 150);

    // 1. Test forged token rejection and unconfirmed social action rejection via ExecuteScript
    unsigned rejectedBefore = g_rejectedMessages;
    if (g_webview) {
        g_webview->ExecuteScript(
            L"window.chrome.webview.postMessage({kind:'command',bridge_token:'forged-token',client_seq:99,command:{action:'refresh_people'}});"
            L"window.chrome.webview.postMessage({kind:'command',bridge_token:window.__synthscanDesktop?.bridge?.bridgeToken||'',client_seq:100,command:{action:'party_many',player_ids:['demo-one'],confirmed:false}});"
            L"window.__synthscanDesktop?.bridge?.stagePlayers(['demo-one']);",
            nullptr);
    }
    pumpUntil([&]() { return !receivedCommands.empty() && g_rejectedMessages >= rejectedBefore + 2; }, 4000);
    bool forgedRejected = g_rejectedMessages >= rejectedBefore + 2;
    bool validStageRouted = !receivedCommands.empty() &&
        receivedCommands.front().textOr("action") == "stage_people" &&
        field(receivedCommands.front(), "player_ids").items.size() == 1 &&
        field(receivedCommands.front(), "player_ids").items[0].text == "demo-one";

    // Capture preview PNG of the rendered WebView2 People UI
    bool screenshotSaved = false;
    auto pngPath = directory / L"webview_people.png";
    if (g_webview) {
        IStream* memStream = nullptr;
        if (SUCCEEDED(CreateStreamOnHGlobal(nullptr, TRUE, &memStream)) && memStream) {
            bool capDone = false;
            HRESULT capHr = E_FAIL;
            if (SUCCEEDED(g_webview->CapturePreview(0 /* PNG */, memStream, new CapturePreviewHandler(&capDone, &capHr)))) {
                pumpUntil([&]() { return capDone; }, 5000);
                if (capDone && SUCCEEDED(capHr)) {
                    HGLOBAL hg = nullptr;
                    if (SUCCEEDED(GetHGlobalFromStream(memStream, &hg)) && hg) {
                        SIZE_T sz = GlobalSize(hg);
                        void* ptr = GlobalLock(hg);
                        if (ptr && sz > 100) {
                            std::ofstream out(pngPath, std::ios::binary);
                            out.write(static_cast<const char*>(ptr), sz);
                            screenshotSaved = out.good();
                        }
                        if (ptr) GlobalUnlock(hg);
                    }
                }
            }
            memStream->Release();
        }
    }

    PROCESS_MEMORY_COUNTERS pmc{};
    K32GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc));
    double hostMemoryMb = pmc.WorkingSetSize / (1024.0 * 1024.0);
    double browserMemoryMb = 0;
    UINT32 browserPid = 0;
    if (g_webview && SUCCEEDED(g_webview->get_BrowserProcessId(&browserPid)) && browserPid) {
        HANDLE hp = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, browserPid);
        if (hp) {
            PROCESS_MEMORY_COUNTERS bpmc{};
            if (K32GetProcessMemoryInfo(hp, &bpmc, sizeof(bpmc))) {
                browserMemoryMb = bpmc.WorkingSetSize / (1024.0 * 1024.0);
            }
            CloseHandle(hp);
        }
    }

    bool foregroundUnchanged = GetForegroundWindow() == beforeForeground;
    bool suitePassed = suiteDone && flag(g_suiteResult, "passed");

    Json report = obj({
        {"webview_available", SynthScan::boolean(true)},
        {"suite_500_roster_passed", SynthScan::boolean(suitePassed)},
        {"suite_500_details", g_suiteResult},
        {"live_ui_ready", SynthScan::boolean(liveReady)},
        {"forged_and_unconfirmed_rejected", SynthScan::boolean(forgedRejected)},
        {"authenticated_stage_routed", SynthScan::boolean(validStageRouted)},
        {"screenshot_saved", SynthScan::boolean(screenshotSaved)},
        {"foreground_unchanged", SynthScan::boolean(foregroundUnchanged)},
        {"startup_ms", num(startupMs)},
        {"host_working_set_mb", num(hostMemoryMb)},
        {"webview_working_set_mb", num(browserMemoryMb)},
        {"outgoing_requests_sent", num(0)}
    });
    write(directory / L"webview_validation.json", report);

    detach();
    DestroyWindow(hostWindow);
    CoUninitialize();
    return suitePassed && liveReady && forgedRejected && validStageRouted && screenshotSaved && foregroundUnchanged ? 0 : 3;
}

} // namespace SynthWebView
