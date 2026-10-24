import json
import unittest
from protocol import validate_line

GOOD = {"version": 1, "type": "position", "source": "test", "stream_id": "unit", "seq": 1,
        "timestamp_utc_ms": 10000, "latitude": 45.0, "longitude": 4.0, "altitude_m": None,
        "speed_mps": 0.0, "heading_deg": None, "test": True}


class ProtocolTests(unittest.TestCase):
    def test_accepts_valid_test_position(self):
        self.assertEqual(validate_line(json.dumps(GOOD).encode(), now_ms=10000), GOOD)

    def test_rejects_out_of_range_coordinates(self):
        item = dict(GOOD, latitude=91)
        with self.assertRaisesRegex(ValueError, "latitude"):
            validate_line(json.dumps(item).encode())

    def test_rejects_stale_message(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_line(json.dumps(GOOD).encode(), now_ms=16001)

    def test_rejects_oversize(self):
        with self.assertRaisesRegex(ValueError, "4096"):
            validate_line(b" " * 4097)

    def test_rejects_test_source_mismatch(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            validate_line(json.dumps(dict(GOOD, source="beamng-earth")).encode())

    def test_rejects_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_line(json.dumps(dict(GOOD, unexpected=1)).encode())


if __name__ == "__main__":
    unittest.main()
