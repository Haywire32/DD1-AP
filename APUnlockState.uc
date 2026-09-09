class APUnlockState extends Object
    config(DD1ArchipelagoUnlocks);

var config int Revision;
var config string Slot;
var config string SeedIdentity;
var config array<string> UnlockedHeroes;
var config array<string> ActiveHeroes;
var config array<string> LevelSixHeroes;
var config array<string> UnlockedDefenses;
var config array<string> UnlockedAbilities;
var config array<string> UnlockedMaps;
var config int MaxEquipmentQuality;
var config int ExperienceMultiplier;
var config int DifficultyMask;
var config int ModeMask;

function bool ContainsValue(const out array<string> Values, string Wanted)
{
    local string Value;

    foreach Values(Value)
    {
        if(Value ~= Wanted)
        {
            return true;
        }
    }
    return false;
}

function bool IsHeroUnlocked(string HeroKey)
{
    return ContainsValue(UnlockedHeroes, HeroKey);
}

function string GetHeroKey(DunDefHero Hero)
{
    if(Hero == none || Hero.GetCurrentHeroTemplate() == none)
    {
        return "";
    }

    switch(Hero.GetCurrentHeroTemplate().MyHeroClass)
    {
        case EHC_APPRENTICE: return "apprentice";
        case EHC_SQUIRE: return "squire";
        case EHC_HUNTRESS: return "huntress";
        case EHC_MONK: return "monk";
        case EHC_ADEPT: return "adept";
        case EHC_COUNTESS: return "countess";
        case EHC_RANGER: return "ranger";
        case EHC_INITIATE: return "initiate";
        case EHC_BARBARIAN: return "barbarian";
        case EHC_EV: return "series_ev";
        case EHC_SUMMONER: return "summoner";
        case EHC_JESTER: return "jester";
        case EHC_HERMIT: return "hermit";
        case EHC_GUNWITCH: return "gunwitch";
        case EHC_WARDEN: return "warden";
        case EHC_GUARDIAN: return "guardian";
    }
    return "";
}

function string GetHeroDisplayName(string HeroKey)
{
    if(HeroKey ~= "apprentice") return "Apprentice";
    if(HeroKey ~= "squire") return "Squire";
    if(HeroKey ~= "huntress") return "Huntress";
    if(HeroKey ~= "monk") return "Monk";
    if(HeroKey ~= "adept") return "Adept";
    if(HeroKey ~= "countess") return "Countess";
    if(HeroKey ~= "ranger") return "Ranger";
    if(HeroKey ~= "initiate") return "Initiate";
    if(HeroKey ~= "barbarian") return "Barbarian";
    if(HeroKey ~= "series_ev") return "Series EV";
    if(HeroKey ~= "summoner") return "Summoner";
    if(HeroKey ~= "jester") return "Jester";
    if(HeroKey ~= "hermit") return "Hermit";
    if(HeroKey ~= "gunwitch") return "Gunwitch";
    if(HeroKey ~= "warden") return "Warden";
    if(HeroKey ~= "guardian") return "Guardian";
    return "Unknown";
}

function bool IsDefenseUnlocked(string DefenseKey)
{
    return ContainsValue(UnlockedDefenses, DefenseKey);
}

function string GetDefenseKey(DunDefTower TowerArchetype, optional string HeroKey)
{
    if(TowerArchetype == none)
    {
        return "";
    }
    return GetDefenseKeyForPath(PathName(TowerArchetype), HeroKey);
}

