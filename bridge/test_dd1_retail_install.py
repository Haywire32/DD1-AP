import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dd1_install import (find_retail_root, select_retail_root, validate_retail_install, RETAIL_EXECUTABLE,
                         REQUIRED_COOKED_FILES, STARTUP_URL)


class RetailInstallTests(unittest.TestCase):
    def make_install(self, root):
        exe = root / RETAIL_EXECUTABLE
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"stock exe fixture")
        tc = root / "TotalConversions" / "DD1ArchipelagoCurrent"
        (tc / "CookedPCConsole").mkdir(parents=True)
        for name in REQUIRED_COOKED_FILES:
            (tc / "CookedPCConsole" / name).write_bytes(b"package fixture")
        (tc / "Config").mkdir()
        (tc / "Config" / "DefaultEngine.ini").write_text(
            '[URL]\n' + ''.join(f'{k}={v}\n' for k,v in STARTUP_URL.items()) +
            "[Engine.Engine]\nGameViewportClientClassName=DD1Archipelago.APViewportClient\n"
            "[OnlineSubsystemSteamworks.OnlineSubsystemSteamworks]\nbUseVAC=false\n")
        (tc / "Config" / "DefaultGame.ini").write_text(
            "[Engine.GameInfo]\nDefaultGame=DD1Archipelago.APGameInfo\n"
            "DefaultServerGame=DD1Archipelago.APGameInfo\n")
        return root

    def test_explicit_install_accepts_fresh_settings_without_generated_inis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "Different Drive" / "DD1")
            self.assertEqual(find_retail_root(root), root.resolve())

    def test_private_install_never_falls_back_to_public_or_edits_public_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.make_install(Path(tmp)/'DD1')
            public=root/'TotalConversions/DD1ArchipelagoCurrent'
            with self.assertRaises(FileNotFoundError):
                find_retail_root(root,tc_directory='DD1ArchipelagoChaos')
            import shutil
            private=root/'TotalConversions/DD1ArchipelagoChaos'
            shutil.copytree(public,private)
            self.assertEqual(find_retail_root(root,tc_directory='DD1ArchipelagoChaos'),root.resolve())
            original=(public/'Config/DefaultEngine.ini').read_bytes()
            validate_retail_install(root,tc_directory='DD1ArchipelagoChaos')
            self.assertEqual((public/'Config/DefaultEngine.ini').read_bytes(),original)
            self.assertEqual((private/'Config/DefaultEngine.ini').read_bytes(),original)
            for bad in ('../UDKGame','',str(root),'DD1Other'):
                with self.assertRaises(ValueError):
                    validate_retail_install(root,tc_directory=bad)

    def test_generated_utf16_ini_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / 'DD1')
            config = root / 'TotalConversions/DD1ArchipelagoCurrent/Config'
            for part in ('Engine', 'Game'):
                (config / f'UDK{part}.ini').write_bytes(
                    (config / f'Default{part}.ini').read_text().encode('utf-16'))
            validate_retail_install(root)

    def test_no_folder_never_attempts_discovery(self):
        with patch("dd1_install.Path.read_text", side_effect=AssertionError("Unexpected read")), \
                patch("dd1_install.Path.is_file", side_effect=AssertionError("Unexpected probe")):
            with self.assertRaisesRegex(ValueError, "Select your"):
                find_retail_root()

    def test_manual_selection_saved_and_reused_without_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "Other Drive" / "Düngéon Defenders")
            settings = Path(tmp) / "client" / "game-install.json"
            picker = Mock(return_value=str(root))
            self.assertEqual(select_retail_root(None, settings, picker), root.resolve())
            picker.assert_called_once_with()
            self.assertEqual(json.loads(settings.read_text())["game_root"], str(root.resolve()))
            picker.reset_mock()
            self.assertEqual(select_retail_root(None, settings, picker), root.resolve())
            picker.assert_not_called()

    def test_cancel_does_not_create_settings_or_select_any_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_install(Path(tmp) / "Steam/steamapps/common/Dungeon Defenders")
            settings = Path(tmp) / "client/game-install.json"
            self.assertIsNone(select_retail_root(None, settings, lambda: None))
            self.assertFalse(settings.parent.exists())

    def test_explicit_choice_overrides_saved_choice_and_skips_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.make_install(Path(tmp) / "first")
            second = self.make_install(Path(tmp) / "second")
            settings = Path(tmp) / "game-install.json"
            select_retail_root(first, settings, lambda: self.fail("Unexpected picker"))
            self.assertEqual(select_retail_root(second, settings, lambda: self.fail("Unexpected picker")),
                             second.resolve())
            self.assertEqual(json.loads(settings.read_text())["game_root"], str(second.resolve()))

    def test_invalid_choice_does_not_replace_saved_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "valid")
            settings = Path(tmp) / "game-install.json"
            select_retail_root(root, settings, lambda: None)
            original = settings.read_bytes()
            with self.assertRaises(FileNotFoundError):
                select_retail_root(None, settings, lambda: str(Path(tmp) / "wrong"),
                                   force_select=True)
            self.assertEqual(settings.read_bytes(), original)
            with self.assertRaises(FileNotFoundError):
                select_retail_root(Path(tmp) / "wrong", settings,
                                   lambda: self.fail("No fallback for an invalid explicit choice"))
            self.assertEqual(settings.read_bytes(), original)

    def test_missing_saved_install_requires_new_manual_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "moved")
            settings = Path(tmp) / "game-install.json"
            settings.write_text(json.dumps({"version": 1, "game_root": str(Path(tmp) / "old")}))
            picker = Mock(return_value=str(root))
            self.assertEqual(select_retail_root(None, settings, picker), root.resolve())
            picker.assert_called_once_with()

    def test_corrupt_or_nonabsolute_saved_path_requires_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "game-install.json"
            for contents in ('broken', '[]', '{"version": 1, "game_root": 42}',
                             '{"version": 1, "game_root": "relative"}',
                             '{"version": 2, "game_root": "ignored"}'):
                settings.write_text(contents)
                picker = Mock(return_value=None)
                self.assertIsNone(select_retail_root(None, settings, picker))
                picker.assert_called_once_with()
                self.assertEqual(settings.read_text(), contents)

    def test_reselect_cancel_preserves_existing_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "valid")
            settings = Path(tmp) / "game-install.json"
            select_retail_root(root, settings, lambda: None)
            original = settings.read_bytes()
            self.assertIsNone(select_retail_root(None, settings, lambda: None, force_select=True))
            self.assertEqual(settings.read_bytes(), original)

    def test_generated_settings_cannot_disable_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "DD1")
            path = root / "TotalConversions" / "DD1ArchipelagoCurrent" / "Config" / "UDKEngine.ini"
            path.write_text("[Engine.Engine]\nGameViewportClientClassName=UDKGame.DunDefViewportClient\n")
            with self.assertRaises(ValueError):
                validate_retail_install(root)

    def test_missing_game_is_read_only_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                find_retail_root(root)
            self.assertFalse(list(root.iterdir()))

    def test_missing_texture_cache_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "DD1")
            (root / "TotalConversions" / "DD1ArchipelagoCurrent" / "CookedPCConsole" / "TC_Textures.tfc").unlink()
            with self.assertRaises(FileNotFoundError):
                validate_retail_install(root)
