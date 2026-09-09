"""Generation for the selectable 0.5.0 check packs."""
from BaseClasses import Item, ItemClassification, Location, Region
from worlds.AutoWorld import World
from .options import DungeonDefendersOptions
from .heroes import HERO_BY_KEY, choose_opening, validate_roster
from .items import (ITEM_NAME_TO_ID, ITEM_CLASSIFICATIONS, HERO_ITEMS, MAP_ITEMS,
                    MAP_TIERS, DEFENSE_OWNER, ANTI_AIR_DEFENSES, progression_items_for_heroes, SUMMIT_MAP_ITEM)
from .dd1_content import (MAPS, CHALLENGES, CATALOG, ContentSettings, DIFFICULTIES,
    PROGRESSIVE_DIFFICULTY, MODE_ITEMS, XP_REWARDS, MANA_REWARDS, selected_checks,
    validate_budget, mana_for_check)
from .dd1_protocol import START_WAVES

GAME_NAME = 'Dungeon Defenders'


class DungeonDefendersItem(Item):
    game = GAME_NAME


class DungeonDefendersLocation(Location):
    game = GAME_NAME


class DungeonDefendersWorld(World):
    game = GAME_NAME
    options_dataclass = DungeonDefendersOptions
    item_name_to_id = ITEM_NAME_TO_ID
    location_name_to_id = {c.name: c.address for c in CATALOG}

    def generate_early(self):
        values = {key: getattr(self.options, key).value for key in ContentSettings.__dataclass_fields__}
        for field in ('survival_checks', 'challenge_checks', 'difficulty_unlocks', 'survival_unlock', 'challenge_unlock'):
            values[field] = bool(values[field])
        values['completion_goal'] = self.options.completion_goal.current_key
        self.content = ContentSettings(**values)
        self.active_heroes = validate_roster(self.options.active_heroes.value)
        self.progression_names = progression_items_for_heroes(self.active_heroes,
            include_summit=self.content.completion_goal == 'challenges') + self.content.unlock_items()
        self.checks = selected_checks(self.content)
        self.check_by_name = {c.name: c for c in self.checks}
        self.reserved_filler = sum(c.map_tag == 'CAMPTS' for c in self.checks)
        # Validate before drawing a starter: Summoner's free minion must not
        # determine whether an otherwise over-budget YAML happens to generate.
        validate_budget(self.checks, len(self.progression_names) - 2, reserved_filler=self.reserved_filler)
        opening = choose_opening(self.active_heroes, self.random)
        self.starting_hero = HERO_BY_KEY[opening.starting_hero].name
        self.second_hero = HERO_BY_KEY[opening.second_hero].name
        self.starting_map = 'The Deeper Well Map'
        self.starting_minion = opening.starting_minion
        self.first_wave_reward = opening.first_wave_reward
        self.extra_defenses = opening.extra_defenses
        self.early_anti_air = opening.anti_air
        self.starting_items = {self.starting_hero, self.starting_map}
        if self.starting_minion:
            self.starting_items.add(self.starting_minion)
        self.locked_rewards = set()

    def create_item(self, name):
        classification = ITEM_CLASSIFICATIONS[name]
        if ((name == MODE_ITEMS['survival'] and not self.content.survival_checks)
            or (name == MODE_ITEMS['challenge'] and not self.content.challenge_checks)):
            classification = ItemClassification.useful
        return DungeonDefendersItem(name, classification, ITEM_NAME_TO_ID[name], self.player)

    def _has_difficulty(self, state, minimum):
        return (not self.content.difficulty_unlocks or minimum == 0
            or state.has(PROGRESSIVE_DIFFICULTY, self.player, minimum))

    def _has_mode(self, state, mode):
        needed = self.content.survival_unlock if mode == 'survival' else self.content.challenge_unlock if mode == 'challenge' else False
        return not needed or state.has(MODE_ITEMS[mode], self.player)

    def _has_anti_air(self, state):
        return any(DEFENSE_OWNER[n] in self.active_heroes and state.has(n, self.player)
            and state.has(HERO_BY_KEY[DEFENSE_OWNER[n]].name, self.player) for n in ANTI_AIR_DEFENSES)

    def _has_combat(self, state):
        return any(state.has(HERO_BY_KEY[key].name, self.player)
            and (not HERO_BY_KEY[key].builder or any(tool.damaging
                and state.has(HERO_BY_KEY[key].item_name(tool), self.player)
                for tool in HERO_BY_KEY[key].defenses)) for key in self.active_heroes)

    def _has_attacking_hero(self, state):
        return any(key != 'summoner' and state.has(HERO_BY_KEY[key].name, self.player) for key in self.active_heroes)

    def _check_rule(self, state, check):
        if not self._has_difficulty(state, check.difficulty) or not self._has_mode(state, check.mode):
            return False
        if check.mode == 'campaign':
            return self._has_combat(state) or (check.wave == START_WAVES[check.map_tag] and self._has_attacking_hero(state))
        if not self._has_combat(state):
            return False
        if check.mode == 'survival':
            return check.wave <= 5 or self._has_anti_air(state)
        if check.challenge_tag in ('SPECDW', 'SPECSQ', 'SPECHC', 'SPECES'):
            return self._has_attacking_hero(state)
        return True

    def _event(self, region, name, rule):
        event = DungeonDefendersLocation(self.player, name + ' Event', None, region)
        event.access_rule = rule
        event.place_locked_item(DungeonDefendersItem(name, ItemClassification.progression, None, self.player))
        region.locations.append(event)

    def _map_item_allowed(self, item, check):
        if item.game != GAME_NAME or item.name not in MAP_ITEMS:
            return True
        if not check.campaign_core:
            return False
        # Keep the existing easiest-check/map-band policy wherever a global
        # map lands in DD1. Remote games use their own location access rules.
        lowest = DIFFICULTIES.index(self.content.campaign_check_difficulties[0])
        if check.difficulty != lowest:
            return False
        host_tier = MAP_TIERS[1] if item.name in MAP_TIERS[2] or item.name == SUMMIT_MAP_ITEM else MAP_TIERS[0]
        return check.map_tag in {MAP_ITEMS[name] for name in host_tier}

    def create_regions(self):
        self.map_regions = {}
        menu = Region('Menu', self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        clear_names = tuple(m.name + ' Cleared' for m in MAPS[:-1])
        for index, m in enumerate(MAPS):
            region = Region(m.name, self.player, self.multiworld)
            self.map_regions[m.tag] = region
            self.multiworld.regions.append(region)
            if m.tag == 'CAMPTS' and self.content.completion_goal == 'summit':
                rule = lambda state: sum(state.has(n, self.player) for n in clear_names) >= self.content.summit_required_maps
            else:
                map_item = next(n for n, tag in MAP_ITEMS.items() if tag == m.tag)
                rule = lambda state, n=map_item, tier2=index >= 4: state.has(n, self.player) and (not tier2 or self._has_anti_air(state))
            menu.connect(region, rule=rule)
            if m.tag != 'CAMPTS' and self.content.completion_goal == 'summit':
                self._event(region, m.name + ' Cleared', lambda state: self._has_combat(state)
                            and self._has_difficulty(state, self.content.summit_unlock_difficulty))
        for c in self.checks:
            region = self.map_regions[c.map_tag]
            loc = DungeonDefendersLocation(self.player, c.name, c.address, region)
            loc.access_rule = lambda state, check=c: self._check_rule(state, check)
            if c.map_tag == 'CAMPTS':
                loc.item_rule = lambda item: item.classification == ItemClassification.filler
            else:
                # Applies to map items for every DD1 player, not only this slot.
                loc.item_rule = lambda item, check=c: self._map_item_allowed(item, check)
            region.locations.append(loc)
        if self.content.completion_goal == 'summit':
            self._event(self.map_regions['CAMPTS'], 'DD1 Goal', lambda state:
                self._has_combat(state) and self._has_difficulty(state, self.content.summit_goal_difficulty))
            self.multiworld.completion_condition[self.player] = lambda state: state.has('DD1 Goal', self.player)
        else:
            for challenge in CHALLENGES:
                self._event(self.map_regions[challenge.parent], challenge.name + ' Cleared',
                    lambda state, tag=challenge.tag: self._has_mode(state, 'challenge')
                    and self._has_difficulty(state, self.content.challenge_goal_difficulty)
                    and self._has_combat(state)
                    and (tag not in ('SPECDW', 'SPECSQ', 'SPECHC', 'SPECES') or self._has_attacking_hero(state)))
            self.multiworld.completion_condition[self.player] = lambda state: sum(
                state.has(c.name + ' Cleared', self.player) for c in CHALLENGES) >= self.content.challenges_required
        self._place_opening_and_maps()

    def _place(self, check, item):
        location = self.multiworld.get_location(check.name, self.player)
        if location.item is not None:
            raise ValueError('Opening placement collision at ' + check.name)
        location.place_locked_item(self.create_item(item))
        self.locked_rewards.add(item)

    def _place_opening_and_maps(self):
        lowest = DIFFICULTIES.index(self.content.campaign_check_difficulties[0])
        first = sorted((c for c in self.checks if c.map_tag == 'CAMPDW'
            and c.mode == 'campaign' and c.difficulty == lowest), key=lambda c: c.wave)
        if self.first_wave_reward:
            self._place(first[0], self.first_wave_reward)
        for c, n in ((first[1], self.second_hero), (first[2], self.extra_defenses[0]), (first[4], self.extra_defenses[1])):
            self._place(c, n)
        if self.options.map_unlock_placement.current_key == 'global':
            # Leave maps in the normal AP progression pool. Other worlds' rules
            # determine their reachable checks; our local route stays unchanged.
            return
        def place_map(item, host):
            choices = [c for c in self.checks if c.map_tag == host and c.campaign_core
                and c.difficulty == lowest and self.multiworld.get_location(c.name, self.player).item is None]
            if not choices:
                raise ValueError('No eligible campaign check remains for the map route at ' + host)
            self._place(self.random.choice(choices), item)
        tier1 = [n for n in MAP_TIERS[0] if n != self.starting_map]
        self.random.shuffle(tier1)
        connected = ['CAMPDW']
        for item in tier1:
            place_map(item, connected[0] if len(connected) == 1 else self.random.choice(connected[1:]))
            connected.append(MAP_ITEMS[item])
        hosts = [MAP_ITEMS[n] for n in tier1]
        self.random.shuffle(hosts)
        tier2 = list(MAP_TIERS[1])
        self.random.shuffle(tier2)
        for item, host in zip(tier2, hosts, strict=True):
            place_map(item, host)
        hosts = [MAP_ITEMS[n] for n in tier2]
        hosts.append(self.random.choice(hosts))
        self.random.shuffle(hosts)
        tier3 = list(MAP_TIERS[2])
        self.random.shuffle(tier3)
        for item, host in zip(tier3, hosts, strict=True):
            place_map(item, host)
        if self.content.completion_goal == 'challenges':
            place_map(SUMMIT_MAP_ITEM, self.random.choice(hosts))

    def create_items(self):
        for name in self.progression_names:
            if name in self.starting_items:
                self.multiworld.push_precollected(self.create_item(name))
            elif name not in self.locked_rewards:
                self.multiworld.itempool.append(self.create_item(name))
        filler = validate_budget(self.checks, len(self.progression_names) - len(self.starting_items),
                                 reserved_filler=self.reserved_filler)
        names = tuple(XP_REWARDS) + tuple(MANA_REWARDS)
        bag = []
        for _ in range(filler):
            if not bag:
                bag = list(names)
                self.random.shuffle(bag)
            self.multiworld.itempool.append(self.create_item(bag.pop()))

    def post_fill(self):
        for location in self.multiworld.get_filled_locations():
            old = location.item
            if old.player != self.player or old.name not in MANA_REWARDS:
                continue
            host = self.multiworld.worlds[location.player]
            if host.game != self.game or location.name not in host.check_by_name:
                continue
            name = mana_for_check(host.check_by_name[location.name])
            if old.name == name:
                continue
            new = self.create_item(name)
            location.item, new.location = new, location
            old.location = None
            for index, item in enumerate(self.multiworld.itempool):
                if item is old:
                    self.multiworld.itempool[index] = new
                    break

    def get_filler_item_name(self):
        return self.random.choice(tuple(XP_REWARDS) + tuple(MANA_REWARDS))

    def fill_slot_data(self):
        return {**self.content.slot_data(), 'active_heroes': list(self.active_heroes),
            'map_unlock_placement': self.options.map_unlock_placement.current_key,
            'starting_hero': HERO_ITEMS[self.starting_hero], 'starting_map': 'CAMPDW',
            'starting_minion': self.starting_minion,
            'level_six_heroes': [HERO_ITEMS[self.starting_hero], HERO_ITEMS[self.second_hero]],
            'early_anti_air': self.early_anti_air,
            'experience_multiplier': self.options.experience_multiplier.value}
