# Building 0.5.0

Run `python tools/build_apworld.py` from this source folder to build
`dist/dungeon_defenders.apworld`. It does not install anything. The Python files
and bundled YAML are copied unchanged from this source.

Players use regular Steam DD1, with `-TOTALCONVERSION=DD1ArchipelagoCurrent`.
The game executable is not modified. The mod only supports Local play.

The game scripts were compiled and cooked using a compatible DDDK installation:

```
TotalConversions/DD1Features050/
  ProbeSource/DD1Archipelago/Classes/   game/Classes and game/BuildOnly
  Script/                             matching compiled dependencies
  Config/                             game/BuildConfig
```

From the development installation's Binaries/Win64 folder:

```
DunDefDevelopment.exe make -TOTALCONVERSION=DD1Features050 -unattended -nopause -forcelogflush
DunDefDevelopment.exe CookPackages DD1Archipelago -platform=PCConsole -TOTALCONVERSION=DD1Features050 -languageforcooking=INT -noloccooking -unattended -nopause -forcelogflush
```

Back up the build first. The compiler can remove compiled dependencies when
their source is absent. Restore those same dependencies before cooking, but
keep the newly compiled DD1Archipelago.u.

The AP scripts are in Startup_INT.upk. Ship its matching TC texture/shader caches
and the working stock dependencies. The player Config files are in release/Config;
they differ from the developer build paths. APRetailMenuProbe is an unused
build-only class retained here because it is present in the compiled package.
The release selects APViewportClient, not that probe.

The manifests record the source and release hashes. No executables, DLLs,
character saves or videos are included. Bundled game content remains third-party
content; this is not a claim that every stock dependency can be rebuilt from
the current DDDK source alone.
