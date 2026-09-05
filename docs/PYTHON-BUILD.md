# Building the Archipelago world and client

The `.apworld` contains the Dungeon Defenders world, Python client, bridge code, and public YAML template. It does not contain the compiled game mod. Building it does not install anything or require Dungeon Defenders to be running.

Use Python 3.10 or newer. The builder uses only Python's standard library; it does not download packages or look for Steam, Archipelago, or game installations.

From this source folder, run:

```text
python tools/build_apworld.py
```

The result is `dist/dungeon_defenders.apworld`. The builder refuses to replace an existing archive. To rebuild it deliberately:

```text
python tools/build_apworld.py --overwrite
```

An alternate destination can be supplied with `--output path/to/dungeon_defenders.apworld`. Relative destinations are resolved from the current working directory.

## Source files included

The builder uses these files from this checkout:

- `apworld/archipelago.json`, copied unchanged to the archive root.
- Top-level Python files in `apworld/dungeon_defenders/`.
- `bridge/dd1_*.py`, placed alongside the world/client Python files.
- `release/Dungeon Defenders.yaml`, placed alongside those files under the same filename.

The YAML in `release/` is the single editable public template. The **Dungeon Defenders YAML** action in Archipelago Launcher exports that bundled file with its comments, defaults, and `PlayerName` placeholder intact. Archipelago's general **Generate Template Options** action uses Archipelago's standard layout and public name placeholder, with DD1's option descriptions and defaults.

The archive does not include tests, logs, saves, installed game files, cached Python files, or UnrealScript assets. Entries are sorted and have fixed timestamps and permissions, so repeated builds with the same inputs and Python compression implementation produce identical bytes.

## Package metadata

The current manifest is the format-7 manifest used and tested with Archipelago 0.6.7. Its `world_version` is the DD1 public release number; `minimum_ap_version` is the minimum Archipelago version. The separate `version` and `compatible_version` fields belong to the package format and remain `7`. Changing the public release number does not mean changing those two fields.

This builder preserves the project's existing archive structure. Archipelago's own source checkout also provides `BuildAPWorlds.py` for its native world-building workflow. Using that alternative means arranging this world's sources and bundled YAML for that builder and following the documentation for that Archipelago revision; it is not necessary for the build command above.

## Verification

The project's Python tests can be run from the source root:

```text
python -m unittest discover -s bridge -p "test_*.py" -v
```

These are Python checks; passing them does not prove that a freshly installed game loads the compiled mod. Game launch and configuration regeneration require their own DDDK playtest.

For an Archipelago integration check, install the built `.apworld` into a separate Archipelago 0.6.7 test installation, then:

1. Use **Dungeon Defenders YAML** in Archipelago Launcher and save a YAML. It should match `release/Dungeon Defenders.yaml` exactly.
2. Use **Generate Template Options**. Its Dungeon Defenders template should have the same option defaults, although the layout is Archipelago's longer standard layout.
3. Generate a test seed from the saved public YAML. The default options are 11 maps, Medium Summit unlock difficulty, and Hard Summit goal difficulty.

The builder itself neither installs the `.apworld` nor launches Archipelago. The Total Conversion must be built separately using the DDDK and the UnrealScript sources; this Python command cannot create the compiled game mod.
