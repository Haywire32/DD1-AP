"""Option definitions. Public explanation text remains author-editable."""
from dataclasses import dataclass
from Options import PerGameCommonOptions, Range, Choice, OptionSet, Toggle
from .heroes import DEFAULT_HERO_KEYS, HERO_BY_KEY, normalize_hero_keys
from .dd1_content import DIFFICULTIES, normalize_difficulties


class ActiveHeroes(OptionSet):
    """Choose 2-16 heroes. DLC ownership is still required.
    apprentice, squire, huntress, monk, adept, countess, ranger, initiate,
    barbarian, series_ev, summoner, jester, hermit, gunwitch, warden, guardian.
    Include at least one builder. Counterparts may be selected together.
    """
    display_name = 'Active Heroes'
    default = frozenset(DEFAULT_HERO_KEYS)
    valid_keys = frozenset(HERO_BY_KEY)

    @classmethod
    def from_any(cls, data):
        return cls(set(normalize_hero_keys(data)))

    @classmethod
    def from_text(cls, data):
        return cls.from_any(data)


class CampaignCheckDifficulties(OptionSet):
    """Choose any combination of easy, medium, hard, insane. Higher clears count for selected lower difficulties."""
    display_name = 'Campaign Check Difficulties'
    default = frozenset(('easy', 'medium', 'hard'))
    valid_keys = frozenset(DIFFICULTIES)

    @classmethod
    def from_any(cls, data):
        return cls(set(normalize_difficulties(data)))

    @classmethod
    def from_text(cls, data):
        return cls.from_any(data)


class Difficulty(Choice):
    """Choose easy, medium, hard, or insane. Higher difficulties also count."""
    display_name = 'Difficulty'
    option_easy = 0
    option_medium = 1
    option_hard = 2
    option_insane = 3
    default = 1


class SurvivalCheckDifficulty(Difficulty):
    display_name = 'Survival Check Difficulty'


class ChallengeCheckDifficulty(Difficulty):
    display_name = 'Challenge Check Difficulty'


class ChallengeGoalDifficulty(Difficulty):
    display_name = 'Challenge Goal Difficulty'


class SummitUnlockDifficulty(Difficulty):
    display_name = 'Summit Unlock Difficulty'


class SummitGoalDifficulty(Difficulty):
    display_name = 'Summit Goal Difficulty'
    default = 2


class MapUnlockPlacement(Choice):
    """Local keeps map items in your DD1 campaign. Global allows them in other players' worlds too."""
    display_name = 'Map Unlock Placement'
    option_local = 0
    option_global = 1
    default = 0


class SurvivalChecks(Toggle):
    """Add survival wave checks on the 12 campaign maps."""
    display_name = 'Survival Checks'


class ChallengeChecks(Toggle):
    """Add checks for the 12 campaign-map challenges."""
    display_name = 'Challenge Checks'


class DifficultyUnlocks(Toggle):
    """Start on Easy. Three Progressive Difficulty items unlock Medium, then Hard, then Insane. Requires Easy campaign checks."""
    display_name = 'Difficulty Unlocks'


class SurvivalUnlock(Toggle):
    """Survival mode requires its item unlock, as well as the map."""
    display_name = 'Survival Unlock'


class ChallengeUnlock(Toggle):
    """Challenges require their mode item, as well as each parent map."""
    display_name = 'Challenge Unlock'


class SurvivalMaxWave(Choice):
    """Give one check per survival wave from 1 through this wave."""
    display_name = 'Last Survival Check Wave'
    option_five = 5
    option_ten = 10
    option_fifteen = 15
    option_twenty = 20
    option_twenty_five = 25
    default = 10


class CompletionGoal(Choice):
    """Beat The Summit, or complete the chosen number of different challenges."""
    display_name = 'Completion Goal'
    option_summit = 0
    option_challenges = 1
    default = 0


class ChallengesRequired(Range):
    """Number of different challenge victories required for the challenges goal."""
    display_name = 'Challenges Required'
    range_start = 1
    range_end = 12
    default = 1


class SummitRequiredMaps(Range):
    """Campaign victories required to unlock The Summit."""
    display_name = 'Maps Required for The Summit'
    range_start = 1
    range_end = 11
    default = 11


class ExperienceMultiplier(Choice):
    """Multiply normal experience after the game's bonuses: 1, 2, 4, 6, 8, or 10."""
    display_name = 'Experience Multiplier'
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
    map_unlock_placement: MapUnlockPlacement
    campaign_check_difficulties: CampaignCheckDifficulties
    survival_checks: SurvivalChecks
    survival_check_difficulty: SurvivalCheckDifficulty
    survival_max_wave: SurvivalMaxWave
    challenge_checks: ChallengeChecks
    challenge_check_difficulty: ChallengeCheckDifficulty
    difficulty_unlocks: DifficultyUnlocks
    survival_unlock: SurvivalUnlock
    challenge_unlock: ChallengeUnlock
    completion_goal: CompletionGoal
    challenges_required: ChallengesRequired
    challenge_goal_difficulty: ChallengeGoalDifficulty
    summit_required_maps: SummitRequiredMaps
    summit_unlock_difficulty: SummitUnlockDifficulty
    summit_goal_difficulty: SummitGoalDifficulty
    experience_multiplier: ExperienceMultiplier
