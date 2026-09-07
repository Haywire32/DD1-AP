class APGameReplicationInfo extends DunDefGameReplicationInfo;

var int LastAPCompletedWave;
var array<string> ReportedUnknownAPActions;

simulated function ShowAPLockedMessage(string Message)
{
    local LinearColor LockedColor;

    LockedColor.R = 1.0;
    LockedColor.G = 0.15;
    LockedColor.B = 0.15;
    LockedColor.A = 1.0;
    NetworkedHUDMessage(Message, LockedColor, 24, 4.0);
}

simulated function LoadMission(CampaignLevelEntryObject MissionObject)
{
    local APGameInfo APGame;

    if(WorldInfo.NetMode == NM_Standalone && MissionObject != none)
    {
        APGame = APGameInfo(WorldInfo.Game);
        if(APGame != none && APGame.UnlockState != none &&
            !APGame.UnlockState.IsMapUnlocked(MissionObject.MyLevelEntry.EntryIdentifierTag))
        {
            `warn("AP:BLOCKED_LOCKED_MAP_LAUNCH tag=" $ MissionObject.MyLevelEntry.EntryIdentifierTag);
            ShowAPLockedMessage("Archipelago: This map is locked.");
            return;
        }
    }

    super.LoadMission(MissionObject);
}

simulated function bool IsHeroAllowed(DunDefPlayerController PC)
{
    local APGameInfo APGame;
    local string HeroKey;

    if(WorldInfo.NetMode != NM_Standalone)
    {
        return true;
    }
    if(PC == none)
    {
        return false;
    }

    APGame = APGameInfo(WorldInfo.Game);
    if(APGame == none)
    {
        return true;
    }
    if(APGame.UnlockState == none)
    {
        return false;
    }

    HeroKey = APGame.UnlockState.GetHeroKey(PC.GetHero());
    return HeroKey != "" && APGame.UnlockState.IsHeroUnlocked(HeroKey) &&
        APGame.IsOwnedHero(PC.GetHero());
}

simulated function bool WeaponsEnabled()
{
    local DunDefPlayerController PC;

    if(WorldInfo.NetMode == NM_Standalone)
    {
        foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
        {
            if(!IsHeroAllowed(PC))
            {
                return false;
            }
        }
    }

    return super.WeaponsEnabled();
}

simulated function bool CanPlaceTowerUnitCost(int Cost, DunDefPlayerController ForPlayer, optional DunDefTower TowerArchetype)
{
    local APGameInfo APGame;
    local string DefenseKey;

    if(WorldInfo.NetMode == NM_Standalone && !IsHeroAllowed(ForPlayer))
    {
        return false;
    }

    if(WorldInfo.NetMode == NM_Standalone && TowerArchetype != none)
    {
        APGame = APGameInfo(WorldInfo.Game);
        if(APGame != none && APGame.UnlockState != none)
        {
            DefenseKey = APGame.UnlockState.GetDefenseKey(TowerArchetype,
                APGame.UnlockState.GetHeroKey(ForPlayer.GetHero()));
            if(DefenseKey == "")
            {
                ReportUnknownAPAction(PathName(TowerArchetype));
                return false;
            }
            if(!APGame.UnlockState.IsDefenseUnlocked(DefenseKey))
            {
                return false;
            }
        }
    }

    return super.CanPlaceTowerUnitCost(Cost, ForPlayer, TowerArchetype);
}

simulated function ReportUnknownAPAction(string ObjectPath)
{
    if(ReportedUnknownAPActions.Find(ObjectPath) == INDEX_NONE)
    {
        ReportedUnknownAPActions.AddItem(ObjectPath);
        `warn("AP:UNSUPPORTED_ACTION blocked=" $ ObjectPath $
            " reason=No verified AP mapping for this game version");
    }
}

simulated function bool ShouldDenyAPAbility(DunDefPlayerAbility Ability)
{
    local APGameInfo APGame;
    local DunDefPlayerController PC;
    local DunDefPlayerAbility_BuildTower BuildAbility;
    local string HeroKey;
    local string ActionKey;

    if(WorldInfo.NetMode != NM_Standalone)
    {
        return false;
    }
    APGame = APGameInfo(WorldInfo.Game);
    if(APGame == none)
    {
        return false;
    }
    if(Ability == none || APGame.UnlockState == none)
    {
        return true;
    }

    PC = Ability.GetPC();
    if(!IsHeroAllowed(PC))
    {
        return true;
    }
    HeroKey = APGame.UnlockState.GetHeroKey(PC.GetHero());

    BuildAbility = DunDefPlayerAbility_BuildTower(Ability);
    if(BuildAbility != none)
    {
        ActionKey = APGame.UnlockState.GetDefenseKey(BuildAbility.TowerArchetype, HeroKey);
        if(ActionKey == "")
        {
            ReportUnknownAPAction(PathName(Ability.ObjectArchetype));
            return true;
        }
        return !APGame.UnlockState.IsDefenseUnlocked(ActionKey);
    }

    ActionKey = APGame.UnlockState.GetAbilityKey(Ability, HeroKey);
    if(ActionKey != "")
    {
        return !APGame.UnlockState.IsAbilityUnlocked(ActionKey);
    }
    if(APGame.UnlockState.IsBasicAbility(Ability, HeroKey))
    {
        return false;
    }

    // Unknown hero-specific actions do not become free unlocks after a game
    // update. Essential ordinary controls have explicit verified identities.
    ReportUnknownAPAction(PathName(Ability.ObjectArchetype));
    return true;
}

simulated function bool UsePlayerAbilityStatusOverride(DunDefPlayerAbility Ability)
{
    // Deny-only: never return CANACTIVATE here for an owned action. Vanilla
    // must still check its mana, cooldown, casting/phase and stance conditions.
    return ShouldDenyAPAbility(Ability) || super.UsePlayerAbilityStatusOverride(Ability);
}

simulated function EPlayerAbilityStatus GetPlayerAbilityStatusOverride(DunDefPlayerAbility Ability)
{
    if(ShouldDenyAPAbility(Ability))
    {
        return EPA_NOTAPPLICABLE;
    }
    return super.GetPlayerAbilityStatusOverride(Ability);
}

function EndedCombatPhase()
{
    local APGameInfo APGame;
    local int CompletedWave;

    if(Role == ROLE_Authority && WorldInfo.NetMode == NM_Standalone && IsGameplayLevel && !IsLobbyLevel)
    {
        // DD1 advances WaveNumber before EndedCombatPhase runs. Its own
        // equipment-stat logger uses WaveNumber - 1 for the completed wave.
        CompletedWave = WaveNumber - 1;
        if(CompletedWave > LastAPCompletedWave)
        {
            LastAPCompletedWave = CompletedWave;
            `log("AP:WAVE_COMPLETE map=" $ WorldInfo.GetPackageName() $ " wave=" $ CompletedWave $ " difficulty=" $ CurrentGameDifficulty);
            APGame = APGameInfo(WorldInfo.Game);
            if(APGame != none && APGame.EventBridge != none)
            {
                APGame.EventBridge.EmitEvent("wave_complete", string(WorldInfo.GetPackageName()), CompletedWave, string(CurrentGameDifficulty));
            }
        }
    }

    super.EndedCombatPhase();
}

defaultproperties
{
    LastAPCompletedWave=-1
    bOverridePlayerAbilityStatus=true
}

simulated function DoLevelVictory()
{
    local APGameInfo APGame;

    // The parent function ignores duplicate authoritative victory calls. Check
    // its state first so this event follows the same exactly-once behavior.
    if(!bDoLevelVictory && !bIsGameOver && Role == ROLE_Authority && WorldInfo.NetMode == NM_Standalone && IsGameplayLevel && !IsLobbyLevel)
    {
        `log("AP:LEVEL_VICTORY map=" $ WorldInfo.GetPackageName() $ " wave=" $ WaveNumber $ " difficulty=" $ CurrentGameDifficulty);
        APGame = APGameInfo(WorldInfo.Game);
        if(APGame != none && APGame.EventBridge != none)
        {
            APGame.EventBridge.EmitEvent("level_victory", string(WorldInfo.GetPackageName()), WaveNumber, string(CurrentGameDifficulty));
        }
    }

    super.DoLevelVictory();

    // Vanilla victory records the next campaign map as ordinary local
    // progress. Reapply AP ownership immediately so it remains hidden and
    // unselectable until its map item arrives.
    APGame = APGameInfo(WorldInfo.Game);
    if(APGame != none)
    {
        APGame.ApplyOwnedMapVisibility();
    }
}
