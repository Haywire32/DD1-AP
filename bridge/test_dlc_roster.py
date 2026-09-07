"""Registry and real world-method tests with only the AP framework stubbed."""

import ast
import importlib
from itertools import combinations
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dd1_roster_under_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "apworld" / "dungeon_defenders"), str(ROOT / "bridge")]
sys.modules[PACKAGE] = package
heroes = importlib.import_module(PACKAGE + ".heroes")
classification = types.SimpleNamespace(progression=1, filler=0)
base_module = types.ModuleType("BaseClasses")
base_module.ItemClassification = classification
with patch.dict(sys.modules, {"BaseClasses": base_module}):
    items = importlib.import_module(PACKAGE + ".items")
locations = importlib.import_module(PACKAGE + ".locations")
protocol = importlib.import_module(PACKAGE + ".dd1_protocol")


class FakeItem:
    def __init__(self, name, classification, code, player):
        self.name, self.classification, self.code, self.player = name, classification, code, player


class FakeLocation:
    def __init__(self, player, name, address, region):
        self.player, self.name, self.address, self.parent_region = player, name, address, region
        self.item = None
        self.access_rule = lambda state: True
        self.item_rule = lambda item: True

    def place_locked_item(self, item):
        if self.item is not None:
            raise AssertionError("Location was filled twice: " + self.name)
        self.item = item


class FakeRegion:
    def __init__(self, name, player, multiworld):
        self.name, self.player = name, player
        self.locations, self.entrances = [], []

    def connect(self, region, rule):
        region.entrances.append(types.SimpleNamespace(access_rule=rule))


class FakeMultiworld:
    def __init__(self):
        self.regions, self.itempool, self.precollected = [], [], []
        self.completion_condition = {}

    def get_region(self, name, player):
        return next(region for region in self.regions if region.name == name)

    def get_location(self, name, player):
        return next(location for region in self.regions for location in region.locations if location.name == name)

    def push_precollected(self, item):
        self.precollected.append(item)


class FakeState:
    def __init__(self, *names):
        self.names = set(names)

    def has(self, name, player):
        return name in self.names


tree = ast.parse((ROOT / "apworld" / "dungeon_defenders" / "__init__.py").read_text())
world_node = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                  and node.name == "DungeonDefendersWorld")
world_globals = {
    **vars(items), **vars(locations), **vars(heroes),
    "World": object, "GAME_NAME": "Dungeon Defenders", "DungeonDefendersOptions": object,
    "Region": FakeRegion, "DungeonDefendersLocation": FakeLocation,
    "DungeonDefendersItem": FakeItem, "ItemClassification": classification,
    "CAMPAIGN_MAPS": protocol.CAMPAIGN_MAPS,
}
exec(compile(ast.fix_missing_locations(ast.Module(
    body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), world_node],
    type_ignores=[])), "__init__.py", "exec"), world_globals)
WorldUnderTest = world_globals["DungeonDefendersWorld"]


def make_world(keys, seed=0):
    world = WorldUnderTest()
    world.player = 1
    world.random = random.Random(seed)
    world.multiworld = FakeMultiworld()
    world.options = types.SimpleNamespace(
        active_heroes=types.SimpleNamespace(value=keys),
        summit_required_maps=types.SimpleNamespace(value=11),
        summit_unlock_difficulty=types.SimpleNamespace(value=1),
        summit_goal_difficulty=types.SimpleNamespace(value=2, current_key="hard"),
        experience_multiplier=types.SimpleNamespace(value=1),
    )
    world.generate_early()
    world.create_regions()
    world.create_items()
    rule_module = types.ModuleType("worlds.generic.Rules")
    rule_module.set_rule = lambda location, rule: setattr(location, "access_rule", rule)
    rule_module.add_item_rule = lambda location, rule: setattr(location, "item_rule", rule)
    with patch.dict(sys.modules, {"worlds.generic.Rules": rule_module}):
        world.set_rules()
    return world


