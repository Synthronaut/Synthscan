"""Host an explicitly requested Tk tool inside the native desktop page."""
import ctypes
from ctypes import wintypes as w
import time


def valid_request(request, owner, now):
    return (isinstance(request, dict) and request.get('owner_pid') == owner
            and type(request.get('parent')) is int and request['parent'] > 0
            and type(request.get('generation')) is int and request['generation'] > 0
            and type(request.get('at')) in (int, float) and 0 <= now-request['at'] < 30)


class EmbeddedWindow:
    def __init__(self, root, directory, owner):
        from telemetry_ipc import read_shared_json
        self.root, self.directory, self.owner = root, directory, owner
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        api = self.api
        api.GetAncestor.argtypes = [w.HWND, w.UINT]; api.GetAncestor.restype = w.HWND
        api.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]; api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        api.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]; api.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        api.SetParent.argtypes = [w.HWND, w.HWND]; api.SetParent.restype = w.HWND
        api.IsWindow.argtypes = [w.HWND]; api.IsWindow.restype = w.BOOL
        api.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        api.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
        api.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
        api.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        request = read_shared_json(directory/'daylight_embed_request.json')
        self.validate(request)
        self.parent = request['parent']
        root.overrideredirect(True); root.update_idletasks()
        self.hwnd = api.GetAncestor(root.winfo_id(), 2)
        style = api.GetWindowLongPtrW(self.hwnd, -16)
        api.SetWindowLongPtrW(self.hwnd, -16, (style & ~0x80CF0000) | 0x40000000 | 0x02000000)
        api.SetWindowLongPtrW(self.hwnd, -20, api.GetWindowLongPtrW(self.hwnd, -20) & ~0x08040088)
        api.SetParent(self.hwnd, self.parent)
        root.deiconify()
        self.request_show(request)
        self.poll()

    def validate(self, request):
        if not valid_request(request, self.owner, time.time()):raise ValueError('Expired desktop page request')
        pid = w.DWORD()
        self.api.GetWindowThreadProcessId(request['parent'], ctypes.byref(pid))
        if pid.value != self.owner or not self.api.IsWindow(request['parent']):raise ValueError('Desktop owner changed')

    def request_show(self, request):
        self.validate(request)
        if request['parent'] != self.parent:raise ValueError('Desktop host changed')
        self.api.PostMessageW(self.parent, 0x8000+417, self.hwnd, request['generation'])

    def show(self):
        from telemetry_ipc import read_shared_json
        self.request_show(read_shared_json(self.directory/'daylight_embed_request.json'))

    def poll(self):
        if not self.api.IsWindow(self.parent):self.root.destroy();return
        rect = w.RECT();self.api.GetClientRect(self.parent, ctypes.byref(rect))
        self.api.SetWindowPos(self.hwnd, None, 0, 0, max(720, rect.right), max(640, rect.bottom), 0x0014)
        self.root.after(250, self.poll)
