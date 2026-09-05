"""Archipelago world and launcher registration for Dungeon Defenders."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from BaseClasses import CollectionState, Item, ItemClassification, Location, Region
from Options import PerGameCommonOptions, Range, Choice
from worlds.AutoWorld import World

from worlds.LauncherComponents import Component, Type, components
from worlds.LauncherComponents import launch as launch_component

from .dd1_protocol import CAMPAIGN_MAPS
from .items import (
    ANTI_AIR_DEFENSES,
    DAMAGING_DEFENSES,
    DEFENSE_OWNER,
    MANA_FILLER_ITEM,
    XP_FILLER_ITEM,
    HERO_ITEMS,
    ITEM_CLASSIFICATIONS,
    ITEM_NAME_TO_ID,
    MAP_ITEMS,
    MAP_TIERS,
    PROGRESSION_ITEMS,
)
from .locations import (
    LOCATION_DIFFICULTY,
    LOCATION_MAP_TAG,
    LOCATION_NAME_TO_ID,
    LOCATION_WAVE,
    SUMMIT_MEDIUM_VICTORY,
)


GAME_NAME = "Dungeon Defenders"


class SummitRequiredMaps(Range):
    """Choose the amount of levels you need to beat to unlock the final map "The Summit". Valid numbers are 1 to 11."""
    display_name = "Maps Required for The Summit"
    range_start = 1
    range_end = 11
    default = 11


class SummitUnlockDifficulty(Choice):
    """Choose the map difficulty that is required to progress towards "The Summit" unlock. Beating higher difficulties counts for any lower ones. For example, you have to beat all 11 maps on at least medium to unlock "The Summit". Choose one: easy, medium, hard, or insane"""
    display_name = "Summit Unlock Difficulty"
    option_easy = 0
    option_medium = 1
    option_hard = 2
    option_insane = 3
    default = 1


class SummitGoalDifficulty(SummitUnlockDifficulty):
    """Choose the difficulty required for "The Summit" to beat the Archipelago goal. Choose one: easy, medium, hard, or insane"""
    display_name = "Summit Goal Difficulty"
    default = 2


@dataclass
class DungeonDefendersOptions(PerGameCommonOptions):
    summit_required_maps: SummitRequiredMaps
    summit_unlock_difficulty: SummitUnlockDifficulty
    summit_goal_difficulty: SummitGoalDifficulty


class DungeonDefendersItem(Item):
    game = GAME_NAME


class DungeonDefendersLocation(Location):
    game = GAME_NAME


class DungeonDefendersWorld(World):
    game = GAME_NAME
    options_dataclass = DungeonDefendersOptions
    item_name_to_id = ITEM_NAME_TO_ID
    location_name_to_id = LOCATION_NAME_TO_ID

    starting_hero: str
    starting_map: str
    early_defense: str
    early_anti_air: str
    locked_map_rewards: set[str]
    second_hero: str
    extra_defenses: tuple[str, str]

    def generate_early(self) -> None:
        self.starting_hero = self.random.choice(tuple(HERO_ITEMS))
        # One hero, Deeper Well, and no precollected defenses or abilities.
        # The Deeper Well is the only reliably manageable level for a fresh
        # character before the first-wave damaging-defense guarantee arrives.
        self.starting_map = "The Deeper Well Map"
        hero_key = HERO_ITEMS[self.starting_hero]
        candidate_defenses = [
            name for name, owner in DEFENSE_OWNER.items()
            if owner == hero_key and name in DAMAGING_DEFENSES
        ]
        self.early_defense = self.random.choice(candidate_defenses)
        anti_air_candidates = [
            name for name, owner in DEFENSE_OWNER.items()
            if owner == hero_key and name in ANTI_AIR_DEFENSES
        ]
        self.early_anti_air = (
            self.early_defense
            if self.early_defense in ANTI_AIR_DEFENSES
            else self.random.choice(anti_air_candidates)
        )
        self.second_hero = self.random.choice([h for h in HERO_ITEMS if h != self.starting_hero])
        owners = {hero_key, HERO_ITEMS[self.second_hero]}
        generic = {
            'Magic Missile Tower (Apprentice)', 'Deadly Striker Tower (Apprentice)',
            'Spike Blockade (Squire)', 'Bouncer Blockade (Squire)',
            'Harpoon Turret (Squire)', 'Bowling Ball Turret (Squire)',
            'Slice and Dice Blockade (Squire)', 'Proximity Mine Trap (Huntress)',
        }
        candidates = [n for n, owner in DEFENSE_OWNER.items()
                      if owner in owners and n != self.early_defense]
        packages = [pair for pair in combinations(candidates, 2)
                    if any(DEFENSE_OWNER[n] == HERO_ITEMS[self.second_hero] for n in pair)
                    and ({self.early_defense, *pair} & generic)
                    and ({self.early_defense, *pair} & ANTI_AIR_DEFENSES)]
        self.extra_defenses = self.random.choice(packages)
        self.early_anti_air = next(n for n in (self.early_defense, *self.extra_defenses)
                                  if n in ANTI_AIR_DEFENSES)

    def create_item(self, name: str) -> DungeonDefendersItem:
        return DungeonDefendersItem(
            name, ITEM_CLASSIFICATIONS[name], ITEM_NAME_TO_ID[name], self.player
        )

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        map_item_by_tag = {tag: name for name, tag in MAP_ITEMS.items()}
        map_name_by_tag = {
            entry.tag: entry.name
            for entry in CAMPAIGN_MAPS
            if entry.tag in map_item_by_tag or entry.tag == "CAMPTS"
        }

        for tag, display_name in map_name_by_tag.items():
            region = Region(display_name, self.player, self.multiworld)
            self.multiworld.regions.append(region)
            if tag == "CAMPTS":
                clear_items = tuple(
                    f"{name} Cleared"
                    for other_tag, name in map_name_by_tag.items()
                    if other_tag != "CAMPTS"
                )
                menu.connect(
                    region,
                    rule=lambda state, items=clear_items, player=self.player: sum(
                        state.has(item, player) for item in items
                    ) >= self.options.summit_required_maps.value,
                )
            else:
                required_map = map_item_by_tag[tag]
                menu.connect(
                    region,
                    rule=lambda state, item=required_map, player=self.player: state.has(item, player),
                )

        for name, address in LOCATION_NAME_TO_ID.items():
            region = self.multiworld.get_region(map_name_by_tag[LOCATION_MAP_TAG[name]], self.player)
            region.locations.append(DungeonDefendersLocation(self.player, name, address, region))

        first_wave_location = next(
            name for name, wave in LOCATION_WAVE.items()
            if LOCATION_MAP_TAG[name] == MAP_ITEMS[self.starting_map] and wave == 1
        )
        self.multiworld.get_location(first_wave_location, self.player).place_locked_item(
            self.create_item(self.early_defense)
        )

        # All three additional opening rewards arrive by Medium completion.
        for location_name, item_name in (
            ('The Deeper Well - Wave 2', self.second_hero),
            ('The Deeper Well - Wave 3', self.extra_defenses[0]),
            ('The Deeper Well - Medium Victory', self.extra_defenses[1]),
        ):
            self.multiworld.get_location(location_name, self.player).place_locked_item(
                self.create_item(item_name))

        # Build an overlapping randomized map ladder without relying on the
        # generic filler's greedy ordering. Tier 1 maps form a connected tree;
        # each non-start Tier 1 map contains one Tier 2 map; the Tier 2 maps
        # contain the four Tier 3 maps. Items and exact checks are shuffled.
        def unlocked_location_names(tag: str) -> list[str]:
            return [
                name for name in LOCATION_NAME_TO_ID
                if LOCATION_MAP_TAG[name] == tag
                and LOCATION_DIFFICULTY[name] in {"Any", "Easy"}
                and self.multiworld.get_location(name, self.player).item is None
            ]

        tier_1_items = [name for name in MAP_TIERS[0] if name != self.starting_map]
        self.random.shuffle(tier_1_items)
        # Only one onward map is required in Deeper Well. Later Tier 1 maps
        # are placed in already connected maps, never behind their own item.
        connected_hosts = [MAP_ITEMS[self.starting_map]]
        for item_name in tier_1_items:
            host = connected_hosts[0] if len(connected_hosts) == 1 else self.random.choice(connected_hosts[1:])
            location_name = self.random.choice(unlocked_location_names(host))
            self.multiworld.get_location(location_name, self.player).place_locked_item(
                self.create_item(item_name)
            )
            connected_hosts.append(MAP_ITEMS[item_name])

        tier_1_host_tags = [MAP_ITEMS[name] for name in tier_1_items]
        tier_2_items = list(MAP_TIERS[1])
        self.random.shuffle(tier_1_host_tags)
        self.random.shuffle(tier_2_items)
        for item_name, host_tag in zip(tier_2_items, tier_1_host_tags, strict=True):
            locations = unlocked_location_names(host_tag)
            self.multiworld.get_location(self.random.choice(locations), self.player).place_locked_item(
                self.create_item(item_name)
            )

        tier_2_host_tags = [MAP_ITEMS[name] for name in tier_2_items]
        tier_3_items = list(MAP_TIERS[2])
        self.random.shuffle(tier_3_items)
        tier_3_hosts = tier_2_host_tags + [self.random.choice(tier_2_host_tags)]
        self.random.shuffle(tier_3_hosts)
        for item_name, host_tag in zip(tier_3_items, tier_3_hosts, strict=True):
            locations = unlocked_location_names(host_tag)
            self.multiworld.get_location(self.random.choice(locations), self.player).place_locked_item(
                self.create_item(item_name)
            )
        self.locked_map_rewards = set(tier_1_items + tier_2_items + tier_3_items)

        # Non-network events model qualifying victories. Difficulty has no
        # separate combat-item requirements in this world's current logic.
        # Runtime enforces the selected minimum using actual victory events.
        # Non-network event items model completed maps for AP's
        # fill logic. Runtime map access uses the bridge's actually observed
        # victory checks, not these generation-only events.
        for tag, display_name in map_name_by_tag.items():
            if tag == "CAMPTS":
                continue
            region = self.multiworld.get_region(display_name, self.player)
            event = DungeonDefendersLocation(
                self.player, f"{display_name} Completion Event", None, region
            )
            event.place_locked_item(DungeonDefendersItem(
                f"{display_name} Cleared", ItemClassification.progression, None, self.player
            ))
            region.locations.append(event)

    def _has_usable_defense(self, state: CollectionState) -> bool:
        for defense_name, owner_key in DEFENSE_OWNER.items():
            hero_name = next(name for name, key in HERO_ITEMS.items() if key == owner_key)
            if state.has(hero_name, self.player) and state.has(defense_name, self.player):
                return True
        return False

    def create_items(self) -> None:
        starters = {self.starting_hero, self.starting_map}
        locked_rewards = self.locked_map_rewards | {self.early_defense, self.second_hero, *self.extra_defenses}
        for name in PROGRESSION_ITEMS:
            item = self.create_item(name)
            if name in starters:
                self.multiworld.push_precollected(item)
            elif name in locked_rewards:
                continue
            else:
                self.multiworld.itempool.append(item)

        filler_count = len(LOCATION_NAME_TO_ID) - (len(PROGRESSION_ITEMS) - len(starters))
        xp_count = (filler_count + 1) // 2
        mana_count = filler_count - xp_count
        for _ in range(xp_count):
            self.multiworld.itempool.append(self.create_item(XP_FILLER_ITEM))
        for _ in range(mana_count):
            self.multiworld.itempool.append(self.create_item(MANA_FILLER_ITEM))

    def set_rules(self) -> None:
        from worlds.generic.Rules import add_item_rule, set_rule

        for map_name in (*MAP_TIERS[1], *MAP_TIERS[2]):
            tag = MAP_ITEMS[map_name]
            region_name = next(m.name for m in CAMPAIGN_MAPS if m.tag == tag)
            entrance = self.multiworld.get_region(region_name, self.player).entrances[0]
            old_rule = entrance.access_rule
            entrance.access_rule = lambda state, old=old_rule: old(state) and any(
                state.has(n, self.player) and state.has(next(h for h, k in HERO_ITEMS.items()
                    if k == DEFENSE_OWNER[n]), self.player) for n in ANTI_AIR_DEFENSES)

        for name, wave in LOCATION_WAVE.items():
            if wave == 1:
                continue
            location = self.multiworld.get_location(name, self.player)
            set_rule(location, lambda state, world=self: world._has_usable_defense(state))

        for name in LOCATION_NAME_TO_ID:
            if name.startswith("The Summit -"):
                location = self.multiworld.get_location(name, self.player)
                add_item_rule(
                    location,
                    lambda item: item.classification == ItemClassification.filler,
                )

        summit = self.multiworld.get_region("The Summit", self.player)
        goal = DungeonDefendersLocation(self.player, "The Summit Goal Event", None, summit)
        goal.place_locked_item(DungeonDefendersItem(
            "Summit Goal", ItemClassification.progression, None, self.player))
        summit.locations.append(goal)
        self.multiworld.completion_condition[self.player] = (
            lambda state: state.has("Summit Goal", self.player))

    def fill_slot_data(self) -> dict:
        return {
            "dd1_slot_data_version": 1,
            "starting_hero": HERO_ITEMS[self.starting_hero],
            "starting_map": MAP_ITEMS[self.starting_map],
            "level_six_heroes": [HERO_ITEMS[self.starting_hero], HERO_ITEMS[self.second_hero]],
            "early_anti_air": self.early_anti_air,
            # Hard-or-higher Summit victory is the goal signal, not a location.
            "goal": "summit_" + self.options.summit_goal_difficulty.current_key + "_or_higher",
            "summit_required_maps": self.options.summit_required_maps.value,
            "summit_unlock_difficulty": self.options.summit_unlock_difficulty.value,
            "summit_goal_difficulty": self.options.summit_goal_difficulty.value,
        }


def launch_client(*args: str) -> None:
    from .Client import launch

    launch_component(launch, name="Dungeon Defenders Client", args=args)


def launch_yaml_template(*args: str) -> None:
    from .public_yaml import launch

    launch_component(launch, name="Dungeon Defenders YAML", args=args)


components.append(Component(
    "Dungeon Defenders Client",
    func=launch_client,
    component_type=Type.CLIENT,
    game_name="Dungeon Defenders",
    supports_uri=True,
    description="Connect Archipelago to the Local-only Dungeon Defenders Total Conversion.",
))

components.append(Component(
    "Dungeon Defenders YAML",
    func=launch_yaml_template,
    component_type=Type.TOOL,
    description="Save the public Dungeon Defenders YAML with the author's instructions and defaults.",
))
