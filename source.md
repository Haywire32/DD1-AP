# Source code

This is the source for DD1 Archipelago 0.3.2. The mod is for Dungeon Defenders
Local play only.

## Where to look

- `apworld/dungeon_defenders/`: items, locations, options, generation logic, and the AP client.
- `bridge/`: communication with the game, save handling, and Python tests.
- `game/Classes/`: the mod's UnrealScript classes.
- `release/`: the public YAML, installation notes, and mod configuration.
- `tools/`: the Python build script.

See [building and testing](docs/PYTHON-BUILD.md),
[client behavior and security](docs/SECURITY.md), or
[building the game mod](game/PATCHING.md).

## What's included

This source folder does not include game images, videos, executables, compiled
game packages, or player saves. It is not a ready-to-play installation. The game
and Development Kit are separate requirements, and the Python client uses
Archipelago.

The playable 0.3.2 download includes compiled game dependencies; players do not
need to compile them. The project owner reports permission to distribute those
dependencies. No reuse license has been chosen for this source yet.

## Changes in 0.3.2

The client now handles wave events and received items on the same event-loop
thread, preventing a wave update from overwriting newly received items. Startup
checks also identify missing or empty native game libraries before launching.
The packaged defaults preserve AP activation when game settings are regenerated.
The public download omits duplicate loading movies and splash images while
retaining the compiled script dependencies. Gameplay and YAML options are unchanged.

## Testing

The 0.3.2 source passed 55 Python tests. Its rebuilt `.apworld` is byte-identical
to the reference release. File hashes are listed in `SOURCE-MANIFEST.json`.

Some tests use stand-ins for Archipelago and the game. They do not replace
playtesting. A complete rebuild of every game dependency from a fresh DDDK
installation has not been verified; the game build notes explain the limits.

Development used AI assistance. The project has not had an independent security
audit.