class RosterTests(unittest.TestCase):
    def test_names_and_validation(self):
        self.assertEqual(heroes.normalize_hero_keys("  SQUIRE, Series EV, squire "), ("squire", "series_ev"))
        for value in (["squire", "missing"], ["squire", 3], "squire,", None,
                      {"squire": 50, "monk": 50}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                heroes.validate_roster(value)
        for value in ([], ["squire"], ["barbarian", "gunwitch"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                heroes.validate_roster(value)
        for left, right in (("apprentice", "adept"), ("squire", "countess"),
                            ("huntress", "ranger"), ("monk", "initiate")):
            with self.assertRaisesRegex(ValueError, "not both"):
                heroes.validate_roster([left, right])

    def test_all_sixteen_heroes_and_combined_summoner(self):
        self.assertEqual(len(heroes.HEROES), 16)
        self.assertEqual(len(heroes.HERO_BY_KEY["summoner"].abilities), 2)
        self.assertIn("summoner.phase_shift_overlord", items.ABILITY_ITEMS.values())
        self.assertNotIn("summoner.phase_shift", items.ABILITY_ITEMS.values())
        self.assertEqual(len(heroes.HERO_BY_KEY["jester"].defenses), 6)

    def test_budget_accepts_some_but_not_all_eight_hero_rosters(self):
        fit = ("apprentice", "squire", "monk", "barbarian", "hermit", "gunwitch", "warden", "guardian")
        overflow = ("apprentice", "squire", "huntress", "monk", "barbarian", "series_ev", "summoner", "jester")
        self.assertEqual(heroes.roster_progression_count(heroes.validate_roster(fit)), 73)
        with self.assertRaisesRegex(ValueError, "only 77 fit"):
            heroes.validate_roster(overflow)
        with self.assertRaisesRegex(ValueError, "2 to 8"):
            heroes.validate_roster((*fit, "ranger"))

    def test_all_115_valid_two_hero_rosters_support_every_starter(self):
        count = 0
        for keys in combinations(heroes.HERO_BY_KEY, 2):
            try:
                heroes.validate_roster(keys)
            except ValueError:
                continue
            # choose_opening validates every possible starter before its draw.
            heroes.choose_opening(keys, random.Random(0))
            count += 1
        self.assertEqual(count, 115)

    def test_published_ids_never_move(self):
        expected = (
            "Apprentice", "Squire", "Huntress", "Monk", "Magic Blockade (Apprentice)",
            "Magic Missile Tower (Apprentice)", "Fireball Tower (Apprentice)", "Lightning Tower (Apprentice)",
            "Deadly Striker Tower (Apprentice)", "Spike Blockade (Squire)", "Bouncer Blockade (Squire)",
            "Harpoon Turret (Squire)", "Bowling Ball Turret (Squire)", "Slice and Dice Blockade (Squire)",
            "Proximity Mine Trap (Huntress)", "Gas Trap (Huntress)", "Inferno Trap (Huntress)",
            "Darkness Trap (Huntress)", "Ethereal Spike Trap (Huntress)", "Ensnare Aura (Monk)",
            "Electric Aura (Monk)", "Healing Aura (Monk)", "Strength Drain Aura (Monk)", "Enrage Aura (Monk)",
            "Overcharge (Apprentice)", "Mana Bomb (Apprentice)", "Blood Rage (Squire)", "Circular Slice (Squire)",
            "Invisibility (Huntress)", "Piercing Shot (Huntress)", "Tower Boost (Monk)", "Hero Boost (Monk)",
            "The Deeper Well Map", "Foundries and Forges Map", "Magus Quarters Map", "Alchemical Laboratory Map",
            "Servants Quarters Map", "Castle Armory Map", "Hall of Court Map", "The Throne Room Map",
            "Royal Gardens Map", "The Ramparts Map", "Endless Spires Map", "Nothing", "Two Hero Levels", "25,000 Bank Mana",
        )
        self.assertEqual(len(expected), 46)
        for index, name in enumerate(expected):
            self.assertEqual(items.ITEM_NAME_TO_ID[name], 9_200_000_000 + index)
        self.assertEqual(len(set(items.ITEM_NAME_TO_ID.values())), len(items.ITEM_NAME_TO_ID))
        self.assertTrue(all(code >= 9_200_000_046 for name, code in items.ITEM_NAME_TO_ID.items()
                            if name not in expected))

    def test_selected_hero_labels_and_modern_items(self):
        selected = items.progression_items_for_heroes(("countess", "ranger"))
        self.assertIn("Mortar Turret (Countess)", selected)
        self.assertIn("Oil Trap (Ranger)", selected)
        self.assertNotIn("Squire", selected)
        self.assertNotIn("Harpoon Turret (Squire)", selected)
        for name in ("Shadow Step (Huntress)", "SAM Unit (Series EV)", "Extra-Deluxe Present (Jester)"):
            self.assertIn(name, items.ITEM_NAME_TO_ID)
        for table in (items.DEFENSE_ITEMS, items.ABILITY_ITEMS):
            for name, key in table.items():
                self.assertTrue(name.endswith(f"({heroes.HERO_BY_KEY[key.split('.')[0]].name})"))

    def test_pool_and_precollected_items_for_varied_rosters(self):
        for keys in (heroes.DEFAULT_HERO_KEYS, ("countess", "ranger", "barbarian"),
                     ("summoner", "gunwitch"), ("jester", "warden", "guardian", "hermit")):
            for seed in range(12):
                world = make_world(keys, seed)
                locations_with_ids = [location for region in world.multiworld.regions
                                      for location in region.locations if location.address is not None]
                self.assertEqual(len(locations_with_ids), 83)
                locked = [location.item for location in locations_with_ids if location.item is not None]
                pool = world.multiworld.itempool
                self.assertEqual(len(pool) + len(locked), 83)
                all_items = pool + locked + world.multiworld.precollected
                progression = [item.name for item in all_items if item.classification == classification.progression]
                self.assertCountEqual(progression, world.progression_names)
                self.assertGreaterEqual(sum(item.classification == classification.filler for item in pool), 6)
                if world.starting_minion:
                    self.assertEqual(sum(item.name == world.starting_minion for item in all_items), 1)
                    self.assertIn(world.starting_minion, [item.name for item in world.multiworld.precollected])
                slot = world.fill_slot_data()
                self.assertEqual(slot["dd1_slot_data_version"], 2)
                self.assertEqual(slot["active_heroes"], list(heroes.normalize_hero_keys(keys)))
                self.assertEqual(slot["starting_minion"], world.starting_minion)
                self.assertEqual(len(slot["level_six_heroes"]), 2)
                for location in locations_with_ids:
                    if location.name.startswith("The Summit -"):
                        self.assertFalse(location.item_rule(FakeItem("Progression", 1, 1, 1)))
                        self.assertTrue(location.item_rule(FakeItem("Filler", 0, 2, 1)))

    def test_nonbuilder_reaches_builder_reward_without_defense_deadlock(self):
        candidates = [make_world(("monk", "barbarian"), seed) for seed in range(10)]
        world = next(world for world in candidates if world.starting_hero == "Barbarian")
        state = FakeState("Barbarian", "The Deeper Well Map")
        self.assertTrue(world.multiworld.get_location("The Deeper Well - Wave 2", 1).access_rule(state))
        self.assertTrue(world.multiworld.get_location("The Deeper Well - Wave 3", 1).access_rule(state))
        state.names.add("Servants Quarters Map")
        region = world.multiworld.get_region("Servants Quarters", 1)
        self.assertFalse(region.entrances[0].access_rule(state))
        state.names.update(("Monk", "Electric Aura (Monk)"))
        self.assertTrue(region.entrances[0].access_rule(state))


if __name__ == "__main__":
    unittest.main()
