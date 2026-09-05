# Contents and third-party boundaries

This source snapshot was selected by an explicit file list, not by copying a
complete game installation, development workspace, or runtime ZIP.

## Included

- The five world/client Python modules and five `dd1_*.py` support modules used
  in the 0.3.1 `.apworld`, plus its manifest and public YAML resource.
- Six Python test modules. Test inputs are artificial fixtures, not exported
  player saves, real seed files, or captured gameplay logs.
- The seven current AP UnrealScript classes, which depend on DD1's existing
  classes and APIs.
- Five small AP-specific default/configuration files. Blank reward and unlock
  files describe initial state, not a played seed's progress.
- The existing public installation and update text, preserved for context.
- New review/build documentation and a source-only Python archive builder.

`SOURCE-MANIFEST.json` records file hashes and the reference runtime identifiers.
The Python and YAML payload can be rebuilt and compared without installing or
running it. The original runtime archive's ZIP timestamps/compression differ
from the source builder's fixed metadata; the relevant comparison is each
archived file's content, not only the outer archive hash.

## Deliberately excluded

- The movies and splash artwork from the earlier runtime package.
- `Core.u`, `Engine.u`, `UDKGame.u`, `DD1Archipelago.u`, and all other compiled
  packages, executables, DLLs, game assets, and complete generated game configs.
- The DDDK's full engine/game source and obsolete copies of base classes from
  development experiments.
- Downloaded third-party guides, other applications' source/runtime files,
  development backups, personal paths/settings, logs, seed outputs, and saves.
- The old installer/deployment scripts that depended on a developer's private
  machine layout. They are not required to read the implementation. The portable
  Python build tool and the documented UnrealScript compilation procedure are
  supplied instead.

## Dependency and rights boundary

The Python integration imports Archipelago APIs. Archipelago must be obtained
separately, and its own license/requirements still apply. This repository does
not bundle Archipelago's runtime or source.

The UnrealScript integration extends Dungeon Defenders classes and requires the
DDDK and compatible precompiled dependencies. Those dependencies must be
obtained separately through the applicable authorized distribution. No complete
base-game rebuild, permission to redistribute each dependency, or removal of
the earlier runtime's asset-distribution concerns is claimed here.

The official DDDK page describes asset use and Total Conversion distribution:
[Dungeon Defenders Development Kit on Steam](https://store.steampowered.com/app/202522/Dungeon_Defenders_Development_Kit_Free_DLC/).
That information is relevant context, not an item-by-item license clearance
for the previous runtime download. The repository author has not selected a
new blanket reuse license for this source-publication draft.
