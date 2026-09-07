"""Opening policy tests, without an Archipelago install or a running game."""

import importlib
import random
import sys
import types
import unittest
from pathlib import Path


PACKAGE = "dd1_opening_under_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / "apworld" / "dungeon_defenders")]
sys.modules[PACKAGE] = package
heroes = importlib.import_module(PACKAGE + ".heroes")


class OpeningPackageTests(unittest.TestCase):
    def test_starting_cost_limit_includes_140_and_rejects_unknown_costs(self):
        eligible = heroes.is_starting_defense
        self.assertTrue(eligible(heroes.action("Boundary", damaging=True, mana_cost=140)))
        for cost in (141, 150, 300, None, -1):
            self.assertFalse(eligible(heroes.action("Not affordable", damaging=True, mana_cost=cost)))
        self.assertFalse(eligible(heroes.action("Not damaging", mana_cost=30)))

    def test_every_builders_entire_first_reward_draw_is_affordable(self):
        class InspectDraw:
            def __init__(self, starter):
                self.starter = starter
                self.calls = []

            def choice(self, values):
                self.calls.append(tuple(values))
                return self.starter if len(self.calls) == 1 else values[0]

        for hero in heroes.HEROES:
            if not hero.builder:
                continue
            with self.subTest(hero=hero.name):
                # Barbarian provides an independent partner for every builder.
                rng = InspectDraw(hero.key)
                opening = heroes.choose_opening((hero.key, "barbarian"), rng)
                self.assertEqual(opening.starting_hero, hero.key)
                candidates = [tool for tool, plans in rng.calls[1]]
                expected = [tool for tool in hero.defenses if heroes.is_starting_defense(tool)]
                if hero.key == "summoner":
                    expected = [tool for tool in expected if tool.key in heroes.STARTING_SUMMONER_MINIONS]
                self.assertTrue(candidates)
                self.assertCountEqual(candidates, expected)
                for tool in candidates:
                    self.assertIsNotNone(tool.mana_cost)
                    self.assertLessEqual(tool.mana_cost, 140)
                self.assertEqual(rng.calls[0].count(hero.key), 1)

    def test_expensive_defenses_remain_in_catalog_but_not_first_reward(self):
        for key, action_key in (
            ("squire", "mortar_turret"), ("countess", "mortar_turret"),
            ("series_ev", "sam_unit"), ("hermit", "forest_golem"),
            ("warden", "shroom_pit"), ("guardian", "owl_nest"),
            ("guardian", "holy_bulwark"),
        ):
            with self.subTest(hero=key, defense=action_key):
                tool = next(tool for tool in heroes.HERO_BY_KEY[key].defenses if tool.key == action_key)
                self.assertTrue(tool.damaging)
                self.assertGreater(tool.mana_cost, 140)
                self.assertFalse(heroes.is_starting_defense(tool))
        squire = heroes.HERO_BY_KEY["squire"]
        slice_dice = next(tool for tool in squire.defenses if tool.key == "slice_n_dice_blockade")
        self.assertTrue(heroes.is_starting_defense(slice_dice))

    def test_original_openings_have_two_heroes_three_usable_defenses(self):
        pairs = set()
        for seed in range(200):
            opening = heroes.choose_opening(heroes.DEFAULT_HERO_KEYS, random.Random(seed))
            pair = (opening.starting_hero, opening.second_hero)
            pairs.add(pair)
            self.assertNotEqual(*pair)
            self.assertIsNone(opening.starting_minion)
            names = {opening.first_wave_reward, *opening.extra_defenses}
            self.assertEqual(len(names), 3)
            self.assertIn(opening.anti_air, names)
            owner_names = {heroes.HERO_BY_KEY[key].name for key in pair}
            self.assertTrue(all(any(name.endswith(f"({owner})") for owner in owner_names)
                                for name in names))
        self.assertEqual(len(pairs), 12)

    def test_nonbuilder_starter_gets_any_own_ability_then_builder(self):
        for nonbuilder in ("barbarian", "gunwitch"):
            observed = set()
            for seed in range(200):
                opening = heroes.choose_opening((nonbuilder, "monk"), random.Random(seed))
                if opening.starting_hero == nonbuilder:
                    self.assertEqual(opening.second_hero, "monk")
                    observed.add(opening.first_wave_reward)
                    self.assertTrue(all(name.endswith("(Monk)") for name in opening.extra_defenses))
            hero = heroes.HERO_BY_KEY[nonbuilder]
            self.assertEqual(observed, {hero.item_name(tool) for tool in hero.abilities})

    def test_summoner_gets_only_an_affordable_random_minion_at_start(self):
        observed = set()
        for seed in range(150):
            opening = heroes.choose_opening(("summoner", "squire"), random.Random(seed))
            if opening.starting_hero == "summoner":
                self.assertIsNone(opening.first_wave_reward)
                self.assertNotIn(opening.starting_minion, opening.extra_defenses)
                observed.add(opening.starting_minion)
        self.assertEqual(observed, {"Archer Minion (Summoner)", "Spider Minion (Summoner)",
                                    "Orc Minion (Summoner)"})

    def test_starter_draw_contains_each_selected_hero_once(self):
        keys = ("adept", "ranger", "barbarian", "summoner", "gunwitch")

        class FirstDraw:
            def __init__(self, index):
                self.index = index
                self.calls = []

            def choice(self, values):
                self.calls.append(tuple(values))
                return values[self.index] if len(self.calls) == 1 else values[0]

        expected = heroes.normalize_hero_keys(keys)
        observed = []
        for index in range(len(expected)):
            rng = FirstDraw(index)
            opening = heroes.choose_opening(keys, rng)
            self.assertEqual(rng.calls[0], expected)
            observed.append(opening.starting_hero)
        self.assertEqual(tuple(observed), expected)

    def test_roster_text_order_does_not_change_seed(self):
        left = heroes.choose_opening("Adept, Gunwitch, Series EV", random.Random(55))
        right = heroes.choose_opening(["series_ev", "gunwitch", "adept"], random.Random(55))
        self.assertEqual(left, right)

    def test_unready_starter_rejects_instead_of_being_rerolled(self):
        with self.assertRaisesRegex(ValueError, "Starting support has not been verified for: Summoner"):
            heroes.choose_opening(("summoner", "squire"), random.Random(0),
                                   starter_readiness={"squire": True, "summoner": False})


if __name__ == "__main__":
    unittest.main()
