# Draft proposal for BeamNG.earth

The text below is ready to adapt as a GitHub Discussion or feature request. It has not been posted.

## Suggested title

Optional GPS location output for external devices and navigation apps

## Proposal

Hello BeamNG.earth team,

I have built an optional companion project that forwards the player vehicle's geographic position to an Android phone. It uses the WGS84 coordinates already calculated by BeamNG.earth, then sends them over localhost TCP to a Windows relay and Bluetooth Classic RFCOMM/SPP to an Android app. The Android app can publish these updates through the public mock-location APIs after the user explicitly enables it.

Would you consider a small, opt-in integration point for external location consumers? A stable callback or documented export containing latitude, longitude, optional altitude, speed, heading, and a timestamp would let companion projects avoid reading a private Lua state table. The external bridge could remain separately installed and disabled by default.

The companion implementation is kept separate from the BeamNG.earth files so normal mod updates do not overwrite it. It does not alter Android Auto, Wi-Fi Direct, or BeamNG.earth navigation. Android mock-location behavior varies by app, so compatibility with Google Maps, Waze, and Android Auto is not assumed.

Repository: **[add the public repository URL after publishing]**

I would be happy to adjust the bridge to a supported interface or provide a focused pull request if this direction fits the project.

Thanks!

## Implementation notes for maintainers

- Current prototype reads `beamngEarth_core._state()` from a separate BeamNG user mod.
- A supported, read-only export would be preferable to adding Bluetooth, phone pairing, or Android-specific code to BeamNG.earth itself.
- Suggested data fields: WGS84 latitude/longitude, optional altitude in metres, speed in m/s, optional true heading in degrees, UTC timestamp, and a monotonically increasing sequence number.
- Suggested transport boundary: local callback or documented extension API; the companion can own TCP/Bluetooth transport, UI, permissions, retries, and mock-location handling.
- Default-off behavior and no change to existing navigation/rendering would preserve current behavior.