function string GetDefenseKeyForPath(string ArchetypePath, optional string HeroKey)
{
    local string FamilyKey;

    // Full identities were checked against serialized build-ability references.
    // Counterparts share tower assets but use their own AP item namespace.
    // An omitted hero keeps legacy base-hero lookups compatible.
    if(HeroKey == "" || HeroKey ~= "squire" || HeroKey ~= "countess")
    {
        FamilyKey = HeroKey;
        if(FamilyKey == "") FamilyKey = "squire";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_SpikyBlockade_Arch")
            return FamilyKey $ ".spike_blockade";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_BouncyBlockade_Arch")
            return FamilyKey $ ".bouncer_blockade";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Harpoon_Arch")
            return FamilyKey $ ".harpoon_turret";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_BowlingBall_Arch")
            return FamilyKey $ ".bowling_ball_turret";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_SliceNDice_Arch")
            return FamilyKey $ ".slice_n_dice_blockade";
        if(ArchetypePath ~= "DunDef_CDT_ReduxTowers.MortarTower.DunDefTower_CannonBall")
            return FamilyKey $ ".mortar_turret";
    }

    if(HeroKey == "" || HeroKey ~= "apprentice" || HeroKey ~= "adept")
    {
        FamilyKey = HeroKey;
        if(FamilyKey == "") FamilyKey = "apprentice";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Blockade_Arch")
            return FamilyKey $ ".magic_blockade";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_MagicMissile_Arch")
            return FamilyKey $ ".magic_missile_tower";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Fireball_Arch")
            return FamilyKey $ ".fireball_tower";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_ChainLightning_Arch")
            return FamilyKey $ ".lightning_tower";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_DeadlyStriker_Arch")
            return FamilyKey $ ".deadly_striker_tower";
    }

    if(HeroKey == "" || HeroKey ~= "huntress" || HeroKey ~= "ranger")
    {
        FamilyKey = HeroKey;
        if(FamilyKey == "") FamilyKey = "huntress";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_ProxMine_Arch")
            return FamilyKey $ ".proximity_mine_trap";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_GasTrap_Arch")
            return FamilyKey $ ".gas_trap";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_InfernoTrap_Arch")
            return FamilyKey $ ".inferno_trap";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_DarknessTrap_Arch")
            return FamilyKey $ ".darkness_trap";
        if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_EtherealSpikeTrap_Arch")
            return FamilyKey $ ".ethereal_spike_trap";
        if(ArchetypePath ~= "DunDef_CDT_ReduxTowers.OilTrap.DunDefTower_OilTrap_Arch")
            return FamilyKey $ ".oil_trap";
    }

    if(HeroKey == "" || HeroKey ~= "monk" || HeroKey ~= "initiate")
    {
        FamilyKey = HeroKey;
        if(FamilyKey == "") FamilyKey = "monk";
        if(ArchetypePath ~= "DunDefAuras.Aura_StickyGloop")
            return FamilyKey $ ".ensnare_aura";
        if(ArchetypePath ~= "DunDefAuras.Aura_DeathyHallows")
            return FamilyKey $ ".electric_aura";
        if(ArchetypePath ~= "DunDefAuras.Aura_Heal")
            return FamilyKey $ ".healing_aura";
        if(ArchetypePath ~= "DunDefAuras.Aura_StrengthDrain")
            return FamilyKey $ ".strength_drain_aura";
        if(ArchetypePath ~= "DunDefAuras.Aura_Enrage")
            return FamilyKey $ ".enrage_aura";
    }

    if(HeroKey == "" || HeroKey ~= "series_ev")
    {
        if(ArchetypePath ~= "RobotGirl.TowerArchetypes.ProtoBeam")
            return "series_ev.proton_beam";
        if(ArchetypePath ~= "RobotGirl.TowerArchetypes.PhysicalBeam_new")
            return "series_ev.physical_beam";
        if(ArchetypePath ~= "RobotGirl.TowerArchetypes.ProjectileReflect")
            return "series_ev.reflection_beam";
        if(ArchetypePath ~= "RobotGirl.TowerArchetypes.ShockBeam")
            return "series_ev.shock_beam";
        if(ArchetypePath ~= "RobotGirl.TowerArchetypes.TowerbuffBeam")
            return "series_ev.tower_buff_beam";
        if(ArchetypePath ~= "DunDef_CDT_ReduxTowers.SamTower.DunDefTower_SAM_Archetype")
            return "series_ev.sam_unit";
    }

    if(HeroKey == "" || HeroKey ~= "summoner")
    {
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonArcher")
            return "summoner.archer_minion";
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonSpider")
            return "summoner.spider_minion";
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonOrc")
            return "summoner.orc_minion";
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonMage")
            return "summoner.mage_minion";
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonWarrior")
            return "summoner.warrior_minion";
        if(ArchetypePath ~= "Summoner.Towers.Tower_SummonOgre")
            return "summoner.ogre_minion";
    }

    if(HeroKey == "" || HeroKey ~= "jester")
    {
        if(ArchetypePath ~= "Jester_NewDefenses.DunDefTower_BoxingGlove_Arch2")
            return "jester.jack_in_the_box";
        if(ArchetypePath ~= "Jester_NewDefenses.DunDefTower_PartyPopper_Arch")
            return "jester.party_popper";
        if(ArchetypePath ~= "Jester.Tower.Present_LowDUPresent")
            return "jester.small_present";
        if(ArchetypePath ~= "Jester.Tower.Present_MidDUPresent")
            return "jester.deluxe_present";
        if(ArchetypePath ~= "Jester.Tower.Present_HighDUPresent")
            return "jester.extravagant_present";
        if(ArchetypePath ~= "Jester.Tower.Present_HigherDUPresent")
            return "jester.extra_deluxe_present";
    }

    if(HeroKey == "" || HeroKey ~= "hermit")
    {
        if(ArchetypePath ~= "Hermit.Towers.SeedBomb.Archetypes.SeedBomb")
            return "hermit.seed_bomb_tower";
        if(ArchetypePath ~= "Hermit.Towers.WebWall.Archetypes.WebWall")
            return "hermit.web_wall";
        if(ArchetypePath ~= "Hermit.Towers.NaturePylon.Archetypes.NaturePylon")
            return "hermit.nature_pylon";
        if(ArchetypePath ~= "Hermit.Towers.MushroomSporeTower.Archetypes.MushroomSpore")
            return "hermit.mushroom_spore_tower";
        if(ArchetypePath ~= "Hermit.Towers.ForestGolem.Archetypes.ForestGolem")
            return "hermit.forest_golem";
    }

    if(HeroKey == "" || HeroKey ~= "warden")
    {
        if(ArchetypePath ~= "Warden.Towers.AngryBlossom.Archetypes.DunDefTower_AngryBlossom_Arch")
            return "warden.angry_blossom";
        if(ArchetypePath ~= "Warden.Towers.SludgeLauncher.Archetypes.DunDefTower_SludgeLauncher_Arch")
            return "warden.sludge_launcher";
        if(ArchetypePath ~= "Warden.Towers.cloud.Archetypes.DunDefTower_cloud_Arch")
            return "warden.cloud_tower";
        if(ArchetypePath ~= "Warden.Towers.WispDen.Archetypes.Tower_WispDen_Archetype")
            return "warden.wisp_den";
        if(ArchetypePath ~= "Warden.Towers.ShroomPit.Archetypes.Tower_ShroomPit_Archetype")
            return "warden.shroom_pit";
    }

    if(HeroKey == "" || HeroKey ~= "guardian")
    {
        if(ArchetypePath ~= "Guardian.Towers.HolyCannon.DunDefTower_HolyCannon_Arch")
            return "guardian.holy_cannon";
        if(ArchetypePath ~= "Guardian.Towers.Obelisk.DunDefTower_Obelisk_Arch")
            return "guardian.obelisk";
        if(ArchetypePath ~= "Guardian.Towers.OwlNest.DunDefTower_OwlNest_Arch")
            return "guardian.owl_nest";
        if(ArchetypePath ~= "Guardian.Towers.EmpoweringShrine.DunDefTower_EmpoweringShrine")
            return "guardian.empowering_shrine";
        if(ArchetypePath ~= "Guardian.Towers.HolyBulwark.DunDefTower_HolyBulwark_Arch")
            return "guardian.holy_bulwark";
    }

    return "";
}

