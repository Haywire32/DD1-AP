# Dungeon Defenders Archipelago

Source for the DD1 Archipelago 0.3.1 world, client, and Local-only Total Conversion.

This repository is for reading, reviewing, testing, and building the integration.
It is not a complete game installation or a replacement playtest download. It
contains no game videos, images, compiled game packages, executables, or saves.
The separate game-file distribution question is not resolved by publishing source.

## Start here

- [Client behavior and security review notes](docs/SECURITY.md): network use, installation lookup, file writes, save switching, and known review limitations.
- [Build the Python world/client and run tests](docs/PYTHON-BUILD.md).
- [Game source, dependencies, and build limitations](game/PATCHING.md).
- [Contents and third-party boundaries](docs/CONTENTS.md).
- [Validation of this source snapshot](docs/VALIDATION.md).

## Source layout

| Folder | Contents |
| --- | --- |
| `apworld/dungeon_defenders/` | Archipelago world generation, options, items, locations, client, and public YAML exporter. |
| `bridge/` | Event parsing, item handling, installation discovery, state/save handling, and Python tests. |
| `game/Classes/` | Seven UnrealScript classes in the separate `DD1Archipelago` package. |
| `release/` | The public YAML, existing 0.3.1 installation/update text, and small AP configuration overrides. |
| `tools/` | Readable developer tools. These are not player installers and do not install game files. |

The Python modules under `bridge/` are placed beside the world/client modules
inside the built `.apworld`. They are kept separate here for testing and review.
The game sources subclass existing DD1 classes; the old experimental patches to
the complete base-game source are not part of this version.

## Development status

This is an experimental community integration, not an official Archipelago or
Dungeon Defenders release. It targets **Play Local only**, not Ranked or online
DD1 sessions. Runtime use requires the player's own Dungeon Defenders, DDDK,
and a compatible Archipelago installation.

Development has used AI assistance. The included automated tests and developer
checks are not an independent human security audit or a certification of safety.
The code is made browsable so reviewers can inspect it directly.

The historical player instructions in `release/` describe the 0.3.1 runtime
package. This source-only repository intentionally omits that package's game
dependencies and media. Do not copy this repository into a game installation and
expect it to be a complete installed mod.

No new source-code reuse license has been selected for this publication draft.
The game's code, assets, tools, and third-party dependencies retain their own
terms. See [the contents notes](docs/CONTENTS.md); publishing this source does not
grant permission to redistribute those dependencies.
