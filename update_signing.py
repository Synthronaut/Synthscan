"""Windows CNG ECDSA-P256 signing; release private keys never ship to clients."""
import base64
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Invalid JSON number')))


def cng():
    api=ctypes.WinDLL('bcrypt',use_last_error=True)
    ptr=ctypes.c_void_p;uint=w.ULONG;status=ctypes.c_long
    specs={
        'BCryptOpenAlgorithmProvider':([ctypes.POINTER(ptr),w.LPCWSTR,w.LPCWSTR,uint],status),
        'BCryptCloseAlgorithmProvider':([ptr,uint],status),
        'BCryptGenerateKeyPair':([ptr,ctypes.POINTER(ptr),uint,uint],status),
        'BCryptFinalizeKeyPair':([ptr,uint],status),
        'BCryptExportKey':([ptr,ptr,w.LPCWSTR,ptr,uint,ctypes.POINTER(uint),uint],status),
        'BCryptImportKeyPair':([ptr,ptr,w.LPCWSTR,ctypes.POINTER(ptr),ptr,uint,uint],status),
        'BCryptDestroyKey':([ptr],status),
        'BCryptSignHash':([ptr,ptr,ptr,uint,ptr,uint,ctypes.POINTER(uint),uint],status),
        'BCryptVerifySignature':([ptr,ptr,ptr,uint,ptr,uint,uint],status)}
    for name,(args,result) in specs.items():getattr(api,name).argtypes=args;getattr(api,name).restype=result
    return api


def checked(status):
    if status<0:raise ValueError(f'Windows signing operation failed: 0x{status & 0xffffffff:08X}')


def generate_key():
    api=cng();algorithm=ctypes.c_void_p();key=ctypes.c_void_p()
    checked(api.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm),'ECDSA_P256',None,0))
    try:
        checked(api.BCryptGenerateKeyPair(algorithm,ctypes.byref(key),256,0));checked(api.BCryptFinalizeKeyPair(key,0))
        def export(kind):
            size=w.ULONG();checked(api.BCryptExportKey(key,None,kind,None,0,ctypes.byref(size),0))
            data=ctypes.create_string_buffer(size.value);checked(api.BCryptExportKey(key,None,kind,data,len(data),ctypes.byref(size),0))
            return data.raw[:size.value]
        return export('ECCPRIVATEBLOB'),export('ECCPUBLICBLOB')
    finally:
        if key:api.BCryptDestroyKey(key)
        api.BCryptCloseAlgorithmProvider(algorithm,0)


def signature(blob,payload,existing=None):
    api=cng();algorithm=ctypes.c_void_p();key=ctypes.c_void_p()
    checked(api.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm),'ECDSA_P256',None,0))
    try:
        keydata=ctypes.create_string_buffer(blob)
        checked(api.BCryptImportKeyPair(algorithm,None,'ECCPUBLICBLOB' if existing is not None else 'ECCPRIVATEBLOB',ctypes.byref(key),keydata,len(blob),0))
        digest=ctypes.create_string_buffer(hashlib.sha256(payload).digest())
        if existing is not None:
            if len(existing)!=64:raise ValueError('Invalid update signature size')
            sig=ctypes.create_string_buffer(existing)
            checked(api.BCryptVerifySignature(key,None,digest,32,sig,len(existing),0))
            return True
        size=w.ULONG();data=ctypes.create_string_buffer(64)
        checked(api.BCryptSignHash(key,None,digest,32,data,64,ctypes.byref(size),0))
        return data.raw[:size.value]
    finally:
        if key:api.BCryptDestroyKey(key)
        api.BCryptCloseAlgorithmProvider(algorithm,0)


def protect(raw,decrypt=False):
    class Blob(ctypes.Structure):_fields_=[('size',w.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    api=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    source_buffer=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(source_buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=api.CryptUnprotectData;fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,w.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        fn=api.CryptProtectData;fn.argtypes=[ctypes.POINTER(Blob),w.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,w.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),'SynthScan release signing key',None,None,None,1,ctypes.byref(target))
    if not ok:raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


def private_key(path):
    return protect(Path(path).read_bytes(),decrypt=True)


def envelope(payload,private,public):
    raw=canonical(payload)
    return dict(schema=1,key_id=hashlib.sha256(public).hexdigest()[:16],
                payload=base64.b64encode(raw).decode(),signature=base64.b64encode(signature(private,raw)).decode())


def verify(raw,trust):
    if len(raw)>256*1024:raise ValueError('Update manifest exceeds limit')
    value=strict_json(raw)
    if not isinstance(value,dict) or value.get('schema')!=1:raise ValueError('Unsupported update envelope')
    key=trust.get('keys',{}).get(value.get('key_id'))
    if not key:raise ValueError('Unknown update signing key')
    public=base64.b64decode(key,validate=True)
    payload=base64.b64decode(value['payload'],validate=True)
    signed=base64.b64decode(value['signature'],validate=True)
    signature(public,payload,signed)
    result=strict_json(payload)
    if not isinstance(result,dict):raise ValueError('Invalid update payload')
    return result
