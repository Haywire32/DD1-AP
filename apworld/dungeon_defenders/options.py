"""Option definitions. Public explanation text remains author-editable."""
from dataclasses import dataclass
from Options import PerGameCommonOptions, Range, Choice, OptionSet, Toggle, DeathLink
from .heroes import DEFAULT_HERO_KEYS, HERO_BY_KEY, normalize_hero_keys
from .dd1_content import DIFFICULTIES, normalize_difficulties
from .dd1_traps import TRAP_KEYS


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
    """Choose any combination of easy, medium, hard, insane, nightmare, ruthless. Higher clears count for selected lower difficulties."""
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
    """Choose easy, medium, hard, insane, nightmare, or ruthless. Higher difficulties also count."""
    display_name = 'Difficulty'
    option_easy = 0
    option_medium = 1
    option_hard = 2
    option_insane = 3
    option_nightmare = 4
    option_ruthless = 5
    default = 1


class SurvivalCheckDifficulty(Difficulty):
    display_name = 'Survival Check Difficulty'


class StartingDifficulty(Difficulty):
    """Starting difficulty with progressive difficulty enabled. Lower difficulties are also unlocked."""
    display_name = 'Starting Difficulty'


class ChallengeCheckDifficulty(Difficulty):
    display_name = 'Challenge Check Difficulty'


class ChallengeGoalDifficulty(Difficulty):
    display_name = 'Challenge Goal Difficulty'


class SummitUnlockDifficulty(Difficulty):
    display_name = 'Summit Unlock Difficulty'


class SummitGoalDifficulty(Difficulty):
    display_name = 'Summit Goal Difficulty'
    default = 2


class CrystallineDimensionDifficulty(Difficulty):
    """Required difficulty for the four Shards maps and Crystalline Dimension."""
    display_name = 'Crystalline Dimension Difficulty'


class ExtraCampaignMaps(Toggle):
    """Extra free campaign maps for the Crystalline Dimension goal."""
    display_name = 'Extra Campaign Maps'


class HeroSkinItems(Toggle):
    """Hero skins as items. Selected heroes only; DLC ownership required."""
    display_name = 'Hero Skin Items'


class TavernThemes(Toggle):
    """Open the upstairs tavern theme selector and shuffle 9 cosmetic theme unlocks into filler. Jester and Halloween are excluded. Requires all four Lost Eternia Shards DLC parts to play this seed. The original tavern remains available."""
    display_name = 'Tavern Themes'
    default = 0


class HeroSkinsUnlocked(Toggle):
    """Hero skins available from the start. Selected heroes only; DLC ownership required."""
    display_name = 'Hero Skins Unlocked'


class MapUnlockPlacement(Choice):
    """Local keeps map items in your DD1 campaign. Global allows them in other players' worlds too."""
    display_name = 'Map Unlock Placement'
    option_local = 0
    option_global = 1
    default = 1


class Shopsanity(Toggle):
    """Add 27 purchases alongside the normal tavern shop. Categories open after completing 3, 5, and 7 different campaign maps on any difficulty. A Crystalline Dimension goal adds 9 Platinum purchases after 12 different campaign maps, costing 5/10/20 million mana per column."""
    display_name = 'Shopsanity'
    default = 1


class RandomGearPets(Toggle):
    """Allow random gear rewards to include pets, using tavern-shop scaling."""
    display_name = 'Random Gear Pets'
    default = 0


class ProgressiveDefenseUnits(Toggle):
    """Add six items that each grant 5 extra defense units, up to 30. No Towers Allowed always stays at 0 defense units."""
    display_name = 'Progressive Defense Units'
    default = 0


class CheckDensity(Choice):
    """Choose every wave, milestone waves and victories, or victories only."""
    display_name = 'Check Density'
    option_every_wave = 0
    option_milestones = 1
    option_victories_only = 2
    default = 0


class SurvivalChecks(Toggle):
    """Add survival checks on enabled campaign maps except Crystalline Dimension."""
    display_name = 'Survival Checks'


class ChallengeChecks(Toggle):
    """Add checks for the 12 campaign-map challenges. This is required for the Challenges goal."""
    display_name = 'Challenge Checks'


class DifficultyUnlocks(Toggle):
    """Unlock difficulties progressively above starting_difficulty. Include campaign checks at or below your starting difficulty."""
    display_name = 'Progressive Difficulty'


class SurvivalUnlock(Toggle):
    """With survival_checks enabled, add three Survival area items, four maps each. Ignored when survival_checks is false. The campaign map must also be unlocked."""
    display_name = 'Survival Unlock'
    default = 1


