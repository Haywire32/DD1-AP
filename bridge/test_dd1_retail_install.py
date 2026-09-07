import tempfile
import unittest
from pathlib import Path

from dd1_install import find_retail_root, validate_retail_install, RETAIL_EXECUTABLE


class RetailInstallTests(unittest.TestCase):
    def make_install(self, root):
        exe = root / RETAIL_EXECUTABLE
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"stock exe fixture")
        tc = root / "TotalConversions" / "DD1ArchipelagoCurrent"
        (tc / "CookedPCConsole").mkdir(parents=True)
        for name in ("Startup_INT.upk", "TC_Textures.tfc", "TC_CharTextures.tfc",
                     "RefShaderCache_TC_-PC-D3D-SM3.upk"):
            (tc / "CookedPCConsole" / name).write_bytes(b"package fixture")
        (tc / "Config").mkdir()
        (tc / "Config" / "DefaultEngine.ini").write_text(
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

    def test_finds_registered_secondary_steam_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steam, library = root / "Steam", root / "Other Drive"
            expected = self.make_install(library / "steamapps" / "common" / "Custom DD1")
            (steam / "steamapps").mkdir(parents=True)
            escaped = str(library).replace("\\", "\\\\")
            (steam / "steamapps" / "libraryfolders.vdf").write_text(f'"1" {{ "path" "{escaped}" }}')
            (library / "steamapps" / "appmanifest_65800.acf").write_text(
                '"appid" "65800" "StateFlags" "4" "installdir" "Custom DD1"')
            self.assertEqual(find_retail_root(steam_install_roots=[steam]), expected.resolve())

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
