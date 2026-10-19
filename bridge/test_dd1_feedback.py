"""October multiworld feedback: disabled modes, build time and Summit progress."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dd1_content import ContentSettings, selected_checks, SURVIVAL_START_ITEM, AREA_ITEMS
from dd1_protocol import summit_clear_count, summit_is_unlocked, CAMPAIGN_MAPS
import test_dd1_client
client = test_dd1_client.client


class FeedbackTests(unittest.TestCase):
    def test_survival_disabled_normalizes_old_and_new_slots(self):
        for enabled in (False, True):
            settings = ContentSettings(survival_checks=False, survival_unlock=enabled)
            self.assertFalse(settings.survival_unlock)
            self.assertNotIn(SURVIVAL_START_ITEM, settings.unlock_items())
            self.assertFalse(set(AREA_ITEMS['survival']) & set(settings.unlock_items()))
            old = settings.slot_data() | {'survival_unlock': enabled}
            self.assertFalse(ContentSettings.from_slot_data(old).survival_unlock)

    def test_survival_enabled_retains_start_waves_and_optional_areas(self):
        for enabled in (False, True):
            settings = ContentSettings(survival_checks=True, survival_unlock=enabled)
            self.assertEqual(settings.unlock_items().count(SURVIVAL_START_ITEM), 5)
            self.assertEqual(set(AREA_ITEMS['survival']) <= set(settings.unlock_items()), enabled)

    def test_build_time_only_for_nm_ruthless_or_cd(self):
        cases = [
            ({}, False),
            ({'campaign_check_difficulties': ('easy', 'medium', 'hard', 'insane'), 'summit_goal_difficulty': 3}, False),
            ({'campaign_check_difficulties': ('medium', 'nightmare'), 'summit_goal_difficulty': 4}, True),
            ({'campaign_check_difficulties': ('medium', 'ruthless'), 'summit_goal_difficulty': 5}, True),
            ({'summit_goal_difficulty': 4}, True),
            ({'survival_checks': True, 'survival_check_difficulty': 3}, False),
            ({'survival_checks': True, 'survival_check_difficulty': 4}, True),
            ({'survival_checks': False, 'survival_check_difficulty': 5}, False),
            ({'challenge_checks': True, 'challenge_check_difficulty': 4}, True),
            ({'challenge_checks': False, 'challenge_check_difficulty': 5}, False),
            ({'completion_goal': 'challenges', 'challenge_checks': True, 'challenge_goal_difficulty': 4}, True),
            ({'completion_goal': 'crystalline_dimension', 'crystalline_dimension_difficulty': 1}, True),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                settings = ContentSettings(**kwargs)
                self.assertEqual(settings.build_time_items(selected_checks(settings)) > 0, expected)

    def test_summit_counts_distinct_qualifying_base_maps(self):
        victories = ['dd1.campaign.CAMPDW.victory.medium', 'dd1.campaign.CAMPDW.victory.hard',
                     'dd1.campaign.CAMPFF.victory.easy', 'dd1.campaign.CAMPMQ.wave.medium.5',
                     'dd1.survival.CAMPAL.victory.ruthless', 'dd1.campaign.CAMPMB.victory.ruthless']
        self.assertEqual(summit_clear_count(victories, 1), 1)
        self.assertFalse(summit_is_unlocked(victories, 2, 1))
        victories += ['dd1.campaign.CAMPFF.victory.nightmare']
        self.assertTrue(summit_is_unlocked(victories, 2, 1))
        all_maps = [f'dd1.campaign.{m.tag}.victory.ruthless' for m in CAMPAIGN_MAPS]
        self.assertEqual(summit_clear_count(all_maps, 5), 11)
        self.assertEqual(summit_clear_count(None), 0)

    def test_client_opens_survival_without_summit_progress_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx = test_dd1_client.ClientPortabilityTests().make_context(Path(directory))
            ctx.slot_data.update(survival_checks=False, survival_unlock=True)
            ctx.state_path = Path(directory) / 'state.json'
            state = client.empty_bridge_state()
            client.atomic_write_json(ctx.state_path, state)
            with patch.object(client.logger, 'info') as log:
                ctx._apply_unlocks()
                ctx._apply_unlocks()
                progress = [c for c in log.call_args_list if c.args[0].startswith('Summit unlock:')]
                self.assertEqual(progress, [])
                self.assertEqual(ctx.mode_mask & 7, 7)
                self.assertEqual(ctx.survival_start_wave, -1)
                state['victory_history'] = {'dd1.campaign.CAMPDW.victory.medium': {}}
                client.atomic_write_json(ctx.state_path, state)
                ctx._apply_unlocks()
                progress = [c for c in log.call_args_list if c.args[0].startswith('Summit unlock:')]
                self.assertEqual(progress, [])


if __name__ == '__main__':
    unittest.main()
