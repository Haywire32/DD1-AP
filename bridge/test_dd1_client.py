"""Exercise real DD1 client paths with the Archipelago UI/network boundary stubbed."""

import asyncio
import argparse
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


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

        async def disconnect(self):
            pass

        async def shutdown(self):
            pass

        async def send_msgs(self, messages):
            pass

    common = types.ModuleType("CommonClient")
    common.CommonContext = CommonContext
    common.get_base_parser = Mock()
    common.gui_enabled = False
    common.server_loop = AsyncMock()
    base = types.ModuleType("BaseClasses")
    base.ItemClassification = types.SimpleNamespace(progression=1, filler=0)
    net = types.ModuleType("NetUtils")
    net.ClientStatus = types.SimpleNamespace(CLIENT_GOAL=30)
    with patch.dict(sys.modules, {
        "CommonClient": common, "Utils": types.ModuleType("Utils"),
        "NetUtils": net, "BaseClasses": base,
    }):
        return importlib.import_module("dd1_client_under_test.Client")


client = load_client()


class ClientPortabilityTests(unittest.IsolatedAsyncioTestCase):
    def make_context(self, root=Path("unused")):
        ctx = client.DungeonDefendersContext(None, None, root, True)
        ctx.seed_name = "portability-test"
        ctx.slot_data = {"starting_hero": "apprentice", "starting_map": "CAMPDW"}
        return ctx

    def make_writer(self):
        writer = Mock()
        writer.get_extra_info.return_value = ("127.0.0.1", 50000)
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        return writer

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
        with patch.object(client.asyncio, "start_server", side_effect=bind):
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
        reader.feed_data(b"DD1HELLO1\nDD1PING1\n")
        reader.feed_eof()
        with self.assertLogs(client.logger, level="INFO") as messages:
            await handler
        self.assertTrue(ctx.game_connected_once)
        self.assertIn("Game connected", " ".join(messages.output))
        writer.write.assert_any_call(b"APSTATE3|test\r\n")
        writer.write.assert_any_call(b"DD1PONG1\r\n")

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
            self.assertEqual(attempts, 2)

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
        parser.parse_args.return_value = argparse.Namespace(dddk_root=None)
        parser.error.side_effect = SystemExit(2)
        popup = Mock()
        with patch.object(client, "get_base_parser", return_value=parser), \
                patch.object(client, "gui_enabled", True), \
                patch.object(client.CommonClient, "handle_url_arg", side_effect=lambda args, **kwargs: args, create=True), \
                patch.object(client.Utils, "messagebox", popup, create=True), \
                patch.object(client, "find_dddk_root", side_effect=ValueError("Mod configuration is missing")):
            with self.assertRaises(SystemExit):
                client.launch()
        popup.assert_called_once_with(
            "Dungeon Defenders installation", "Mod configuration is missing", error=True,
        )
        parser.error.assert_called_once_with("Mod configuration is missing")


if __name__ == "__main__":
    unittest.main()
