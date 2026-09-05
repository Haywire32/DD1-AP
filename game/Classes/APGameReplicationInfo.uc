class APGameReplicationInfo extends DunDefGameReplicationInfo;

var int LastAPCompletedWave;

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

    if(WorldInfo.NetMode != NM_Standalone || PC == none)
    {
        return true;
    }

    APGame = APGameInfo(WorldInfo.Game);
    if(APGame == none || APGame.UnlockState == none)
    {
        return true;
    }

    HeroKey = APGame.UnlockState.GetHeroKey(PC.GetHero());
    return HeroKey != "" && APGame.UnlockState.IsHeroUnlocked(HeroKey);
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
            DefenseKey = APGame.UnlockState.GetDefenseKey(TowerArchetype);
            if(DefenseKey != "" && !APGame.UnlockState.IsDefenseUnlocked(DefenseKey))
            {
                return false;
            }
        }
    }

    return super.CanPlaceTowerUnitCost(Cost, ForPlayer, TowerArchetype);
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