function bool IsTowerUnlocked(DunDefTower TowerArchetype, optional string HeroKey)
{
    local string DefenseKey;

    DefenseKey = GetDefenseKey(TowerArchetype, HeroKey);
    return DefenseKey != "" && IsDefenseUnlocked(DefenseKey);
}

function bool IsAbilityUnlocked(string AbilityKey)
{
    return ContainsValue(UnlockedAbilities, AbilityKey);
}

function string GetAbilityKey(DunDefPlayerAbility Ability, optional string HeroKey)
{
    if(Ability == none || Ability.ObjectArchetype == none)
    {
        return "";
    }
    if(HeroKey == "" && Ability.GetPC() != none)
    {
        HeroKey = GetHeroKey(Ability.GetPC().GetHero());
    }
    return GetAbilityKeyForPath(PathName(Ability.ObjectArchetype), HeroKey);
}

function string GetAbilityKeyForPath(string ArchetypePath, optional string HeroKey)
{
    // Match archetypes, never classes: different stances and spells can share
    // a class. A newer unknown action is rejected by the GRI compatibility gate.
    if(HeroKey == "" || HeroKey ~= "apprentice")
    {
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Apprentice_Overcharge")
            return "apprentice.overcharge";
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Apprentice_ManaBomb")
            return "apprentice.mana_bomb";
    }

    if(HeroKey == "" || HeroKey ~= "squire")
    {
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Squire_BloodRage")
            return "squire.blood_rage";
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Squire_CircleSlice")
            return "squire.circular_slice";
    }

    if(HeroKey == "" || HeroKey ~= "huntress")
    {
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Initiate_Invisibility_Old")
            return "huntress.invisibility";
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Initiate_Invisibility")
            return "huntress.shadow_step";
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Huntress_PiercingShot")
            return "huntress.piercing_shot";
    }

    if(HeroKey == "" || HeroKey ~= "monk")
    {
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Recruit_TowerBoost")
            return "monk.tower_boost";
        if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Recruit_HeroBoost")
            return "monk.hero_boost";
    }

    if(HeroKey == "" || HeroKey ~= "adept")
    {
        if(ArchetypePath ~= "Sorceress_Skin.Abilities.Ability_InstantUpgrade")
            return "adept.upgrade_aura";
        if(ArchetypePath ~= "Sorceress_Skin.Abilities.Ability_PurifyBomb")
            return "adept.purity_bomb";
    }

    if(HeroKey == "" || HeroKey ~= "countess")
    {
        if(ArchetypePath ~= "LadyKnight_Skin.Abilities.Ability_LadyKnight_CalltoArms")
            return "countess.call_to_arms";
        if(ArchetypePath ~= "LadyKnight_Skin.Abilities.Ability_LadyKnight_SlamDash")
            return "countess.joust";
    }

    if(HeroKey == "" || HeroKey ~= "ranger")
    {
        if(ArchetypePath ~= "Hunter_Skin.Abilities.PlayerAbilityMassInvisibility")
            return "ranger.invisibility_field";
        if(ArchetypePath ~= "Hunter_Skin.Abilities.PlayerAbilitySpreadShot")
            return "ranger.piercing_spreadshot";
    }

    if(HeroKey == "" || HeroKey ~= "initiate")
    {
        if(ArchetypePath ~= "Monkette_Skin.Abilities.PlayerAbilityDefenseBoost")
            return "initiate.remote_defense_boost";
        if(ArchetypePath ~= "Monkette_Skin.Abilities.PlayerAbilityEnemyDrain")
            return "initiate.enemy_drain";
    }

    if(HeroKey == "" || HeroKey ~= "barbarian")
    {
        if(ArchetypePath ~= "Barbarian.Abilities.Ability_Barbarian_LeapSlam")
            return "barbarian.battle_leap";
        if(ArchetypePath ~= "Barbarian.Abilities.Ability_Barbarian_InPlaceLeapSlam")
            return "barbarian.battle_pound";
        if(ArchetypePath ~= "Barbarian.Abilities.Ability_Barbarian_TornadoStance")
            return "barbarian.tornado_stance";
        if(ArchetypePath ~= "Barbarian.Abilities.Barbarian_Ability_LightningStance")
            return "barbarian.lightning_stance";
        if(ArchetypePath ~= "Barbarian.Abilities.Barbarian_Ability_SiphonStance")
            return "barbarian.siphon_stance";
        if(ArchetypePath ~= "Barbarian.Abilities.Ability_Barbarian_TurtleStance")
            return "barbarian.turtle_stance";
        if(ArchetypePath ~= "Barbarian.Abilities.Ability_Barbarian_HawkStance")
            return "barbarian.hawk_stance";
    }

    if(HeroKey == "" || HeroKey ~= "series_ev")
    {
        if(ArchetypePath ~= "RobotGirl.Abilities.Ability_RobotGirl_Decoy")
            return "series_ev.holographic_decoy";
        if(ArchetypePath ~= "EV_Skins.Ability_RobotGirl_Decoy_Male")
            return "series_ev.holographic_decoy";
        if(ArchetypePath ~= "RobotGirl.Abilities.Ability_ManaCharge")
            return "series_ev.proton_charge_blast";
    }

    if(HeroKey == "" || HeroKey ~= "summoner")
    {
        if(ArchetypePath ~= "Summoner.Abilities.Ability_PhaseShift")
            return "summoner.phase_shift_overlord";
        if(ArchetypePath ~= "Summoner.Abilities.Ability_PhaseShift_Overlord")
            return "summoner.phase_shift_overlord";
        if(ArchetypePath ~= "Summoner.Abilities.Ability_FlashHeal")
            return "summoner.flash_heal";
    }

    if(HeroKey == "" || HeroKey ~= "jester")
    {
        if(ArchetypePath ~= "Jester.Abilities.Ability_MoveTower")
            return "jester.move_tower";
        if(ArchetypePath ~= "Jester.Abilities.PlayerAbility_WheeloFortuna")
            return "jester.wheel_o_fortuna";
    }

    if(HeroKey == "" || HeroKey ~= "hermit")
    {
        if(ArchetypePath ~= "Hermit.Abilities.ThornShot.Archetypes.Ability_Hermit_ThornShot")
            return "hermit.thorn_shot";
        if(ArchetypePath ~= "Hermit.Abilities.NaturesGift.Archetype.Ability_Hermit_NaturesGift")
            return "hermit.nature_s_gift";
    }

    if(HeroKey == "" || HeroKey ~= "gunwitch")
    {
        if(ArchetypePath ~= "Gunwitch.Abilities.IcyNeedle.Ability_Gunwitch_IcyNeedle")
            return "gunwitch.icy_needle";
        if(ArchetypePath ~= "Gunwitch.Abilities.VroomBroom.Ability_Gunwtich_VroomBroom")
            return "gunwitch.vroom_broom";
        if(ArchetypePath ~= "Gunwitch.Abilities.TwoForOne.Ability_Gunwitch_TwoForOne")
            return "gunwitch.two_for_the_price_of_one";
        if(ArchetypePath ~= "Gunwitch.Abilities.WitchsCurse.Ability_Gunwitch_WitchsCurse")
            return "gunwitch.witch_s_curse";
        if(ArchetypePath ~= "Gunwitch.Abilities.BroomNado.Ability_BroomNado")
            return "gunwitch.broom_nado";
        if(ArchetypePath ~= "Gunwitch.Abilities.BlunderBroomBuster.AbilityBlunderBroomBuster")
            return "gunwitch.blunder_broom_buster";
    }

    if(HeroKey == "" || HeroKey ~= "warden")
    {
        if(ArchetypePath ~= "Warden.Abilities.Wrath.Archetype.Ability_Warden_Wrath")
            return "warden.wrath";
        if(ArchetypePath ~= "Warden.Abilities.MushroomCircle.Archetype.Ability_MushroomCircle")
            return "warden.forest_s_protection";
    }

    if(HeroKey == "" || HeroKey ~= "guardian")
    {
        if(ArchetypePath ~= "Guardian.Abilities.ShieldBash.AbilityShieldBash")
            return "guardian.shield_bash";
        if(ArchetypePath ~= "Guardian.Abilities.DivineJudgement.Ability_DivineJudgement")
            return "guardian.divine_judgement";
    }

    return "";
}

