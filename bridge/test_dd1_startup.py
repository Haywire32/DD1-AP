"""Startup-only regressions: no real game, user settings or network touched."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
from zipfile import ZipFile

from dd1_install import (REQUIRED_COOKED_FILES, STARTUP_URL, _ini_settings,
                         validate_retail_install, verify_conversion_package)
import test_dd1_retail_install as install_tests
import test_dd1_client as client_tests

client = client_tests.client

ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = install_tests.RetailInstallTests().make_install(Path(self.tmp.name)/'DD1')
        self.tc = self.root/'TotalConversions/DD1ArchipelagoCurrent'
        self.config = self.tc/'Config'
        self.default = self.config/'DefaultEngine.ini'
        self.generated = self.config/'UDKEngine.ini'

    def snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def manifest(self):
        files = {f'CookedPCConsole/{n}': dict(size=(self.tc/'CookedPCConsole'/n).stat().st_size,
            sha256=hashlib.sha256((self.tc/'CookedPCConsole'/n).read_bytes()).hexdigest()) for n in REQUIRED_COOKED_FILES}
        data = dict(format=1, files=files)
        (self.tc/'package-manifest.json').write_text(json.dumps(data))
        return data

    def test_bearkat_missing_url_cache_is_rejected_without_writing(self):
        # All other mod activation checks pass, as in the supplied report.
        self.generated.write_text('[Engine.Engine]' + self.default.read_text().split('[Engine.Engine]')[1])
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, r'UDKEngine.ini: Protocol, Map, LocalMap'):
            validate_retail_install(self.root)
        self.assertEqual(before, self.snapshot())

    def test_partial_or_blank_startup_cache_is_rejected(self):
        for key in ('Protocol', 'Map', 'LocalMap', 'TransitionMap', 'MapExt', 'Port'):
            with self.subTest(key=key):
                self.generated.write_text(self.default.read_text().replace(f'{key}={STARTUP_URL[key]}\n', f'{key}=\n'))
                with self.assertRaisesRegex(ValueError, key):
                    validate_retail_install(self.root)

    def test_inherited_default_is_valid_but_generated_cache_is_not_a_delta(self):
        text = self.default.read_text()
        for key, value in STARTUP_URL.items():
            if key not in ('Map', 'LocalMap'):
                text = text.replace(f'{key}={value}\n', '')
        self.default.write_text(text)
        validate_retail_install(self.root)
        self.generated.write_text(text)
        with self.assertRaisesRegex(ValueError, 'Protocol'):
            validate_retail_install(self.root)

    def test_wrong_startup_map_rejected(self):
        self.generated.write_text(self.default.read_text()+'\n[URL]\nLocalMap=Entry\n')
        with self.assertRaisesRegex(ValueError, 'LocalMap'):
            validate_retail_install(self.root)

    def test_encodings_and_auto_language_are_read_only(self):
        text = self.default.read_text()+'\n[SystemSettings]\nGameLanguageOverride=AUTO\nResX=2548\nResY=1371\n'
        for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'utf-16-be'):
            with self.subTest(encoding=encoding):
                raw = text.encode(encoding)
                if encoding == 'utf-16-be':
                    raw = b'\xfe\xff'+raw
                self.generated.write_bytes(raw)
                before = self.snapshot()
                validate_retail_install(self.root)
                self.assertEqual(before, self.snapshot())

    def test_invalid_text_is_actionable_not_a_raw_decode_error(self):
        for raw in (b'\x80\x81', b'[Engine.Engine]\n\x00bad'):
            self.generated.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'UDKEngine.ini'):
                validate_retail_install(self.root)

    def test_missing_entry_map_now_detected(self):
        (self.tc/'CookedPCConsole/DunDefEntry.upk').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'DunDefEntry.upk'):
            validate_retail_install(self.root)

    def test_manifest_good_and_legacy_are_read_only(self):
        self.assertIn('legacy', verify_conversion_package(self.root))
        self.manifest()
        before = self.snapshot()
        self.assertIn('verified', verify_conversion_package(self.root))
        self.assertEqual(before, self.snapshot())

    def test_same_size_wrong_version_and_truncated_package_rejected(self):
        self.manifest()
        path = self.tc/'CookedPCConsole/Startup_INT.upk'
        for raw in (b'x'*path.stat().st_size, b'x'):
            path.write_bytes(raw)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'Startup_INT.upk'):
                verify_conversion_package(self.root)
            self.assertEqual(before, self.snapshot())

    def test_invalid_manifests_do_not_read_arbitrary_paths(self):
        good = self.manifest()
        for data in ([], {'format':2, 'files':good['files']}, {'format':1, 'files':{}},
                     dict(format=1, files={**good['files'], '../save.dun':dict(size=1, sha256='0'*64)})):
            (self.tc/'package-manifest.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Cannot verify'):
                verify_conversion_package(self.root)

    def test_packaged_defaults_match_build_and_cover_full_startup(self):
        release = ROOT/'release/Config/DefaultEngine.ini'
        settings = _ini_settings(release)
        self.assertEqual(settings, _ini_settings(ROOT/'game/BuildConfig/DefaultEngine.ini'))
        for key,value in STARTUP_URL.items():
            self.assertEqual(settings[('url', key.casefold())], value.casefold())
        self.assertEqual(settings[('systemsettings', 'gamelanguageoverride')], 'int')
        self.assertEqual({key for section,key in settings if section == 'systemsettings'}, {'gamelanguageoverride'})

    def test_package_builder_excludes_generated_settings_saves_and_executables(self):
        spec = importlib.util.spec_from_file_location('build_conversion', ROOT/'tools/build_conversion.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        baseline, output = Path(self.tmp.name)/'base.zip', Path(self.tmp.name)/'out.zip'
        with ZipFile(baseline, 'w') as z:
            for p in self.tc.rglob('*'):
                if p.is_file():
                    z.write(p, builder.PREFIX+p.relative_to(self.tc).as_posix())
            for name in ('Config/UDKEngine.ini', 'Config/DunDefHeroes.dun', 'Config/DD1ArchipelagoUnlocks.ini', 'Binaries/test.exe'):
                z.writestr(builder.PREFIX+name, b'never ship this')
        builder.build(ROOT, baseline, output)
        with ZipFile(output) as z:
            self.assertIsNone(z.testzip())
            names = {n.removeprefix(builder.PREFIX) for n in z.namelist()}
            self.assertEqual(names, {f'CookedPCConsole/{n}' for n in REQUIRED_COOKED_FILES} |
                             {'Config/DefaultEngine.ini','Config/DefaultGame.ini','package-manifest.json'})
            z.extractall(Path(self.tmp.name)/'extracted')
        verify_conversion_package(Path(self.tmp.name)/'extracted')
        with self.assertRaises(FileExistsError):
            builder.build(ROOT, baseline, output)


class LaunchTests(unittest.IsolatedAsyncioTestCase):
    def context(self, root):
        return client_tests.ClientPortabilityTests().make_context(root)

    async def test_windows_launch_selects_int_and_does_not_edit_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = install_tests.RetailInstallTests().make_install(Path(tmp)/'DD1')
            config = root/'TotalConversions/DD1ArchipelagoCurrent/Config'
            generated = config/'UDKEngine.ini'
            generated.write_text((config/'DefaultEngine.ini').read_text()+'\n[SystemSettings]\nGameLanguageOverride=FRA\nResX=2548\n')
            before = {p.name:p.read_bytes() for p in config.glob('*.ini')}
            ctx = self.context(root)
            with patch.object(client.sys, 'platform', 'win32'), patch.object(client.subprocess, 'Popen', return_value=Mock(pid=42)) as popen:
                ctx._launch_local_game()
            command = popen.call_args.args[0]
            self.assertIn('-LANGUAGE=INT', command)
            self.assertIn('-TOTALCONVERSION=DD1ArchipelagoCurrent', command)
            self.assertEqual(before, {p.name:p.read_bytes() for p in config.glob('*.ini')})

    async def test_flatpak_also_passes_language_override(self):
        ctx = self.context(Path('/linux/game'))
        with patch.object(client.sys, 'platform', 'linux'), patch.object(client, 'validate_retail_install'), \
                patch.object(client.shutil, 'which', side_effect=lambda n:'/usr/bin/flatpak' if n=='flatpak' else None), \
                patch.object(client.subprocess, 'Popen', return_value=Mock(pid=42)) as popen:
            ctx._launch_local_game()
        self.assertEqual(popen.call_args.args[0][:4], ['/usr/bin/flatpak','run','com.valvesoftware.Steam','-applaunch'])
        self.assertIn('-LANGUAGE=INT', popen.call_args.args[0])

    async def test_failed_package_check_never_launches_game(self):
        ctx = self.context(Path('unused'))
        with patch.object(client, 'validate_retail_install'), \
                patch.object(client, 'verify_conversion_package', side_effect=ValueError('mixed files')), \
                patch.object(client.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'mixed files'):
                ctx._launch_local_game()
        popen.assert_not_called()

    async def test_failed_package_check_precedes_seed_and_save_mutations(self):
        ctx = self.context(Path('unused'))
        ctx._select_slot_state = Mock()
        ctx._activate_seed_hero_save = Mock()
        ctx._apply_unlocks = Mock()
        ctx.disconnect = AsyncMock()
        with patch.object(client, 'validate_retail_install'), \
                patch.object(client, 'verify_conversion_package', side_effect=ValueError('mixed files')), \
                self.assertLogs(client.logger, level='ERROR'):
            ctx.on_package('Connected', {'slot_data':ctx.slot_data})
            await asyncio.sleep(0)
        ctx._select_slot_state.assert_not_called()
        ctx._activate_seed_hero_save.assert_not_called()
        ctx._apply_unlocks.assert_not_called()
        ctx.disconnect.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
