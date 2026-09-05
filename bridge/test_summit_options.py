import unittest
import tempfile
from pathlib import Path
from dd1_protocol import (empty_bridge_state, record_locations, summit_is_unlocked,
                          summit_settings, ProtocolError, SUMMIT_REQUIRED_CLEAR_TAGS,
                          atomic_write_json, load_bridge_state)


class SummitOptionsTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        self.assertEqual(summit_settings({})['summit_required_maps'], 11)
        for key, values in [('summit_required_maps', [0, 12, True]),
                            ('summit_unlock_difficulty', [-1, 4]),
                            ('summit_goal_difficulty', [-1, 4])]:
            for value in values:
                with self.assertRaises(ProtocolError):
                    summit_settings({key: value})

    def test_all_thresholds(self):
        tags = sorted(SUMMIT_REQUIRED_CLEAR_TAGS)
        for count in range(1, 12):
            for minimum in range(4):
                for actual, difficulty in enumerate(['easy', 'medium', 'hard', 'insane']):
                    keys = [f'dd1.campaign.{tag}.victory.{difficulty}' for tag in tags[:count]]
                    self.assertEqual(summit_is_unlocked(keys, count, minimum), actual >= minimum)
                    self.assertFalse(summit_is_unlocked(keys[:-1], count, minimum))

    def test_goal_and_check_invariance(self):
        for actual, difficulty in enumerate(['EASY', 'MEDIUM', 'HARD', 'INSANE']):
            results = []
            for goal in range(4):
                state = empty_bridge_state()
                state['summit_settings'] = summit_settings({'summit_goal_difficulty': goal})
                event = dict(protocol=1, event='level_victory', map='DD_Finale', wave=9, detail='EGD_' + difficulty)
                results.append(record_locations(state, 'test', event))
                self.assertEqual(state['goal_complete'], actual >= goal)
            self.assertTrue(all(result == results[0] for result in results))

    def test_insane_history_and_distinct_maps(self):
        state = empty_bridge_state()
        event = dict(protocol=1, event='level_victory', map='DD_Lev_02', wave=5, detail='EGD_INSANE')
        record_locations(state, 'one', event)
        record_locations(state, 'two', event)
        self.assertTrue(summit_is_unlocked(state['victory_history'], 1, 3))
        self.assertFalse(summit_is_unlocked(state['observed_locations'], 1, 3))
        self.assertFalse(summit_is_unlocked(state['victory_history'], 2, 0))
        state['summit_settings'] = summit_settings({'summit_unlock_difficulty': 3})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            atomic_write_json(path, state)
            restored = load_bridge_state(path)
            self.assertEqual(restored, state)