function bool IsBasicAbility(DunDefPlayerAbility Ability, string HeroKey)
{
    local string ArchetypePath;

    if(Ability == none || Ability.ObjectArchetype == none)
    {
        return false;
    }
    ArchetypePath = PathName(Ability.ObjectArchetype);

    // These are ordinary controls, not randomized hero skills.
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_HealSelf" ||
        ArchetypePath ~= "DunDefPlayers.Abilities.Ability_RepairTower" ||
        ArchetypePath ~= "DunDefPlayers.Abilities.Ability_UpgradeTower" ||
        ArchetypePath ~= "DunDefPlayers.Abilities.Ability_SellTower" ||
        ArchetypePath ~= "DunDefPlayers.Abilities.Ability_DetonateTraps")
    {
        return true;
    }

    if(HeroKey ~= "hermit" &&
        ArchetypePath ~= "Hermit.Abilities.WhirlWind.Archetype.PlayerAbilityWhirlWind")
    {
        return true;
    }

    if(HeroKey ~= "summoner")
    {
        return ArchetypePath ~= "Summoner.Abilities.Ability_RepairTower_Summoner" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_UpgradeTower_Summoner" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_DeSelectUnits" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_SelectUnits" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_SelectAllUnits" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandMoveDefensive" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandMoveOffensive" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandAttackTarget" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandFollow" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandFollowTarget" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandHoldDefensive" ||
            ArchetypePath ~= "Summoner.Abilities.Ability_CommandHoldOffensive";
    }
    return false;
}

