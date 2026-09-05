# Security and behavior notes for version 0.3.1

This document describes the original Dungeon Defenders Archipelago integration code in this source release. It is intended to make its behavior reviewable. It is not an independent security audit, a certification, or a guarantee about the complete game, Development Kit, Archipelago installation, or compiled release files.

An `.apworld` contains executable Python code. Archipelago loads that code with the permissions of the account running Archipelago. Packaging a client inside an `.apworld`, rather than distributing a separate executable, does not remove the need to trust or review it.

## When code runs

Importing the world module defines its item, location, option, and generation logic and registers the **Dungeon Defenders Client** and **Dungeon Defenders YAML** launcher entries. In the original integration code, import alone does not search for an installation, start the game, open the local bridge, or switch save files. Seed generation runs the world-generation methods through Archipelago.

Selecting the client entry runs `Client.launch()`. It locates and validates an installed Development Kit and mod, then starts Archipelago's normal client interface. Connecting to an Archipelago slot initializes that slot's local state, selects its hero save, writes its unlock configuration, starts the local listener, and normally launches the game. The `--no-launch-game` option disables automatic game launching; it does not disable the client's other state and bridge operations.

Selecting the YAML entry opens a Save As dialog and writes the bundled template to the chosen `.yaml` or `.yml` file. The noninteractive `--output` option creates a new file and refuses an existing destination. Interactive replacement uses Archipelago's save dialog.

## Installation lookup and processes

`bridge/dd1_install.py` reads Steam's installation paths from the Windows registry, checks standard Steam installation locations, and reads Steam's `libraryfolders.vdf` and Development Kit app manifest. It checks only those candidate library paths; it does not recursively scan drives. An explicit `--dddk-root` selects a folder instead. This lookup reads the registry and installation files; it does not modify them.

Before initializing a slot, the client checks for the Development Kit executable, the mod's `DD1Archipelago.u` and `UDKGame.u` scripts, and activation settings in `DefaultEngine.ini`, `DefaultGame.ini`, `UDKEngine.ini`, and `UDKGame.ini`. These checks detect some incomplete installations. They are not signature checks, malware scans, or verification of every dependency's contents.

The client starts the selected installation's `Binaries/Win64/DunDefDevelopment.exe` with the fixed argument `-TOTALCONVERSION=DD1ArchipelagoCurrent`, using the executable's own directory as its working directory. It also runs Windows `tasklist` with fixed arguments to check whether `DunDefDevelopment.exe` is running before switching saves. These calls pass argument lists to `subprocess`; they do not build or invoke shell commands from server data. The `tasklist` name is resolved by the operating system, and the selected game's executable is an installed dependency, not authenticated by this code.

The client does not repair the installation or copy base-game files into the Development Kit. Installation and updates are manual. Development tools under `tools/` are separate programs for preparing or building the project and require their own review before execution.

## Network and local communication

The client uses Archipelago's `CommonClient` to connect to the server selected by the player. It receives slot information and items, sends completed location IDs and goal status, and displays normal Archipelago messages. Server authentication and transport behavior come from the installed Archipelago version and the selected server. This document does not certify those dependencies or servers.

The DD1-specific listener binds to `127.0.0.1:38282`. The game connects to that same loopback address. This listener is not bound to an external network interface. The client waits for a successful bind before automatically launching the game; a port conflict produces an error.

The game sends the fixed greeting `DD1HELLO1`. The client requires that greeting before recording a game connection and sending its current unlock snapshot. The initial greeting has a five-second timeout, and the Python listener has a line-buffer limit. Subsequent `DD1PING1` and `DD1PONG1` messages maintain the link. Unlock snapshots contain a sanitized seed/team/slot label, a revision, unlocked game content, and cumulative reward counters. Item-notification text is reduced to printable ASCII and limited in length before being sent to the game.

**The greeting is a protocol identifier, not authentication.** There is no secret, authenticated process identity, or cryptographic binding between the game and client. Another local process able to reach the listener can imitate a game connection and receive a snapshot. The game also trusts the process listening on that fixed local port. Another local process could interfere with that connection or imitate the client when it has control of the port. These are local trust and game-integrity limitations; a successful greeting does not prove which executable connected or that every reward was applied. The message “Game connected: Archipelago mod loaded.” reports that the expected greeting was received.

Game-to-client wave and victory reporting uses local event files, not authenticated network messages. `APEventBridge` uses the engine's `FileWriter` and engine-managed User directory to write and close one JSON file per event. The Python watcher reads matching event files in the two locations listed below. It validates the event shape and recognized map, wave, and difficulty, deduplicates checks, and submits only IDs present in the connected slot's location table. A local process with write access to those directories can forge event files; this is not an anti-cheat system.

The integration is designed for DD1 Local/standalone play. The UnrealScript bridge checks the standalone game mode. That scope is not a claim that the underlying Steam client, game executable, or Development Kit makes no network connections of its own.

