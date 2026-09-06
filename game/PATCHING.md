# Building the game mod

Updated 5 September 2026, for version 0.3.1.

The seven files in [Classes](Classes) compile into `DD1Archipelago.u` using the
Dungeon Defenders Development Kit (DDDK). They extend existing game classes;
no base-game source patches are required. Do not use the old experimental
hero-manager patch scripts.

The Python world/client is built separately. See
[building the apworld](../docs/PYTHON-BUILD.md).

## Build method tested

This is a developer build record, not the finished player installation guide.
It requires a working 64-bit DDDK, its matching native DLLs, and installed game
content. The test used the existing repaired installation, not a new PC. Its
compiler reported version 6262, changelist 450718, built 1 July 2026.

Close the development game first. Use a separate Total Conversion with no player
saves, and back up any existing files before rebuilding. The compiler can remove
old script packages during a build. Do not use your normal
`DD1ArchipelagoCurrent` folder for these tests.

This was a full rebuild of an existing test conversion, not a verified setup
starting with an empty `Script` folder. The log confirms all 37 packages were
compiled and saved rather than only loaded from existing files.

The test conversion was named `DD1ArchipelagoOwnedAssets031`:

```text
TotalConversions/DD1ArchipelagoOwnedAssets031/
  Config/
  FullSource/
    Core/Classes/...
    Engine/Classes/...
    UDKGame/Classes/...
    ...all other installed source packages...
    DD1Archipelago/Classes/AP*.uc
  Script/
```

1. Copy the installed DDDK's entire `Development/Src` directory into `FullSource`.
   Use the current root source, not `TotalConversions/Template/Src`. Copying keeps
   generated compiler files away from the original installed source.
2. Copy this repository's seven `game/Classes/AP*.uc` files into
   `FullSource/DD1Archipelago/Classes`.
3. The test used the 0.3.1 release's `Config` folder. In `DefaultEngine.ini`,
   `UDKEngine.ini`, `DefaultGame.ini` and `UDKGame.ini`, replace references to
   `DD1ArchipelagoCurrent` with the test conversion name. In both Engine files,
   change the source directory from `APSrc` to `FullSource`.
4. Keep the engine's inherited `EditPackages` list and put `DD1Archipelago` after
   the game dependencies. Keep the Default UI and game-settings configs too;
   omitting these caused broken interface graphics in an earlier test.

Check these paths in both Engine configs (relative to `Binaries/Win64`):

```ini
[UnrealEd.EditorEngine]
EditPackagesInPath=..\..\TotalConversions\DD1ArchipelagoOwnedAssets031\FullSource
EditPackagesOutPath=..\..\TotalConversions\DD1ArchipelagoOwnedAssets031\Script
FRScriptOutputPath=..\..\TotalConversions\DD1ArchipelagoOwnedAssets031\ScriptFinalRelease

[Core.System]
ScriptPaths=..\..\TotalConversions\DD1ArchipelagoOwnedAssets031\Script
FRScriptPaths=..\..\TotalConversions\DD1ArchipelagoOwnedAssets031\ScriptFinalRelease
```

Do not replace the whole config with that excerpt. Keep the release's Local-only
settings, `APViewportClient` and `APGameInfo` activation, and installed content
paths. Do not add the whole cooked-content directory to ordinary package lookup;
that produced ambiguous-package errors in a rejected test.

From DDDK's `Binaries/Win64`, run:

```text
DunDefDevelopment.exe make -TOTALCONVERSION=DD1ArchipelagoOwnedAssets031 -full -unattended -nopause -forcelogflush
```

Output goes into the test conversion's `Script` folder. Check
`UDKGame/Logs/Launch.log` for the result. This compiles UnrealScript, not the
game executable or native DLLs. Do not publish the generated game dependencies
as if they were original mod files.

Keep this development folder separate from normal play. Leaving source files
in the configured build path can cause rebuild prompts when launching the game.

## What the rebuild showed

All 36 game dependencies and the AP package compiled and saved successfully:
0 errors, 0 warnings, 18.28 seconds.

- All seven AP source inputs matched the published files exactly.
- Every rebuilt game dependency matched its release counterpart outside the
  16-byte header region at offsets 69-84.
- The rebuilt AP package was also 95,969 bytes, but differed at those 16 header
  bytes and at offset 6056: `Main` in the release became `main` in a name entry.
  The header field's meaning has not been independently decoded. This is not a
  byte-identical build or proof of complete behavioural equivalence.
- The original released AP package loaded against the rebuilt dependencies.
  The menu and starting-items popup rendered correctly, and the game's AP bridge
  sent its greeting and heartbeat messages. A full gameplay test of this reduced
  setup is still needed.

The earlier statement that a complete script rebuild had not succeeded is now
out of date. A short fresh-PC installation procedure is still being tested.

## Files in the older download

The DLC-named `.u` files are game scripts included with the dependencies, not
complete maps or new AP features. Several are referenced by the game's startup
settings. The randomizer only supports the 12 original campaign maps.

Tests now show a route to generate these dependencies locally and omit bundled
game movies and images. That replacement is not a finished public release yet,
and these tests do not establish redistribution permission.

DDDK reverse-compilation has not been verified. These checks used the published
source, a rebuild and file comparisons, not recovered source from the release.
