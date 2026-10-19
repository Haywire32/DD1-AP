import importlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from dd1_traps import TRAP_NAMES, TRAP_KEYS, replace_filler_with_traps, trap_snapshot
import test_dd1_client as client_tests

client = client_tests.client
ROOT = Path(__file__).resolve().parents[1]


class TrapTests(unittest.TestCase):
    def test_balanced_replacement_and_protected_items(self):
        original = ['mana'] * 70 + ['hero', 'defense', 'skin']
        result = replace_filler_with_traps(original, 50, TRAP_KEYS, random.Random(7), {'mana'})
        self.assertEqual(len(result), len(original))
        self.assertEqual(result[-3:], original[-3:])
        self.assertEqual(result.count('mana'), 35)
        for name in TRAP_NAMES:
            self.assertEqual(result.count(name), 5)
        self.assertEqual(original.count('mana'), 70)

    def test_off_has_no_rng_side_effect(self):
        rng = random.Random(10)
        before = rng.getstate()
        self.assertEqual(replace_filler_with_traps(['mana'] * 10, 0, [], rng, {'mana'}), ['mana'] * 10)
        self.assertEqual(before, rng.getstate())

    def test_single_trap_and_invalid_choices(self):
        result = replace_filler_with_traps(['mana'] * 10, 100, ['skill_jam'], random.Random(1), {'mana'})
        self.assertEqual(result, ['Skill Jam'] * 10)
        for rate, enabled in ((-1, TRAP_KEYS), (101, TRAP_KEYS), (50, []), (0, ['invalid'])):
            with self.assertRaises(ValueError):
                replace_filler_with_traps(['mana'], rate, enabled, random.Random(1), {'mana'})

    def test_cumulative_snapshot(self):
        ids = dict(zip(TRAP_NAMES, range(100, 107)))
        received = [{'item_id': 100}, {'item_id': 106}, {'item_id': 100}, {'item_id': 10}]
        seed = 'dd1-' + 'a' * 64
        self.assertEqual(trap_snapshot(seed, received, ids),
            ('APTRAPS1|' + seed + '|2,0,0,0,0,0,1\r\n').encode())
        for seed in ('', 'bad|seed', 'dd1-' + 'g' * 64):
            with self.assertRaises(ValueError):
                trap_snapshot(seed, [], ids)

    def test_old_ids_are_unchanged_and_traps_are_classified(self):
        from zipfile import ZipFile
        frozen = ROOT.parents[2] / 'outputs/release/DD1-Archipelago-v0.8.0/dungeon_defenders.apworld'
        with ZipFile(frozen) as archive:
            old = {'__name__': client.__package__ + '.old_items', '__package__': client.__package__}
            base = type('Base', (), {'ItemClassification': type('Flags', (), {'filler':0,'useful':2,'progression':1,'trap':4})})
            with patch.dict('sys.modules', {'BaseClasses':base}):
                items = importlib.import_module(client.__package__ + '.items')
                exec(compile(archive.read('dungeon_defenders/items.py'), 'old_items.py', 'exec'), old)
        for name, item_id in old['ITEM_NAME_TO_ID'].items():
            self.assertEqual(items.ITEM_NAME_TO_ID[name], item_id)
        for name in TRAP_NAMES:
            self.assertEqual(items.ITEM_CLASSIFICATIONS[name], 4)
        from dd1_themes import THEME_NAMES
        self.assertEqual(len(items.ITEM_NAME_TO_ID), len(old['ITEM_NAME_TO_ID']) + 7 + len(THEME_NAMES))

    def test_all_map_skill_gates_are_covered(self):
        classes = ROOT / 'game/Classes'
        for source in classes.glob('AP*.uc'):
            text = source.read_text()
            if 'function bool ShouldDenyAPAbility(' in text:
                self.assertIn('Traps.DeniesAbility(Ability)', text, source.name)
                self.assertIn('Traps.SkillJammed()', text, source.name)

    def test_live_and_linux_file_packets_include_traps(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp, patch.object(client.sys, 'platform', 'linux'):
            ctx = client_tests.ClientPortabilityTests().make_context(Path(temp))
            ctx.state_path = Path(temp) / 'state.json'
            state = client.empty_bridge_state()
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            packets = ctx._snapshot_packets()
            self.assertEqual(sum(p.startswith(b'APTRAPS1|') for p in packets), 1)
            ctx._publish_file_snapshot()
            text = (Path(temp) / 'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm').read_text()
            self.assertIn('APTRAPS1|' + ctx._live_seed_identity() + '|0,0,0,0,0,0,0', text)
            packet = {'index':0, 'items':[
                {'item':client.ITEM_NAME_TO_ID[name], 'location':10+i, 'player':1}
                for i, name in enumerate(('Chicken!', 'Skill Jam', 'Chicken!'))]}
            self.assertEqual(client.ingest_mana_packet(state, packet, client.ITEM_NAME_TO_ID, ctx._live_seed_identity()), 3)
            self.assertEqual(client.ingest_mana_packet(state, packet, client.ITEM_NAME_TO_ID, ctx._live_seed_identity()), 0)
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks(); ctx._file_write_time=0; ctx._publish_file_snapshot()
            text = (Path(temp) / 'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm').read_text()
            self.assertIn('APTRAPS1|' + ctx._live_seed_identity() + '|2,0,0,1,0,0,0', text)

    def test_package_cooked_overrides_and_manifest(self):
        import hashlib
        import tempfile
        from zipfile import ZipFile
        from dd1_install import REQUIRED_COOKED_FILES
        spec = importlib.util.spec_from_file_location('trap_builder', ROOT/'tools/build_conversion.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            baseline = folder/'base.zip'; cooked = folder/'cooked'; cooked.mkdir()
            with ZipFile(baseline, 'w') as archive:
                for name in REQUIRED_COOKED_FILES:
                    archive.writestr(builder.PREFIX+'CookedPCConsole/'+name, b'old')
                archive.writestr(builder.PREFIX+'Config/UDKDD1ArchipelagoTraps.ini', b'never ship')
            for name in ('Startup_INT.upk', 'TC_Textures.tfc'):
                (cooked/name).write_bytes(b'new '+name.encode())
            builder.build(ROOT, baseline, folder/'out.zip', cooked)
            with ZipFile(folder/'out.zip') as archive:
                manifest = json.loads(archive.read(builder.PREFIX+'package-manifest.json'))
                self.assertNotIn(builder.PREFIX+'Config/UDKDD1ArchipelagoTraps.ini', archive.namelist())
                for name in REQUIRED_COOKED_FILES:
                    data = archive.read(builder.PREFIX+'CookedPCConsole/'+name)
                    expected = (cooked/name).read_bytes() if (cooked/name).exists() else b'old'
                    self.assertEqual(data, expected)
                    self.assertEqual(manifest['files']['CookedPCConsole/'+name]['sha256'], hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    unittest.main()