## Files and saved data

In this table, `<DDDK>` is the selected Development Kit installation, `<TC>` is `<DDDK>/TotalConversions/DD1ArchipelagoCurrent`, and `<AP data>` is the location returned by Archipelago's `Utils.user_path`. The latter is determined by the user's Archipelago installation; it is not a fixed developer-specific path.

| Location | Direct integration behavior and purpose |
| --- | --- |
| `<TC>/Config/UDKDD1ArchipelagoUnlocks.ini` | The Python client creates or replaces the mod's unlock state, including unlocked heroes, defenses, abilities, maps, equipment permission, and designated level-six heroes. Writes use a temporary file followed by replacement. |
| `<AP data>/dd1_archipelago/<sanitized-seed>-team<number>-<sanitized-slot>.json` | The client stores slot identity, received item records, observed and pending checks, acknowledgements, goal state, and Summit settings. It maintains a `.bak` and temporary write file. |
| `<AP data>/dd1_archipelago/hero_saves/` | Stores per-seed/team/slot hero-save copies under hashed filenames, an initial `legacy-shared` backup where applicable, and active-profile and pending-switch JSON records. Temporary files and JSON backups may also be created here. |
| `<TC>/DunDefHeroes.dun` and `<TC>/DunDefHeroes.dun.bak` | The profile-switch operation copies, replaces, or removes this active TC save pair so the game uses the selected seed's heroes. This behavior is explained below. |
| `<TC>/Config/UDKDD1ArchipelagoRewards.ini` | The UnrealScript reward state uses the engine's `SaveConfig()` to persist the active reward identity and applied reward counters. |
| `<DDDK>/UDKGame/User` and `<TC>/User` | The watcher reads files matching `DD1ArchipelagoEvent*json` or `DD1ArchipelagoEvents*jsonl`. The engine creates the event files through `FileWriter`; its active User-directory behavior determines which location is used. |
| Player-selected YAML destination | The optional template-export tool writes the bundled YAML to the path chosen by the player. |

The underlying game and Archipelago can also create their normal logs, generated configuration, caches, and saves. The table describes paths directly handled by the original integration code; it is not a complete inventory of writes performed by those dependencies. Client logs can include installation paths, seed/slot labels, and gameplay information. Review diagnostic logs before sharing them publicly.

### Hero-save switching

Connecting to a different seed/team/slot can change the active TC save files without a separate confirmation dialog. This implements fresh characters per seed. `switch_hero_profile()` derives a filename key from SHA-256 of the identity and accepts only expected hash-shaped keys or the specific `legacy-shared` key when reading profile records.

When switching, the client copies the outgoing active save pair into its stored profile. When encountering a preexisting shared TC save for the first time, it preserves a legacy copy where one does not already exist. It then restores the destination profile's saved files. If a destination profile has no saved file yet, it removes the corresponding active TC file so the game starts fresh. A pending-switch record supports recovery if the operation is interrupted.

These precautions reduce accidental loss; they are not a guarantee against all failures. Save replacement and deletion are real operations, and recovery depends on the saved copies and filesystem being available. The client attempts to prevent switching seeds while a development-game process is running, but its process-name check and profile marker are not an operating-system lock or a security boundary. Do not delete the existing TC folder as an update procedure: it contains active saves and persistent reward state.

## Input validation and review limits

The original code sanitizes server-derived labels before using them in state filenames, validates supported unlock identifiers before writing the INI, checks numeric Summit settings, and validates stored item and location records. Server-provided game data is not used as a shell command or an arbitrary executable path. The DD1-specific state files and local unlock snapshots do not include the Archipelago password; authentication is delegated to `CommonClient`.

Validation is incomplete as a defense against hostile input. There is no comprehensive schema and size limit for every server slot-data value, event file, state file, or local connection. Malformed nested values can still raise exceptions, and large inputs or many files/connections can consume resources. Event files and local state are trusted for game progression once their supported shape passes validation; they are not signed or authenticated. The installation and save paths also rely on the local filesystem and its permissions, without comprehensive protection against another local process changing files, links, or directories during an operation.

Automated regression tests cover selected installation failures, protocol handling, state persistence, save switching, and progression behavior. Passing those tests does not establish that the project is free of vulnerabilities. This document does not certify native executable dependencies, compiled script packages, the game engine's behavior, archive provenance, or third-party Python packages. No independent security certification is claimed.

Reviewers can start with `apworld/dungeon_defenders/Client.py`, `bridge/dd1_install.py`, `bridge/dd1_protocol.py`, `bridge/dd1_bridge_service.py`, `bridge/dd1_event_watcher.py`, and the original classes under `game/Classes/`. This documentation describes the integration's behavior; it does not modify or grant rights to the game's assets or engine.
