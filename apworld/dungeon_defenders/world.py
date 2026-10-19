"""Dungeon Defenders Archipelago generation."""
from BaseClasses import Item, ItemClassification, Location, Region
from worlds.AutoWorld import World
from .options import DungeonDefendersOptions
from .heroes import HERO_BY_KEY, choose_opening, validate_roster
from .chaos_loadouts import generate_for_world, validate_slot_mapping, recipient_item_names
from .items import (ITEM_NAME_TO_ID, ITEM_CLASSIFICATIONS, HERO_ITEMS, MAP_ITEMS,
                    MAP_TIERS, DEFENSE_OWNER, ANTI_AIR_DEFENSES, progression_items_for_heroes, SUMMIT_MAP_ITEM)
from .dd1_content import (MAPS, CHALLENGES, CATALOG, ContentSettings, DIFFICULTIES, CHAOS_SLOT_DATA_VERSION,
    PROGRESSIVE_DIFFICULTY, MODE_ITEMS, XP_REWARDS, MANA_REWARDS, SCALED_MANA_ITEM, selected_checks,
    validate_budget, AREA_ITEMS, BUILD_TIME_ITEM, map_area, filler_mix_counts)
from .dd1_protocol import START_WAVES
from .dd1_traps import replace_filler_with_traps
from .dd1_shop import MAP_REQUIREMENTS
from .dd1_cosmetic_rewards import CRYSTAL_ITEMS, GEAR_ITEM
from .dd1_hero_skins import selected_skin_items
from .dd1_campaign import (BASE_MAPS, SHARD_TAGS, CD_TAG, enabled_maps, EXTRA_MAP_ITEMS,
    ETERNIA_SHARD_ITEMS, LATE_GEAR_MAPS)
from .hero_logic import (area_requirements, count_usable_heroes, hero_action_names,
                        ACTION_HERO, install_hero_order_rule, has_high_difficulty_support)
from .combat_logic import (combat_tier, gear_event, difficulty_deadline, MAP_STAGE,
                           LATE_BASE, INSANE_FARM_MAPS, PREDECESSORS)

GAME_NAME = 'Dungeon Defenders'
MAP_NAMES = {m.tag: m.name for m in MAPS}


