"""Shared Dungeon Defenders settings and check catalog."""
from dataclasses import dataclass, asdict
from collections.abc import Mapping

try:
    from .dd1_campaign import enabled_maps, BASE_MAPS
    from .dd1_protocol import CAMPAIGN_MAPS, START_WAVES, FINAL_WAVES, summit_is_unlocked
except ImportError:
    from dd1_campaign import enabled_maps, BASE_MAPS
    from dd1_protocol import CAMPAIGN_MAPS, START_WAVES, FINAL_WAVES, summit_is_unlocked

SLOT_DATA_VERSION = 16
CHAOS_SLOT_DATA_VERSION = 1003  # Scaling mana requires the matching 0.8.0 client.
SUPPORTED_SLOT_DATA_VERSIONS = frozenset((8, 9, 10, 11, 12, 13, 14, 15, 1001, 1002, SLOT_DATA_VERSION, CHAOS_SLOT_DATA_VERSION))
DIFFICULTIES = ('easy', 'medium', 'hard', 'insane', 'nightmare', 'ruthless')
SUMMIT_MAP_ITEM = 'The Summit Map'
MAPS = CAMPAIGN_MAPS
MODE_ITEMS = {'survival': 'Survival Mode', 'challenge': 'Challenge Mode'}
DIFFICULTY_ITEMS = {d: d.title() + ' Difficulty' for d in DIFFICULTIES[1:]}
# Retain the former individual names only to preserve their network IDs.
PROGRESSIVE_DIFFICULTY = 'Progressive Difficulty'
XP_REWARDS = {'One Hero Level': 1}
MANA_REWARDS = {f'{n:,} Bank Mana': n for n in (25000, 50000, 75000)}
SCALED_MANA_ITEM = 'Bank Mana'
AREA_ITEMS = {mode: tuple(f'{mode.title()} Area {i}' for i in (1, 2, 3))
              for mode in ('survival', 'challenge')}
BUILD_TIME_ITEM = 'Progressive Build Time'
DEFENSE_UNITS_ITEM = 'Progressive Defense Units'
SURVIVAL_START_ITEM = 'Progressive Survival Starting Wave'
FILLER_MIX_WEIGHTS = (3, 2, 3, 2)  # mana, hero levels, random gear, crystal skins


