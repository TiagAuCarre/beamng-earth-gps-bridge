"""Strict validator for the shared UTF-8 JSON Lines v1 position protocol."""
import json
import math

MAX_LINE_BYTES = 4096
FIELDS = {"version", "type", "source", "stream_id", "seq", "timestamp_utc_ms", "latitude", "longitude", "altitude_m", "speed_mps", "heading_deg", "test"}


def validate_line(raw: bytes, *, now_ms: int | None = None, max_age_ms: int = 5000) -> dict:
    if len(raw) > MAX_LINE_BYTES:
        raise ValueError("message exceeds 4096 bytes")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8/JSON: {exc}") from exc
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise ValueError("missing or unknown protocol fields")
    if obj.get("version") != 1 or obj.get("type") != "position":
        raise ValueError("unsupported protocol version or type")
    if obj.get("source") not in ("beamng-earth", "test"):
        raise ValueError("invalid source")
    if not isinstance(obj.get("test"), bool) or obj["test"] != (obj["source"] == "test"):
        raise ValueError("test marker/source mismatch")
    if not isinstance(obj.get("stream_id"), str) or not 1 <= len(obj["stream_id"]) <= 64:
        raise ValueError("invalid stream_id")
    if type(obj.get("seq")) is not int or obj["seq"] < 0:
        raise ValueError("invalid sequence")
    if type(obj.get("timestamp_utc_ms")) is not int or obj["timestamp_utc_ms"] <= 0:
        raise ValueError("invalid UTC timestamp")
    for key, low, high in (("latitude", -90, 90), ("longitude", -180, 180), ("speed_mps", 0, 150)):
        value = obj.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"invalid {key}")
    for key, low, high in (("altitude_m", None, None), ("heading_deg", 0, 360)):
        value = obj.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (low is not None and not low <= value <= high)):
            raise ValueError(f"invalid {key}")
    if now_ms is not None and (now_ms - obj["timestamp_utc_ms"] > max_age_ms or obj["timestamp_utc_ms"] - now_ms > 60_000):
        raise ValueError("stale or future timestamp")
    return obj
