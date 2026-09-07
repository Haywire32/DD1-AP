"""Archipelago world and launcher registration for Dungeon Defenders."""

from __future__ import annotations

from dataclasses import dataclass

from BaseClasses import CollectionState, Item, ItemClassification, Location, Region
from Options import PerGameCommonOptions, Range, Choice, OptionSet
from worlds.AutoWorld import World

from worlds.LauncherComponents import Component, Type, components
from worlds.LauncherComponents import launch as launch_component

from .dd1_protocol import CAMPAIGN_MAPS
from .heroes import (
    DEFAULT_HERO_KEYS, HERO_BY_KEY, SUMMIT_FILLER_COUNT,
    choose_opening, normalize_hero_keys,
)
from .items import (
    ANTI_AIR_DEFENSES,
    DEFENSE_OWNER,
    MANA_FILLER_ITEM,
    XP_FILLER_ITEM,
    HERO_ITEMS,
    ITEM_CLASSIFICATIONS,
    ITEM_NAME_TO_ID,
    MAP_ITEMS,
    MAP_TIERS,
    progression_items_for_heroes,
)
from .locations import (
    LOCATION_DIFFICULTY,
    LOCATION_MAP_TAG,
    LOCATION_NAME_TO_ID,
    LOCATION_WAVE,
    SUMMIT_MEDIUM_VICTORY,
)


GAME_NAME = "Dungeon Defenders"


class ActiveHeroes(OptionSet):
    """Choose 2 to 8 heroes to include in this seed. Choose only heroes whose DLC
    you own; selecting a hero here does not grant DLC ownership. Valid names:
    apprentice, adept, squire, countess, huntress, ranger, monk, initiate,
    barbarian, series_ev, summoner, jester, hermit, gunwitch, warden, guardian.
    Do not select both members of Apprentice/Adept, Squire/Countess,
    Huntress/Ranger, or Monk/Initiate. Include at least one builder. Larger
    rosters must leave room for six Summit filler rewards. Names can be a YAML
    list or comma-separated text; order does not affect generation.
    """
    display_name = "Active Heroes"
    default = frozenset(DEFAULT_HERO_KEYS)
    valid_keys = frozenset(HERO_BY_KEY)

    @classmethod
    def from_any(cls, data):
        return cls(set(normalize_hero_keys(data)))

    @classmethod
    def from_text(cls, data):
        return cls.from_any(data)


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


class ExperienceMultiplier(Choice):
    """Multiply all experience earned through normal DD1 gameplay. This is applied after the game's map, difficulty, wave, and performance bonuses. Choose one: 1, 2, 4, 6, 8, or 10."""
    display_name = "Experience Multiplier"
    option_vanilla = 1
    option_double = 2
    option_quadruple = 4
    option_sextuple = 6
    option_octuple = 8
    option_decuple = 10
    default = 1


@dataclass
class DungeonDefendersOptions(PerGameCommonOptions):
    active_heroes: ActiveHeroes
    summit_required_maps: SummitRequiredMaps
    summit_unlock_difficulty: SummitUnlockDifficulty
    summit_goal_difficulty: SummitGoalDifficulty
    experience_multiplier: ExperienceMultiplier


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
    active_heroes: tuple[str, ...]
    progression_names: tuple[str, ...]
    first_wave_reward: str | None
    starting_minion: str | None

    def generate_early(self) -> None:
        option = getattr(self.options, "active_heroes", None)
        configured = option.value if option is not None else DEFAULT_HERO_KEYS
        opening = choose_opening(configured, self.random)
        self.active_heroes = normalize_hero_keys(configured)
        self.progression_names = progression_items_for_heroes(self.active_heroes)
        self.starting_hero = HERO_BY_KEY[opening.starting_hero].name
        self.second_hero = HERO_BY_KEY[opening.second_hero].name
        self.starting_map = "The Deeper Well Map"
        self.first_wave_reward = opening.first_wave_reward
        self.starting_minion = opening.starting_minion
        self.early_defense = opening.first_wave_reward or opening.starting_minion
        self.extra_defenses = opening.extra_defenses
        self.early_anti_air = opening.anti_air

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
        if self.first_wave_reward is not None:
            self.multiworld.get_location(first_wave_location, self.player).place_locked_item(
                self.create_item(self.first_wave_reward)
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
            if owner_key not in self.active_heroes:
                continue
            hero_name = HERO_BY_KEY[owner_key].name
            if state.has(hero_name, self.player) and state.has(defense_name, self.player):
                return True
        return False

    def _has_usable_combat(self, state: CollectionState) -> bool:
        # A non-builder must be able to reach the wave-two builder reward and
        # wave-three defense using normal weapon attacks. Tier-two/three map
        # entry still separately requires an owned anti-air defense and hero.
        return self._has_usable_defense(state) or any(
            not HERO_BY_KEY[key].builder and state.has(HERO_BY_KEY[key].name, self.player)
            for key in self.active_heroes
        )

    def create_items(self) -> None:
        starters = {self.starting_hero, self.starting_map}
        if self.starting_minion is not None:
            starters.add(self.starting_minion)
        locked_rewards = self.locked_map_rewards | {self.second_hero, *self.extra_defenses}
        if self.first_wave_reward is not None:
            locked_rewards.add(self.first_wave_reward)
        for name in self.progression_names:
            item = self.create_item(name)
            if name in starters:
                self.multiworld.push_precollected(item)
            elif name in locked_rewards:
                continue
            else:
                self.multiworld.itempool.append(item)

        filler_count = len(LOCATION_NAME_TO_ID) - (len(self.progression_names) - len(starters))
        if filler_count < SUMMIT_FILLER_COUNT:
            raise ValueError("The selected hero items do not leave enough filler for The Summit.")
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
                DEFENSE_OWNER[n] in self.active_heroes
                and state.has(n, self.player)
                and state.has(HERO_BY_KEY[DEFENSE_OWNER[n]].name, self.player)
                for n in ANTI_AIR_DEFENSES)

        for name, wave in LOCATION_WAVE.items():
            if wave == 1:
                continue
            location = self.multiworld.get_location(name, self.player)
            set_rule(location, lambda state, world=self: world._has_usable_combat(state))

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
            "dd1_slot_data_version": 2,
            "active_heroes": list(self.active_heroes),
            "starting_hero": HERO_ITEMS[self.starting_hero],
            "starting_map": MAP_ITEMS[self.starting_map],
            "starting_minion": self.starting_minion,
            "level_six_heroes": [HERO_ITEMS[self.starting_hero], HERO_ITEMS[self.second_hero]],
            "early_anti_air": self.early_anti_air,
            # Hard-or-higher Summit victory is the goal signal, not a location.
            "goal": "summit_" + self.options.summit_goal_difficulty.current_key + "_or_higher",
            "summit_required_maps": self.options.summit_required_maps.value,
            "summit_unlock_difficulty": self.options.summit_unlock_difficulty.value,
            "summit_goal_difficulty": self.options.summit_goal_difficulty.value,
            "experience_multiplier": self.options.experience_multiplier.value,
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