def _weighted_counts(total, weights):
    """Return exact integer counts using largest-remainder apportionment."""
    weight_total = sum(weights)
    counts = [total * weight // weight_total for weight in weights]
    order = sorted(range(len(weights)),
                   key=lambda i: (total * weights[i] % weight_total, weights[i], -i),
                   reverse=True)
    for index in order[:total - sum(counts)]:
        counts[index] += 1
    return tuple(counts)


def filler_mix_counts(total, crystal_cap):
    """30% mana, 20% levels, 30% gear, 20% unique crystal skins.

    Once every available crystal skin is present, its unused share is
    redistributed across the three repeatable rewards in their 3:2:3 ratio.
    """
    if type(total) is not int or total < 0 or type(crystal_cap) is not int or crystal_cap < 0:
        raise ValueError('Filler counts must be non-negative integers.')
    mana, levels, gear, crystals = _weighted_counts(total, FILLER_MIX_WEIGHTS)
    if crystals <= crystal_cap:
        return mana, levels, gear, crystals
    crystals = crystal_cap
    mana, levels, gear = _weighted_counts(total - crystals, FILLER_MIX_WEIGHTS[:3])
    return mana, levels, gear, crystals


def map_area(tag):
    if tag == 'CDTCDD':
        return 0
    return min(2, next(i // 4 for i, m in enumerate(MAPS) if m.tag == tag))


@dataclass(frozen=True)
class Challenge:
    name: str
    tag: str
    parent: str
    start: int
    final: int
    victory_only: bool = False


# Installed map Kismet final-wave values and MapInfo/config start values.
# File-audited for the 0.5.0 playtest; not all challenges have live victory coverage.
CHALLENGES = tuple(Challenge(name, 'SPEC' + m.tag[4:], m.tag, start, final, single)
    for m, (name, start, final, single) in zip(BASE_MAPS, (
        ('No Towers Allowed', 1, 8, False),
        ('Unlikely Allies', 2, 7, False),
        ('Warping Core', 2, 7, False),
        ('Raining Goblins', 3, 9, False),
        ('Wizardry', 3, 6, False),
        ('Ogre Crush', 4, 8, False),
        ('Zippy Terror', 4, 8, False),
        ('Chicken', 4, 8, False),
        ('Moving Core', 3, 7, False),
        ('Death From Above', 5, 10, False),
        ('Assault', 0, 0, True),
        ('Treasure Hunt', 5, 9, False),
    ), strict=True))
CHALLENGE_BY_TAG = {c.tag: c for c in CHALLENGES}


def normalize_difficulties(value):
    if isinstance(value, str):
        value = value.split(',')
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError('campaign_check_difficulties must be a list or comma-separated names.')
    if not all(isinstance(d, str) for d in value):
        raise ValueError('Use difficulty names: easy, medium, hard, insane, nightmare, ruthless.')
    selected = {d.strip().lower() for d in value}
    unknown = selected - set(DIFFICULTIES)
    if unknown:
        raise ValueError('Unknown campaign difficulty: ' + ', '.join(sorted(unknown)))
    if not selected:
        raise ValueError('Select at least one campaign check difficulty for the map-unlock route.')
    return tuple(d for d in DIFFICULTIES if d in selected)


@dataclass(frozen=True)
class ContentSettings:
    # Protocol flag, not a YAML option: old seeds retain their original locations.
    goal_check_limits: bool = True
    death_link: bool = False
    death_link_mode: str = 'hero_death'
    hero_skin_items: bool = False
    hero_skins_unlocked: bool = False
    extra_campaign_maps: bool = False
    crystalline_dimension_difficulty: int = 1
    crystalline_dimension_unlock: str = 'shard_maps'
    shopsanity: bool = False
    # Derived by generation, not a YAML option. Missing in older seeds.
    platinum_shop: bool = False
    random_gear_pets: bool = False
    progressive_defense_units: bool = False
    check_density: str = 'every_wave'
    campaign_check_difficulties: tuple[str, ...] = ('easy', 'medium', 'hard')
    survival_checks: bool = False
    survival_check_difficulty: int = 1
    survival_max_wave: int = 10
    challenge_checks: bool = False
    challenge_check_difficulty: int = 1
    difficulty_unlocks: bool = False
    starting_difficulty: int = 1
    survival_unlock: bool = False
    challenge_unlock: bool = False
    completion_goal: str = 'summit'
    challenges_required: int = 1
    challenge_goal_difficulty: int = 1
    summit_required_maps: int = 11
    summit_unlock_difficulty: int = 1
    summit_goal_difficulty: int = 2

    def __post_init__(self):
        if type(self.platinum_shop) is not bool:
            raise ValueError('platinum_shop must be true or false.')
        if self.completion_goal != 'crystalline_dimension' or not self.shopsanity:
            object.__setattr__(self, 'platinum_shop', False)
        if self.death_link_mode not in ('hero_death', 'crystal_destruction'):
            raise ValueError('death_link_mode must be hero_death or crystal_destruction.')
        # Only the selected goal's settings affect generation or client logic.
        ignored = ({'summit_required_maps': 11, 'summit_unlock_difficulty': 1,
                    'summit_goal_difficulty': 2} if self.completion_goal != 'summit'
                   else {'challenges_required': 1, 'challenge_goal_difficulty': 1})
        for field, value in ignored.items():
            object.__setattr__(self, field, value)
        if self.hero_skin_items and self.hero_skins_unlocked:
            raise ValueError('Choose hero_skin_items OR hero_skins_unlocked, not both.')
        if self.completion_goal != 'crystalline_dimension':
            object.__setattr__(self, 'extra_campaign_maps', False)
            object.__setattr__(self, 'crystalline_dimension_unlock', 'shard_maps')
        if self.crystalline_dimension_unlock not in ('shard_maps', 'eternia_shards'):
            raise ValueError('crystalline_dimension_unlock must be shard_maps or eternia_shards.')
        object.__setattr__(self, 'campaign_check_difficulties',
                           normalize_difficulties(self.campaign_check_difficulties))
        for field in ('goal_check_limits', 'death_link', 'hero_skin_items', 'hero_skins_unlocked', 'extra_campaign_maps', 'shopsanity', 'random_gear_pets', 'progressive_defense_units', 'survival_checks', 'challenge_checks', 'difficulty_unlocks',
                      'survival_unlock', 'challenge_unlock'):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f'{field} must be true or false.')
        # Disabled check categories must not add unrelated unlock rewards.
        # Survival remains available for farming, without AP area/start gates.
        if not self.survival_checks:
            object.__setattr__(self, 'survival_unlock', False)
        if not self.challenge_checks:
            object.__setattr__(self, 'challenge_unlock', False)
        if self.check_density not in ('every_wave', 'milestones', 'victories_only'):
            raise ValueError('check_density must be every_wave, milestones, or victories_only.')
        for field in ('survival_check_difficulty', 'challenge_check_difficulty',
                      'challenge_goal_difficulty', 'summit_unlock_difficulty', 'summit_goal_difficulty', 'starting_difficulty', 'crystalline_dimension_difficulty'):
            v = getattr(self, field)
            if type(v) is not int or not 0 <= v <= 5:
                raise ValueError(f'{field} must be easy, medium, hard, insane, nightmare, or ruthless.')
        if type(self.survival_max_wave) is not int or self.survival_max_wave not in (5, 10, 15, 20, 25):
            raise ValueError('survival_max_wave must be 5, 10, 15, 20, or 25.')
        for field, maximum in (('challenges_required', 12), ('summit_required_maps', 11)):
            v = getattr(self, field)
            if type(v) is not int or not 1 <= v <= maximum:
                raise ValueError(f'{field} must be between 1 and {maximum}.')
        if self.completion_goal not in ('summit', 'challenges', 'crystalline_dimension'):
            raise ValueError('Unknown completion_goal.')
        if self.difficulty_unlocks and not any(DIFFICULTIES.index(d) <= self.starting_difficulty for d in self.campaign_check_difficulties):
            raise ValueError('Enable campaign checks at or below starting_difficulty when difficulty_unlocks is true; '
                             'otherwise the seed starts without a reachable difficulty unlock.')
        if self.completion_goal == 'challenges' and not self.challenge_checks:
            raise ValueError('Enable challenge_checks to use the challenges completion goal.')

    @classmethod
    def from_slot_data(cls, data):
        if not isinstance(data, Mapping):
            raise ValueError('DD1 slot settings must be an object.')
        if (type(data.get('dd1_slot_data_version')) is not int or
                data['dd1_slot_data_version'] not in SUPPORTED_SLOT_DATA_VERSIONS):
            raise ValueError('Use the matching DD1 APWorld/client; this client supports seeds through 0.8.0.')
        data = dict(data)
        data.setdefault('platinum_shop', False)
        if data['dd1_slot_data_version'] < 14:
            data.setdefault('death_link_mode', 'hero_death')
        data.setdefault('random_gear_pets', False)
        if data['dd1_slot_data_version'] < 13:
            data.setdefault('death_link', False)
            data.setdefault('goal_check_limits', False)
        if (data['dd1_slot_data_version'] == 11 and data.get('completion_goal') == 'crystalline_dimension'
                and data.get('extra_campaign_maps')):
            raise ValueError('This earlier 0.7.0 test seed includes a removed map. Generate a new seed with the updated APWorld.')
        if data['dd1_slot_data_version'] < 12:
            data.setdefault('crystalline_dimension_unlock', 'shard_maps')
        if data['dd1_slot_data_version'] < 11:
            for key in ('hero_skin_items', 'hero_skins_unlocked', 'extra_campaign_maps'):
                data.setdefault(key, False)
            data.setdefault('crystalline_dimension_difficulty', 1)
        # Earlier 0.6.4 seeds always included DU items; pre-0.6.4 seeds did not.
        data.setdefault('progressive_defense_units', data['dd1_slot_data_version'] >= 10)
        if data['dd1_slot_data_version'] < 10:
            data.setdefault('starting_difficulty', 0)
        missing = set(cls.__dataclass_fields__) - data.keys()
        if missing:
            raise ValueError('DD1 slot data is missing: ' + ', '.join(sorted(missing)))
        return cls(**{k: data[k] for k in cls.__dataclass_fields__})

    def slot_data(self):
        return {'dd1_slot_data_version': SLOT_DATA_VERSION, **asdict(self)}

    def unlock_items(self):
        # Farming without Survival checks does not require AP Survival rewards.
        return ((DEFENSE_UNITS_ITEM,) * 6 if self.progressive_defense_units else ()) + ((SURVIVAL_START_ITEM,) * 5 if self.survival_checks else ()) + ((PROGRESSIVE_DIFFICULTY,) * (5 - self.starting_difficulty) if self.difficulty_unlocks else ()) + (
            AREA_ITEMS['survival'] if self.survival_unlock else ()) + (
            AREA_ITEMS['challenge'] if self.challenge_unlock else ())

    def build_time_items(self, checks):
        late_goal = (self.completion_goal == 'summit' and self.summit_goal_difficulty >= 4
                     or self.completion_goal == 'challenges' and self.challenge_goal_difficulty >= 4)
        if self.completion_goal != 'crystalline_dimension' and not late_goal and not any(c.difficulty >= 4 for c in checks):
            return 0
        return max(5, min(20, len(checks) // 30))

    def summit_unlocked(self, received_maps, victories):
        if self.completion_goal != 'summit':
            return 'CAMPTS' in received_maps
        return summit_is_unlocked(victories, self.summit_required_maps, self.summit_unlock_difficulty)


@dataclass(frozen=True)
class Check:
    name: str
    address: int
    map_tag: str
    mode: str
    difficulty: int
    wave: int
    victory: bool = False
    challenge_tag: str = ''

    @property
    def campaign_core(self):
        return self.mode == 'campaign' and self.map_tag != 'CAMPTS'


def check_catalog():
    rows = []
    # New disjoint IDs: never reinterpret a published difficulty-independent ID.
    for i, m in enumerate(MAPS):
        # Keep the retired development map's address range unused.
        if m.tag == 'CAMPMB':
            i += 1
        for d, difficulty in enumerate(DIFFICULTIES):
            for wave in range(START_WAVES[m.tag], FINAL_WAVES[m.tag] + 1):
                victory = wave == FINAL_WAVES[m.tag]
                label = 'Victory' if victory else f'Wave {wave}'
                rows.append(Check(f'{m.name} - {difficulty.title()} {label}',
                    9_110_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'campaign', d, wave, victory))
            for wave in (() if m.tag == 'CAMPCL' else range(1, 26)):
                rows.append(Check(f'{m.name} - Survival {difficulty.title()} Wave {wave}',
                    9_120_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'survival', d, wave))
            if i >= len(CHALLENGES):
                continue
            c = CHALLENGES[i]
            for wave in range(c.start, c.final + 1):
                victory = wave == c.final
                label = 'Victory' if victory else f'Wave {wave}'
                rows.append(Check(f'{c.name} - {difficulty.title()} {label}',
                    9_130_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'challenge', d, wave, victory, c.tag))
    for category, label in enumerate(('Bronze', 'Silver', 'Gold', 'Platinum')):
        for slot in range(3):
            for stage in range(3):
                index = category * 9 + slot * 3 + stage
                rows.append(Check(f'Tavern Shop - {label} Slot {slot + 1} Purchase {stage + 1}',
                    9_140_000_000 + index, 'SHOP', 'shop', 0, index))
    return tuple(rows)


CATALOG = check_catalog()
CHECK_BY_ID = {c.address: c for c in CATALOG}


def selected_checks(settings):
    opening_difficulty = DIFFICULTIES.index(settings.campaign_check_difficulties[0])
    map_tags = {m.tag for m in enabled_maps(settings)}

    def density_enabled(c):
        if c.mode == 'shop' or settings.check_density == 'every_wave':
            return True
        # The five opening-map checks carry the starter's first defense,
        # second hero, and early defense package. Keep them on only the lowest
        # selected difficulty so reduced-density seeds remain playable.
        if (c.mode == 'campaign' and c.map_tag == 'CAMPDW'
                and c.difficulty == opening_difficulty):
            return True
        if c.mode == 'survival':
            return (c.wave % 5 == 0 if settings.check_density == 'milestones'
                    else c.wave == settings.survival_max_wave)
        if settings.check_density == 'victories_only':
            return c.victory
        # Campaign and challenge milestones use one middle check plus victory.
        start = START_WAVES[c.map_tag] if c.mode == 'campaign' else CHALLENGE_BY_TAG[c.challenge_tag].start
        final = FINAL_WAVES[c.map_tag] if c.mode == 'campaign' else CHALLENGE_BY_TAG[c.challenge_tag].final
        midpoint = start + (final - start) // 2
        return c.victory or (midpoint < final and c.wave == midpoint)

    def enabled(c):
        if not density_enabled(c):
            return False
        if c.mode == 'shop':
            return settings.shopsanity and (c.wave < 27 or settings.platinum_shop)
        if c.map_tag not in map_tags:
            return False
        if c.mode == 'campaign':
            if settings.goal_check_limits and settings.completion_goal == 'crystalline_dimension' and c.map_tag == 'CAMPCL':
                if c.difficulty > settings.crystalline_dimension_difficulty:
                    return False
            if settings.goal_check_limits and settings.completion_goal == 'summit' and c.map_tag == 'CAMPTS':
                if c.difficulty > settings.summit_goal_difficulty:
                    return False
            return (DIFFICULTIES[c.difficulty] in settings.campaign_check_difficulties
                and not (settings.completion_goal != 'crystalline_dimension' and c.map_tag == 'CAMPTS' and c.victory
                    and c.difficulty >= 2))
        if c.mode == 'survival':
            if settings.goal_check_limits and settings.completion_goal == 'summit' and c.map_tag == 'CAMPTS':
                return False
            return settings.survival_checks and c.difficulty == settings.survival_check_difficulty and c.wave <= settings.survival_max_wave
        challenge_difficulty = settings.challenge_check_difficulty
        if settings.goal_check_limits and settings.completion_goal == 'challenges':
            challenge_difficulty = min(challenge_difficulty, settings.challenge_goal_difficulty)
        return settings.challenge_checks and c.difficulty == challenge_difficulty
    return tuple(c for c in CATALOG if enabled(c))


def validate_budget(checks, required_items, *, reserved_filler=0):
    available = len(checks) - reserved_filler
    if required_items > available:
        raise ValueError(f'These settings need {required_items} unlock items, but only '
            f'{available} eligible checks are available ({len(checks)} total; '
            f'{reserved_filler} reserved for filler). Enable more campaign difficulties, '
            'survival/challenge checks, or choose fewer heroes/unlock items.')
    return len(checks) - required_items


def matching_checks(settings, *, mode, map_tag, difficulty, wave, victory, challenge_tag=''):
    """Survival backfills lower checks only after a later wave is completed."""
    if mode not in ('campaign', 'survival', 'challenge'):
        raise ValueError('Unsupported DD1 mode; Pure Strategy and mixed modes have no checks.')
    if type(difficulty) is not int or not 0 <= difficulty <= 5:
        raise ValueError('Unsupported observed difficulty; only Easy through Ruthless are allowed.')
    if type(wave) is not int or not 0 <= wave <= 99 or type(victory) is not bool:
        raise ValueError('Invalid observed wave or victory.')
    if map_tag not in {m.tag for m in enabled_maps(settings)}:
        raise ValueError('Map is outside this seed campaign.')
    if mode == 'challenge':
        c = CHALLENGE_BY_TAG.get(challenge_tag)
        if c is None or c.parent != map_tag:
            raise ValueError('Challenge does not match its parent map.')
        if not c.victory_only and not c.start <= wave <= c.final:
            raise ValueError('Challenge wave is outside the verified range.')
        if c.victory_only:
            wave = 0
    if mode == 'survival' and wave < 1:
        raise ValueError('Survival checks require a completed wave, not a starting-wave selection.')
    return tuple(c for c in selected_checks(settings)
        if c.mode == mode and c.map_tag == map_tag and c.difficulty <= difficulty
        and (c.wave <= wave if mode == 'survival' else c.wave == wave)
        and (c.mode == 'survival' or c.victory == victory)
        and (c.mode != 'challenge' or c.challenge_tag == challenge_tag))


