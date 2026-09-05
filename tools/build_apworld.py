#!/usr/bin/env python3
"""Build the DD1 Python world/client archive using only Python's standard library.

This packages files from the source checkout. It does not find installations,
install anything, download dependencies, or include Dungeon Defenders assets.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PACKAGE_NAME = "dungeon_defenders"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_inputs(source_root: Path) -> dict[str, bytes]:
    manifest_path = source_root / "apworld" / "archipelago.json"
    package_path = source_root / "apworld" / PACKAGE_NAME
    bridge_path = source_root / "bridge"
    template_path = source_root / "release" / "Dungeon Defenders.yaml"

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if manifest.get("game") != "Dungeon Defenders":
        raise ValueError("apworld/archipelago.json must describe Dungeon Defenders.")
    if not manifest.get("world_version") or not manifest.get("minimum_ap_version"):
        raise ValueError("The manifest needs world_version and minimum_ap_version.")
    if manifest.get("version") != 7 or manifest.get("compatible_version") != 7:
        raise ValueError("This builder supports the tested DD1 format-7 package metadata.")

    # These entry points/resources are required by the current client and world.
    for filename in ("__init__.py", "Client.py", "items.py", "locations.py", "public_yaml.py"):
        if not (package_path / filename).is_file():
            raise FileNotFoundError(f"Missing apworld/{PACKAGE_NAME}/{filename}")
    for filename in ("dd1_ap_adapter.py", "dd1_bridge_service.py", "dd1_event_watcher.py",
                     "dd1_install.py", "dd1_protocol.py"):
        if not (bridge_path / filename).is_file():
            raise FileNotFoundError(f"Missing bridge/{filename}")

    entries = {"archipelago.json": manifest_bytes}
    for path in sorted(package_path.glob("*.py")) + sorted(bridge_path.glob("dd1_*.py")):
        archive_name = f"{PACKAGE_NAME}/{path.name}"
        if archive_name in entries:
            raise ValueError(f"Two source files would use the same archive path: {archive_name}")
        entries[archive_name] = path.read_bytes()
    entries[f"{PACKAGE_NAME}/Dungeon Defenders.yaml"] = template_path.read_bytes()
    return entries


def archive_bytes(entries: dict[str, bytes]) -> bytes:
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        directory = ZipInfo(f"{PACKAGE_NAME}/", date_time=ZIP_TIMESTAMP)
        directory.create_system = 3
        directory.external_attr = (0o40755 << 16) | 0x10
        bundle.writestr(directory, b"")
        for archive_name, content in sorted(entries.items()):
            info = ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)
    return archive.getvalue()


def build(source_root: Path, output: Path, *, overwrite: bool = False) -> Path:
    source_root = source_root.resolve()
    output = output.resolve()
    if output.suffix.lower() != ".apworld":
        raise ValueError("The output filename must end in .apworld.")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Already exists: {output}. Use --overwrite to replace it.")

    # Build fully in memory before opening the output, so a missing source file
    # cannot damage an existing archive even when --overwrite was requested.
    content = archive_bytes(build_inputs(source_root))
    output.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        # Exclusive creation also prevents an unexpected overwrite if another
        # process creates the destination while this archive is being built.
        with output.open("xb") as target:
            target.write(content)
    else:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".dd1-apworld-", delete=False) as target:
                temporary_path = Path(target.name)
                target.write(content)
            temporary_path.replace(output)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return output


def main() -> None:
    source_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=source_root / "dist" / "dungeon_defenders.apworld",
                        help="Output archive path (default: dist/dungeon_defenders.apworld in this checkout).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output archive.")
    args = parser.parse_args()
    try:
        result = build(source_root, args.output, overwrite=args.overwrite)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"Built {result}")


if __name__ == "__main__":
    main()
