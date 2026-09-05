# Source snapshot validation

Prepared for review on 2026-09-05 against the DD1 Archipelago 0.3.1 implementation.

## Scope

The ten production Python modules and public YAML are unchanged from the
reference 0.3.1 `.apworld` contents. The seven game-source files are unchanged
from the current development source. Tests and public installation text are
included, rather than rewritten to hide the existing implementation.

The new source builder reads only this checkout and writes the requested
`.apworld` output. It does not search for an installation, contact a server,
launch the game, or install its output.

## Checks for this prepared folder

- Run all six test modules: 50 Python tests.
- Rebuild the `.apworld` from this folder using the supplied builder.
- Compare every non-directory archive entry byte-for-byte with the reference
  0.3.1 `.apworld`.
- Check that repeated source builds produce the same archive bytes, and that
  replacing an existing output requires explicit `--overwrite`.
- Audit the exact source-folder inventory: readable code, configuration, test,
  metadata, and documentation files only; no game media, compiled packages,
  executables, archives, logs, seed outputs, or saves.

`SOURCE-MANIFEST.json` provides the completed-check summary and source hashes.

## Earlier runtime verification, not repeated by publishing source

The existing 0.3.1 runtime was tested with actual native INI regeneration and
then launched in an isolated Total Conversion. The game's log showed AP class
initialization, and a localhost test received its greeting and heartbeat.
The Python templates were also exercised in an isolated Archipelago 0.6.7
runtime and used to generate a seed.

These checks do not establish that the runtime is safe on every machine,
that every file in the old full ZIP may be redistributed, or that the native
packages can all be reproduced from current Steam source. This publication does
not repeat a full game build or a complete gameplay seed.

Automated tests are regression checks, not an independent security audit. Some
tests stub the Archipelago/UI/network boundary. The opening-selection test
executes selected statements from the repository's own trusted Python source;
it does not prove safety for arbitrary downloaded code or hostile server input.
