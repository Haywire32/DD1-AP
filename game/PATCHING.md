# Game build

Use a separate, compatible DDDK installation with matching script dependencies.

Under `TotalConversions/DD1ArchipelagoCurrent/`, copy:

- `game/Classes/*.uc` and `game/BuildOnly/*.uc` to `ProbeSource/DD1Archipelago/Classes/`.
- `game/BuildConfig/*.ini` to `Config/`.
- Matching compiled dependencies to `Script/`.

Copy `game/Assets/APLogoNative.upk` to `UDKGame/Content/`.

From `Binaries/Win64/`:

```text
DunDefDevelopment.exe make -TOTALCONVERSION=DD1ArchipelagoCurrent
DunDefDevelopment.exe CookPackages DD1Archipelago -platform=PCConsole -TOTALCONVERSION=DD1ArchipelagoCurrent -languageforcooking=INT -noloccooking
```

Back up dependencies before compiling. If the compiler removes them, restore
those dependencies before cooking, keeping the new `DD1Archipelago.u`.

Package from a matching release ZIP and the new cooked output:

```text
python tools/build_conversion.py baseline.zip output.zip --cooked path/to/CookedPCConsole
```

This replaces the mod scripts, texture cache and default configuration while
preserving the baseline's other game assets. It excludes saves and generated INIs.
Retail dependencies cannot all be rebuilt from the public DDDK alone.
