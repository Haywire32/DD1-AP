"""Archipelago 0.6.7 client shell for the DD1 Local-only file bridge."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import CommonClient
import Utils
from CommonClient import CommonContext, get_base_parser, gui_enabled, server_loop
from NetUtils import ClientStatus

from .dd1_ap_adapter import ingest_received_packet, reconcile_locations
from .dd1_bridge_service import baseline_existing_events, process_once
from .dd1_install import find_dddk_root, validate_dddk_install
from .items import ITEM_ID_TO_UNLOCK, ITEM_NAME_TO_ID, MANA_FILLER_ITEM, XP_FILLER_ITEM
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
STATE_DATA_VERSION = 1
LIVE_BRIDGE_HOST = "127.0.0.1"
LIVE_BRIDGE_PORT = 38282
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

    def __init__(
        self,
        server_address: Optional[str],
        password: Optional[str],
        dddk_root: Path,
        launch_game: bool,
    ) -> None:
        super().__init__(server_address, password)
        self.dddk_root = dddk_root
        self.launch_game = launch_game
        self.launched_game: Optional[subprocess.Popen] = None
        self.seed_name: Optional[str] = None
        self.state_path: Optional[Path] = None
        self.poll_task: Optional[asyncio.Task] = None
        self.slot_data: dict = {}
        self.live_server: Optional[asyncio.AbstractServer] = None
        self.live_clients: set[asyncio.StreamWriter] = set()
        self.live_snapshot: Optional[str] = None
        self.startup_task: Optional[asyncio.Task] = None
        self.game_watch_task: Optional[asyncio.Task] = None
        self.game_connected_once = False
        self.unlock_write_pending = False
        self.unlock_write_error: Optional[str] = None
        self.unlock_retry_at = 0.0

    @property
    def game_executable(self) -> Path:
        return self.dddk_root / "Binaries" / "Win64" / "DunDefDevelopment.exe"

    def _launch_local_game(self) -> None:
        if not self.launch_game:
            return
        if self.launched_game is not None and self.launched_game.poll() is None:
            logger.info("Dungeon Defenders is already running from this client.")
            return
        validate_dddk_install(self.dddk_root)
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
        # Invoke the installed game's trusted executable directly. No shell,
        # batch file, helper executable, or online game mode is involved.
        self.launched_game = subprocess.Popen(
            [
                str(executable),
                "-TOTALCONVERSION=DD1ArchipelagoCurrent",
            ],
            cwd=executable.parent,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
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
            await self._reconcile_checks()
            self._launch_local_game()
        except (OSError, ProtocolError, ValueError) as error:
            logger.error("Cannot start the DD1 game connection: %s", error)
            await self.disconnect()
            return
        if self.poll_task is None or self.poll_task.done():
            self.poll_task = asyncio.create_task(
                self._poll_game_events(), name="DD1 event-file poll"
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
                if result is not None:
                    if self.game_connected_once:
                        logger.info("Dungeon Defenders closed (exit code %s).", result)
                    else:
                        logger.error(
                            "Dungeon Defenders closed before the AP mod connected (exit code %s). "
                            "The Archipelago server connection does not mean the game mod loaded. "
                            "Check any game error message and the mod installation.", result,
                        )
                    return
            if not self.game_connected_once and not warned and time.monotonic() >= deadline:
                warned = True
                logger.warning(
                    "The DD1 mod has not connected after %d seconds. "
                    "If the game is still loading, wait for loading to finish. "
                    "If the menu or game has loaded without AP restrictions, close the game "
                    "and merge DD1ArchipelagoCurrent from the latest release over your installed mod. "
                    "Archipelago items are saved in the client, but delivery to the game is unconfirmed.",
                    GAME_CONNECT_TIMEOUT,
                )
            await asyncio.sleep(1.0)

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def _select_slot_state(self, slot_data: dict) -> None:
        if not self.seed_name:
            raise ProtocolError("server did not provide a seed name")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        version = slot_data.get("dd1_slot_data_version", STATE_DATA_VERSION)
        if not isinstance(version, int) or version < 0:
            raise ProtocolError("invalid DD1 slot-data version")
        filename = (
            f"{safe_filename(self.seed_name)}-team{self.team}-"
            f"{safe_filename(slot_name)}.json"
        )
        self.state_path = Path(Utils.user_path("dd1_archipelago", filename))
        is_new_slot_state = not self.state_path.exists()
        state = load_bridge_state(self.state_path)
        bind_slot_identity(
            state,
            seed_name=self.seed_name,
            slot=slot_name,
            team=self.team,
            slot_data_version=version,
        )
        state["summit_settings"] = summit_settings(slot_data)
        if is_new_slot_state:
            ignored = baseline_existing_events(self.dddk_root, state)
            if ignored:
                logger.info(
                    "Ignored %d DD1 event file(s) created before this slot connected.",
                    ignored,
                )
        atomic_write_json(self.state_path, state)
        logger.info("Using durable DD1 state: %s", self.state_path)

    def _activate_seed_hero_save(self) -> None:
        if not self.seed_name:
            raise ProtocolError("cannot select a hero save without seed identity")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        identity = f"{self.seed_name}|team{self.team}|{slot_name}"
        tc_root = self.dddk_root / "TotalConversions" / "DD1ArchipelagoCurrent"
        profiles_root = Path(Utils.user_path("dd1_archipelago", "hero_saves"))
        expected_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        process_check = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq DunDefDevelopment.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process_check.returncode != 0:
            detail = " ".join((process_check.stderr or process_check.stdout or "no details").split())[:240]
            raise ProtocolError(
                "Cannot check whether Dungeon Defenders is running, so no hero save was switched. "
                "Close any running DD1 game and try again. "
                f"Windows reported: {detail}"
            )
        if "dundefdevelopment.exe" in process_check.stdout.casefold():
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
            self.dddk_root
            / "TotalConversions"
            / "DD1ArchipelagoCurrent"
            / "Config"
            / "UDKDD1ArchipelagoUnlocks.ini"
        )

    @staticmethod
    def _snapshot_field(values: set[str]) -> str:
        # UnrealScript drops empty delimited fields, which would shift the
        # APSTATE envelope. A dash is an explicit empty sentinel.
        return ",".join(sorted(values)) if values else "-"

    def _make_live_snapshot(
        self, revision: int, unlocked: dict[str, set[str]], xp_rewards: int, mana_rewards: int
    ) -> str:
        if not self.seed_name:
            raise ProtocolError("cannot create live snapshot without seed identity")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        seed_identity = safe_filename(
            f"{self.seed_name}-team{self.team}-{slot_name}"
        )
        return "|".join((
            "APSTATE3",
            seed_identity,
            str(revision),
            self._snapshot_field(unlocked["heroes"]),
            self._snapshot_field(unlocked["defenses"]),
            self._snapshot_field(unlocked["abilities"]),
            self._snapshot_field(unlocked["maps"]),
            "19",
            str(xp_rewards),
            str(mana_rewards),
        )) + "\r\n"

    async def _send_live_snapshot(self, writer: asyncio.StreamWriter) -> None:
        if self.live_snapshot is None:
            return
        writer.write(self.live_snapshot.encode("ascii"))
        await writer.drain()

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
            greeting = await asyncio.wait_for(reader.readline(), GAME_HANDSHAKE_TIMEOUT)
            if greeting.rstrip(b"\r\n") != b"DD1HELLO1":
                logger.warning("Ignored a localhost connection that was not the DD1 mod.")
                return
            self.live_clients.add(writer)
            self.game_connected_once = True
            connected = True
            logger.info("Game connected: Archipelago mod loaded.")
            await self._send_live_snapshot(writer)
            while not reader.at_eof() and not self.exit_event.is_set():
                line = await reader.readline()
                if line.rstrip(b"\r\n") == b"DD1PING1":
                    writer.write(b"DD1PONG1\r\n")
                    await writer.drain()
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

    async def _start_live_bridge(self) -> None:
        if self.live_server is not None:
            return
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
        unlocked: dict[str, set[str]] = {
            "heroes": set(), "defenses": set(), "abilities": set(), "maps": set(),
        }
        starting_hero = self.slot_data.get("starting_hero")
        starting_map = self.slot_data.get("starting_map")
        if isinstance(starting_hero, str):
            unlocked["heroes"].add(starting_hero)
        if isinstance(starting_map, str):
            unlocked["maps"].add(starting_map)
        for received in state["received_items"]:
            mapping = ITEM_ID_TO_UNLOCK.get(received["item_id"])
            if mapping is not None:
                category, key = mapping
                unlocked[category].add(key)
        xp_rewards = sum(
            received["item_id"] == ITEM_NAME_TO_ID[XP_FILLER_ITEM]
            for received in state["received_items"]
        )
        mana_rewards = sum(
            received["item_id"] == ITEM_NAME_TO_ID[MANA_FILLER_ITEM]
            for received in state["received_items"]
        )
        settings = summit_settings(self.slot_data)
        victories = set(state["observed_locations"]) | set(state.get("victory_history", {}))
        if summit_is_unlocked(victories, settings["summit_required_maps"], settings["summit_unlock_difficulty"]):
            unlocked["maps"].add("CAMPTS")
        slot_name = self.player_names.get(self.slot, self.auth or str(self.slot))
        revision = state["last_received_index"] + 2
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
        )
        self.live_snapshot = self._make_live_snapshot(
            revision, unlocked, xp_rewards, mana_rewards
        )
        if self.live_clients:
            asyncio.create_task(self._broadcast_live_snapshot())
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
        logger.info("Dungeon Defenders goal complete: The Summit defeated on %s or higher.",
                    ("Easy", "Medium", "Hard", "Insane")[summit_settings(self.slot_data)["summit_goal_difficulty"]])

    async def _reconcile_checks(self) -> None:
        if self.state_path is None:
            return
        state = load_bridge_state(self.state_path)
        recovered = recover_observed_victories(state, self.checked_locations)
        safe_to_send, unknown = reconcile_locations(
            state,
            server_locations=self.server_locations,
            checked_locations=self.checked_locations,
        )
        atomic_write_json(self.state_path, state)
        if recovered:
            logger.info(
                "Recovered %d DD1 map-victory record(s) from server checks.", recovered
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

    async def _poll_game_events(self) -> None:
        while not self.exit_event.is_set():
            if self.state_path is not None:
                try:
                    self._retry_pending_unlocks()
                    # Keep this local read-modify-write on the same event-loop
                    # thread as ReceivedItems. A background writer could replace
                    # newly received items with an earlier state snapshot.
                    processed, added = process_once(self.dddk_root, self.state_path)
                    if processed or added:
                        await self._reconcile_checks()
                except (OSError, ProtocolError, ValueError) as error:
                    logger.error("DD1 bridge poll failed: %s", error)
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
        if cmd == "PrintJSON" and args.get("type") == "ItemSend":
            item = args.get("item")
            receiver = args.get("receiving")
            if item is not None and self.slot in (item.player, receiver):
                name = self.item_names.lookup_in_slot(item.item, receiver)
                if item.player == receiver == self.slot:
                    message = f"You found {name}"
                elif receiver == self.slot:
                    sender_name = self.player_names.get(item.player, "Archipelago")
                    message = f"You received {name} from {sender_name}"
                else:
                    receiver_name = self.player_names.get(receiver, f"Player {receiver}")
                    message = f"You sent {name} to {receiver_name}"
                asyncio.create_task(self._broadcast_item_message(message))
        if cmd == "RoomInfo":
            seed_name = args.get("seed_name")
            if isinstance(seed_name, str) and seed_name:
                self.seed_name = seed_name
        elif cmd == "Connected":
            try:
                # Never create a save/profile or unlock INI in an incomplete
                # installation: that used to make a missing mod look installed.
                validate_dddk_install(self.dddk_root)
                self.slot_data = args.get("slot_data") or {}
                self._select_slot_state(self.slot_data)
                self._activate_seed_hero_save()
                self._apply_unlocks()
            except (OSError, ProtocolError, ValueError) as error:
                logger.error("Cannot initialize DD1 slot state: %s", error)
                asyncio.create_task(self.disconnect())
                return
            logger.info("Using DD1 mod installation: %s", self.dddk_root)
            self.game_connected_once = bool(self.live_clients)
            if self.startup_task is not None and not self.startup_task.done():
                self.startup_task.cancel()
            self.startup_task = asyncio.create_task(
                self._finish_slot_startup(), name="DD1 game startup"
            )
        elif cmd == "RoomUpdate" and "checked_locations" in args:
            asyncio.create_task(self._reconcile_checks())
        elif cmd == "ReceivedItems" and self.state_path is not None:
            try:
                state = load_bridge_state(self.state_path)
                added = ingest_received_packet(state, args)
                atomic_write_json(self.state_path, state)
            except (OSError, ProtocolError, ValueError) as error:
                logger.error("Rejected ReceivedItems packet: %s", error)
            else:
                if added:
                    self._queue_unlock_write()
                    logger.info(
                        "Saved %d received item(s) in the AP client. "
                        "Game delivery is tracked separately from the server connection.",
                        added,
                    )

    async def shutdown(self) -> None:
        tasks = [task for task in (self.startup_task, self.game_watch_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
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
        args.connect, args.password, args.dddk_root, args.launch_game
    )
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    await ctx.exit_event.wait()
    await ctx.shutdown()


def launch(*launch_args: str) -> None:
    parser = get_base_parser(
        description="Dungeon Defenders Archipelago client (Local-only Total Conversion)."
    )
    parser.add_argument("--name", default=None, help="Archipelago slot name.")
    parser.add_argument(
        "--dddk-root",
        type=Path,
        default=None,
        help="Optional Dungeon Defenders Development Kit folder override.",
    )
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
        args.dddk_root = find_dddk_root(args.dddk_root)
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
