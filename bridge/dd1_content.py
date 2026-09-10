"""0.5.0 settings and check catalog, shared by generation and the client."""
from dataclasses import dataclass, asdict
from collections.abc import Mapping

try:
    from .dd1_protocol import CAMPAIGN_MAPS, START_WAVES, FINAL_WAVES, summit_is_unlocked
except ImportError:
    from dd1_protocol import CAMPAIGN_MAPS, START_WAVES, FINAL_WAVES, summit_is_unlocked

DIFFICULTIES = ('easy', 'medium', 'hard', 'insane')
SUMMIT_MAP_ITEM = 'The Summit Map'
MAPS = CAMPAIGN_MAPS[:12]
MODE_ITEMS = {'survival': 'Survival Mode', 'challenge': 'Challenge Mode'}
DIFFICULTY_ITEMS = {d: d.title() + ' Difficulty' for d in DIFFICULTIES[1:]}
# Retain the former individual names only to preserve their network IDs.
PROGRESSIVE_DIFFICULTY = 'Progressive Difficulty'
XP_REWARDS = {'One Hero Level': 1, 'Two Hero Levels': 2,
              'Three Hero Levels': 3, 'Four Hero Levels': 4}
MANA_REWARDS = {f'{n:,} Bank Mana': n for n in (25000, 100000, 500000, 1000000, 2000000)}


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
    for m, (name, start, final, single) in zip(MAPS, (
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
        raise ValueError('Use difficulty names: easy, medium, hard, insane.')
    selected = {d.strip().lower() for d in value}
    unknown = selected - set(DIFFICULTIES)
    if unknown:
        raise ValueError('Unknown campaign difficulty: ' + ', '.join(sorted(unknown)))
    if not selected:
        raise ValueError('Select at least one campaign check difficulty for the map-unlock route.')
    return tuple(d for d in DIFFICULTIES if d in selected)


@dataclass(frozen=True)
class ContentSettings:
    campaign_check_difficulties: tuple[str, ...] = ('easy', 'medium', 'hard')
    survival_checks: bool = False
    survival_check_difficulty: int = 1
    survival_max_wave: int = 10
    challenge_checks: bool = False
    challenge_check_difficulty: int = 1
    difficulty_unlocks: bool = False
    survival_unlock: bool = False
    challenge_unlock: bool = False
    completion_goal: str = 'summit'
    challenges_required: int = 1
    challenge_goal_difficulty: int = 1
    summit_required_maps: int = 11
    summit_unlock_difficulty: int = 1
    summit_goal_difficulty: int = 2

    def __post_init__(self):
        # Only the selected goal's settings affect generation or client logic.
        ignored = ({'summit_required_maps': 11, 'summit_unlock_difficulty': 1,
                    'summit_goal_difficulty': 2} if self.completion_goal == 'challenges'
                   else {'challenges_required': 1, 'challenge_goal_difficulty': 1})
        for field, value in ignored.items():
            object.__setattr__(self, field, value)
        object.__setattr__(self, 'campaign_check_difficulties',
                           normalize_difficulties(self.campaign_check_difficulties))
        for field in ('survival_checks', 'challenge_checks', 'difficulty_unlocks',
                      'survival_unlock', 'challenge_unlock'):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f'{field} must be true or false.')
        for field in ('survival_check_difficulty', 'challenge_check_difficulty',
                      'challenge_goal_difficulty', 'summit_unlock_difficulty', 'summit_goal_difficulty'):
            v = getattr(self, field)
            if type(v) is not int or not 0 <= v <= 3:
                raise ValueError(f'{field} must be easy, medium, hard, or insane.')
        if type(self.survival_max_wave) is not int or self.survival_max_wave not in (5, 10, 15, 20, 25):
            raise ValueError('survival_max_wave must be 5, 10, 15, 20, or 25.')
        for field, maximum in (('challenges_required', 12), ('summit_required_maps', 11)):
            v = getattr(self, field)
            if type(v) is not int or not 1 <= v <= maximum:
                raise ValueError(f'{field} must be between 1 and {maximum}.')
        if self.completion_goal not in ('summit', 'challenges'):
            raise ValueError('completion_goal must be summit or challenges.')
        if self.difficulty_unlocks and 'easy' not in self.campaign_check_difficulties:
            raise ValueError('Enable Easy campaign checks when difficulty_unlocks is true; '
                             'otherwise the seed starts without a reachable difficulty unlock.')
        if self.completion_goal == 'challenges' and not self.challenge_checks:
            raise ValueError('Enable challenge_checks to use the challenges completion goal.')

    @classmethod
    def from_slot_data(cls, data):
        if not isinstance(data, Mapping):
            raise ValueError('DD1 slot settings must be an object.')
        if data.get('dd1_slot_data_version') != 5:
            raise ValueError('Generate a new seed after installing the matching APWorld (slot data version 5).')
        missing = set(cls.__dataclass_fields__) - data.keys()
        if missing:
            raise ValueError('DD1 slot data is missing: ' + ', '.join(sorted(missing)))
        return cls(**{k: data[k] for k in cls.__dataclass_fields__})

    def slot_data(self):
        return {'dd1_slot_data_version': 5, **asdict(self)}

    def unlock_items(self):
        # Mode-unlock switches are independent of whether that mode has checks.
        return ((PROGRESSIVE_DIFFICULTY,) * 3 if self.difficulty_unlocks else ()) + (
            (MODE_ITEMS['survival'],) if self.survival_unlock else ()) + (
            (MODE_ITEMS['challenge'],) if self.challenge_unlock else ())

    def summit_unlocked(self, received_maps, victories):
        if self.completion_goal == 'challenges':
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
        for d, difficulty in enumerate(DIFFICULTIES):
            for wave in range(START_WAVES[m.tag], FINAL_WAVES[m.tag] + 1):
                victory = wave == FINAL_WAVES[m.tag]
                label = 'Victory' if victory else f'Wave {wave}'
                rows.append(Check(f'{m.name} - {difficulty.title()} {label}',
                    9_110_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'campaign', d, wave, victory))
            for wave in range(1, 26):
                rows.append(Check(f'{m.name} - Survival {difficulty.title()} Wave {wave}',
                    9_120_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'survival', d, wave))
            c = CHALLENGES[i]
            for wave in range(c.start, c.final + 1):
                victory = wave == c.final
                label = 'Victory' if victory else f'Wave {wave}'
                rows.append(Check(f'{c.name} - {difficulty.title()} {label}',
                    9_130_000_000 + i * 10000 + d * 1000 + wave,
                    m.tag, 'challenge', d, wave, victory, c.tag))
    return tuple(rows)


CATALOG = check_catalog()
CHECK_BY_ID = {c.address: c for c in CATALOG}


def selected_checks(settings):
    def enabled(c):
        if c.mode == 'campaign':
            return (DIFFICULTIES[c.difficulty] in settings.campaign_check_difficulties
                and not (c.map_tag == 'CAMPTS' and c.victory
                    and c.difficulty >= 2))
        if c.mode == 'survival':
            return settings.survival_checks and c.difficulty == settings.survival_check_difficulty and c.wave <= settings.survival_max_wave
        return settings.challenge_checks and c.difficulty == settings.challenge_check_difficulty
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
    """One completed wave only; no credit for earlier waves skipped on entry."""
    if mode not in ('campaign', 'survival', 'challenge'):
        raise ValueError('Unsupported DD1 mode; Pure Strategy and mixed modes have no checks.')
    if type(difficulty) is not int or not 0 <= difficulty <= 3:
        raise ValueError('Unsupported observed difficulty; only Easy through Insane are allowed.')
    if type(wave) is not int or not 0 <= wave <= 99 or type(victory) is not bool:
        raise ValueError('Invalid observed wave or victory.')
    if map_tag not in {m.tag for m in MAPS}:
        raise ValueError('Map is outside the 12-map campaign.')
    if mode == 'challenge':
        c = CHALLENGE_BY_TAG.get(challenge_tag)
        if c is None or c.parent != map_tag:
            raise ValueError('Challenge does not match its parent map.')
        if not c.victory_only and not c.start <= wave <= c.final:
            raise ValueError('Challenge wave is outside the verified range.')
        if c.victory_only:
            wave = 0
    return tuple(c for c in selected_checks(settings)
        if c.mode == mode and c.map_tag == map_tag and c.difficulty <= difficulty
        and c.wave == wave and (c.mode == 'survival' or c.victory == victory)
        and (c.mode != 'challenge' or c.challenge_tag == challenge_tag))


def mana_for_check(check):
    """Placement amounts for DD1 only. Other worlds retain their drawn amount."""
    index = next(i for i, m in enumerate(MAPS) if m.tag == check.map_tag)
    tier = 0 if index < 4 else 1 if index < 7 else 2
    score = tier + check.difficulty
    if check.mode == 'survival':
        score += (check.wave - 1) // 5
    elif check.mode == 'challenge':
        score += 1
    return tuple(MANA_REWARDS)[min(score, 4)]
