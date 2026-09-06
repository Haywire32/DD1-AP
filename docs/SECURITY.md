# Security and file behavior

An `.apworld` runs Python code with the permissions of the account running
Archipelago. This project was developed with AI assistance. The notes below
describe what its own code does; they do not cover everything the game, DDDK or
Archipelago may do.

The client reads Steam's registry entries and registered library folders to find
DDDK. It does not scan entire drives or change Steam's settings. It checks the
mod's required files and configuration, but does not authenticate those files.
Version 0.3.2 also checks that four required native DLLs exist and are nonempty;
this detects common incomplete installs, not every possible dependency problem.
After connecting to a slot, it normally starts the installed
`DunDefDevelopment.exe` with `-TOTALCONVERSION=DD1ArchipelagoCurrent`.

The client connects to your chosen Archipelago server and opens
`127.0.0.1:38282` for the game. This local connection is unauthenticated: another
program on the same PC could imitate either side. “Game connected” means the
expected greeting arrived, not that the process's identity was verified. Local
event files can also be forged by programs with permission to write them.

Here, **TC** means `DDDK/TotalConversions/DD1ArchipelagoCurrent`. The integration
uses these files:

- `TC/Config/UDKDD1ArchipelagoUnlocks.ini`: the client replaces the current unlock
  state. The game records applied rewards in `UDKDD1ArchipelagoRewards.ini` beside it.
- Archipelago's user-data folder, under `dd1_archipelago`: item/check state, JSON
  backups and temporary files. Its `hero_saves` folder holds per-seed saves and
  profile-switch recovery records.
- `TC/DunDefHeroes.dun` and its `.bak`: the active character save pair.
- `DDDK/UDKGame/User` or `TC/User`: game-written check events read by the client.
- A location you choose: the optional YAML export.

Version 0.3.2 processes game events on the same event-loop thread as received
items. This removes the previous background-writer race that could replace new
item state with an older copy. It does not coordinate separate client processes;
run one DD1 client at a time.

Changing seed, team or slot switches the active TC character save **without a
separate prompt**. The client keeps the outgoing profile and preserves an initial
shared-save backup when applicable. It restores the selected profile, or deletes
the active save files when that profile has none, giving a new seed fresh
characters. Recovery records help interrupted switches; they cannot guarantee
recovery from every failure. Updates should merge files into the existing TC
folder, not delete that folder.

The code checks supported item/location identifiers, sanitizes filenames and
limits some message lengths. Validation is not comprehensive: malformed or large
inputs can still cause errors or consume resources. Regression tests cover
selected behavior; they are not an independent security audit. Review logs before
sharing them, since they can contain local paths and seed/slot information.
