# Building and testing

These instructions are for working on the source, not installing the mod to play.
Use Python 3.10 or newer. The build script needs no extra Python packages.

From the repository's main folder, run:

```text
python tools/build_apworld.py
```

This creates `dist/dungeon_defenders.apworld`. To replace an earlier build, add
`--overwrite`. Use `--output path/to/file.apworld` to choose another destination.

The archive contains the world, client, bridge code, and
`release/Dungeon Defenders.yaml`. The script does not download dependencies,
install the result, or change your game files. The game mod must be built
separately; see [the game build notes](../game/PATCHING.md).

## Run the tests

From the same folder:

```text
python -m unittest discover -s bridge -p "test_*.py" -v
```

There are 50 Python tests in version 0.3.1. They cover selected client,
progression, and save-handling behavior, but not a complete game session.

Archipelago integration was tested with 0.6.7. For changes to the world or YAML,
also generate a seed in a separate test installation. The **Dungeon Defenders
YAML** launcher entry should export the bundled template unchanged.
