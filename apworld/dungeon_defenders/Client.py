"""Archipelago client for the regular-DD1 Local-only Total Conversion."""

from __future__ import annotations

import argparse
import configparser
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import CommonClient
import Utils
from CommonClient import CommonContext, get_base_parser, gui_enabled, server_loop
from NetUtils import ClientStatus

from .dd1_ap_adapter import ingest_received_packet, reconcile_locations
from .dd1_mana import ingest_mana_packet, mana_reward_units
from .dd1_bridge_service import live_seed_identity
from .dd1_events050 import read_pending_event_journal, receive_live_event, recover_victories
from .dd1_shop import SHOP_BASE, SHOP_COUNT, LEGACY_SHOP_COUNT, shop_count, completed_maps
from .dd1_cosmetic_rewards import cosmetic_totals
from .dd1_content import ContentSettings, XP_REWARDS, MANA_REWARDS, PROGRESSIVE_DIFFICULTY, AREA_ITEMS, BUILD_TIME_ITEM
from .dd1_content import DEFENSE_UNITS_ITEM, SURVIVAL_START_ITEM
from .dd1_content import SLOT_DATA_VERSION, SUPPORTED_SLOT_DATA_VERSIONS
from .dd1_install import select_retail_root, validate_retail_install, verify_conversion_package, RETAIL_LAUNCH_FLAGS
from .dd1_campaign import enabled_maps, cd_unlocked, CD_TAG, eternia_shard_display_mask
from .dd1_hero_skins import unlocked_skin_keys
from .dd1_deathlink import DeathLinkBridge
from .dd1_traps import trap_snapshot
from .dd1_themes import theme_snapshot, theme_mask
from .items import DEFENSE_ITEMS, ITEM_ID_TO_UNLOCK, ITEM_NAME_TO_ID, MANA_FILLER_ITEM, XP_FILLER_ITEM
from .heroes import DEFAULT_HERO_KEYS, validate_roster, is_starting_defense
from .chaos_loadouts import validate_slot_mapping, recipient_item_names
from .runtime_profile import PRIVATE_CHAOS_BUILD, TC_DIRECTORY, STATE_DIRECTORY, LIVE_BRIDGE_PORT, CLIENT_TITLE
from .dd1_protocol import (
    CAMPAIGN_MAPS,
    ProtocolError,
    atomic_write_json,
    bind_slot_identity,
    empty_bridge_state,
    load_bridge_state,
    recover_observed_victories,
    summit_is_unlocked,
    summit_settings,
    switch_hero_profile,
    write_unlock_ini,
)


GAME_NAME = "Dungeon Defenders"
LIVE_BRIDGE_HOST = "127.0.0.1"
GAME_CONNECT_TIMEOUT = 60.0
GAME_HANDSHAKE_TIMEOUT = 5.0
UNLOCK_RETRY_INTERVAL = 2.0
logger = logging.getLogger("DungeonDefendersClient")


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "unnamed"


