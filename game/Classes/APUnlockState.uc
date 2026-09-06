class APUnlockState extends Object
    config(DD1ArchipelagoUnlocks);

var config int Revision;
var config string Slot;
var config array<string> UnlockedHeroes;
var config array<string> LevelSixHeroes;
var config array<string> UnlockedDefenses;
var config array<string> UnlockedAbilities;
var config array<string> UnlockedMaps;
var config int MaxEquipmentQuality;
var config int ExperienceMultiplier;

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
    if(Hero == none)
    {
        return "";
    }

    switch(Hero.GetCurrentHeroTemplate().MyHeroClass)
    {
        case EHC_APPRENTICE:
            return "apprentice";
        case EHC_SQUIRE:
            return "squire";
        case EHC_HUNTRESS:
            return "huntress";
        case EHC_MONK:
            return "monk";
    }

    // The first playable item table contains only the four original heroes.
    return "";
}

function bool IsDefenseUnlocked(string DefenseKey)
{
    return ContainsValue(UnlockedDefenses, DefenseKey);
}

function string GetDefenseKey(DunDefTower TowerArchetype)
{
    local string ArchetypePath;

    if(TowerArchetype == none)
    {
        return "";
    }

    ArchetypePath = PathName(TowerArchetype);

    // Stable base-game archetype identities. Exact paths distinguish traps
    // and other defenses that intentionally share an UnrealScript class.
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_SpikyBlockade_Arch")
        return "squire.spike_blockade";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_BouncyBlockade_Arch")
        return "squire.bouncer_blockade";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Harpoon_Arch")
        return "squire.harpoon_turret";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_BowlingBall_Arch")
        return "squire.bowling_ball_turret";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_SliceNDice_Arch")
        return "squire.slice_n_dice_blockade";

    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Blockade_Arch")
        return "apprentice.magic_blockade";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_MagicMissile_Arch")
        return "apprentice.magic_missile_tower";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_Fireball_Arch")
        return "apprentice.fireball_tower";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_ChainLightning_Arch")
        return "apprentice.lightning_tower";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_DeadlyStriker_Arch")
        return "apprentice.deadly_striker_tower";

    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_ProxMine_Arch")
        return "huntress.proximity_mine_trap";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_GasTrap_Arch")
        return "huntress.gas_trap";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_InfernoTrap_Arch")
        return "huntress.inferno_trap";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_DarknessTrap_Arch")
        return "huntress.darkness_trap";
    if(ArchetypePath ~= "DunDefArchetypes.DunDefTower_EtherealSpikeTrap_Arch")
        return "huntress.ethereal_spike_trap";

    // The current live build stores these two Monk archetypes in DunDefAuras;
    // "DeathyHallows" is the shipped internal spelling for Electric Aura.
    if(ArchetypePath ~= "DunDefAuras.Aura_StickyGloop")
        return "monk.ensnare_aura";
    if(ArchetypePath ~= "DunDefAuras.Aura_DeathyHallows")
        return "monk.electric_aura";

    if(TowerArchetype.IsA('DunDefTower_AuraHeal'))
        return "monk.healing_aura";
    if(TowerArchetype.IsA('DunDefTower_AuraStrengthDrain'))
        return "monk.strength_drain_aura";
    if(TowerArchetype.IsA('DunDefTower_AuraEnrage'))
        return "monk.enrage_aura";

    return "";
}

function bool IsTowerUnlocked(DunDefTower TowerArchetype)
{
    local string DefenseKey;

    DefenseKey = GetDefenseKey(TowerArchetype);
    if(DefenseKey != "")
    {
        return IsDefenseUnlocked(DefenseKey);
    }

    // Unmapped defenses remain vanilla until their stable key is added.
    return true;
}

function bool IsAbilityUnlocked(string AbilityKey)
{
    return ContainsValue(UnlockedAbilities, AbilityKey);
}

function string GetAbilityKey(DunDefPlayerAbility Ability)
{
    local string ArchetypePath;

    if(Ability == none || Ability.ObjectArchetype == none)
    {
        return "";
    }

    ArchetypePath = PathName(Ability.ObjectArchetype);

    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Apprentice_Overcharge")
        return "apprentice.overcharge";
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Apprentice_ManaBomb")
        return "apprentice.mana_bomb";

    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Squire_BloodRage")
        return "squire.blood_rage";
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Squire_CircleSlice")
        return "squire.circular_slice";

    // Both live Huntress invisibility variants intentionally share one AP
    // unlock. Only one is exposed by a given hero/action-wheel configuration.
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Initiate_Invisibility" ||
        ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Initiate_Invisibility_Old")
        return "huntress.invisibility";
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Huntress_PiercingShot")
        return "huntress.piercing_shot";

    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Recruit_TowerBoost")
        return "monk.tower_boost";
    if(ArchetypePath ~= "DunDefPlayers.Abilities.Ability_Recruit_HeroBoost")
        return "monk.hero_boost";

    return "";
}

function bool IsMapUnlocked(string CampaignTag)
{
    return ContainsValue(UnlockedMaps, CampaignTag);
}

function bool IsRandomizerMap(string CampaignTag)
{
    return CampaignTag == "CAMPDW" || CampaignTag == "CAMPFF" ||
        CampaignTag == "CAMPMQ" || CampaignTag == "CAMPAL" ||
        CampaignTag == "CAMPSQ" || CampaignTag == "CAMPCA" ||
        CampaignTag == "CAMPHC" || CampaignTag == "CAMPTR" ||
        CampaignTag == "CAMPRG" || CampaignTag == "CAMPRP" ||
        CampaignTag == "CAMPES" || CampaignTag == "CAMPTS";
}

function string GetStartingHeroDisplayName()
{
    if(IsHeroUnlocked("apprentice")) return "Apprentice";
    if(IsHeroUnlocked("squire")) return "Squire";
    if(IsHeroUnlocked("huntress")) return "Huntress";
    if(IsHeroUnlocked("monk")) return "Monk";
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
