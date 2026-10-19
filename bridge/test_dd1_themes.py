import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dd1_themes import THEME_NAMES, AVAILABLE_THEME_NAMES, EXCLUDED_THEME_NAMES, add_theme_rewards, theme_mask, theme_snapshot
from dd1_traps import TRAP_NAMES, TRAP_KEYS, replace_filler_with_traps
import test_dd1_client as ct


class ThemeTests(unittest.TestCase):
    def test_filler_only_and_once_each(self):
        original = ['mana'] * 25 + ['hero', 'crystal', 'skin']
        result = add_theme_rewards(original, True, random.Random(5), {'mana'})
        self.assertEqual(len(result), len(original))
        self.assertEqual(result[-3:], original[-3:])
        for name in AVAILABLE_THEME_NAMES:
            self.assertEqual(result.count(name), 1)
        self.assertFalse(set(result) & set(EXCLUDED_THEME_NAMES))
        result = replace_filler_with_traps(result, 100, TRAP_KEYS, random.Random(7), {'mana'})
        self.assertEqual(sum(n in TRAP_NAMES for n in result), 16)
        self.assertEqual(sum(n in THEME_NAMES for n in result), 9)
        with self.assertRaisesRegex(ValueError, '9 ordinary filler'):
            add_theme_rewards(['mana'] * 8, True, random.Random(1), {'mana'})
        self.assertEqual(set(add_theme_rewards(['mana'] * 9, True, random.Random(1), {'mana'})), set(AVAILABLE_THEME_NAMES))

    def test_off_preserves_rng(self):
        rng = random.Random(3); before = rng.getstate()
        self.assertEqual(add_theme_rewards(['mana'], False, rng, {'mana'}), ['mana'])
        self.assertEqual(before, rng.getstate())

    def test_inventory_and_invalid_seed(self):
        ids = dict(zip(THEME_NAMES, range(11)))
        received = [{'item_id':0}, {'item_id':0}, {'item_id':10}, {'item_id':99}]
        self.assertEqual(theme_mask(True, received, ids), 1024)
        self.assertEqual(theme_mask(True, [{'item_id': i} for i in range(11)], ids), 1534)
        self.assertEqual(theme_mask(True, [{'item_id': 0}, {'item_id': 9}], ids), 0)
        self.assertEqual(theme_mask(False, received, ids), 0)
        with self.assertRaises(ValueError):
            theme_snapshot('invalid', True, received, ids)

    def test_ini_tcp_and_linux_live_delivery(self):
        client = ct.client
        with tempfile.TemporaryDirectory() as temp, patch.object(client.sys, 'platform', 'linux'):
            root = Path(temp)
            ctx = ct.ClientPortabilityTests().make_context(root)
            ctx.slot_data['tavern_themes'] = True
            ctx.state_path = root / 'state.json'
            state = client.empty_bridge_state()
            packet = {'index':0, 'items':[{'item':client.ITEM_NAME_TO_ID[n], 'location':i+1, 'player':1}
                for i, n in enumerate((THEME_NAMES[1], THEME_NAMES[10], THEME_NAMES[0], THEME_NAMES[9]))]}
            client.ingest_mana_packet(state, packet, client.ITEM_NAME_TO_ID, ctx._live_seed_identity())
            client.atomic_write_json(ctx.state_path, state)
            ctx._apply_unlocks()
            ini = ctx.unlock_path.read_text()
            self.assertIn('bTavernThemes=True', ini)
            self.assertIn('TavernThemeMask=1026', ini)
            expected = f'APTHEMES1|{ctx._live_seed_identity()}|1|1026'
            self.assertIn((expected+'\r\n').encode(), ctx._snapshot_packets())
            ctx._publish_file_snapshot()
            self.assertIn(expected, (root/'Binaries/Web/DD1ArchipelagoCurrent-live.uhtm').read_text())
            ctx.slot_data.pop('tavern_themes')
            ctx._apply_unlocks()
            self.assertIn('bTavernThemes=False', ctx.unlock_path.read_text())
            self.assertIn(f'APTHEMES1|{ctx._live_seed_identity()}|0|0\r\n'.encode(), ctx._snapshot_packets())

if __name__ == '__main__':
    unittest.main()