class DungeonDefendersContext(CommonContext):
    game = GAME_NAME
    items_handling = 0b111
    want_slot_data = True

    def make_gui(self):
        class DungeonDefendersManager(super().make_gui()):
            base_title = CLIENT_TITLE

        return DungeonDefendersManager

    def __init__(
        self,
        server_address: Optional[str],
        password: Optional[str],
        game_root: Path,
        launch_game: bool,
    ) -> None:
        super().__init__(server_address, password)
        self.game_root = game_root
        self.launch_game = launch_game
        self.launched_game: Optional[subprocess.Popen] = None
        self.seed_name: Optional[str] = None
        self.state_path: Optional[Path] = None
        self.poll_task: Optional[asyncio.Task] = None
        self.slot_data: dict = {}
        self.death_bridge = None
        self._seen_deathlinks = []
        self.live_server: Optional[asyncio.AbstractServer] = None
        self.live_clients: set[asyncio.StreamWriter] = set()
        self.live_snapshot: Optional[str] = None
        self.startup_task: Optional[asyncio.Task] = None
        self.game_watch_task: Optional[asyncio.Task] = None
        self.reverse_task: Optional[asyncio.Task] = None
        self.game_connected_once = False
        self._steam_launch_wrapper = False
        try:
            self.io_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            self.io_loop = None
        self.io_thread = threading.get_ident()
        self.last_state_ack = -1
        self.unlock_write_pending = False
        self.unlock_write_error: Optional[str] = None
        self.unlock_retry_at = 0.0
        self._rejected_journal_events: set[str] = set()
        self._diagnostic(f"CLIENT_START version=0.8.1 platform={sys.platform} game_root={self.game_root}")

    def _diagnostic(self, message: str) -> None:
        """Small cross-platform trace with no server address, password, or item names."""
        try:
            path = self.game_root / "TotalConversions" / TC_DIRECTORY / "Config" / "DD1ArchipelagoLive.log"
            if not path.parent.is_dir():
                return
            if path.exists() and path.stat().st_size > 512_000:
                path.write_text("", encoding="utf-8")
            with path.open("a", encoding="utf-8") as stream:
                stream.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
        except OSError:
            pass

    def _schedule_task(self, coroutine, *, name=None):
        """Schedule Kivy/network callbacks safely even when invoked off the asyncio thread."""
        loop = self.io_loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
                self.io_loop = loop
                self.io_thread = threading.get_ident()
            except RuntimeError:
                coroutine.close()
                logger.error("Could not schedule DD1 live update: the client event loop is unavailable.")
                return None
        if loop.is_closed():
            coroutine.close()
            return None
        if threading.get_ident() == self.io_thread:
            return loop.create_task(coroutine, name=name)
        return asyncio.run_coroutine_threadsafe(coroutine, loop)

    @property
    def game_executable(self) -> Path:
        return self.game_root / "Binaries" / "Win64" / "DunDefGame.exe"

    def _launch_local_game(self) -> None:
        if not self.launch_game:
            return
        if self.launched_game is not None and self.launched_game.poll() is None:
            logger.info("Dungeon Defenders is already running from this client.")
            return
        try:
            validate_retail_install(self.game_root, tc_directory=TC_DIRECTORY)
            package_status = verify_conversion_package(self.game_root, tc_directory=TC_DIRECTORY)
        except (OSError, ValueError) as error:
            self._diagnostic(f'STARTUP_PREFLIGHT failed: {error}')
            raise
        self._diagnostic(f'STARTUP_PREFLIGHT ok; {package_status}; launch_language=INT')
        executable = self.game_executable
        starting_hero = self.slot_data.get("starting_hero", "unknown")
        starting_map = self.slot_data.get("starting_map", "unknown")
        experience_multiplier = self.slot_data.get("experience_multiplier", 1)
        logger.warning(
            "STARTING HERO: %s    |    STARTING MAP: %s    |    EXPERIENCE: x%s",
            str(starting_hero).replace("_", " ").title(),
            next(
                (entry.name for entry in CAMPAIGN_MAPS if entry.tag == starting_map),
                starting_map,
            ),
            experience_multiplier,
        )
        if sys.platform.startswith("linux"):
            steam = shutil.which("steam")
            if steam:
                command = [steam, "-applaunch", "65800"]
            else:
                flatpak = shutil.which("flatpak")
                if not flatpak:
                    raise ProtocolError("Steam could not be found. Start Steam, or launch DD1 with the AP Total Conversion manually.")
                command = [flatpak, "run", "com.valvesoftware.Steam", "-applaunch", "65800"]
            command += [f"-TOTALCONVERSION={TC_DIRECTORY}", *RETAIL_LAUNCH_FLAGS, "-MULTIHOME=127.0.0.1"]
            self.launched_game = subprocess.Popen(command, cwd=self.game_root)
            self._steam_launch_wrapper = True
        else:
            # Windows invokes the trusted installed executable directly.
            game_log = self.unlock_path.parent / time.strftime('DD1ArchipelagoGame-%Y%m%d-%H%M%S.log')
            self._requested_game_log = game_log
            self.launched_game = subprocess.Popen(
                [str(executable), f"-TOTALCONVERSION={TC_DIRECTORY}", *RETAIL_LAUNCH_FLAGS,
                 "-log", "-forcelogflush", f"-ABSLOG={game_log}"],
                cwd=executable.parent,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            self._steam_launch_wrapper = False
            self._diagnostic(f"GAME_LOG requested={game_log}")
            logger.info('Requested DD1 game log: %s', game_log)
        self._diagnostic(f"GAME_LAUNCH steam_wrapper={int(self._steam_launch_wrapper)}")
        logger.info(
            "Started Dungeon Defenders with the AP mod selected (process %d). "
            "Waiting for the game to confirm that the mod loaded.",
            self.launched_game.pid,
        )

    async def _finish_slot_startup(self) -> None:
        try:
            # A second client must not launch a game into the first client's
            # listener. Wait for a successful bind before launching anything.
            await self._start_live_bridge()
            if sys.platform.startswith('linux') and (self.reverse_task is None or self.reverse_task.done()):
                self.reverse_task = asyncio.create_task(self._connect_reverse_game(), name='DD1 reverse connection')
            self.death_bridge = DeathLinkBridge(self.unlock_path.parent,
                self._live_seed_identity(), bool(self.slot_data.get('death_link', False)),
                self.slot_data.get('death_link_mode', 'hero_death'))
            self.death_bridge.write(True, force=True)
            await self.update_death_link(self.death_bridge.enabled)
            await self._reconcile_checks()
            self._launch_local_game()
        except (OSError, ProtocolError, ValueError) as error:
            logger.error("Cannot start the DD1 game connection: %s", error)
            await self.disconnect()
            return
        if self.poll_task is None or self.poll_task.done():
            self.poll_task = asyncio.create_task(
                self._poll_game_events(), name="DD1 durable check retries"
            )
        if self.game_watch_task is not None:
            self.game_watch_task.cancel()
        self.game_watch_task = asyncio.create_task(
            self._watch_game_connection(), name="DD1 game connection status"
        )

    async def _watch_game_connection(self) -> None:
        deadline = time.monotonic() + GAME_CONNECT_TIMEOUT
        warned = False
        while not self.exit_event.is_set():
            if self.launched_game is not None:
                result = self.launched_game.poll()
                if result is not None and not self._steam_launch_wrapper:
                    self._diagnostic(f'GAME_EXIT code={result} hex=0x{result & 0xffffffff:08X} connected={int(self.game_connected_once)}')
                    if self.game_connected_once:
                        logger.info("Dungeon Defenders closed (exit code %s).", result)
                    else:
                        logger.error(
                            "Dungeon Defenders closed before the AP mod connected (exit code %s). "
                            "The Archipelago server connection does not mean the game mod loaded. "
                            "Check any game error message and the mod installation.", result,
                        )
                        game_log = getattr(self, '_requested_game_log', None)
                        if game_log is not None:
                            logger.error('Requested game log: %s (exists: %s). If missing, the game may have exited before logging started.',
                                         game_log, game_log.is_file())
                    return
            if not self.game_connected_once and not warned and time.monotonic() >= deadline:
                warned = True
                logger.warning(
                    "The DD1 mod has not connected after %d seconds. "
                    "If the game is still loading, wait for loading to finish. "
                    "If the menu or game has loaded without AP restrictions, close the game "
                    f"and merge {TC_DIRECTORY} from the matching package over your installed mod. "
                    "Archipelago items are saved in the client, but delivery to the game is unconfirmed.",
                    GAME_CONNECT_TIMEOUT,
                )
            await asyncio.sleep(1.0)

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_deathlink(self, data: dict) -> None:
        event = (data.get('source'), data.get('time'))
        if event in self._seen_deathlinks or data.get('source') == self.player_names.get(self.slot):
            return
        self._seen_deathlinks.append(event)
        del self._seen_deathlinks[:-128]
        super().on_deathlink(data)
        if self.death_bridge is not None:
            try:
                if self.death_bridge.receive(live_connected=bool(self.live_clients)):
                    self._diagnostic(f'DEATHLINK received=1 sequence={self.death_bridge.incoming}')
                    self._schedule_task(self._broadcast_deathlink())
                else:
                    logger.info('DeathLink ignored: disabled or no current game connection/status.')
                    self._diagnostic('DEATHLINK received=1 ignored=disabled_or_stale')
            except (OSError, ValueError) as error:
                logger.error('Could not deliver DeathLink: %s', error)

    async def _broadcast_deathlink(self) -> None:
        """Deliver immediately; the game validates its current state and ACKs.

        Do not depend on a config-file write or the next game heartbeat. The
        heartbeat still retransmits the sequence, and the engine deduplicates.
        """
        if self.death_bridge is None:
            return
        packet = self.death_bridge.snapshot(bool(self.server and self.server.socket))
        for writer in tuple(self.live_clients):
            try:
                writer.write(packet)
                await writer.drain()
            except (ConnectionError, OSError):
                self.live_clients.discard(writer)
                writer.close()

    def _select_slot_state(self, slot_data: dict) -> None:
        if not self.seed_name:
            raise ProtocolError("server did not provide a seed name")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        version = slot_data.get("dd1_slot_data_version", 1)
        if type(version) is not int or version not in SUPPORTED_SLOT_DATA_VERSIONS:
            raise ProtocolError(
                f"Unsupported DD1 slot-data version {version!r}; this client generates version {SLOT_DATA_VERSION}. "
                "Install the matching APWorld and generate a new seed."
            )
        catch_up = slot_data.get("level_catch_up_multiplier", 1)
        if isinstance(catch_up, bool) or catch_up not in {1, 2, 4, 6, 8, 10}:
            raise ProtocolError("The level catch-up multiplier must be off or 2, 4, 6, 8, or 10.")
        ContentSettings.from_slot_data(slot_data)
        self._active_heroes(slot_data)
        try:
            validate_slot_mapping(slot_data, self.slot)
        except (ValueError, KeyError, TypeError) as error:
            raise ProtocolError(f'Invalid randomized loadout: {error}') from error
        filename = (
            f"{safe_filename(self.seed_name)}-team{self.team}-"
            f"{safe_filename(slot_name)}.json"
        )
        self.state_path = Path(Utils.user_path(STATE_DIRECTORY, filename))
        state = load_bridge_state(self.state_path)
        bind_slot_identity(
            state,
            seed_name=self.seed_name,
            slot=slot_name,
            team=self.team,
            slot_data_version=version,
        )
        token = (slot_data.get('chaos_loadout') or {}).get('seed')
        if 'chaos_mapping_token' in state and state['chaos_mapping_token'] != token:
            raise ProtocolError('The randomized loadout changed for an existing seed/slot. No save was changed.')
        if token is not None:
            state['chaos_mapping_token'] = token
        state["summit_settings"] = summit_settings(slot_data)
        state["content_settings"] = ContentSettings.from_slot_data(slot_data).slot_data()
        # Retail completion events are explicitly seed-bound. Never import
        # older, unbound DDDK event files into a regular-DD1 seed.
        atomic_write_json(self.state_path, state)
        logger.info("Using durable DD1 state: %s", self.state_path)

    def _activate_seed_hero_save(self) -> None:
        if not self.seed_name:
            raise ProtocolError("cannot select a hero save without seed identity")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        identity = f"{self.seed_name}|team{self.team}|{slot_name}"
        tc_root = self.game_root / "TotalConversions" / TC_DIRECTORY
        install_key = hashlib.sha256(str(tc_root.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
        profiles_root = Path(Utils.user_path(STATE_DIRECTORY, "retail_hero_saves", install_key))
        expected_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        if sys.platform.startswith("linux"):
            process_check = subprocess.run(
                ["ps", "-eo", "args="], capture_output=True, text=True, errors="replace", check=False,
            )
            process_label = "Linux"
        else:
            process_check = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq DunDefGame.exe", "/NH"],
                capture_output=True, text=True, errors="replace", check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            process_label = "Windows"
        if process_check.returncode != 0:
            detail = " ".join((process_check.stderr or process_check.stdout or "no details").split())[:240]
            raise ProtocolError(
                "Cannot check whether Dungeon Defenders is running, so no hero save was switched. "
                "Close any running DD1 game and try again. "
                f"{process_label} reported: {detail}"
            )
        # A few Windows setups return a successful task-list result with no
        # stdout object.  Treat that like an empty result instead of crashing
        # with "NoneType has no attribute casefold" while connecting.
        process_output = process_check.stdout or ""
        if process_check.stdout is None:
            logger.warning("%s process check returned no text; continuing with DD1 treated as closed.", process_label)
        if "dundefgame.exe" in process_output.casefold():
            marker = profiles_root / "active_profile.json"
            try:
                active = json.loads(marker.read_text(encoding="utf-8")).get("active")
            except (OSError, ValueError, AttributeError):
                active = None
            if active != expected_key:
                raise ProtocolError(
                    "Dungeon Defenders is already running; close it before changing AP seeds"
                )
            logger.info("The correct per-seed DD1 hero profile is already active.")
            return
        key = switch_hero_profile(tc_root, profiles_root, identity)
        logger.info("Activated fresh per-seed DD1 hero profile %s.", key)

    @property
    def unlock_path(self) -> Path:
        return (
            self.game_root
            / "TotalConversions"
            / TC_DIRECTORY
            / "Config"
            / "UDKDD1ArchipelagoUnlocks.ini"
        )

    @staticmethod
    def _snapshot_field(values: set[str]) -> str:
        # UnrealScript drops empty delimited fields, which would shift the
        # APSTATE envelope. A dash is an explicit empty sentinel.
        return ",".join(sorted(values)) if values else "-"

    @staticmethod
    def _active_heroes(slot_data: dict) -> tuple[str, ...]:
        if slot_data.get("dd1_slot_data_version", 1) < 2:
            return DEFAULT_HERO_KEYS
        if not isinstance(slot_data.get("active_heroes"), list):
            raise ProtocolError("This seed is missing its active hero roster.")
        roster = validate_roster(slot_data["active_heroes"])
        if slot_data.get("starting_hero") not in roster:
            raise ProtocolError("The starting hero is not in this seed's active roster.")
        early = slot_data.get("level_six_heroes", [])
        if not isinstance(early, list) or any(hero not in roster for hero in early):
            raise ProtocolError("The level-six heroes do not match this seed's roster.")
        minion = slot_data.get("starting_minion")
        if slot_data.get('chaos_loadout') is not None and minion is not None:
            try:
                document = slot_data['chaos_loadout']
                assignments = validate_slot_mapping(slot_data, document['player'])
                valid = slot_data['starting_hero'] == 'summoner' and any(
                    a.item == minion and a.recipient == 'summoner'
                    and a.item in DEFENSE_ITEMS and is_starting_defense(a.definition)
                    for a in assignments)
            except (ValueError, KeyError, TypeError) as error:
                raise ProtocolError('Invalid randomized starting defense.') from error
            if not valid:
                raise ProtocolError('Invalid randomized starting defense.')
        elif minion is not None and (
            slot_data["starting_hero"] != "summoner" or minion not in {
                "Archer Minion (Summoner)", "Spider Minion (Summoner)", "Orc Minion (Summoner)"
            }
        ):
            raise ProtocolError("Invalid starting Summoner minion.")
        if slot_data["starting_hero"] == "summoner" and minion is None:
            raise ProtocolError("A starting Summoner needs its starting minion.")
        return roster

    def _live_seed_identity(self) -> str:
        if not self.seed_name:
            raise ProtocolError("cannot create live snapshot without seed identity")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        return live_seed_identity(self.seed_name, self.team, slot_name)

    def _make_live_snapshot(
        self, revision: int, unlocked: dict[str, set[str]], xp_rewards: int, mana_rewards: int
    ) -> str:
        fields = (
            "APSTATE11",
            self._live_seed_identity(),
            str(revision),
            self._snapshot_field(unlocked["heroes"]),
            self._snapshot_field(unlocked["defenses"]),
            self._snapshot_field(unlocked["abilities"]),
            self._snapshot_field(unlocked["maps"]),
            "19",
            str(xp_rewards),
            str(mana_rewards),
            self._snapshot_field(set(self._active_heroes(self.slot_data))),
            str(self.slot_data.get("experience_multiplier", 1)),
            str(self.slot_data.get("level_catch_up_multiplier", 1)),
            self._snapshot_field(set(self.slot_data.get("level_six_heroes", []))),
            str(self.difficulty_mask),
            str(self.mode_mask),
            str(self.slot_data['starting_crystal_roll']),
            str(self.build_time_seconds),
            str(self.gear_rewards),
            str(self.crystal_skin_mask),
            str(self.defense_units_bonus),
            str(self.survival_start_wave),
            self._snapshot_field(self.active_map_tags),
            str(self.hero_skin_mode),
            self._snapshot_field(self.hero_skin_keys),
        )
        if validate_slot_mapping(self.slot_data, self.slot):
            fields = ('APSTATE12', *fields[1:], self.slot_data['chaos_loadout']['seed'])
        return "|".join(fields) + "\r\n"

    def _gear_settings_snapshot(self) -> bytes:
        return (f"APGEAR1|{self._live_seed_identity()}|"
                f"{int(self.slot_data.get('random_gear_pets', False))}\r\n").encode('ascii')

    def _chaos_display_names(self) -> dict[str, str]:
        if not self.slot_data.get('chaos_loadout'):
            return {}
        return recipient_item_names(validate_slot_mapping(self.slot_data, self.slot))

    def _item_display_name(self, item_id: int, receiver: int) -> str:
        original = self.item_names.lookup_in_slot(item_id, receiver)
        # Never project our loadout onto another player's same-game items.
        if receiver != self.slot:
            return original
        return self._chaos_display_names().get(original, original)

    def on_print_json(self, args: dict):
        # AP prints before on_package. Change a COPY of display nodes only;
        # packets, data-package tables and received-item identities stay intact.
        names = self._chaos_display_names()
        data = []
        for original in args.get('data', []):
            node = dict(original)
            if node.get('type') == 'item_id' and node.get('player') == self.slot:
                try:
                    item_name = self.item_names.lookup_in_slot(int(node['text']), self.slot)
                except (ValueError, TypeError, KeyError):
                    item_name = None
                if item_name in names:
                    node.update(type='item_name', text=names[item_name])
            data.append(node)
        super().on_print_json({**args, 'data': data})

    def _shard_display_snapshot(self) -> bytes:
        # Separate optional message keeps the existing gameplay protocol intact.
        return (f"APSHARDS1|{self._live_seed_identity()}|"
                f"{getattr(self, 'eternia_shard_mask', -1)}\r\n").encode('ascii')

    def _snapshot_packets(self) -> list[bytes]:
        if self.live_snapshot is None:
            return []
        packets = [self.live_snapshot.encode("ascii"), self._shard_display_snapshot(), self._gear_settings_snapshot()]
        if self.state_path is not None:
            state = load_bridge_state(self.state_path)
            packets.append(trap_snapshot(self._live_seed_identity(), state['received_items'], ITEM_NAME_TO_ID))
            packets.append(theme_snapshot(self._live_seed_identity(), self.slot_data.get('tavern_themes', False),
                state['received_items'], ITEM_NAME_TO_ID))
            bought = set(self.checked_locations)
            bought.update(v['prototype_location_id'] for v in state['observed_locations'].values())
            count = shop_count(self.slot_data)
            mask = sum(1 << i for i in range(LEGACY_SHOP_COUNT) if SHOP_BASE + i in bought)
            cleared = completed_maps(state.get('victory_history', {}))
            if count > LEGACY_SHOP_COUNT:
                high = sum(1 << (i - LEGACY_SHOP_COUNT) for i in range(LEGACY_SHOP_COUNT, count) if SHOP_BASE + i in bought)
                packets.append(f"APSHOP2|{self._live_seed_identity()}|1|{cleared}|{mask}|1|{high}\r\n".encode('ascii'))
            else:
                packets.append(f"APSHOP1|{self._live_seed_identity()}|{int(count > 0)}|{cleared}|{mask}\r\n".encode('ascii'))
            for index in range(count):
                info = getattr(self, 'shop_scouts', {}).get(SHOP_BASE + index)
                if info is not None:
                    title = self._item_display_name(info.item, info.player)
                    owner = self.player_names.get(info.player, f'Player {info.player}')
                    # UTF-16 hex keeps delimiters, markup and Unicode out of the wire framing.
                    fields = [text.encode('utf-16-be', errors='replace').hex() for text in (title[:160], owner[:80])]
                    packets.append(f"APSHOPITEM1|{self._live_seed_identity()}|{index}|{fields[0]}|{fields[1]}\r\n".encode('ascii'))
        return packets

    async def _send_live_snapshot(self, writer: asyncio.StreamWriter) -> None:
        for packet in self._snapshot_packets():
            writer.write(packet)
        await writer.drain()

    def _publish_file_snapshot(self) -> None:
        """Fresh-read Linux fallback, independent of sockets and UE config caching."""
        if not sys.platform.startswith('linux') or self.live_snapshot is None:
            return
        now = time.monotonic()
        if now - getattr(self, '_file_write_time', -10.0) < 1.0:
            return
        session = getattr(self, '_file_session', None)
        if session is None:
            session = self._file_session = secrets.token_hex(16)
        sequence = getattr(self, '_file_sequence', 0) + 1
        packets = self._snapshot_packets()
        if self.death_bridge is not None:
            connected = bool(self.server and self.server.socket and not self.server.socket.closed)
            packets.append(self.death_bridge.snapshot(connected))
        lines = [p.decode('ascii').rstrip('\r\n') for p in packets]
        if any(not line or len(line) > 8192 or any(c in line for c in '\r\n<>%') for line in lines):
            raise ProtocolError('Invalid file-bridge snapshot.')
        header = f'APFILE1|{self._live_seed_identity()}|{session}|{sequence}|{len(lines)}'
        data = ('\n'.join([header, *lines, 'END|' + header]) + '\n').encode('ascii')
        if len(lines) > 46 or len(data) > 65536:
            raise ProtocolError('File-bridge snapshot exceeds its size limit.')
        # Native WebResponse reads Binaries/Web in DD1. No web server is started
        # and no existing engine/user config, graphics or save is modified here.
        path = self.game_root / 'Binaries' / 'Web' / f'{TC_DIRECTORY}-live.uhtm'
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        self._file_sequence, self._file_write_time = sequence, now
        if sequence == 1:
            self._diagnostic(f'FILE_BRIDGE ready=1 path={path}')
        self._read_file_ack()

    def _read_file_ack(self) -> None:
        for folder in (self.unlock_path.parent, self.game_root / 'UDKGame' / 'Config'):
            parser = configparser.ConfigParser(strict=False)
            try:
                parser.read_string((folder / 'UDKDD1ArchipelagoFileStatus.ini').read_text(encoding='utf-8-sig'))
                status = parser['DD1Archipelago.APFileSnapshotStatus']
                if (status.get('SeedIdentity') != self._live_seed_identity()
                        or status.get('Session') != self._file_session):
                    continue
                revision = status.getint('Revision')
                if revision is not None and revision != getattr(self, '_file_ack', None):
                    self._file_ack = revision
                    self._diagnostic(f'FILE_STATE_ACK revision={revision}')
            except (OSError, UnicodeError, configparser.Error, ValueError, KeyError):
                continue

    async def _broadcast_live_snapshot(self) -> None:
        stale: list[asyncio.StreamWriter] = []
        for writer in tuple(self.live_clients):
            try:
                await self._send_live_snapshot(writer)
            except (ConnectionError, OSError):
                stale.append(writer)
        for writer in stale:
            self.live_clients.discard(writer)
            writer.close()

    async def _handle_live_game(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        if not peer or peer[0] not in {"127.0.0.1", "::1"}:
            writer.close()
            await writer.wait_closed()
            return
        connected = False
        try:
            self._diagnostic('GAME_LINK incoming=1')
            greeting = await asyncio.wait_for(reader.readline(), GAME_HANDSHAKE_TIMEOUT)
            if greeting.rstrip(b"\r\n") != b"DD1HELLO10":
                self._diagnostic('GAME_LINK rejected=handshake')
                if greeting.rstrip(b"\r\n") in {
                    b"DD1HELLO1", b"DD1HELLO2", b"DD1HELLO3",
                    b"DD1HELLO4", b"DD1HELLO5", b"DD1HELLO6", b"DD1HELLO7", b"DD1HELLO8", b"DD1HELLO9",
                }:
                    logger.error("Install the matching updated game files before playing this seed.")
                    return
                logger.warning("Ignored a localhost connection that was not the DD1 mod.")
                return
            self.live_clients.add(writer)
            self.game_connected_once = True
            connected = True
            logger.info("Game connected: Archipelago mod loaded.")
            self._diagnostic("GAME_LINK connected=1")
            await self._send_live_snapshot(writer)
            while not reader.at_eof() and not self.exit_event.is_set():
                line = await reader.readline()
                if not line:
                    break
                if line.rstrip(b"\r\n") == b"DD1PING1":
                    writer.write(b"DD1PONG1\r\n")
                    if self.death_bridge is not None:
                        writer.write(self.death_bridge.snapshot(bool(self.server and self.server.socket)))
                    if self.live_snapshot is not None:
                        writer.write(self.live_snapshot.encode("ascii"))
                        writer.write(self._shard_display_snapshot())
                        writer.write(self._gear_settings_snapshot())
                        if self.state_path is not None:
                            writer.write(trap_snapshot(self._live_seed_identity(),
                                load_bridge_state(self.state_path)['received_items'], ITEM_NAME_TO_ID))
                            writer.write(theme_snapshot(self._live_seed_identity(), self.slot_data.get('tavern_themes', False),
                                load_bridge_state(self.state_path)['received_items'], ITEM_NAME_TO_ID))
                    await writer.drain()
                elif line.startswith(b"DD1DEATH1|"):
                    value = line.decode('ascii', errors='replace').strip()
                    if self.death_bridge is not None and self.death_bridge.accept_status(value):
                        if value != getattr(self, '_last_death_status', None):
                            self._last_death_status = value
                            self._diagnostic('DEATHLINK ' + value)
                elif line.startswith(b"DD1DIAG1|"):
                    self._diagnostic('GAME_DIAGNOSTIC ' + line.decode('ascii', errors='replace').strip()[:1800])
                elif line.startswith(b"DD1STATEACK1|"):
                    try:
                        revision = int(line.decode("ascii").strip().split("|", 2)[1])
                    except (UnicodeError, ValueError, IndexError):
                        logger.warning("Ignored an invalid DD1 state acknowledgement.")
                    else:
                        if revision != self.last_state_ack:
                            self.last_state_ack = revision
                            self._diagnostic(f"STATE_ACK revision={revision}")
                elif line.startswith(b"DD1EVENT2|") and self.state_path is not None:
                    ack, changed = receive_live_event(line, self.state_path, self._live_seed_identity())
                    if changed:
                        self._queue_unlock_write()
                    writer.write(ack)
                    await writer.drain()
                    if changed:
                        await self._reconcile_checks()
        except ProtocolError as error:
            logger.error("DD1 game link rejected: %s", error)
        except (ConnectionError, OSError, asyncio.TimeoutError, ValueError):
            pass
        finally:
            self.live_clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            if connected and not self.live_clients and not self.exit_event.is_set():
                logger.info("DD1 game link disconnected; waiting for the mod to reconnect.")
                self._diagnostic("GAME_LINK connected=0")

    async def _connect_reverse_game(self) -> None:
        """Optional localhost-only recovery without touching Proton/system settings."""
        port = 38285 if PRIVATE_CHAOS_BUILD else 38284
        while not self.exit_event.is_set():
            writer = None
            try:
                if not self.live_clients and self.live_snapshot is not None:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection('127.0.0.1', port, limit=4096), 2.0)
                    writer.write(('APREVERSE1|' + self._live_seed_identity() + '\r\n').encode('ascii'))
                    await writer.drain()
                    self._diagnostic('GAME_REVERSE connected=1')
                    await self._handle_live_game(reader, writer)
            except (OSError, asyncio.TimeoutError, ValueError, ProtocolError):
                pass
            finally:
                if writer is not None:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except (OSError, ConnectionError):
                        pass
            await asyncio.sleep(2.0)

    async def _start_live_bridge(self) -> None:
        if self.live_server is not None:
            return
        self.io_loop = asyncio.get_running_loop()
        self.io_thread = threading.get_ident()
        try:
            self.live_server = await asyncio.start_server(
                self._handle_live_game, LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT, limit=1024
            )
        except OSError as error:
            raise ProtocolError(
                f"Cannot open the local DD1 connection on port {LIVE_BRIDGE_PORT}. "
                "Close any other DD1 Archipelago clients and try again. "
                f"The game was not launched. ({error})"
            ) from error
        logger.info(
            "DD1 local connection is ready on localhost:%d; waiting for the game mod.", LIVE_BRIDGE_PORT
        )
        self._diagnostic(f'GAME_LISTENER ready=1 port={LIVE_BRIDGE_PORT}')

    def _queue_unlock_write(self) -> None:
        self.unlock_write_pending = True
        self._retry_pending_unlocks(force=True)

    def _retry_pending_unlocks(self, *, force: bool = False) -> bool:
        if not self.unlock_write_pending:
            return True
        if not force and time.monotonic() < self.unlock_retry_at:
            return False
        try:
            self._apply_unlocks()
        except (OSError, ProtocolError, ValueError) as error:
            message = str(error)
            if message != self.unlock_write_error:
                logger.error(
                    "Items are saved in the AP client, but DD1 unlock-file writing failed at %s: %s. "
                    "Check that this mod folder can be written to. The client will retry automatically.",
                    self.unlock_path, error,
                )
            self.unlock_write_error = message
            self.unlock_retry_at = time.monotonic() + UNLOCK_RETRY_INTERVAL
            return False
        if self.unlock_write_error is not None:
            logger.info("DD1 unlock-file writing recovered; the saved items are now queued for the game.")
        self.unlock_write_pending = False
        self.unlock_write_error = None
        return True

    def _apply_unlocks(self) -> None:
        if self.state_path is None:
            return
        state = load_bridge_state(self.state_path)
        active_heroes = self._active_heroes(self.slot_data)
        unlocked: dict[str, set[str]] = {
            "heroes": set(), "defenses": set(), "abilities": set(), "maps": set(),
        }
        starting_hero = self.slot_data.get("starting_hero")
        starting_map = self.slot_data.get("starting_map")
        if isinstance(starting_hero, str):
            unlocked["heroes"].add(starting_hero)
        if isinstance(starting_map, str):
            unlocked["maps"].add(starting_map)
        starting_minion = self.slot_data.get("starting_minion")
        if starting_minion is not None:
            unlocked["defenses"].add(DEFENSE_ITEMS[starting_minion])
        for received in state["received_items"]:
            mapping = ITEM_ID_TO_UNLOCK.get(received["item_id"])
            if mapping is not None:
                category, key = mapping
                owner = key if category == "heroes" else key.split(".")[0]
                if category == "maps" or owner in active_heroes:
                    unlocked[category].add(key)
        xp_values = {ITEM_NAME_TO_ID[n]: amount for n, amount in XP_REWARDS.items()}
        xp_rewards = sum(xp_values.get(r["item_id"], 0) for r in state["received_items"])
        mana_rewards = mana_reward_units(state, ITEM_NAME_TO_ID)
        content = ContentSettings.from_slot_data(self.slot_data)
        received_ids = {r["item_id"] for r in state["received_items"]}
        # Recompute from the persisted indexed item history, not receipt callbacks:
        # reconnects cannot advance the tier twice; cap at Ruthless.
        difficulty_count = min(5, content.starting_difficulty + sum(r['item_id'] == ITEM_NAME_TO_ID[PROGRESSIVE_DIFFICULTY]
                                    for r in state['received_items']))
        self.difficulty_mask = (1 << (difficulty_count + 1)) - 1 if content.difficulty_unlocks else 63
        self.mode_mask = 0
        for mode, offset, required in (('survival', 0, content.survival_unlock),
                                       ('challenge', 3, content.challenge_unlock)):
            for area, name in enumerate(AREA_ITEMS[mode]):
                if not required or ITEM_NAME_TO_ID[name] in received_ids:
                    self.mode_mask |= 1 << (offset + area)
        # Without challenge unlocks, preserve the campaign-map requirement.
        if not content.challenge_unlock:
            self.mode_mask |= 64
        self.build_time_seconds = 10 * min(20, sum(
            r['item_id'] == ITEM_NAME_TO_ID[BUILD_TIME_ITEM] for r in state['received_items']))
        self.defense_units_bonus = (5 * min(6, sum(
            r['item_id'] == ITEM_NAME_TO_ID[DEFENSE_UNITS_ITEM] for r in state['received_items']))
            if content.progressive_defense_units else 0)
        # Without Survival checks, farming uses vanilla starting-wave access.
        self.survival_start_wave = (max(1, 5 * min(5, sum(
            r['item_id'] == ITEM_NAME_TO_ID[SURVIVAL_START_ITEM] for r in state['received_items'])))
            if self.slot_data['dd1_slot_data_version'] >= 10 and content.survival_checks else -1)
        self.gear_rewards, self.crystal_skin_mask = cosmetic_totals(state['received_items'], ITEM_NAME_TO_ID)
        self.active_map_tags = {m.tag for m in enabled_maps(content)}
        self.eternia_shard_mask = eternia_shard_display_mask(content, state['received_items'])
        self.hero_skin_mode = 2 if content.hero_skins_unlocked else int(content.hero_skin_items)
        self.hero_skin_keys = unlocked_skin_keys(active_heroes, content,
            {r['item_id'] for r in state['received_items']}, ITEM_NAME_TO_ID)
        unlocked['maps'].intersection_update(self.active_map_tags)
        if content.completion_goal == 'crystalline_dimension' and cd_unlocked(
                state.get('victory_history', {}), content.crystalline_dimension_difficulty,
                content.crystalline_dimension_unlock, state['received_items']):
            unlocked['maps'].add(CD_TAG)
        else:
            unlocked['maps'].discard(CD_TAG)
        victories = set(state["observed_locations"]) | set(state.get("victory_history", {}))
        if content.summit_unlocked(unlocked["maps"], victories):
            unlocked["maps"].add("CAMPTS")
        else:
            unlocked["maps"].discard("CAMPTS")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        # A map clear can unlock The Summit even when its AP item is sent to
        # somebody else. Such local progress must refresh the game on its own.
        revision = state["last_received_index"] + 2 + len(victories)
        write_unlock_ini(
            self.unlock_path,
            {
                "protocol": 1,
                "revision": revision,
                "slot": safe_filename(slot_name),
                "unlocked": {
                    **{category: sorted(values) for category, values in unlocked.items()},
                    "max_equipment_quality": 19,
                },
            },
            level_six_heroes=self.slot_data.get("level_six_heroes", []),
            experience_multiplier=self.slot_data.get("experience_multiplier", 1),
            level_catch_up_multiplier=self.slot_data.get("level_catch_up_multiplier", 1),
            active_heroes=active_heroes,
            seed_identity=self._live_seed_identity(),
            difficulty_mask=self.difficulty_mask,
            mode_mask=self.mode_mask,
            starting_crystal_roll=self.slot_data['starting_crystal_roll'],
            build_time_seconds=self.build_time_seconds,
            defense_units_bonus=self.defense_units_bonus,
            survival_start_wave=self.survival_start_wave,
            crystal_skin_mask=self.crystal_skin_mask,
            shopsanity=self.slot_data['shopsanity'],
            received_xp_rewards=xp_rewards,
            received_mana_rewards=mana_rewards,
            received_gear_rewards=self.gear_rewards,
            active_maps=self.active_map_tags,
            hero_skin_mode=self.hero_skin_mode,
            hero_skin_keys=self.hero_skin_keys,
            eternia_shard_mask=self.eternia_shard_mask,
            random_gear_pets=content.random_gear_pets,
            chaos_slot_data=self.slot_data,
            chaos_player=self.slot,
            reverse_bridge=sys.platform.startswith('linux'),
            tavern_themes=bool(self.slot_data.get('tavern_themes', False)),
            tavern_theme_mask=theme_mask(self.slot_data.get('tavern_themes', False), state['received_items'], ITEM_NAME_TO_ID),
        )
        self.live_snapshot = self._make_live_snapshot(
            revision, unlocked, xp_rewards, mana_rewards
        )
        self._diagnostic(
            f"STATE_READY revision={revision} last_index={state['last_received_index']} "
            f"game_links={len(self.live_clients)}"
        )
        if self.live_clients:
            self._schedule_task(self._broadcast_live_snapshot())
        logger.info(
            "Wrote DD1 unlock file: %d hero(es), %d defense(s), %d ability/abilities, %d map(s). "
            "In-game application is not yet acknowledged.",
            len(unlocked["heroes"]), len(unlocked["defenses"]),
            len(unlocked["abilities"]), len(unlocked["maps"]),
        )

    async def _report_goal_if_complete(self) -> None:
        if self.state_path is None or self.finished_game:
            return
        state = load_bridge_state(self.state_path)
        if not state["goal_complete"]:
            return
        self.finished_game = True
        await self.send_msgs([
            {"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}
        ])
        logger.info("Dungeon Defenders goal complete: %s.", self.slot_data['completion_goal'])

    async def _reconcile_checks(self) -> None:
        if self.state_path is None:
            return
        state = load_bridge_state(self.state_path)
        recovered = recover_victories(state, self.checked_locations)
        safe_to_send, unknown = reconcile_locations(
            state,
            server_locations=self.server_locations,
            checked_locations=self.checked_locations,
        )
        atomic_write_json(self.state_path, state)
        if recovered:
            logger.info(
                "Recovered %d locally observed DD1 victory record(s).", recovered
            )
            self._queue_unlock_write()
        if unknown:
            logger.warning(
                "Quarantined %d pending DD1 prototype check(s) absent from this slot's table.",
                len(unknown),
            )
        if safe_to_send:
            self.locations_checked.update(safe_to_send)
            await self.send_msgs([{"cmd": "LocationChecks", "locations": safe_to_send}])
            logger.info("Submitted %d Dungeon Defenders check(s).", len(safe_to_send))
        await self._report_goal_if_complete()

    @property
    def event_journal_paths(self) -> tuple[Path, ...]:
        return tuple(self.game_root / folder / name
            for folder in (f'TotalConversions/{TC_DIRECTORY}/Config', 'Config', 'UDKGame/Config')
            for name in ('UDKDD1ArchipelagoBridgeDiagnostics.ini', 'DefaultDD1ArchipelagoBridgeDiagnostics.ini'))

    def _poll_event_journal(self) -> bool:
        if self.state_path is None or not self.seed_name:
            return False
        expected_seed = self._live_seed_identity()
        changed = False
        for path in self.event_journal_paths:
            for payload in read_pending_event_journal(path, expected_seed):
                payload_key = hashlib.sha256(payload.encode('utf-8', errors='replace')).hexdigest()
                if payload_key in self._rejected_journal_events:
                    continue
                try:
                    _, fresh = receive_live_event(
                        ('DD1EVENT2|' + payload + '\r\n').encode('ascii'),
                        self.state_path, expected_seed)
                except (ProtocolError, UnicodeEncodeError) as error:
                    self._rejected_journal_events.add(payload_key)
                    logger.warning('Ignored invalid DD1 journal entry in %s: %s', path, error)
                    self._diagnostic('EVENT_JOURNAL rejected=' + payload_key[:12])
                    continue
                changed = changed or fresh
        if changed:
            logger.info('Recovered DD1 completion event(s) from the game journal.')
            self._diagnostic('EVENT_JOURNAL recovered=1')
        return changed

    async def _poll_game_events(self) -> None:
        next_check_retry = 0.0
        while not self.exit_event.is_set():
            if self.state_path is not None:
                try:
                    if self.death_bridge is not None:
                        connected = bool(self.server and self.server.socket and not self.server.socket.closed)
                        # The INI heartbeat is a fallback transport. A locked or
                        # unwritable file must not block live death reports or
                        # unrelated check reconciliation.
                        try:
                            self.death_bridge.write(connected)
                        except OSError as error:
                            if not getattr(self, '_deathlink_write_failed', False):
                                logger.warning('DeathLink configuration write failed; live transport remains active: %s', error)
                            self._deathlink_write_failed = True
                        else:
                            if getattr(self, '_deathlink_write_failed', False):
                                logger.info('DeathLink configuration writes recovered.')
                            self._deathlink_write_failed = False
                        # Consume offline deaths without replaying them on reconnect.
                        if self.death_bridge.poll_death() and connected:
                            player = self.player_names.get(self.slot, 'A DD1 player')
                            cause = (f"{player}'s Eternia Crystal was destroyed in Dungeon Defenders."
                                     if self.death_bridge.mode == 'crystal_destruction'
                                     else f'{player} died in Dungeon Defenders.')
                            await self.send_death(cause)
                    if self._poll_event_journal():
                        self._queue_unlock_write()
                        await self._reconcile_checks()
                    self._retry_pending_unlocks()
                    try:
                        self._publish_file_snapshot()
                    except (OSError, ProtocolError) as error:
                        if not getattr(self, '_file_publish_failed', False):
                            logger.warning('DD1 file bridge could not update: %s', error)
                            self._diagnostic('FILE_BRIDGE write_failed=1')
                        self._file_publish_failed = True
                    else:
                        self._file_publish_failed = False
                    # ACK means recorded locally, not acknowledged by the AP
                    # server. Keep retrying pending checks after interruptions.
                    if time.monotonic() >= next_check_retry:
                        next_check_retry = time.monotonic() + 2.0
                        if load_bridge_state(self.state_path)["pending_location_ids"]:
                            await self._reconcile_checks()
                except (OSError, ProtocolError, ValueError) as error:
                    logger.error("DD1 bridge poll failed: %s", error)
                except Exception:
                    # A single malformed retained event must never permanently
                    # stop item receipt or all later check reconciliation.
                    logger.exception("Unexpected DD1 bridge poll error; polling will continue.")
                    self._diagnostic('BRIDGE_POLL unexpected_error=1')
            await asyncio.sleep(0.25)

    async def _broadcast_item_message(self, message: str) -> None:
        # Plain text only: no control characters or line-protocol injection.
        clean = ''.join(c if 32 <= ord(c) < 127 else '?' for c in message)[:240]
        for writer in tuple(self.live_clients):
            try:
                writer.write(('DD1MSG1|' + clean + '\n').encode('ascii'))
                await writer.drain()
            except (ConnectionError, OSError):
                self.live_clients.discard(writer)

    def on_package(self, cmd: str, args: dict) -> None:
        if self.io_loop is not None and threading.get_ident() != self.io_thread:
            self.io_loop.call_soon_threadsafe(self.on_package, cmd, dict(args))
            return
        if cmd == 'Bounced' and 'DeathLink' in args.get('tags', []):
            # CommonClient filters solely by timestamp. Two players can send
            # within the same clock tick; distinguish source + time instead.
            # on_deathlink also deduplicates the normal CommonClient dispatch.
            self.on_deathlink(args['data'])
        if cmd == "PrintJSON" and args.get("type") == "ItemSend":
            item = args.get("item")
            receiver = args.get("receiving")
            if item is not None and self.slot in (item.player, receiver):
                name = self._item_display_name(item.item, receiver)
                if item.player == receiver == self.slot:
                    message = f"You found {name}"
                elif receiver == self.slot:
                    sender_name = self.player_names.get(item.player, "Archipelago")
                    message = f"You received {name} from {sender_name}"
                else:
                    receiver_name = self.player_names.get(receiver, f"Player {receiver}")
                    message = f"You sent {name} to {receiver_name}"
                self._schedule_task(self._broadcast_item_message(message))
                if item.player == 0 and receiver == self.slot and hasattr(item, "_replace"):
                    # Some Kivy versions have no color entry for the AP pseudo-player.
                    # Preserve the in-game wording above, then render it as self-sent.
                    args["item"] = item._replace(player=self.slot)
        if cmd == "RoomInfo":
            seed_name = args.get("seed_name")
            if isinstance(seed_name, str) and seed_name:
                self.seed_name = seed_name
        elif cmd == "Connected":
            try:
                incoming = args.get('slot_data') or {}
                is_chaos = incoming.get('dd1_slot_data_version') in (1001, 1002, 1003) or incoming.get('chaos_loadout') is not None
                # The regular 0.8.0 conversion supports both modes. Keep the
                # historical private profile isolated from normal saves.
                if PRIVATE_CHAOS_BUILD and not is_chaos:
                    raise ProtocolError('This private test client only accepts Chaos Loadouts seeds. Use the normal client for this seed.')
                # Never create a save/profile or unlock INI in an incomplete
                # installation: that used to make a missing mod look installed.
                validate_retail_install(self.game_root, tc_directory=TC_DIRECTORY)
                verify_conversion_package(self.game_root, tc_directory=TC_DIRECTORY)
                self.slot_data = args.get("slot_data") or {}
                self._select_slot_state(self.slot_data)
                self._activate_seed_hero_save()
                self._apply_unlocks()
                self.shop_scouts = {}
                if self.slot_data.get('shopsanity'):
                    self._schedule_task(self.send_msgs([{'cmd': 'LocationScouts',
                        'locations': list(range(SHOP_BASE, SHOP_BASE + shop_count(self.slot_data))), 'create_as_hint': 0}]))
            except (OSError, ProtocolError, ValueError) as error:
                logger.error("Cannot initialize DD1 slot state: %s", error)
                self._schedule_task(self.disconnect())
                return
            logger.info("Using regular DD1 mod installation: %s", self.game_root)
            self.game_connected_once = bool(self.live_clients)
            if self.startup_task is not None and not self.startup_task.done():
                self.startup_task.cancel()
            self.startup_task = self._schedule_task(
                self._finish_slot_startup(), name="DD1 game startup"
            )
        elif cmd == "RoomUpdate" and "checked_locations" in args:
            self._schedule_task(self._reconcile_checks())
            self._queue_unlock_write()
        elif cmd == 'LocationInfo':
            if not hasattr(self, 'shop_scouts'):
                self.shop_scouts = {}
            self.shop_scouts.update({info.location: info for info in args.get('locations', [])
                                    if SHOP_BASE <= info.location < SHOP_BASE + SHOP_COUNT})
            self._schedule_task(self._broadcast_live_snapshot())
        elif cmd in ('DataPackage', 'RoomUpdate'):
            if self.live_snapshot is not None:
                self._schedule_task(self._broadcast_live_snapshot())
        elif cmd == "ReceivedItems" and self.state_path is not None:
            try:
                state = load_bridge_state(self.state_path)
                added = ingest_mana_packet(state, args, ITEM_NAME_TO_ID, self._live_seed_identity())
                atomic_write_json(self.state_path, state)
            except (OSError, ProtocolError, ValueError) as error:
                logger.error("Rejected ReceivedItems packet: %s", error)
            else:
                if added:
                    self._queue_unlock_write()
                    self._diagnostic(f"RECEIVED_ITEMS added={added} last_index={state['last_received_index']}")
                    logger.info(
                        "Saved %d received item(s) in the AP client. "
                        "Game delivery is tracked separately from the server connection.",
                        added,
                    )

    async def shutdown(self) -> None:
        tasks = [task for task in (self.startup_task, self.game_watch_task, self.reverse_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.death_bridge is not None:
            try:
                self.death_bridge.write(False, force=True)
            except OSError:
                logger.exception('Could not disable the DD1 DeathLink input during shutdown.')
        for writer in tuple(self.live_clients):
            writer.close()
        if self.live_clients:
            await asyncio.gather(
                *(writer.wait_closed() for writer in self.live_clients),
                return_exceptions=True,
            )
        self.live_clients.clear()
        if self.live_server is not None:
            self.live_server.close()
            await self.live_server.wait_closed()
            self.live_server = None
        if self.poll_task is not None:
            self.poll_task.cancel()
            await asyncio.gather(self.poll_task, return_exceptions=True)
        await super().shutdown()


async def _main(args: argparse.Namespace) -> None:
    ctx = DungeonDefendersContext(
        args.connect, args.password, args.game_root, args.launch_game
    )
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    await ctx.exit_event.wait()
    await ctx.shutdown()


def choose_game_folder() -> Optional[str]:
    if gui_enabled:
        try:
            return Utils.open_directory("Select your Dungeon Defenders game folder")
        except Exception as error:
            raise ValueError("Could not open the folder picker. Use --game-root followed by "
                             "your Dungeon Defenders folder.") from error
    try:
        return input("Dungeon Defenders game folder (blank to cancel): ").strip().strip('"') or None
    except (EOFError, KeyboardInterrupt):
        return None


def launch(*launch_args: str) -> None:
    parser = get_base_parser(
        description="Dungeon Defenders Archipelago client (Local-only Total Conversion)."
    )
    parser.add_argument("--name", default=None, help="Archipelago slot name.")
    parser.add_argument(
        "--game-root",
        type=Path,
        default=None,
        help="Select and remember your Dungeon Defenders installation folder.",
    )
    parser.add_argument("--select-game-folder", action="store_true",
                        help="Choose a game folder again instead of using the saved choice.")
    parser.add_argument(
        "--no-launch-game",
        action="store_false",
        dest="launch_game",
        help="Connect the client without automatically starting Dungeon Defenders.",
    )
    parser.set_defaults(launch_game=True)
    parser.add_argument("url", nargs="?", help="Archipelago connection URL.")
    args = parser.parse_args(launch_args)
    args = CommonClient.handle_url_arg(args, parser=parser)
    try:
        args.game_root = select_retail_root(
            args.game_root, Path(Utils.user_path(STATE_DIRECTORY, "game-install.json")),
            choose_game_folder, force_select=args.select_game_folder, tc_directory=TC_DIRECTORY)
        if args.game_root is None:
            return
    except (OSError, ValueError) as error:
        if gui_enabled:
            try:
                Utils.messagebox("Dungeon Defenders installation", str(error), error=True)
            except Exception:
                logger.exception("Could not display the DD1 installation error window.")
        parser.error(str(error))
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main(args))


if __name__ == "__main__":
    launch(*sys.argv[1:])
