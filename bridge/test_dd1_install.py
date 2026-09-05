import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dd1_install import DDDK_EXECUTABLE, find_dddk_root, validate_dddk_install


class DDDKDiscoveryTests(unittest.TestCase):
    @staticmethod
    def make_dddk(library: Path) -> Path:
        root = library / "steamapps" / "common" / "DungeonDefendersDevelopmentKit"
        DDDKDiscoveryTests.install_mod(root)
        return root

    @staticmethod
    def install_mod(root: Path) -> None:
        executable = root / DDDK_EXECUTABLE
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(b"test executable")
        tc_root = root / "TotalConversions" / "DD1ArchipelagoCurrent"
        (tc_root / "Script").mkdir(parents=True, exist_ok=True)
        for name in ("DD1Archipelago.u", "UDKGame.u"):
            (tc_root / "Script" / name).write_bytes(b"test script")
        (tc_root / "Config").mkdir(parents=True, exist_ok=True)
        for prefix in ("Default", "UDK"):
            (tc_root / "Config" / f"{prefix}Engine.ini").write_text(
                "[Engine.Engine]\nGameViewportClientClassName=DD1Archipelago.APViewportClient\n",
                encoding="utf-8",
            )
            (tc_root / "Config" / f"{prefix}Game.ini").write_text(
                "[Engine.GameInfo]\nDefaultGame=DD1Archipelago.APGameInfo\n"
                "DefaultServerGame=DD1Archipelago.APGameInfo\n", encoding="utf-8",
            )

    @staticmethod
    def register_library(steam: Path, library: Path) -> None:
        (steam / "steamapps").mkdir(parents=True, exist_ok=True)
        escaped = str(library).replace("\\", "\\\\")
        (steam / "steamapps" / "libraryfolders.vdf").write_text(
            f'"libraryfolders"\n{{\n"1"\n{{\n"path" "{escaped}"\n}}\n}}\n', encoding="utf-8",
        )

    def test_finds_default_steam_library(self):
        with tempfile.TemporaryDirectory() as directory:
            steam = Path(directory) / "Steam"
            expected = self.make_dddk(steam)
            self.assertEqual(
                find_dddk_root(steam_install_roots=[steam]), expected.resolve()
            )

    def test_finds_registered_secondary_library(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            steam = base / "Steam"
            library = base / "Games"
            (steam / "steamapps").mkdir(parents=True)
            escaped = str(library).replace("\\", "\\\\")
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders"\n{{\n\t"1"\n\t{{\n\t\t"path" "{escaped}"\n\t}}\n}}\n',
                encoding="utf-8",
            )
            expected = self.make_dddk(library)
            self.assertEqual(
                find_dddk_root(steam_install_roots=[steam]), expected.resolve()
            )

    def test_explicit_folder_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CustomDDDK"
            self.install_mod(root)
            self.assertEqual(find_dddk_root(root), root.resolve())

    def test_missing_install_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "not found in any Steam library"):
                find_dddk_root(steam_install_roots=[Path(directory) / "Steam"])

    def test_missing_mod_is_rejected_without_creating_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / DDDK_EXECUTABLE
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"test executable")
            with self.assertRaisesRegex(FileNotFoundError, "installation is incomplete"):
                find_dddk_root(root)
            self.assertFalse((root / "TotalConversions").exists())

    def test_unmodded_first_library_does_not_hide_modded_library(self):
        with tempfile.TemporaryDirectory() as directory:
            steam, library = Path(directory) / "Steam", Path(directory) / "Games"
            first = steam / "steamapps" / "common" / "DungeonDefendersDevelopmentKit"
            executable = first / DDDK_EXECUTABLE
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"test executable")
            expected = self.make_dddk(library)
            self.register_library(steam, library)
            self.assertEqual(find_dddk_root(steam_install_roots=[steam]), expected.resolve())
            self.assertFalse((first / "TotalConversions").exists())

    def test_steam_manifest_install_wins_over_leftover_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            steam, library = Path(directory) / "Steam", Path(directory) / "Games"
            self.make_dddk(steam)
            expected = self.make_dddk(library)
            self.register_library(steam, library)
            (library / "steamapps" / "appmanifest_216840.acf").write_text(
                '"AppState"\n{\n"appid" "216840"\n"StateFlags" "4"\n'
                '"installdir" "DungeonDefendersDevelopmentKit"\n}\n', encoding="utf-8",
            )
            self.assertEqual(find_dddk_root(steam_install_roots=[steam]), expected.resolve())

    def test_ambiguous_modded_installs_are_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            steam, library = Path(directory) / "Steam", Path(directory) / "Games"
            self.make_dddk(steam)
            self.make_dddk(library)
            self.register_library(steam, library)
            with self.assertRaisesRegex(ValueError, "More than one.*--dddk-root"):
                find_dddk_root(steam_install_roots=[steam])

    def test_all_four_activation_configs_are_required(self):
        for filename in ("DefaultEngine.ini", "DefaultGame.ini", "UDKEngine.ini", "UDKGame.ini"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = self.make_dddk(Path(directory))
                path = root / "TotalConversions" / "DD1ArchipelagoCurrent" / "Config" / filename
                path.write_text("[Configuration]\nBasedOn=vanilla.ini\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mod is not enabled"):
                    validate_dddk_install(root)

    def test_empty_or_missing_overlay_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_dddk(Path(directory))
            path = root / "TotalConversions" / "DD1ArchipelagoCurrent" / "Script" / "UDKGame.u"
            path.write_bytes(b"")
            with self.assertRaisesRegex(FileNotFoundError, "UDKGame.u"):
                validate_dddk_install(root)


if __name__ == "__main__":
    unittest.main()
