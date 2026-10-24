"""Install the independent GPS bridge into BeamNG's user mods/unpacked folder."""
from pathlib import Path
import argparse
import shutil

SOURCE = Path(__file__).resolve().parent / "bng_gps_bridge"
MARKER = SOURCE / "info.json"


def install(user_dir: Path) -> Path:
    dest = user_dir / "mods" / "unpacked" / "bng_gps_bridge"
    if dest.exists() and not (dest / "info.json").is_file():
        raise RuntimeError(f"Refusing to overwrite an unrelated folder: {dest}")
    if not MARKER.is_file():
        raise RuntimeError(f"Bridge mod source is incomplete: {SOURCE}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, dest, dirs_exist_ok=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_dir", type=Path, help="BeamNG user data folder, e.g. H:/Beamng Data/current")
    args = parser.parse_args()
    print(f"Installed independent mod: {install(args.user_dir)}")
    print("Restart BeamNG.drive or reload mods to mount it; then enable it in the Mod Manager.")


if __name__ == "__main__":
    main()
