# Game source and base-package dependencies

The current 0.3.1 integration uses the seven `AP*.uc` classes in the separate
`DD1Archipelago` UnrealScript package. These classes extend the existing DD1
classes. The current AP sources do **not** require the historical
`ConfigureArchipelagoHeroGate` patch to `DunDefHeroManager`.

Hero selection is controlled by `APViewportClient`. During Local play,
`APGameInfo.ConfigureHeroOwnership()` starts a repeating
`CorrectLockedActiveHeroes()` check. That check uses the game's existing hero
manager API to switch a locked active class to an owned hero. This is the current
implementation; the older direct hero-manager patch is not part of this source
release or its build procedure.

## Historical experiments that are not build inputs

An early experiment added `ConfigureArchipelagoHeroGate`,
`IsArchipelagoHeroAllowed`, and `bArchipelagoHeroGateEnabled` to DD1's
`DunDefHeroManager` source. That experiment was reverted when rebuilding the
distributed base source proved incompatible with the working native package set.
The `patch-hero-manager.ps1` and `unpatch-hero-manager.ps1` development scripts
therefore must not be applied when building this version.

A separate early experiment copied the complete `DunDefGameReplicationInfo.uc`
class and added two event-log hooks. That copied class is also obsolete. The
current event hooks are implemented in the original `APGameReplicationInfo`
subclass instead. Neither complete base-game source file is included here.

## Checks performed for this source publication

The following checks were performed against the 0.3.1 release on 2026-09-05:

- None of the seven current AP source files references the old hero-gate API.
- Neither released `DD1Archipelago.u` nor released `UDKGame.u` contains the three
  old hero-gate symbol names in an ASCII/UTF-16 string scan. The AP package does
  contain the current `ConfigureHeroOwnership` and `CorrectLockedActiveHeroes`
  names. A string scan is supporting evidence, not a decompilation or complete
  binary equivalence proof.
- The development backup's `DunDefHeroManager.uc` and the fresh installed source
  have no AP additions; a text comparison differs only in two trailing blank
  lines.
- Released `UDKGame.u` is byte-identical to the preserved, working root dependency
  package used by the AP compiler. Its SHA-256 is
  `F9066F487F7030919CFE693E408A7003E21096A24B939596C9D1D503B6B08670`.

These checks support publishing the separate AP sources without a base-game
source patch. They do not establish the full provenance of every third-party
runtime package or provide a license for redistributing those packages.

## Building the separate AP package

This is developer information, not an installation step for players.

The working compilation procedure requires a compatible DD1 development
executable, its matching compiled base packages, and the player's installed game
assets. The AP source tree is placed under a development-only Total Conversion
source directory, with this layout:

```text
TotalConversions/DD1ArchipelagoCurrent/
  APSrc/DD1Archipelago/Classes/AP*.uc
  Script/                       matching precompiled dependencies
  Config/                       AP Total Conversion configuration
```

The engine configuration must point `EditPackagesInPath` to that TC's `APSrc`,
`EditPackagesOutPath` and `ScriptPaths` to its `Script`, and include
`DD1Archipelago` in `EditPackages`. The persistent `DefaultEngine.ini` and
`DefaultGame.ini` overrides also select `APViewportClient` and `APGameInfo`; these
activation settings must survive generated-INI updates.

The command used with the known-working development installation was:

```text
DunDefDevelopment.exe make -TOTALCONVERSION=DD1ArchipelagoCurrent -unattended -nopause -forcelogflush
```

Run it from that installation's `Binaries/Win64` directory, using a backed-up,
isolated development TC. Preserve its matching compiled dependencies before
running `make`: the compiler has removed dependency packages when their source
was absent from the TC. Restore those same dependencies afterward while keeping
the newly built `DD1Archipelago.u`. Exclude or move the AP source directory away
from the configured source path for normal play to avoid the development
recompile prompt.

## Reproducibility limit

The AP package has been compiled successfully using an existing compatible
dependency set. A complete, byte-identical build of all game/runtime packages
from a fresh current Steam DDDK source installation has **not** been verified.
Earlier attempts to rebuild the entire base source failed, and those sources do
not exactly match the working native/precompiled set.

Accordingly, these are the current original AP sources and configuration
overrides, not a claim that this repository alone rebuilds every binary in the
previous full runtime download. A reproducible process for obtaining the game's
required dependencies from the user's own installation remains separate work.