function bool IsMapUnlocked(string CampaignTag)
{
    if(Left(CampaignTag, 4) == "SPEC")
        return (ModeMask & 2) != 0 && IsRandomizerMap(CampaignTag) &&
            ContainsValue(UnlockedMaps, "CAMP" $ Mid(CampaignTag, 4));
    return ContainsValue(UnlockedMaps, CampaignTag);
}

function bool IsRandomizerMap(string CampaignTag)
{
    if(Left(CampaignTag, 4) == "SPEC")
        CampaignTag = "CAMP" $ Mid(CampaignTag, 4);
    return CampaignTag == "CAMPDW" || CampaignTag == "CAMPFF" ||
        CampaignTag == "CAMPMQ" || CampaignTag == "CAMPAL" ||
        CampaignTag == "CAMPSQ" || CampaignTag == "CAMPCA" ||
        CampaignTag == "CAMPHC" || CampaignTag == "CAMPTR" ||
        CampaignTag == "CAMPRG" || CampaignTag == "CAMPRP" ||
        CampaignTag == "CAMPES" || CampaignTag == "CAMPTS";
}

function bool IsDifficultyUnlocked(int Difficulty)
{
    if(Difficulty < 0 || Difficulty > 3)
        return false;
    return (DifficultyMask & (1 << Difficulty)) != 0;
}