class ChallengeUnlock(Toggle):
    """Challenges have three area items, four maps each, independent of campaign map unlocks."""
    display_name = 'Challenge Unlock'
    default = 0


class SurvivalMaxWave(Choice):
    """Give one check per survival wave from 1 through this wave."""
    display_name = 'Last Survival Check Wave'
    option_five = 5
    option_ten = 10
    option_fifteen = 15
    option_twenty = 20
    option_twenty_five = 25
    default = 15


class CompletionGoal(Choice):
    """Choose the completion goal."""
    display_name = 'Completion Goal'
    option_summit = 0
    option_challenges = 1
    option_crystalline_dimension = 2
    default = 0


class CrystallineDimensionUnlock(Choice):
    """Choose how Crystalline Dimension is unlocked."""
    display_name = 'Crystalline Dimension Unlock'
    option_shard_maps = 0
    option_eternia_shards = 1
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


class LevelCatchUpMultiplier(Choice):
    """Heroes below your highest unlocked hero gain experience faster until they catch up. Choose off, 2, 4, 6, 8, or 10."""
    display_name = 'Level Catch-Up Multiplier'
    option_off = 1
    option_double = 2
    option_quadruple = 4
    option_sextuple = 6
    option_octuple = 8
    option_decuple = 10
    default = 1


class DeathLinkMode(Choice):
    """Choose hero death or crystal destruction when DeathLink is enabled."""
    display_name = 'DeathLink Mode'
    option_hero_death = 0
    option_crystal_destruction = 1
    default = 0


class SkillShuffle(Toggle):
    """Skill shuffle randomizes the ability and defense pool of all enabled heroes. For example a squire can end up with an apprentice tower."""
    display_name = 'Skill Shuffle'
    default = 0


class SkillShuffleMode(Choice):
    """Separate: hero abilities and defenses are shuffled separately from each other. Mixed: any ability/defense can be put in either ability/defense slot"""
    display_name = 'Skill Shuffle Mode'
    option_mixed = 0
    option_separate = 1
    default = 0


class TrapPercentage(Range):
    """Percentage of ordinary filler rewards replaced by traps. Zero disables traps."""
    display_name = 'Trap Percentage'
    range_start = 0
    range_end = 100
    default = 0


class EnabledTraps(OptionSet):
    """Choose traps that replace filler. Ready or Not skips a build phase after a completed wave; other traps wait for combat."""
    display_name = 'Enabled Traps'
    valid_keys = frozenset(TRAP_KEYS)
    default = frozenset(TRAP_KEYS)


@dataclass
class DungeonDefendersOptions(PerGameCommonOptions):
    tavern_themes: TavernThemes
    trap_percentage: TrapPercentage
    enabled_traps: EnabledTraps
    death_link: DeathLink
    death_link_mode: DeathLinkMode
    hero_skin_items: HeroSkinItems
    hero_skins_unlocked: HeroSkinsUnlocked
    extra_campaign_maps: ExtraCampaignMaps
    crystalline_dimension_difficulty: CrystallineDimensionDifficulty
    crystalline_dimension_unlock: CrystallineDimensionUnlock
    shopsanity: Shopsanity
    random_gear_pets: RandomGearPets
    progressive_defense_units: ProgressiveDefenseUnits
    check_density: CheckDensity
    active_heroes: ActiveHeroes
    skill_shuffle: SkillShuffle
    skill_shuffle_mode: SkillShuffleMode
    map_unlock_placement: MapUnlockPlacement
    campaign_check_difficulties: CampaignCheckDifficulties
    survival_checks: SurvivalChecks
    survival_check_difficulty: SurvivalCheckDifficulty
    survival_max_wave: SurvivalMaxWave
    challenge_checks: ChallengeChecks
    challenge_check_difficulty: ChallengeCheckDifficulty
    difficulty_unlocks: DifficultyUnlocks
    starting_difficulty: StartingDifficulty
    survival_unlock: SurvivalUnlock
    challenge_unlock: ChallengeUnlock
    completion_goal: CompletionGoal
    challenges_required: ChallengesRequired
    challenge_goal_difficulty: ChallengeGoalDifficulty
    summit_required_maps: SummitRequiredMaps
    summit_unlock_difficulty: SummitUnlockDifficulty
    summit_goal_difficulty: SummitGoalDifficulty
    experience_multiplier: ExperienceMultiplier
    level_catch_up_multiplier: LevelCatchUpMultiplier
