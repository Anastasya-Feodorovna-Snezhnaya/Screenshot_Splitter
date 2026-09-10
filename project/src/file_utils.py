from __future__ import annotations

import ctypes
from pathlib import Path


def move_to_recycle_bin(path: Path) -> None:
    """将文件移动到 Windows 回收站，不直接永久删除。"""
    if not path.exists():
        raise FileNotFoundError(str(path))

    if not hasattr(ctypes, "windll"):
        raise OSError("将文件移至回收站仅支持 Windows。")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_bool),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040

    operation = SHFILEOPSTRUCTW(
        None,
        FO_DELETE,
        str(path) + "\0",
        None,
        FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO,
        False,
        None,
        None,
    )
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise OSError(f"无法将文件移至回收站（错误码：{result}）。")
