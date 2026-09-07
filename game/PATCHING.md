# Building 0.4.0

The Python world/client is built separately from the game mod. Run
`python tools/build_apworld.py` from this source checkout. It creates
`dist/dungeon_defenders.apworld` without installing anything. The packaged Python
files and YAML are exact copies of this source.

The game uses regular DD1's unmodified 64-bit executable with
`-TOTALCONVERSION=DD1ArchipelagoCurrent`. Only Local mode is supported.
DDDK is used by developers to compile/cook the mod, not by players to run it.

The tested development TC was named `DD1RetailFull040`. Its layout was:

```
TotalConversions/DD1RetailFull040/
  ProbeSource/DD1Archipelago/Classes/   files from game/Classes
  Script/                             matching compiled game dependencies
  Config/                             TC build configuration
```

The build also contained `game/BuildOnly/APRetailMenuProbe.uc`, an unused
diagnostic subclass. It is included here because it was compiled into the
tested package. The release selects APViewportClient, not that diagnostic.

From the compatible development installation's Binaries/Win64 folder:

```
DunDefDevelopment.exe make -TOTALCONVERSION=DD1RetailFull040 -unattended -nopause -forcelogflush
DunDefDevelopment.exe CookPackages DD1Archipelago -platform=PCConsole -TOTALCONVERSION=DD1RetailFull040 -languageforcooking=INT -noloccooking -unattended -nopause -forcelogflush
```

The build INIs point EditPackagesInPath at ProbeSource, outputs at Script, and
include DD1Archipelago in EditPackages, NonNativePackages and startup packages.
Use a backed-up development TC: `make` can remove precompiled dependency
packages whose source is absent. Restore the same dependencies before cooking,
without replacing the newly compiled DD1Archipelago.u.

The AP code is inside the cooked Startup_INT.upk. Its matching TC texture and
shader caches are included for correct graphics. Other cooked dependencies
come from the regular game. No executable, DLL, save or video is in this release.
Game content remains third-party content, not newly authored AP source.

The release manifest lists file hashes. The AP class sources were compared with
the compilation inputs. This is not a claim that every bundled game dependency
can be rebuilt byte-for-byte from the current Steam DDDK source alone.