def map_event(tag, purpose):
    return f'{MAP_NAMES[tag]} - {purpose}'


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
        values = {key: getattr(self.options, key).value for key in ContentSettings.__dataclass_fields__
                  if key not in ('goal_check_limits', 'platinum_shop')}
        for field in ('death_link', 'hero_skin_items', 'hero_skins_unlocked', 'extra_campaign_maps', 'shopsanity', 'random_gear_pets', 'progressive_defense_units', 'survival_checks', 'challenge_checks', 'difficulty_unlocks', 'survival_unlock', 'challenge_unlock'):
            values[field] = bool(values[field])
        values['completion_goal'] = self.options.completion_goal.current_key
        values['platinum_shop'] = values['shopsanity'] and values['completion_goal'] == 'crystalline_dimension'
        values['death_link_mode'] = self.options.death_link_mode.current_key
        values['crystalline_dimension_unlock'] = self.options.crystalline_dimension_unlock.current_key
        values['check_density'] = self.options.check_density.current_key
        self.content = ContentSettings(**values)
        self.campaign_maps = enabled_maps(self.content)
        self.map_tags = {m.tag for m in self.campaign_maps}
        if not set(self.content.campaign_check_difficulties) & {'easy', 'medium', 'hard'}:
            raise ValueError('Map unlocks require campaign checks on Easy, Medium, or Hard. Select at least one of these difficulties.')
        if self.options.map_unlock_placement.current_key == 'local':
            self.options.local_items.value.update(MAP_ITEMS)
        self.active_heroes = validate_roster(self.options.active_heroes.value)
        self.hero_action_names = hero_action_names(self.active_heroes)
        self.progression_names = progression_items_for_heroes(self.active_heroes,
            include_summit=self.content.completion_goal != 'summit', map_tags=self.map_tags) + self.content.unlock_items()
        if self.content.crystalline_dimension_unlock == 'eternia_shards':
            self.progression_names += tuple(ETERNIA_SHARD_ITEMS)
        if self.content.hero_skin_items:
            self.progression_names += selected_skin_items(self.active_heroes)
        self.checks = selected_checks(self.content)
        self.build_time_count = self.content.build_time_items(self.checks)
        self.progression_names += (BUILD_TIME_ITEM,) * self.build_time_count
        self.check_by_name = {c.name: c for c in self.checks}
        self.reserved_filler = sum(c.map_tag == 'CAMPTS' for c in self.checks) if self.content.completion_goal != 'crystalline_dimension' else 0
        # Validate before drawing a starter: Summoner's free minion must not
        # determine whether an otherwise over-budget YAML happens to generate.
        validate_budget(self.checks, len(self.progression_names) - 2, reserved_filler=self.reserved_filler)
        self.chaos_loadout = None
        self.action_owners = ACTION_HERO
        if self.options.skill_shuffle:
            self.chaos_loadout, assignments, opening = generate_for_world(
                self.active_heroes, self.player, self.random,
                mode=self.options.skill_shuffle_mode.current_key)
            self.action_owners = {a.item: HERO_BY_KEY[a.recipient].name for a in assignments}
        else:
            opening = choose_opening(self.active_heroes, self.random)
        self.crystal_roll = self.random.randrange(1_000_000_000)
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
        # Survival can be required for gear even when it has no AP checks.
        if name in AREA_ITEMS['challenge'] and not self.content.challenge_checks:
            classification = ItemClassification.useful
        return DungeonDefendersItem(name, classification, ITEM_NAME_TO_ID[name], self.player)

    def _has_difficulty(self, state, minimum):
        return self._owns_difficulty(state, minimum) and (minimum < 4 or
            has_high_difficulty_support(self.active_heroes,
                lambda name: state.has(name, self.player), self.action_owners))

    def _owns_difficulty(self, state, minimum):
        # Item deadlines must not also require the later roster readiness gates.
        return (not self.content.difficulty_unlocks or minimum <= self.content.starting_difficulty
                or state.has(PROGRESSIVE_DIFFICULTY, self.player, minimum - self.content.starting_difficulty))

    def _has_difficulty_route(self, state, tag):
        # Deadlines now belong to combat tiers, not the map-selection door.
        return True

    def _has_tier(self, state, tier):
        if not self._owns_difficulty(state, difficulty_deadline(tier)):
            return False
        roster_tag = 'CAMPTS' if tier >= 4 else 'CAMPRG' if tier == 3 else 'CAMPSQ' if tier == 2 else 'CAMPDW'
        if not self._has_area_progress(state, roster_tag):
            return False
        if tier >= 5 and not has_high_difficulty_support(
                self.active_heroes, lambda name: state.has(name, self.player), self.action_owners):
            return False
        # The base campaign has no tier 7/8 campaign maps. Its explicit,
        # difficult Nightmare Survival route prepares for early Ruthless;
        # do not manufacture higher gear tiers from low-difficulty Survival.
        if tier == 9 and self.content.completion_goal != 'crystalline_dimension':
            return state.has('Late Campaign Nightmare Survival Farming', self.player)
        return tier <= 1 or state.has(gear_event(tier - 1), self.player)

    def _combat_rule(self, state, tag, difficulty, mode='campaign', wave=0, victory=True):
        tier = combat_tier(tag, difficulty, mode, wave, victory)
        if not self._has_difficulty(state, difficulty) or not self._has_tier(state, tier):
            return False
        if difficulty >= 4 and not state.has('Late Campaign Insane Farming', self.player):
            return False
        # On the extended campaign, difficult low-difficulty bosses require
        # real Insane farming access, not merely owning Insane or many heroes.
        if self.content.completion_goal == 'crystalline_dimension' and tier >= 6:
            if not state.has('Extended Campaign Insane Farming', self.player):
                return False
        if difficulty == 5 and self.content.completion_goal != 'crystalline_dimension':
            if not state.has('Late Campaign Nightmare Survival Farming', self.player):
                return False
            if tier >= 10 and not state.has('Deeper Well Ruthless Survival Farming', self.player):
                return False
        return True

    def _has_mode(self, state, mode, tag):
        needed = self.content.survival_unlock if mode == 'survival' else self.content.challenge_unlock if mode == 'challenge' else False
        return not needed or state.has(AREA_ITEMS[mode][map_area(tag)], self.player)

    def _has_anti_air(self, state):
        return any(DEFENSE_OWNER[n] in self.active_heroes and state.has(n, self.player)
            and state.has(self.action_owners[n], self.player) for n in ANTI_AIR_DEFENSES)

    def _has_combat(self, state):
        if self.chaos_loadout is not None:
            return count_usable_heroes(self.active_heroes, lambda name: state.has(name, self.player), self.action_owners) > 0
        return any(state.has(HERO_BY_KEY[key].name, self.player)
            and (not HERO_BY_KEY[key].builder or any(tool.damaging
                and state.has(HERO_BY_KEY[key].item_name(tool), self.player)
                for tool in HERO_BY_KEY[key].defenses)) for key in self.active_heroes)

    def _has_attacking_hero(self, state):
        return any(key != 'summoner' and state.has(HERO_BY_KEY[key].name, self.player) for key in self.active_heroes)

    def _has_area_progress(self, state, map_tag):
        if map_tag not in {m.tag for m in BASE_MAPS}:
            map_tag = 'CAMPAL' if map_tag == 'CDTCDD' else 'CAMPTS'
        required_heroes, required_actions = area_requirements(map_tag, self.active_heroes)
        if count_usable_heroes(
            self.active_heroes, lambda name: state.has(name, self.player), self.action_owners
        ) < required_heroes:
            return False
        return sum(state.has(name, self.player) and state.has(self.action_owners[name], self.player)
                   for name in self.hero_action_names) >= required_actions

    @classmethod
    def stage_pre_fill(cls, multiworld):
        for location in multiworld.get_locations():
            install_hero_order_rule(location)

    def fill_hook(self, progitempool, usefulitempool, filleritempool, fill_locations):
        # Reverse fill must place actions while their owning heroes are still
        # assumed. Otherwise a hero can be removed before its many dependents,
        # forcing unsafe swaps and circular multiworld placements. This only
        # orders the fill operation; locations and receipt spheres stay random.
        indices = [i for i, item in enumerate(progitempool) if item.player == self.player]
        def fill_order(item):
            if item.name in HERO_ITEMS:
                return 0
            if item.name == PROGRESSIVE_DIFFICULTY:
                return 1
            if item.name in MAP_ITEMS:
                # Map items have stage-limited hosts, so retain early map
                # access in assumed state until late-stage maps are placed.
                return 10 + MAP_STAGE[MAP_ITEMS[item.name]]
            return 30 if item.name in ACTION_HERO else 25
        items = sorted((progitempool[i] for i in indices), key=fill_order)
        for index, item in zip(indices, items):
            progitempool[index] = item

    def _has_survival_map_progress(self, state, wave):
        required = 4 if wave <= 10 else 8 if wave <= 16 else 12
        return sum(self.map_regions[m.tag].can_reach(state) for m in BASE_MAPS) >= required

    def _check_rule(self, state, check):
        if check.mode == 'shop':
            return sum(state.has(m.name + ' Shop Clear', self.player) for m in self.campaign_maps) >= MAP_REQUIREMENTS[check.wave // 9]
        tag = check.challenge_tag if check.mode == 'challenge' else check.map_tag
        if (not self._combat_rule(state, tag, check.difficulty, check.mode, check.wave, check.victory)
                or not self._has_mode(state, check.mode, check.map_tag)):
            return False
        if check.mode == 'campaign':
            return self._has_combat(state) or (check.wave == START_WAVES[check.map_tag] and self._has_attacking_hero(state))
        if not self._has_combat(state):
            return False
        if check.mode == 'survival':
            return self._has_survival_map_progress(state, check.wave) and (check.wave <= 5 or self._has_anti_air(state))
        if not self._has_difficulty(state, 2) or not self._has_difficulty_route(state, check.map_tag):
            return False
        if check.challenge_tag in ('SPECDW', 'SPECSQ', 'SPECHC', 'SPECES'):
            return self._has_attacking_hero(state)
        return True

    def _event(self, region, name, rule, item_name=None):
        event = DungeonDefendersLocation(self.player, name + ' Event', None, region)
        event.access_rule = rule
        event.place_locked_item(DungeonDefendersItem(item_name or name, ItemClassification.progression, None, self.player))
        region.locations.append(event)

    def _map_item_allowed(self, item, check):
        if item.game != GAME_NAME or item.name not in MAP_ITEMS:
            return True
        if check.mode != 'campaign' or (check.map_tag == 'CAMPTS' and self.content.completion_goal != 'crystalline_dimension'):
            return False
        if check.difficulty > 2:
            return False
        target_tag = MAP_ITEMS[item.name]
        target_tier, host_tier = MAP_STAGE[target_tag], MAP_STAGE[check.map_tag]
        if item.name in EXTRA_MAP_ITEMS:
            # Extra maps remain random. Do not make optional branch maps the
            # only possible hosts for the mandatory Shards route.
            return host_tier <= target_tier and check.map_tag != CD_TAG and (
                target_tag == 'CDTCDD' or check.map_tag != 'CAMPDW')
        # Early maps stay in the first group; middle maps start beyond Deeper
        # Well; final maps start in the middle group. Same-group hosts allow
        # sparse-density seeds to retain a connected route.
        return (max(0, target_tier - 1) <= host_tier <= target_tier
                and not (target_tier > 0 and check.map_tag == 'CAMPDW'))

    def _shop_item_allowed(self, item, check):
        # Shops may contain progression, useful items, hero levels, gear and
        # crystal skins.  Bank mana would merely sell mana for mana and is the
        # only DD1 reward excluded in addition to the existing map-item rule.
        return (self._map_item_allowed(item, check)
            and not (item.game == GAME_NAME and (item.name in MANA_REWARDS or item.name == SCALED_MANA_ITEM)))

    def create_regions(self):
        self.map_regions = {}
        self.challenge_regions = {}
        menu = Region('Menu', self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        shop = Region('Tavern Shop', self.player, self.multiworld)
        self.multiworld.regions.append(shop)
        menu.connect(shop)
        clear_names = tuple(m.name + ' Cleared' for m in BASE_MAPS[:-1])
        for index, m in enumerate(self.campaign_maps):
            region = Region(m.name, self.player, self.multiworld)
            self.map_regions[m.tag] = region
            self.multiworld.regions.append(region)
            if m.tag == 'CAMPTS' and self.content.completion_goal == 'summit':
                rule = lambda state: (sum(state.has(n, self.player) for n in clear_names) >= self.content.summit_required_maps
                    and self._has_difficulty_route(state, 'CAMPTS')
                    and self._has_area_progress(state, 'CAMPTS'))
            elif m.tag == CD_TAG:
                rule = self._can_access_cd
            else:
                map_item = next(n for n, tag in MAP_ITEMS.items() if tag == m.tag)
                rule = lambda state, n=map_item, tag=m.tag, tier2=index >= 4: (state.has(n, self.player)
                    and self._has_area_progress(state, tag)
                    and self._has_difficulty_route(state, tag)
                    and (not tier2 or tag == 'CDTCDD' or self._has_anti_air(state))
                    and self._has_campaign_stage(state, tag))
            predecessor = PREDECESSORS.get(m.tag)
            # Explicit graph edges let AP invalidate reachability correctly
            # during restrictive fill and multiworld progression balancing.
            parent = self.map_regions[predecessor] if predecessor else menu
            parent.connect(region, rule=rule)
            if self.content.shopsanity:
                self._event(region, m.name + ' Shop Clear', lambda state, tag=m.tag:
                    self._has_combat(state) and self._combat_rule(state, tag, 0))
            if m.tag != 'CAMPTS' and self.content.completion_goal == 'summit':
                self._event(region, m.name + ' Cleared', lambda state, tag=m.tag: self._has_combat(state)
                            and self._combat_rule(state, tag, self.content.summit_unlock_difficulty))
            if m.tag in SHARD_TAGS:
                self._event(region, map_event(m.tag, 'Shard Clear'), lambda state, tag=m.tag:
                    self._has_combat(state) and self._has_anti_air(state)
                    and self._combat_rule(state, tag, self.content.crystalline_dimension_difficulty))
            if self.content.crystalline_dimension_unlock == 'eternia_shards' and (
                    m.tag == 'CAMPSC' or m.tag in LATE_GEAR_MAPS):
                # Reachability events model being able to farm, not victories.
                # Events also make indirect route dependencies visible to AP's
                # reachability cache and multiworld progression balancing.
                self._event(region, map_event(m.tag, 'Farming Access for CD'), lambda state, tag=m.tag:
                    self._has_combat(state) and self._has_anti_air(state)
                    and self._combat_rule(state, tag, 0, victory=False))
            if m.tag not in {base.tag for base in BASE_MAPS}:
                continue
            challenge_region = Region(m.name + ' Challenge', self.player, self.multiworld)
            self.multiworld.regions.append(challenge_region)
            self.challenge_regions[m.tag] = challenge_region
            if self.content.challenge_unlock:
                menu.connect(challenge_region, rule=lambda state, tag=m.tag:
                    self._has_mode(state, 'challenge', tag)
                    and self._has_area_progress(state, tag))
            else:
                region.connect(challenge_region)
        self._create_farming_events()
        for c in self.checks:
            region = shop if c.mode == 'shop' else (self.challenge_regions if c.mode == 'challenge' else self.map_regions)[c.map_tag]
            loc = DungeonDefendersLocation(self.player, c.name, c.address, region)
            loc.access_rule = lambda state, check=c: self._check_rule(state, check)
            if c.mode == 'shop':
                loc.item_rule = lambda item, check=c: self._shop_item_allowed(item, check)
            elif c.map_tag == 'CAMPTS' and self.content.completion_goal != 'crystalline_dimension':
                loc.item_rule = lambda item: item.classification in (ItemClassification.filler, ItemClassification.trap)
            else:
                # Applies to map items for every DD1 player, not only this slot.
                loc.item_rule = lambda item, check=c: self._map_item_allowed(item, check)
            region.locations.append(loc)
        if self.content.completion_goal == 'summit':
            self._event(self.map_regions['CAMPTS'], 'DD1 Goal', lambda state:
                self._has_combat(state) and self._owns_difficulty(state, 5)
                and self._combat_rule(state, 'CAMPTS', self.content.summit_goal_difficulty))
            self.multiworld.completion_condition[self.player] = lambda state: state.has('DD1 Goal', self.player)
        elif self.content.completion_goal == 'crystalline_dimension':
            self._event(self.map_regions[CD_TAG], 'DD1 Goal', lambda state:
                self._has_combat(state) and self._has_anti_air(state)
                and self._combat_rule(state, CD_TAG, self.content.crystalline_dimension_difficulty))
            self.multiworld.completion_condition[self.player] = lambda state: state.has('DD1 Goal', self.player)
        else:
            for challenge in CHALLENGES:
                self._event(self.challenge_regions[challenge.parent], challenge.name + ' Cleared',
                    lambda state, tag=challenge.tag, parent=challenge.parent: self._has_mode(state, 'challenge', parent)
                    and self._has_difficulty(state, 2)
                    and self._combat_rule(state, tag, self.content.challenge_goal_difficulty, 'challenge')
                    and self._has_combat(state)
                    and (tag not in ('SPECDW', 'SPECSQ', 'SPECHC', 'SPECES') or self._has_attacking_hero(state)))
            self.multiworld.completion_condition[self.player] = lambda state: sum(
                state.has(c.name + ' Cleared', self.player) for c in CHALLENGES) >= self.content.challenges_required and self._owns_difficulty(state, 5)
        self._place_opening_and_maps()

    def _has_campaign_stage(self, state, tag):
        # Ordering is represented by graph edges. Requiring a predecessor win
        # at the CD goal difficulty here would lock away lower-difficulty gear
        # needed to make that very win possible (especially NM/Ruthless).
        if tag in PREDECESSORS:
            return state.has(map_event(PREDECESSORS[tag], 'Campaign Route Clear'), self.player)
        return True

    def _create_farming_events(self):
        for m in self.campaign_maps:
            if m.tag == CD_TAG or (m.tag == 'CAMPTS' and self.content.completion_goal == 'summit'):
                # Never require farming the goal to prepare for the goal.
                continue
            region = self.map_regions[m.tag]
            self._event(region, m.name + ' - Easy Campaign Clear (Route)', lambda state, tag=m.tag:
                self._has_combat(state) and self._combat_rule(state, tag, 0),
                map_event(m.tag, 'Campaign Route Clear'))
            for difficulty in range(6):
                # Only the two pre-boss exceptions have distinct access rules.
                # Avoid two equivalent events for every ordinary map/difficulty.
                victories = (False, True) if m.tag in ('CAMPPA', 'CAMPJ2') else (True,)
                for victory in victories:
                    tier = combat_tier(m.tag, difficulty, victory=victory)
                    stage = 'Clear' if victory else 'Pre-Boss Waves'
                    self._event(region, f'{m.name} - {DIFFICULTIES[difficulty].title()} Campaign {stage} (Farming)',
                        lambda state, tag=m.tag, d=difficulty, v=victory:
                            self._has_combat(state) and self._combat_rule(state, tag, d, victory=v),
                        gear_event(tier))
                # No generic Survival gear events: its gear is conservatively
                # represented by the same map/difficulty's campaign source.
                # Harder Survival checks do not imply better-quality gear.
            if m.tag in LATE_BASE:
                self._event(region, m.name + ' - Insane Campaign Clear (Nightmare Preparation)', lambda state, tag=m.tag:
                    self._has_combat(state) and self._combat_rule(state, tag, 3),
                    'Late Campaign Insane Farming')
                if self.content.completion_goal != 'crystalline_dimension':
                    self._event(region, m.name + ' - Nightmare Survival Wave 25 (Ruthless Preparation)', lambda state, tag=m.tag:
                        self._has_combat(state) and self._has_anti_air(state)
                        and self._has_mode(state, 'survival', tag)
                        and self._combat_rule(state, tag, 4, 'survival', 25),
                        'Late Campaign Nightmare Survival Farming')
            if m.tag in INSANE_FARM_MAPS:
                # Farming early waves for gear is possible before a full clear.
                # This preparation event has no AP check or item placement.
                self._event(region, m.name + ' - Insane Early Waves (DLC Preparation)', lambda state:
                    self._has_combat(state) and self._has_anti_air(state)
                    and self._has_difficulty(state, 3) and self._has_tier(state, 5),
                    'Extended Campaign Insane Farming')
            if m.tag == 'CAMPDW' and self.content.completion_goal != 'crystalline_dimension':
                self._event(region, 'Deeper Well Ruthless Survival Farming', lambda state:
                    self._has_combat(state) and self._has_anti_air(state)
                    and self._has_mode(state, 'survival', 'CAMPDW')
                    and self._combat_rule(state, 'CAMPDW', 5))

    def _can_access_cd(self, state):
        if self.content.crystalline_dimension_unlock == 'shard_maps':
            return all(state.has(map_event(tag, 'Shard Clear'), self.player) for tag in SHARD_TAGS)
        # The four items unlock the actual door. Generation additionally needs
        # a suitable gear route, not four obligatory victories under a new name.
        # Sky City access implies all four Shards map items plus the base route.
        return (all(state.has(name, self.player) for name in ETERNIA_SHARD_ITEMS)
                and self._has_difficulty(state, self.content.crystalline_dimension_difficulty)
                and self._has_combat(state) and self._has_anti_air(state)
                and state.has(map_event('CAMPSC', 'Farming Access for CD'), self.player)
                and (not self.content.extra_campaign_maps or
                     sum(state.has(map_event(tag, 'Farming Access for CD'), self.player) for tag in LATE_GEAR_MAPS) >= 3))

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
        if self.options.map_unlock_placement.current_key == 'local':
            # Reserve a connected, shuffled route before filling other items.
            # Each next map is found in the preceding map, so late maps cannot
            # replace the early route or be buried in optional modes.
            previous = self.starting_map
            for tier in MAP_TIERS:
                maps = [n for n in tier if n in self.progression_names
                        and n not in self.starting_items]
                self.random.shuffle(maps)
                if SUMMIT_MAP_ITEM in maps:
                    maps.remove(SUMMIT_MAP_ITEM)
                    maps.append(SUMMIT_MAP_ITEM)
                for name in maps:
                    candidates = [c for c in self.checks
                        if c.campaign_core and c.map_tag == MAP_ITEMS[previous]
                        and c.difficulty == lowest
                        and self.multiworld.get_location(c.name, self.player).item is None]
                    if not candidates:
                        raise ValueError('Not enough campaign checks for the map route after ' + previous)
                    self._place(self.random.choice(candidates), name)
                    previous = name

    def create_items(self):
        for name in self.progression_names:
            if name in self.starting_items:
                self.multiworld.push_precollected(self.create_item(name))
            elif name not in self.locked_rewards:
                self.multiworld.itempool.append(self.create_item(name))
        filler = validate_budget(self.checks, len(self.progression_names) - len(self.starting_items),
                                 reserved_filler=self.reserved_filler)
        skins = [name for index, name in enumerate(CRYSTAL_ITEMS)
                 if index != self.crystal_roll % len(CRYSTAL_ITEMS)]
        self.random.shuffle(skins)
        mana_count, level_count, gear_count, skin_count = filler_mix_counts(filler, len(skins))
        filler_names = skins[:skin_count]
        mana_bag = []
        for _ in range(mana_count):
            if not mana_bag:
                mana_bag = ([SCALED_MANA_ITEM] if self.content.completion_goal == 'crystalline_dimension'
                            else list(MANA_REWARDS))
                self.random.shuffle(mana_bag)
            filler_names.append(mana_bag.pop())
        filler_names.extend((next(iter(XP_REWARDS)),) * level_count)
        filler_names.extend((GEAR_ITEM,) * gear_count)
        self.random.shuffle(filler_names)
        from .dd1_themes import add_theme_rewards
        filler_names = add_theme_rewards(filler_names, self.options.tavern_themes.value,
            self.random, set(MANA_REWARDS) | set(XP_REWARDS) | {GEAR_ITEM, SCALED_MANA_ITEM})
        filler_names = replace_filler_with_traps(filler_names,
            self.options.trap_percentage.value, self.options.enabled_traps.value,
            self.random, set(MANA_REWARDS) | set(XP_REWARDS) | {GEAR_ITEM, SCALED_MANA_ITEM})
        for name in filler_names:
            self.multiworld.itempool.append(self.create_item(name))

    def get_filler_item_name(self):
        category = self.random.choice(('mana',) * 3 + ('level',) * 2 + ('gear',) * 3)
        if category == 'mana':
            if self.content.completion_goal == 'crystalline_dimension':
                return SCALED_MANA_ITEM
            return self.random.choice(tuple(MANA_REWARDS))
        if category == 'level':
            return next(iter(XP_REWARDS))
        return GEAR_ITEM

    def fill_slot_data(self):
        return {**self.content.slot_data(), 'active_heroes': list(self.active_heroes),
            'tavern_themes': bool(self.options.tavern_themes.value),
            'trap_percentage': self.options.trap_percentage.value,
            'enabled_traps': sorted(self.options.enabled_traps.value),
            'trap_protocol': 1,
            **({'dd1_slot_data_version': CHAOS_SLOT_DATA_VERSION} if self.chaos_loadout else {}),
            'chaos_loadout': self.chaos_loadout,
            'starting_crystal_roll': self.crystal_roll,
            'map_unlock_placement': self.options.map_unlock_placement.current_key,
            'starting_hero': HERO_ITEMS[self.starting_hero], 'starting_map': 'CAMPDW',
            'starting_minion': self.starting_minion,
            'level_six_heroes': [HERO_ITEMS[self.starting_hero], HERO_ITEMS[self.second_hero]],
            'early_anti_air': self.early_anti_air,
            'experience_multiplier': self.options.experience_multiplier.value,
            'level_catch_up_multiplier': self.options.level_catch_up_multiplier.value}

    def write_spoiler_header(self, spoiler_handle):
        if not self.chaos_loadout:
            return
        assignments = validate_slot_mapping(self.fill_slot_data(), self.player)
        display_names = recipient_item_names(assignments)
        spoiler_handle.write('\nRandomized hero loadouts (names show the receiving hero):\n')
        for key in self.active_heroes:
            names = [display_names[a.item] for a in sorted(assignments, key=lambda a: a.slot) if a.recipient == key]
            spoiler_handle.write(f"  {HERO_BY_KEY[key].name}: " + ', '.join(names) + '\n')
        spoiler_handle.write('\nOriginal AP item names -> names shown by the DD1 client:\n')
        for original, display in display_names.items():
            spoiler_handle.write(f'  {original} -> {display}\n')
