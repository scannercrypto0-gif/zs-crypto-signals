"""Windows Job Object watchdog. A cooperative child waits before doing work."""
import ctypes
from ctypes import wintypes
import subprocess

START = b"ZS-START\n"


class BasicLimits(ctypes.Structure):
    _fields_ = [("per_process", ctypes.c_longlong), ("per_job", ctypes.c_longlong),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("active_process_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority_class", wintypes.DWORD),
                ("scheduling_class", wintypes.DWORD)]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", ctypes.c_ulonglong*6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]


def _api():
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, args, result in (
        ("CreateJobObjectW", [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        ("SetInformationJobObject", [wintypes.HANDLE,wintypes.INT,ctypes.c_void_p,wintypes.DWORD], wintypes.BOOL),
        ("AssignProcessToJobObject", [wintypes.HANDLE,wintypes.HANDLE], wintypes.BOOL),
        ("OpenProcess", [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD], wintypes.HANDLE),
        ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
    ):
        fn = getattr(dll,name)
        fn.argtypes, fn.restype = args, result
    return dll


def run_tree(argv, timeout):
    api = _api()
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    process = None
    assigned = False
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        process = subprocess.Popen(argv, stdin=subprocess.PIPE)
        handle = api.OpenProcess(0x0101, False, process.pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            assigned = bool(api.AssignProcessToJobObject(job, handle))
            if not assigned:
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(handle)
        process.stdin.write(START)
        process.stdin.close()
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124
        except KeyboardInterrupt:
            return 130
    finally:
        api.CloseHandle(job)
        if process is not None:
            process.stdin.close()
            if not assigned and process.poll() is None:
                process.kill()
            process.wait(timeout=5)
