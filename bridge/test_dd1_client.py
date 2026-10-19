"""Exercise real DD1 client paths with the Archipelago UI/network boundary stubbed."""

import asyncio
import argparse
import importlib
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch


def load_client():
    root = Path(__file__).resolve().parents[1]
    package = types.ModuleType("dd1_client_under_test")
    package.__path__ = [str(root / "apworld" / "dungeon_defenders"), str(root / "bridge")]
    sys.modules[package.__name__] = package

    class CommonContext:
        def __init__(self, server_address, password):
            self.exit_event = asyncio.Event()
            self.slot, self.team, self.auth = 1, 0, "Haywire"
            self.player_names = {1: "Haywire"}
            self.finished_game = False
            self.server_locations = self.checked_locations = set()
            self.locations_checked = set()
            self.item_names = types.SimpleNamespace(
                lookup_in_slot=lambda item, player: "Test Item"
            )

        async def disconnect(self):
            pass

        async def shutdown(self):
            pass

        async def send_msgs(self, messages):
            pass

        async def update_death_link(self, enabled):
            pass

        def on_print_json(self, args):
            self.last_print_json = args

    common = types.ModuleType("CommonClient")
    common.CommonContext = CommonContext
    common.get_base_parser = Mock()
    common.gui_enabled = False
    common.server_loop = AsyncMock()
    base = types.ModuleType("BaseClasses")
    base.ItemClassification = types.SimpleNamespace(progression=1, filler=0, useful=2, trap=4)
    net = types.ModuleType("NetUtils")
    net.ClientStatus = types.SimpleNamespace(CLIENT_GOAL=30)
    with patch.dict(sys.modules, {
        "CommonClient": common, "Utils": types.ModuleType("Utils"),
        "NetUtils": net, "BaseClasses": base,
    }):
        return importlib.import_module("dd1_client_under_test.Client")


client = load_client()


class ClientPortabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_connected_accepts_current_and_supported_seed_versions(self):
        for version in (8, 9, 10, 11, 12, 13):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                ctx = self.make_context(root)
                ctx.slot_data['dd1_slot_data_version'] = version
                ctx._activate_seed_hero_save = Mock()
                ctx._finish_slot_startup = AsyncMock()
                ctx.disconnect = AsyncMock()
                with patch.object(client, 'validate_retail_install'), patch.object(
                    client.Utils, 'user_path', lambda *parts: str(root.joinpath(*parts)), create=True):
                    ctx.on_package('Connected', {'slot_data': ctx.slot_data})
                    await asyncio.sleep(0)
                ctx.disconnect.assert_not_awaited()
                ctx._activate_seed_hero_save.assert_called_once()
                ctx._finish_slot_startup.assert_awaited_once()
                self.assertTrue(ctx.state_path.is_file())
                self.assertIsNotNone(ctx.live_snapshot)

    async def test_slot_validation_still_rejects_invalid_and_retired_seeds(self):
        for version in (7, 17, '12', 12.0, True):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                ctx = self.make_context(Path(directory))
                ctx.slot_data['dd1_slot_data_version'] = version
                with self.assertRaises(client.ProtocolError):
                    ctx._select_slot_state(ctx.slot_data)
        ctx = self.make_context()
        ctx.slot_data.update(dd1_slot_data_version=11, completion_goal='crystalline_dimension',
                             extra_campaign_maps=True)
        with self.assertRaisesRegex(ValueError, 'removed map'):
            ctx._select_slot_state(ctx.slot_data)

    def make_context(self, root=Path("unused")):
        ctx = client.DungeonDefendersContext(None, None, root, True)
        ctx.seed_name = "portability-test"
        ctx.slot_data = {
            **client.ContentSettings().slot_data(),
            'active_heroes': ['apprentice', 'squire', 'huntress', 'monk'],
            'starting_crystal_roll': 0,
            "starting_hero": "apprentice",
            "starting_map": "CAMPDW",
            "experience_multiplier": 4,
        }
        return ctx

    def make_writer(self):
        writer = Mock()
        writer.get_extra_info.return_value = ("127.0.0.1", 50000)
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        return writer

    async def test_v2_roster_and_starting_minion_reach_game_config(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.state_path = Path(directory) / "state.json"
            client.atomic_write_json(ctx.state_path, client.empty_bridge_state())
            ctx.slot_data.update({
                "dd1_slot_data_version": 10,
                "active_heroes": ["summoner", "barbarian"],
                "starting_hero": "summoner",
                "starting_minion": "Spider Minion (Summoner)",
                "level_six_heroes": ["summoner", "barbarian"],
            })
            ctx._apply_unlocks()
            text = ctx.unlock_path.read_text()
            self.assertIn("ActiveHeroes=summoner", text)
            self.assertIn("LevelSixHeroes=barbarian", text)
            self.assertIn("UnlockedDefenses=summoner.spider_minion", text)
            fields = ctx.live_snapshot.strip().split("|")
            self.assertEqual(len(fields), 25)
            self.assertEqual(fields[0], "APSTATE11")
            self.assertEqual(set(fields[10].split(",")), {"summoner", "barbarian"})
            self.assertEqual(fields[11], "4")
            self.assertEqual(set(fields[13].split(",")), {"summoner", "barbarian"})

    async def test_v2_rejects_invalid_starter_before_mutating_save(self):
        ctx = self.make_context()
        ctx.slot_data.update({"dd1_slot_data_version": 2,
                              "active_heroes": ["squire", "barbarian"]})
        with self.assertRaisesRegex(client.ProtocolError, "starting hero"):
            ctx._active_heroes(ctx.slot_data)

    async def test_cd_unlock_and_skin_receipts_refresh_both_transports(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.slot_data.update(completion_goal='crystalline_dimension',
                                 crystalline_dimension_difficulty=2, extra_campaign_maps=True,
                                 hero_skin_items=True)
            ctx.state_path = Path(directory) / 'state.json'
            state = client.empty_bridge_state()
            names = ['Mummy Hero Skin (Apprentice)', 'Demoness Hero Skin (Summoner)',
                     'The Summit Map', 'Mistymire Forest Map', 'Dread Dungeon Map']
            client.ingest_received_packet(state, {'index': 0, 'items': [
                {'item': client.ITEM_NAME_TO_ID[n], 'location': i, 'player': 1}
                for i,n in enumerate(names)]})
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            fields = ctx.live_snapshot.strip().split('|')
            self.assertEqual(len(fields[22].split(',')), 26)
            self.assertEqual(fields[23], '1')
            self.assertEqual(fields[24], 'apprentice.100')
            self.assertNotIn('CAMPCL', fields[6])
            self.assertIn('CAMPTS', fields[6])
            self.assertIn('CDTCDD', fields[6])
            first_revision = int(fields[2])
            for tag in ('CAMPMF','CAMPAR','CAMPAQ','CAMPSC'):
                state.setdefault('victory_history', {})[f'dd1.campaign.{tag}.victory.hard'] = True
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            fields = ctx.live_snapshot.strip().split('|')
            self.assertIn('CAMPCL', fields[6])
            self.assertGreater(int(fields[2]), first_revision)
            config = ctx.unlock_path.read_text()
            self.assertIn('UnlockedMaps=CAMPCL', config)
            self.assertIn('UnlockedHeroSkins=apprentice.100', config)
            self.assertNotIn('UnlockedHeroSkins=summoner.', config)

    async def test_shard_receipts_unlock_cd_without_map_clears_on_both_transports(self):
        shard = importlib.import_module('dd1_client_under_test.dd1_campaign').ETERNIA_SHARD_ITEMS
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.slot_data.update(completion_goal='crystalline_dimension',
                crystalline_dimension_unlock='eternia_shards', crystalline_dimension_difficulty=5,
                extra_campaign_maps=True)
            ctx.state_path = Path(directory) / 'state.json'
            state = client.empty_bridge_state()
            ids = list(shard.values())
            for index, item_id in enumerate(ids):
                client.ingest_received_packet(state, {'index': index, 'items': [
                    {'item': item_id, 'location': index, 'player': 2}]})
                client.atomic_write_json(ctx.state_path, state)
                ctx._apply_unlocks()
                maps = ctx.live_snapshot.strip().split('|')[6].split(',')
                self.assertEqual('CAMPCL' in maps, index == 3)
                self.assertNotIn('CDTEME', ctx.live_snapshot)
                self.assertEqual('UnlockedMaps=CAMPCL' in ctx.unlock_path.read_text(), index == 3)
            self.assertFalse(state['goal_complete'])
            self.assertFalse(state.get('victory_history'))
            # Reconnect/reapply uses the saved receipt history, not callbacks.
            ctx._apply_unlocks()
            self.assertIn('CAMPCL', ctx.live_snapshot.strip().split('|')[6])
            # Actual-map mode must not treat the Eternia Shards as victories.
            ctx.slot_data['crystalline_dimension_unlock'] = 'shard_maps'
            ctx._apply_unlocks()
            self.assertNotIn('CAMPCL', ctx.live_snapshot.strip().split('|')[6])

    async def test_starting_skin_mode_is_filtered_to_active_roster(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.slot_data.update(hero_skins_unlocked=True)
            ctx.state_path = Path(directory) / 'state.json'
            client.atomic_write_json(ctx.state_path, client.empty_bridge_state())
            ctx._apply_unlocks()
            fields = ctx.live_snapshot.strip().split('|')
            self.assertEqual(fields[23], '2')
            keys = fields[24].split(',')
            self.assertEqual(len(keys), 40)
            self.assertEqual({k.split('.')[0] for k in keys}, set(ctx.slot_data['active_heroes']))

    async def test_old_game_handshake_does_not_receive_dlc_permissions(self):
        ctx = self.make_context()
        ctx.live_snapshot = "APSTATE4|never-deliver\r\n"
        reader = asyncio.StreamReader()
        reader.feed_data(b"DD1HELLO1\n")
        reader.feed_eof()
        writer = self.make_writer()
        with self.assertLogs(client.logger, level="ERROR"):
            await ctx._handle_live_game(reader, writer)
        writer.write.assert_not_called()
        self.assertFalse(ctx.game_connected_once)

    async def test_excluded_hero_receipt_does_not_grant_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.state_path = Path(directory) / "state.json"
            state = client.empty_bridge_state()
            client.ingest_received_packet(state, {"index": 0, "items": [{
                "item": client.ITEM_NAME_TO_ID["Guardian"], "location": 1, "player": 1,
            }]})
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            self.assertNotIn("UnlockedHeroes=guardian", ctx.unlock_path.read_text())

    async def test_future_slot_version_is_rejected(self):
        ctx = self.make_context()
        with self.assertRaisesRegex(client.ProtocolError, "slot-data version"):
            ctx._select_slot_state({"dd1_slot_data_version": 999})

    async def test_local_summit_unlock_refreshes_without_receiving_an_item(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.slot_data.update({"summit_required_maps": 1, "summit_unlock_difficulty": 0})
            ctx.state_path = Path(directory) / "state.json"
            state = client.empty_bridge_state()
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            old_revision = int(ctx.live_snapshot.split("|")[2])
            state["victory_history"] = {"dd1.campaign.CAMPDW.victory.easy": {}}
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            self.assertIn("CAMPTS", ctx.live_snapshot.split("|")[6])
            self.assertGreater(int(ctx.live_snapshot.split("|")[2]), old_revision)

    async def test_event_poll_retries_durably_pending_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.state_path = Path(directory) / "state.json"
            state = client.empty_bridge_state()
            state["pending_location_ids"] = [9100000001]
            client.atomic_write_json(ctx.state_path, state)
            ctx._reconcile_checks = AsyncMock(side_effect=lambda: ctx.exit_event.set())
            ctx._queue_unlock_write = Mock()
            await ctx._poll_game_events()
            ctx._reconcile_checks.assert_awaited_once()
            ctx._queue_unlock_write.assert_not_called()

    async def test_incomplete_mod_stops_before_save_or_state_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = self.make_context(root)
            ctx._select_slot_state = Mock()
            ctx._activate_seed_hero_save = Mock()
            ctx._apply_unlocks = Mock()
            ctx.disconnect = AsyncMock()
            with self.assertLogs(client.logger, level="ERROR"):
                ctx.on_package("Connected", {"slot_data": ctx.slot_data})
                await asyncio.sleep(0)
            ctx._select_slot_state.assert_not_called()
            ctx._activate_seed_hero_save.assert_not_called()
            ctx._apply_unlocks.assert_not_called()
            ctx.disconnect.assert_awaited_once()
            self.assertEqual(list(root.iterdir()), [])

    async def test_port_conflict_does_not_launch_game(self):
        ctx = self.make_context()
        ctx._launch_local_game = Mock()
        ctx.disconnect = AsyncMock()
        with patch.object(client.asyncio, "start_server", AsyncMock(side_effect=OSError("port in use"))):
            with self.assertLogs(client.logger, level="ERROR") as messages:
                await ctx._finish_slot_startup()
        self.assertIn("Close any other DD1", " ".join(messages.output))
        ctx._launch_local_game.assert_not_called()
        ctx.disconnect.assert_awaited_once()

    async def test_linux_launches_through_steam_and_not_the_executable(self):
        ctx = self.make_context(Path("/linux/game"))
        process = Mock(pid=42)
        with patch.object(client.sys, "platform", "linux"), \
                patch.object(client, "validate_retail_install"), \
                patch.object(client.shutil, "which", return_value="/usr/bin/steam"), \
                patch.object(client.subprocess, "Popen", return_value=process) as popen:
            ctx._launch_local_game()
        popen.assert_called_once_with(
            [
                "/usr/bin/steam", "-applaunch", "65800",
                "-TOTALCONVERSION=DD1ArchipelagoCurrent", "-LANGUAGE=INT", "-windowed", "-MULTIHOME=127.0.0.1",
            ],
            cwd=Path("/linux/game"),
        )
        self.assertTrue(ctx._steam_launch_wrapper)

    async def test_linux_process_check_uses_ps(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = self.make_context(Path(directory))
            ctx.state_path = Path(directory) / "state.json"
            client.atomic_write_json(ctx.state_path, client.empty_bridge_state())
            query = types.SimpleNamespace(
                returncode=0,
                stdout="steam --applaunch 65800 DunDefGame.exe",
                stderr="",
            )
            with patch.object(client.sys, "platform", "linux"), \
                    patch.object(client.subprocess, "run", return_value=query) as run, \
                    patch.object(client.Utils, "user_path", return_value="unused-profiles", create=True), \
                    patch.object(client, "switch_hero_profile") as switch:
                with self.assertRaisesRegex(client.ProtocolError, "already running"):
                    ctx._activate_seed_hero_save()
            run.assert_called_once_with(
                  ["ps", "-eo", "args="], capture_output=True, text=True, errors="replace", check=False,
            )
            switch.assert_not_called()

    async def test_game_journal_replays_wave_when_live_link_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = self.make_context(root)
            ctx.slot_data.update(client.ContentSettings().slot_data())
            ctx.state_path = root / "state.json"
            state = client.empty_bridge_state()
            state["content_settings"] = ctx.slot_data
            client.atomic_write_json(ctx.state_path, state)
            payload = (
                ctx._live_seed_identity()
                + "|wave_complete|DD_Lev_02|1|EGD_EASY|campaign|CAMPDW"
            )
            journal = root / "TotalConversions" / "DD1ArchipelagoCurrent" / "Config" / (
                "UDKDD1ArchipelagoBridgeDiagnostics.ini"
            )
            journal.parent.mkdir(parents=True)
            journal.write_text(
                "[DD1Archipelago.APEventBridge]\n"
                "PendingEvents=old-seed|wave_complete|DD_Lev_02|1|EGD_EASY|campaign|CAMPDW\n"
                f"PendingEvents={payload}\n"
                f"PendingEvents={payload}\n",
                encoding="utf-8",
            )
            self.assertTrue(ctx._poll_event_journal())
            saved = client.load_bridge_state(ctx.state_path)
            self.assertEqual(len(saved["pending_location_ids"]), 1)
            self.assertFalse(ctx._poll_event_journal())

    async def test_listener_is_bound_before_launch(self):
        ctx = self.make_context()
        order = []

        async def bind(*args, **kwargs):
            order.append("listener")
            return Mock()

        ctx._reconcile_checks = AsyncMock()
        ctx._launch_local_game = Mock(side_effect=lambda: order.append("launch"))
        ctx._poll_game_events = AsyncMock()
        ctx._watch_game_connection = AsyncMock()
        with patch.object(client.asyncio, "start_server", side_effect=bind), patch.object(client, 'DeathLinkBridge'):
            await ctx._finish_slot_startup()
        self.assertEqual(order, ["listener", "launch"])
        await asyncio.gather(ctx.poll_task, ctx.game_watch_task)

    async def test_connection_needs_game_hello_before_sending_state(self):
        ctx = self.make_context()
        ctx.live_snapshot = "APSTATE3|test\r\n"
        reader = asyncio.StreamReader()
        writer = self.make_writer()
        handler = asyncio.create_task(ctx._handle_live_game(reader, writer))
        await asyncio.sleep(0)
        writer.write.assert_not_called()
        self.assertFalse(ctx.live_clients)
        reader.feed_data(b"DD1HELLO10\nDD1PING1\n")
        reader.feed_eof()
        with self.assertLogs(client.logger, level="INFO") as messages:
            await handler
        self.assertTrue(ctx.game_connected_once)
        self.assertIn("Game connected", " ".join(messages.output))
        writer.write.assert_any_call(b"APSTATE3|test\r\n")
        writer.write.assert_any_call(b"DD1PONG1\r\n")

    async def test_heartbeat_replays_latest_snapshot_for_delayed_linux_updates(self):
        """A missed first push must not leave a Proton game stale until restart."""
        ctx = self.make_context()
        ctx.live_snapshot = "APSTATE5|snapshot\r\n"
        reader = asyncio.StreamReader()
        reader.feed_data(b"DD1HELLO10\nDD1PING1\n")
        reader.feed_eof()
        writer = self.make_writer()

        await ctx._handle_live_game(reader, writer)

        self.assertEqual(
            writer.write.call_args_list,
            [
                call(b"APSTATE5|snapshot\r\n"),
                call(ctx._shard_display_snapshot()),
                call(ctx._gear_settings_snapshot()),
                call(b"DD1PONG1\r\n"),
                call(b"APSTATE5|snapshot\r\n"),
                call(ctx._shard_display_snapshot()),
                call(ctx._gear_settings_snapshot()),
            ],
        )

    def test_shard_display_snapshot_is_seed_scoped_and_replayable(self):
        ctx = self.make_context()
        for mask in range(-1, 16):
            ctx.eternia_shard_mask = mask
            self.assertEqual(ctx._shard_display_snapshot(),
                f"APSHARDS1|{ctx._live_seed_identity()}|{mask}\r\n".encode('ascii'))

    def test_pet_option_live_transport(self):
        ctx = self.make_context()
        for enabled in (False, True):
            ctx.slot_data['random_gear_pets'] = enabled
            self.assertEqual(ctx._gear_settings_snapshot(),
                f"APGEAR1|{ctx._live_seed_identity()}|{int(enabled)}\r\n".encode('ascii'))

    async def test_live_update_can_be_scheduled_from_packet_callback_thread(self):
        """ReceivedItems remains live if Archipelago invokes the callback off-loop."""
        ctx = self.make_context()
        applied = asyncio.Event()

        async def marker():
            applied.set()

        thread = threading.Thread(target=lambda: ctx._schedule_task(marker()))
        thread.start()
        thread.join()
        await asyncio.wait_for(applied.wait(), timeout=1)

    async def test_unrelated_localhost_connection_is_not_game_ready(self):
        ctx = self.make_context()
        ctx.live_snapshot = "APSTATE3|test\r\n"
        reader = asyncio.StreamReader()
        reader.feed_data(b"GET / HTTP/1.1\r\n")
        reader.feed_eof()
        writer = self.make_writer()
        with self.assertLogs(client.logger, level="WARNING"):
            await ctx._handle_live_game(reader, writer)
        self.assertFalse(ctx.game_connected_once)
        writer.write.assert_not_called()
        writer.close.assert_called_once()

    async def test_server_sent_item_message_uses_archipelago_name(self):
        ctx = self.make_context()
        ctx._broadcast_item_message = AsyncMock()
        item = types.SimpleNamespace(item=123, player=0)
        ctx.on_package("PrintJSON", {
            "type": "ItemSend",
            "item": item,
            "receiving": ctx.slot,
        })
        await asyncio.sleep(0)
        ctx._broadcast_item_message.assert_awaited_once_with(
            "You received Test Item from Archipelago"
        )

    async def test_saved_reward_is_retried_after_temporary_permission_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = self.make_context(root)
            ctx.state_path = root / "state.json"
            client.atomic_write_json(ctx.state_path, client.empty_bridge_state())
            packet = {"index": 0, "items": [{
                "item": client.ITEM_NAME_TO_ID["Squire"], "location": -2, "player": 1,
            }]}
            original_write = client.write_unlock_ini
            attempts = 0

            def temporary_failure(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError("unlock file is temporarily locked")
                return original_write(*args, **kwargs)

            with patch.object(client, "write_unlock_ini", side_effect=temporary_failure):
                with self.assertLogs(client.logger, level="ERROR"):
                    ctx.on_package("ReceivedItems", packet)
                self.assertTrue(ctx.unlock_write_pending)
                self.assertEqual(client.load_bridge_state(ctx.state_path)["last_received_index"], 0)
                # The AP server replay contains no new items, but a queued
                # failed write must remain eligible for the poll-loop retry.
                ctx.on_package("ReceivedItems", packet)
                self.assertTrue(ctx._retry_pending_unlocks(force=True))
            self.assertFalse(ctx.unlock_write_pending)
            self.assertIn("UnlockedHeroes=squire", ctx.unlock_path.read_text())
            self.assertIn("ExperienceMultiplier=4", ctx.unlock_path.read_text())
            self.assertEqual(attempts, 2)

    async def test_event_poll_cannot_overwrite_concurrently_received_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = self.make_context(root)
            ctx.state_path = root / "state.json"
            state = client.empty_bridge_state()
            state['content_settings'] = client.ContentSettings().slot_data()
            client.atomic_write_json(ctx.state_path, state)
            ctx._reconcile_checks = AsyncMock()
            packet = {"index": 0, "items": [{
                "item": client.ITEM_NAME_TO_ID["Squire"], "location": -2, "player": 1,
            }]}
            loop = asyncio.get_running_loop()
            loop_thread = threading.get_ident()
            packet_saved = threading.Event()
            service_globals = client.receive_live_event.__globals__
            original_load = service_globals["load_bridge_state"]

            def receive_packet():
                try:
                    ctx.on_package("ReceivedItems", packet)
                finally:
                    packet_saved.set()
                    ctx.exit_event.set()

            def load_then_schedule_packet(path):
                state = original_load(path)
                loop.call_soon_threadsafe(receive_packet)
                # Reproduce the old race deterministically if polling is ever
                # moved back to a worker without serializing state writers.
                # On the event-loop thread the packet runs after this save.
                if threading.get_ident() != loop_thread:
                    if not packet_saved.wait(2):
                        raise AssertionError("ReceivedItems did not run during the worker poll")
                return state

            with patch.dict(service_globals, {
                "load_bridge_state": load_then_schedule_packet,
            }):
                reader = asyncio.StreamReader()
                reader.feed_data(("DD1HELLO10\nDD1EVENT2|" + ctx._live_seed_identity()
                                  + "|wave_complete|DD_Lev_02|1|EGD_EASY|campaign|CAMPDW\n").encode())
                reader.feed_eof()
                await asyncio.wait_for(ctx._handle_live_game(reader, self.make_writer()), timeout=3)
                await asyncio.sleep(0)
            state = client.load_bridge_state(ctx.state_path)
            self.assertEqual(len(state["received_items"]), 1)
            self.assertEqual(state["last_received_index"], 0)
            self.assertEqual(len(state["processed_files"]), 1)
            self.assertTrue(state["processed_files"][0].startswith("tcp:"))

    async def test_failed_process_query_cannot_switch_hero_save(self):
        ctx = self.make_context()
        query = types.SimpleNamespace(returncode=1, stdout="", stderr="Access denied")
        with patch.object(client.subprocess, "run", return_value=query), \
                patch.object(client.Utils, "user_path", return_value="unused-profiles", create=True), \
                patch.object(client, "switch_hero_profile") as switch:
            with self.assertRaisesRegex(client.ProtocolError, "no hero save was switched"):
                ctx._activate_seed_hero_save()
        switch.assert_not_called()

    async def test_successful_empty_process_query_allows_hero_save_switch(self):
        ctx = self.make_context()
        query = types.SimpleNamespace(returncode=0, stdout="No tasks are running.", stderr="")
        with patch.object(client.subprocess, "run", return_value=query), \
                patch.object(client.Utils, "user_path", return_value="unused-profiles", create=True), \
                patch.object(client, "switch_hero_profile", return_value="test-key") as switch:
            ctx._activate_seed_hero_save()
        switch.assert_called_once()

    async def test_no_handshake_timeout_has_clear_game_status(self):
        ctx = self.make_context()

        async def stop_after_warning(delay):
            ctx.exit_event.set()

        with patch.object(client, "GAME_CONNECT_TIMEOUT", 0), patch.object(client.asyncio, "sleep", side_effect=stop_after_warning):
            with self.assertLogs(client.logger, level="WARNING") as messages:
                await ctx._watch_game_connection()
        self.assertIn("mod has not connected", " ".join(messages.output))

    async def test_process_exit_before_handshake_is_reported(self):
        ctx = self.make_context()
        ctx.launched_game = Mock()
        ctx.launched_game.poll.return_value = 7
        with self.assertLogs(client.logger, level="ERROR") as messages:
            await ctx._watch_game_connection()
        self.assertIn("closed before the AP mod connected", " ".join(messages.output))

    async def test_install_failure_opens_error_window_before_gui_startup(self):
        parser = Mock()
        parser.parse_args.return_value = argparse.Namespace(game_root=None, select_game_folder=False)
        parser.error.side_effect = SystemExit(2)
        popup = Mock()
        with patch.object(client, "get_base_parser", return_value=parser), \
                patch.object(client, "gui_enabled", True), \
                patch.object(client.CommonClient, "handle_url_arg", side_effect=lambda args, **kwargs: args, create=True), \
                patch.object(client.Utils, "messagebox", popup, create=True), \
                patch.object(client.Utils, "user_path", return_value="unused/game-install.json", create=True), \
                patch.object(client, "select_retail_root", side_effect=ValueError("Mod configuration is missing")):
            with self.assertRaises(SystemExit):
                client.launch()
        popup.assert_called_once_with(
            "Dungeon Defenders installation", "Mod configuration is missing", error=True,
        )
        parser.error.assert_called_once_with("Mod configuration is missing")


class ManualFolderLaunchTests(unittest.TestCase):
    def setUp(self):
        from test_dd1_retail_install import RetailInstallTests
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = RetailInstallTests().make_install(self.root / 'selected game')
        self.settings = self.root / 'client/game-install.json'
        self.picker = Mock(return_value=str(self.game))
        self.main = AsyncMock()
        patches = [
            patch.object(client, 'get_base_parser', side_effect=lambda **kw: argparse.ArgumentParser(**kw)),
            patch.object(client.CommonClient, 'handle_url_arg', side_effect=lambda args, **kw: args, create=True),
            patch.object(client.Utils, 'user_path', return_value=str(self.settings), create=True),
            patch.object(client.Utils, 'open_directory', self.picker, create=True),
            patch.object(client, 'gui_enabled', True),
            patch.object(client, '_main', self.main),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_first_launch_prompts_then_reuses_choice(self):
        client.launch()
        self.picker.assert_called_once_with('Select your Dungeon Defenders game folder')
        self.assertEqual(self.main.call_args.args[0].game_root, self.game.resolve())
        self.assertTrue(self.main.call_args.args[0].launch_game)
        client.launch()
        self.assertEqual(self.picker.call_count, 1)
        self.assertEqual(self.main.await_count, 2)

    def test_cancel_never_starts_client_or_game(self):
        self.picker.return_value = None
        client.launch()
        self.main.assert_not_called()
        self.assertFalse(self.settings.exists())

    def test_explicit_path_and_no_launch_still_remember_manual_choice(self):
        client.launch('--game-root', str(self.game), '--no-launch-game')
        self.picker.assert_not_called()
        self.assertFalse(self.main.call_args.args[0].launch_game)
        self.assertEqual(self.main.call_args.args[0].game_root, self.game.resolve())

    def test_reselection_cancel_does_not_launch_or_erase_choice(self):
        client.launch('--game-root', str(self.game))
        original = self.settings.read_bytes()
        self.main.reset_mock()
        self.picker.return_value = None
        client.launch('--select-game-folder')
        self.main.assert_not_called()
        self.assertEqual(self.settings.read_bytes(), original)

    def test_cli_selection_without_gui(self):
        with patch.object(client, 'gui_enabled', False), patch('builtins.input', return_value=str(self.game)):
            client.launch()
        self.picker.assert_not_called()
        self.assertEqual(self.main.call_args.args[0].game_root, self.game.resolve())

    def test_picker_failure_never_starts_client(self):
        self.picker.side_effect = RuntimeError('No display available')
        with patch.object(client.Utils, 'messagebox', create=True), self.assertRaises(SystemExit):
            client.launch()
        self.main.assert_not_called()
        self.assertFalse(self.settings.exists())


if __name__ == "__main__":
    unittest.main()
