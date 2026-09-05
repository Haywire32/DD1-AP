"""Exercise the actual generator's opening selection without AP dependencies."""
import ast
import random
import unittest
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace


class OpeningPackageTests(unittest.TestCase):
    def test_random_openings_have_two_heroes_three_usable_defenses(self):
        root = Path(__file__).resolve().parents[1] / 'apworld' / 'dungeon_defenders'
        env = {'combinations': combinations}
        tree = ast.parse((root / 'items.py').read_text())
        wanted = {'HERO_ITEMS', 'DEFENSE_ITEMS', 'DEFENSE_OWNER', 'DAMAGING_DEFENSES', 'ANTI_AIR_DEFENSES'}
        nodes = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'items.py', 'exec'), env)
        tree = ast.parse((root / '__init__.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DungeonDefendersWorld')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'generate_early')
        exec(compile(ast.Module(body=[method], type_ignores=[]), '__init__.py', 'exec'), env)
        pairs = set()
        for seed in range(1000):
            world = SimpleNamespace(random=random.Random(seed))
            env['generate_early'](world)
            self.assertEqual(world.starting_map, 'The Deeper Well Map')
            self.assertNotEqual(world.starting_hero, world.second_hero)
            defenses = {world.early_defense, *world.extra_defenses}
            self.assertEqual(len(defenses), 3)
            self.assertIn(world.early_defense, env['DAMAGING_DEFENSES'])
            self.assertTrue(defenses & env['ANTI_AIR_DEFENSES'])
            owners = {env['DEFENSE_OWNER'][n] for n in defenses}
            self.assertEqual(owners, {env['HERO_ITEMS'][world.starting_hero], env['HERO_ITEMS'][world.second_hero]})
            self.assertTrue(any('Squire' in n or n in {'Magic Missile Tower (Apprentice)',
                'Deadly Striker Tower (Apprentice)', 'Proximity Mine Trap (Huntress)'} for n in defenses))
            pairs.add((world.starting_hero, world.second_hero))
        self.assertEqual(len(pairs), 12)