function string GetStartingHeroDisplayName()
{
    if(IsHeroUnlocked("apprentice")) return "Apprentice";
    if(IsHeroUnlocked("squire")) return "Squire";
    if(IsHeroUnlocked("huntress")) return "Huntress";
    if(IsHeroUnlocked("monk")) return "Monk";
    if(IsHeroUnlocked("adept")) return "Adept";
    if(IsHeroUnlocked("countess")) return "Countess";
    if(IsHeroUnlocked("ranger")) return "Ranger";
    if(IsHeroUnlocked("initiate")) return "Initiate";
    if(IsHeroUnlocked("barbarian")) return "Barbarian";
    if(IsHeroUnlocked("series_ev")) return "Series EV";
    if(IsHeroUnlocked("summoner")) return "Summoner";
    if(IsHeroUnlocked("jester")) return "Jester";
    if(IsHeroUnlocked("hermit")) return "Hermit";
    if(IsHeroUnlocked("gunwitch")) return "Gunwitch";
    if(IsHeroUnlocked("warden")) return "Warden";
    if(IsHeroUnlocked("guardian")) return "Guardian";
    return "Unknown";
}

function string GetStartingMapDisplayName()
{
    if(IsMapUnlocked("CAMPDW")) return "The Deeper Well";
    if(IsMapUnlocked("CAMPFF")) return "Foundries and Forges";
    if(IsMapUnlocked("CAMPMQ")) return "Magus Quarters";
    if(IsMapUnlocked("CAMPAL")) return "Alchemical Laboratory";
    if(IsMapUnlocked("CAMPSQ")) return "Servants Quarters";
    if(IsMapUnlocked("CAMPCA")) return "Castle Armory";
    if(IsMapUnlocked("CAMPHC")) return "Hall of Court";
    if(IsMapUnlocked("CAMPTR")) return "The Throne Room";
    if(IsMapUnlocked("CAMPRG")) return "Royal Gardens";
    if(IsMapUnlocked("CAMPRP")) return "The Ramparts";
    if(IsMapUnlocked("CAMPES")) return "Endless Spires";
    if(IsMapUnlocked("CAMPTS")) return "The Summit";
    return "Unknown";
}

function int GetEquipmentQualityRank(byte QualityIndex)
{
    // DD1 stores the original tiers in reverse order (Godly=0 through
    // Cursed=12), then appends Mythical through Ultimate++ as 13..19.
    if(QualityIndex <= 12)
    {
        return 12 - int(QualityIndex);
    }

    return int(QualityIndex);
}

function bool IsEquipmentQualityUnlocked(HeroEquipment Equipment)
{
    if(Equipment == none)
    {
        return true;
    }

    return GetEquipmentQualityRank(Equipment.NameIndex_QualityDescriptor) <= MaxEquipmentQuality;
}

defaultproperties
{
    Revision=0
    Slot="Unconfigured"
    MaxEquipmentQuality=0
    ExperienceMultiplier=1
}
