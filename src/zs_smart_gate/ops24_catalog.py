"""Explicit Windows catalog discovery and WinVerifyTrust member verification.

No catalog installation, trust-store edits, unsigned-file or cached-status fallback.
Catalog discovery is separable from verification for noninteractive diagnostics.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import msvcrt
from pathlib import Path
import uuid

VERSION='WINDOWS_EXPLICIT_CATALOG_MEMBER_V1'

class CatalogInfo(c.Structure):
    _fields_=[('size',w.DWORD),('path',w.WCHAR*260)]

class CatalogMember(c.Structure):
    _fields_=[('size',w.DWORD),('version',w.DWORD),('catalog',w.LPCWSTR),
              ('tag',w.LPCWSTR),('path',w.LPCWSTR),('file',w.HANDLE),
              ('hash',c.c_void_p),('hash_size',w.DWORD),('context',c.c_void_p),
              ('admin',w.HANDLE)]

class TrustData(c.Structure):
    _fields_=[('size',w.DWORD),('policy',c.c_void_p),('sip',c.c_void_p),
              ('ui',w.DWORD),('revocation',w.DWORD),('choice',w.DWORD),
              ('info',c.c_void_p),('state_action',w.DWORD),('state',w.HANDLE),
              ('url',w.LPWSTR),('flags',w.DWORD),('ui_context',w.DWORD),
              ('signature_settings',c.c_void_p)]

def api():
    system=c.create_unicode_buffer(32768)
    _check(c.windll.kernel32.GetSystemDirectoryW(system,len(system)))
    dll=c.WinDLL(str(Path(system.value)/'wintrust.dll'),use_last_error=True)
    specs={
        'CryptCATAdminAcquireContext2':([c.POINTER(w.HANDLE),c.c_void_p,w.LPCWSTR,c.c_void_p,w.DWORD],w.BOOL),
        'CryptCATAdminCalcHashFromFileHandle2':([w.HANDLE,w.HANDLE,c.POINTER(w.DWORD),c.c_void_p,w.DWORD],w.BOOL),
        'CryptCATAdminEnumCatalogFromHash':([w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,c.POINTER(w.HANDLE)],w.HANDLE),
        'CryptCATCatalogInfoFromContext':([w.HANDLE,c.POINTER(CatalogInfo),w.DWORD],w.BOOL),
        'CryptCATAdminReleaseCatalogContext':([w.HANDLE,w.HANDLE,w.DWORD],w.BOOL),
        'CryptCATAdminReleaseContext':([w.HANDLE,w.DWORD],w.BOOL),
        'WinVerifyTrust':([w.HWND,c.c_void_p,c.POINTER(TrustData)],w.LONG),
    }
    for name,(args,result) in specs.items():
        fn=getattr(dll,name);fn.argtypes=args;fn.restype=result
    return dll

def _check(ok):
    if not ok:
        raise c.WinError(c.get_last_error())

def member_proof(path,*,catalog=None):
    """Return actual native catalog/chain/member result; only code zero succeeds.

    Default SHA256 Authenticode/SIP hash is calculated by Windows, not the raw
    file digest. Whole-file SHA256 additionally binds the observed binary bytes.
    Optional catalog selects a real file, never a claimed successful result.
    """
    path=Path(path).resolve(strict=True)
    if path.stat().st_size>16*1024*1024:
        raise ValueError('BOUNDED_SYSTEM_BINARY_REQUIRED')
    dll=api();admin=w.HANDLE();info_handle=None
    _check(dll.CryptCATAdminAcquireContext2(c.byref(admin),None,'SHA256',None,0))
    try:
        with path.open('rb') as stream:
            handle=w.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
            length=w.DWORD()
            _check(dll.CryptCATAdminCalcHashFromFileHandle2(admin,handle,c.byref(length),None,0))
            if not 0<length.value<=64:
                raise ValueError('CATALOG_HASH_SIZE_INVALID')
            value=(c.c_ubyte*length.value)()
            stream.seek(0)
            _check(dll.CryptCATAdminCalcHashFromFileHandle2(admin,handle,c.byref(length),value,0))
            tag=bytes(value).hex().upper()
            if catalog is None:
                previous=w.HANDLE()
                info_handle=dll.CryptCATAdminEnumCatalogFromHash(admin,value,length,0,c.byref(previous))
                if not info_handle:
                    raise OSError(c.get_last_error(),'CATALOG_MEMBER_NOT_DISCOVERED')
                found=CatalogInfo();found.size=c.sizeof(found)
                _check(dll.CryptCATCatalogInfoFromContext(info_handle,c.byref(found),0))
                catalog=found.path
            catalog=Path(catalog).resolve(strict=True)
            if catalog.stat().st_size>32*1024*1024:
                raise ValueError('BOUNDED_CATALOG_REQUIRED')
            before=hashlib.sha256(catalog.read_bytes()).hexdigest()
            member=CatalogMember();member.size=c.sizeof(member)
            member.catalog=str(catalog);member.tag=tag;member.path=str(path)
            member.file=handle;member.hash=c.cast(value,c.c_void_p)
            member.hash_size=length.value;member.admin=admin
            data=TrustData();data.size=c.sizeof(data);data.ui=2
            data.choice=2;data.info=c.cast(c.pointer(member),c.c_void_p)
            data.state_action=1
            action=(c.c_ubyte*16).from_buffer_copy(uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le)
            # Standard generic Authenticode policy, no UI, no trust-root changes.
            # As in Microsoft's WinVerifyTrust sample, revocation is not requested
            # separately here. This is NOT independent revocation-freshness proof.
            try:
                result=int(dll.WinVerifyTrust(None,action,c.byref(data)))
            finally:
                data.state_action=2
                dll.WinVerifyTrust(None,action,c.byref(data))
            stream.seek(0);binary_sha=hashlib.sha256(stream.read()).hexdigest()
            after=hashlib.sha256(catalog.read_bytes()).hexdigest()
            if before!=after:
                raise ValueError('CATALOG_CHANGED_DURING_VERIFICATION')
            return dict(version=VERSION,file=str(path),file_sha256=binary_sha,
                        catalog=str(catalog),catalog_sha256=after,
                        hash_algorithm='SHA256',sip_member_tag=tag,
                        winverifytrust_code=result,verified=(result==0),
                        revocation_freshness='NOT_SEPARATELY_PROVEN')
    finally:
        if info_handle:
            dll.CryptCATAdminReleaseCatalogContext(admin,info_handle,0)
        dll.CryptCATAdminReleaseContext(admin,0)
