"""Windows native Bluetooth Classic RFCOMM client using CPython's AF_BTH socket."""
import ctypes
import json
import re
import socket
import subprocess
import uuid

AF_BTH = 32
BTHPROTO_RFCOMM = 3
SPP_UUID = uuid.UUID("00001101-0000-1000-8000-00805F9B34FB")


def paired_devices() -> list[tuple[str, str]]:
    """Enumerate Bluetooth device records Windows exposes through its built-in PnP cmdlet."""
    command = (
        "Get-PnpDevice -Class Bluetooth | "
        "Select-Object FriendlyName,InstanceId,Status | ConvertTo-Json -Compress"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, timeout=15, check=True)
    items = json.loads(result.stdout or "[]")
    if isinstance(items, dict): items = [items]
    found = {}
    for item in items:
        match = re.search(r"BTHENUM\\DEV_([0-9A-F]{12})", item.get("InstanceId", ""), re.I)
        if not match: continue
        digits = match.group(1).upper()
        address = ":".join(digits[i:i + 2] for i in range(0, 12, 2))
        found[address] = item.get("FriendlyName") or "Appareil Bluetooth"
    return [(address, name) for address, name in sorted(found.items(), key=lambda pair: pair[1].casefold())]


class SockAddrBth(ctypes.Structure):
    # ws2bth.h SOCKADDR_BTH is packed to 1 in CPython's Windows socket build.
    _pack_ = 1
    _fields_ = [("family", ctypes.c_ushort), ("address", ctypes.c_ulonglong),
                ("service_uuid", ctypes.c_ubyte * 16), ("port", ctypes.c_ulong)]


def connect(address: str) -> socket.socket:
    """Connect to an Android SPP listener; Winsock resolves the RFCOMM channel via SDP."""
    compact = address.replace(":", "").replace("-", "")
    if not re.fullmatch(r"[0-9A-Fa-f]{12}", compact): raise ValueError("invalid Bluetooth address")
    sock = socket.socket(AF_BTH, socket.SOCK_STREAM, BTHPROTO_RFCOMM)
    addr = SockAddrBth(AF_BTH, int(compact, 16), (ctypes.c_ubyte * 16).from_buffer_copy(SPP_UUID.bytes_le), 0)
    winsock = ctypes.WinDLL("Ws2_32.dll", use_last_error=True)
    connect_fn = winsock.connect
    connect_fn.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    connect_fn.restype = ctypes.c_int
    try:
        result = connect_fn(sock.fileno(), ctypes.byref(addr), ctypes.sizeof(addr))
        if result != 0:
            err = winsock.WSAGetLastError()
            raise OSError(err, f"Winsock RFCOMM connect error {err}")
        return sock
    except Exception:
        sock.close()
        raise
