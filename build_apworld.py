"""Build the source checkout's world/client archive; no installs or downloads."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def build(root, output):
    entries = {"archipelago.json": root / "apworld/archipelago.json"}
    for folder, pattern in (("apworld/dungeon_defenders", "*.py"), ("bridge", "dd1_*.py")):
        for path in sorted((root / folder).glob(pattern)):
            key = "dungeon_defenders/" + path.name
            if key in entries:
                raise ValueError("Duplicate archive entry: " + key)
            entries[key] = path
    entries["dungeon_defenders/Dungeon Defenders.yaml"] = root / "release/Dungeon Defenders.yaml"
    contents = {key: path.read_bytes() for key, path in entries.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        directory = ZipInfo("dungeon_defenders/", (1980, 1, 1, 0, 0, 0))
        directory.external_attr = (0o40755 << 16) | 0x10
        archive.writestr(directory, b"")
        for key, content in sorted(contents.items()):
            entry = ZipInfo(key, (1980, 1, 1, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content, compress_type=ZIP_DEFLATED, compresslevel=9)
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(build(root, root / "dist/dungeon_defenders.apworld"))
