import ctypes
import unittest
from bluetooth_win import AF_BTH, SockAddrBth, SPP_UUID, connect


class WindowsBluetoothTests(unittest.TestCase):
    def test_sockaddr_uses_packed_windows_layout_and_spp_uuid(self):
        address = SockAddrBth(AF_BTH, 0x010203040506, (ctypes.c_ubyte * 16).from_buffer_copy(SPP_UUID.bytes_le), 0)
        self.assertEqual(ctypes.sizeof(address), 30)
        self.assertEqual(bytes(address.service_uuid), SPP_UUID.bytes_le)

    def test_rejects_invalid_address_before_opening_socket(self):
        with self.assertRaisesRegex(ValueError, "address"):
            connect("not-an-address")


if __name__ == "__main__": unittest.main()
