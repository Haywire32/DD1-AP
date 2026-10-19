class APGameRuntime extends Info;

var APEventBridge EventBridge;
var APUnlockState UnlockState;
var APChaosRuntime ChaosRuntime;
var string LastChaosFailure;
var APInboundLink InboundLink;
var APReverseListener ReverseListener;
var APFileSnapshotBridge FileSnapshotBridge;
var APRewardState RewardState;
var int PendingXPRewardCount;
var int PendingManaRewardCount;
var int PendingGearRewardCount;
var array<string> APMessageQueue;
var bool bAPReturningToMenu;
var DunDefPlayerController APDeniedHeroController;
var string APDeniedHeroReason;
var UI_BuildTimer APLastBuildTimer;
var int APLastTimerWave;
var int APAppliedBuildBonus;
var int APFileBridgeRevision;
var string APFileBridgeSeedIdentity;
var bool bAPCapturedVictoryGearScale;
var APDeathLink DeathLink;
var APTrapRuntime Traps;
var APTavernThemes Themes;
var array<LocalPlayer> APPendingSplitPlayerRemoval;
var DunDefGameReplicationInfo APDUInfo;
var int APBaseDefenseUnits, APLastDefenseUnits;
var APMoonbaseDefenseUnits MoonbaseDefenseUnits;
var array<APSummonerMapIcon> SummonerMapGuards;

struct APHeroExperienceTracker
{
    var DunDefHero Hero;
    var int LastExperience;
};
var array<APHeroExperienceTracker> APExperienceTrackers;

function bool ApplyChaosLoadout(DunDefPlayerController PC)
{
    local string Reason;
    local APChaosRuntime Candidate;
    if(WorldInfo.NetMode != NM_Standalone || WorldInfo.Pauser != none || bAPReturningToMenu ||
        UnlockState == none || !UnlockState.bChaosLoadouts || !IsStableLocalController(PC)) return false;
    if(ChaosRuntime == none || ChaosRuntime.bDeleteMe)
    {
        Candidate=Spawn(class'APChaosRuntime',self);
        if(Candidate != none && Candidate.Initialize(UnlockState,Reason)) ChaosRuntime=Candidate;
        else if(Candidate != none) Candidate.Destroy();
    }
    if(ChaosRuntime != none && ChaosRuntime.Apply(PC,Reason)) return true;
    if(Reason != "" && Reason != LastChaosFailure)
    {
        LastChaosFailure=Reason;
        `warn("AP:CHAOS_LOADOUT_NOT_READY " $ Reason);
    }
    return false;
}

function RefreshChaosLoadouts()
{
    local DunDefPlayerController PC;
    local int I;
    if(UnlockState == none || !UnlockState.bChaosLoadouts || WorldInfo.Pauser != none) return;
    if(ChaosRuntime != none)
        for(I=ChaosRuntime.Players.Length-1; I>=0; I--)
        {
            PC=ChaosRuntime.Players[I].PC;
            if(PC == none || PC.bDeleteMe) ChaosRuntime.ClearFor(PC);
        }
    foreach WorldInfo.AllControllers(class'DunDefPlayerController',PC) ApplyChaosLoadout(PC);
}

simulated event Tick(float DeltaTime)
{
    local DunDefPlayerController PC;
    local DunDefPlayer_Summoner SummonerPawn;
    local APSummonerMapIcon Guard;
    local bool Found;
    local int I;
    super.Tick(DeltaTime);
    if(WorldInfo.NetMode != NM_Standalone || bAPReturningToMenu) return;
    for(I = SummonerMapGuards.Length - 1; I >= 0; I--)
        if(SummonerMapGuards[I] == none || SummonerMapGuards[I].bDeleteMe)
            SummonerMapGuards.Remove(I, 1);
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        SummonerPawn = DunDefPlayer_Summoner(PC.Pawn);
        if(SummonerPawn == none || !IsStableLocalController(PC)) continue;
        Found = false;
        foreach SummonerMapGuards(Guard)
            if(Guard.Summoner == SummonerPawn) { Found = true; break; }
        if(!Found)
        {
            Guard = Spawn(class'APSummonerMapIcon', self);
            if(Guard != none)
            {
                Guard.Initialize(SummonerPawn);
                SummonerMapGuards.AddItem(Guard);
                class'APRuntimeDiagnostics'.static.Record(WorldInfo,
                    "SUMMONER guard_attached pc=" $ PC.Class $ " replaced=" $ Guard.bReplacedIcon);
            }
        }
    }
}

function QueueAPMessage(string Message)
{
    if(WorldInfo.NetMode != NM_Standalone || Message == "")
        return;
    if(APMessageQueue.Length < 100)
        APMessageQueue.AddItem(Left(Message, 240));
    if(!IsTimerActive('DisplayNextAPMessage'))
        DisplayNextAPMessage();
}

function ApplyAPDefenseUnits()
{
    local DunDefGameReplicationInfo GRI;
    local UI_GlobalHUD GlobalHUD;
    local int Wanted;
    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none) return;
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none || !GRI.IsGameplayLevel || GRI.IsLobbyLevel) return;
    if(GameInfo_NoTowers(WorldInfo.Game) != none)
    {
        // This challenge must display and enforce zero even with all DU items.
        // Match the native mission class (including its AP subclass), not the
        // Deeper Well map name, so campaign and Survival retain their bonuses.
        APDUInfo = GRI;
        APBaseDefenseUnits = 0;
        Wanted = 0;
    }
    else if(GameInfo_ZippyTerror(WorldInfo.Game) != none)
    {
        // Fixed challenge baseline: never recapture the already-bonused cap
        // or a native reset to zero as a new base on a later update.
        APDUInfo = GRI;
        APBaseDefenseUnits = class'APGameZippy'.const.AP_BASE_DU;
        Wanted = class'APGameZippy'.static.DefenseUnitsForBonus(UnlockState.DefenseUnitsBonus);
    }
    else
    {
        if(MoonbaseDefenseUnits==none && UnlockState.DefenseUnitsBonus>0 &&
            Caps(WorldInfo.GetMapName(true))=="CR4ZY_MOONBASE")
            MoonbaseDefenseUnits=new(self) class'APMoonbaseDefenseUnits';
        // Keep native map/difficulty changes; never repeatedly add the bonus.
        if(MoonbaseDefenseUnits!=none && MoonbaseDefenseUnits.ReadBase(WorldInfo,APBaseDefenseUnits))
            APDUInfo=GRI;
        else if(APDUInfo != GRI || GRI.MaxTowerUnits != APLastDefenseUnits)
        {
            APDUInfo = GRI;
            APBaseDefenseUnits = GRI.MaxTowerUnits;
        }
        Wanted = APBaseDefenseUnits + Clamp(UnlockState.DefenseUnitsBonus, 0, 30);
    }
    APLastDefenseUnits = Wanted;
    if(GRI.MaxTowerUnits == Wanted) return;
    GRI.MaxTowerUnits = Wanted;
    GlobalHUD = class'UI_GlobalHUD'.static.GetGlobalHUD();
    if(GlobalHUD != none)
        GlobalHUD.SetTowerUnitCosts(GRI.CurrentTowerUnits, GRI.CurrentAltTowerUnits, Wanted);
    `log("AP:DEFENSE_UNITS base=" $ APBaseDefenseUnits $ " total=" $ Wanted);
}

function DisplayNextAPMessage()
{
    local DunDefPlayerController PC;
    if(APMessageQueue.Length == 0)
        return;
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(PC.myHUD != none)
        {
            class'DunDefGameMessage'.static.PrintHUDMessage(PC, APMessageQueue[0], false,,true,3,,true,4.0,true,0.2);
            APMessageQueue.Remove(0,1);
            break;
        }
    }
    SetTimer(4.5,false,'DisplayNextAPMessage');
}







simulated event PostBeginPlay()
{
    local APViewportClient Viewport;
    if(WorldInfo.NetMode != NM_Standalone)
    {
        bAPReturningToMenu = true;
        ConsoleCommand("quit");
        return;
    }
    super.PostBeginPlay();

    if(WorldInfo.NetMode == NM_Standalone)
    {
        if(bAPReturningToMenu)
            return;
        `log("AP:INITIALIZED map=" $ WorldInfo.GetMapName() $ " mode=LOCAL_STANDALONE");
        UnlockState = new(self) class'APUnlockState';
        Viewport = APViewportClient(class'DunDefViewportClient'.static.GetViewportClient());
        if(Viewport != none)
            UnlockState.CopyFrom(Viewport.GetTravelUnlockState());
        class'APHeroSkins'.static.SilenceNativeAwards(UnlockState, WorldInfo);
        `log("AP:TRAVEL_STATE_RESTORED map=" $ WorldInfo.GetMapName() $ " revision=" $ UnlockState.Revision);
        APFileBridgeRevision = UnlockState.Revision;
        APFileBridgeSeedIdentity = UnlockState.SeedIdentity;
        RewardState = new(self) class'APRewardState';
        DeathLink = Spawn(class'APDeathLink');
        if(DeathLink != none) DeathLink.Initialize(self);
        Traps=Spawn(class'APTrapRuntime',self);
        if(Traps != none) Traps.Initialize(self);
        Themes=Spawn(class'APTavernThemes',self);
        if(Themes != none) Themes.Initialize(self);
        ApplyOwnedMapVisibility();
        ConfigureHeroOwnership();
        SetTimer(0.10, true, 'ApplyAPExperienceMultiplier');
        SetTimer(0.10, true, 'ApplyAPBuildTime');
        SetTimer(0.10, true, 'ApplyAPDefenseUnits');
        SetTimer(1.0, true, 'ApplyPendingGearReward');
        SetTimer(0.25, true, 'CaptureVictoryGearScale');
        SetTimer(0.50, true, 'PollUnlockFile');
        SetTimer(0.50, true, 'ApplyTavernShardDisplay');
        if(UnlockState.bChaosLoadouts) SetTimer(0.25,true,'RefreshChaosLoadouts');
        `log("AP:UNLOCK_STATE revision=" $ UnlockState.Revision $ " slot=" $ UnlockState.Slot $
            " heroes=" $ UnlockState.UnlockedHeroes.Length $ " defenses=" $ UnlockState.UnlockedDefenses.Length $
            " abilities=" $ UnlockState.UnlockedAbilities.Length $ " maps=" $ UnlockState.UnlockedMaps.Length $
            " max_quality=" $ UnlockState.MaxEquipmentQuality $
            " experience_multiplier=" $ GetAPExperienceMultiplier() $
            " catch_up_multiplier=" $ GetAPLevelCatchUpMultiplier());
        EventBridge = Spawn(class'APEventBridge');
        if(EventBridge != none)
        {
            EventBridge.Initialize();
        }
        InboundLink = Spawn(class'APInboundLink');
        if(InboundLink != none)
        {
            InboundLink.Initialize(self);
        }
        if(UnlockState.bReverseBridge)
        {
            FileSnapshotBridge=Spawn(class'APFileSnapshotBridge',self);
            if(FileSnapshotBridge != none) FileSnapshotBridge.Initialize(self);
            ReverseListener = Spawn(class'APReverseListener',self);
            if(ReverseListener != none) ReverseListener.Initialize(self);
        }
    }
    else
    {
        // The prototype must never operate in an online/networked session.
        `warn("AP:DISABLED_NON_LOCAL map=" $ WorldInfo.GetMapName());
    }
}

// DD1 creates the next Tavern stock from the best quality and rarity observed
// during the map which was just completed. Preserve that native shop tier for
// AP gear rewards so delivery location does not change their strength.
function CaptureVictoryGearScale()
{
    local DunDefGameReplicationInfo GRI;
    local DunDefHeroManager Manager;
    local float ShopQuality;
    local float ShopRarity;
    local float ShopRandomizerMultiplier;
    local float ScaleScore;

    if(bAPCapturedVictoryGearScale || RewardState == none || UnlockState == none ||
        RewardState.AppliedSeedIdentity != UnlockState.SeedIdentity)
        return;
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none || GRI.IsLobbyLevel || !GRI.IsGameplayLevel || !GRI.bDoLevelVictory)
        return;
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none)
        return;

    // This is the same first-stage adjustment as SetRandomShopEquipments().
    ShopQuality = GRI.LastItemDropQuality * Manager.ShopItemQualityMutliplier +
        Manager.ShopItemQualityAddition;
    ShopRarity = GRI.LastItemDropExtraRarity * Manager.ShopRarityMultiplier +
        Manager.ShopRarityAddition;
    // Shop items normally ask the completed mission for this multiplier while
    // they are generated. Save one native shop roll so it remains available
    // after returning to the Tavern or entering another map.
    ShopRandomizerMultiplier = Manager.GetCurrentMissionEquipmentRandomizerMultiplier(true);
    ShopRandomizerMultiplier = FMax(1.0, ShopRandomizerMultiplier);
    ScaleScore = ShopQuality * ShopRandomizerMultiplier + FMax(0.0, ShopRarity) * 0.01;

    if(ScaleScore > RewardState.BestGearScaleScore)
    {
        RewardState.BestGearQuality = ShopQuality;
        RewardState.BestGearExtraRarity = ShopRarity;
        RewardState.BestGearRandomizerMultiplier = ShopRandomizerMultiplier;
        RewardState.BestGearScaleScore = ScaleScore;
        RewardState.SaveConfig();
        `log("AP:GEAR_SCALE_UPDATED quality=" $ ShopQuality $ " rarity=" $ ShopRarity $
            " randomizer=" $ ShopRandomizerMultiplier);
    }
    bAPCapturedVictoryGearScale = true;
}

// Proton can isolate the Windows game's loopback connection from the native
// Linux AP client. Both processes still share this atomic config file, so poll
// it as a cross-platform live-delivery fallback. On Windows this remains idle
// while revisions are already applied by the socket.
function ApplyTavernShardDisplay()
{
    class'APTavernShards'.static.Apply(WorldInfo, UnlockState);
}

function ApplyShardDisplaySnapshot(string Line)
{
    local array<string> Fields;
    local int Mask;
    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none) return;
    ParseStringIntoArray(Line, Fields, "|", false);
    if(Fields.Length != 3 || Fields[0] != "APSHARDS1" ||
        Fields[1] != UnlockState.SeedIdentity) return;
    Mask = int(Fields[2]);
    if(Mask < -1 || Mask > 15 || string(Mask) != Fields[2]) return;
    UnlockState.EterniaShardMask = Mask;
    RememberSessionUnlocks();
    ApplyTavernShardDisplay();
}

function ApplyGearSettingsSnapshot(string Line)
{
    local array<string> Fields;
    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none) return;
    ParseStringIntoArray(Line, Fields, "|", false);
    if(Fields.Length != 3 || Fields[0] != "APGEAR1" || Fields[1] != UnlockState.SeedIdentity ||
        (Fields[2] != "0" && Fields[2] != "1")) return;
    UnlockState.bRandomGearPets = Fields[2] == "1";
    RememberSessionUnlocks();
}

function PollUnlockFile()
{
    local APUnlockState Candidate;
    local DunDefPlayerController PC;

    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none || APFileBridgeSeedIdentity == "")
        return;
    if(InboundLink != none && InboundLink.IsConnected() && InboundLink.bSnapshotAccepted)
        return;

    // ReloadCfg is the UE3 runtime command for refreshing config variables.
    // Use the fully qualified class so no unrelated game configuration reloads.
    ConsoleCommand("ReloadCfg DD1Archipelago.APUnlockState");
    Candidate = new(self) class'APUnlockState';
    if(Candidate.bChaosLoadouts != UnlockState.bChaosLoadouts ||
        Candidate.ChaosMappingToken != UnlockState.ChaosMappingToken ||
        Candidate.ChaosPlayerSlot != UnlockState.ChaosPlayerSlot)
        return;
    if(Candidate.SeedIdentity != APFileBridgeSeedIdentity || Candidate.Revision <= APFileBridgeRevision)
        return;

    APFileBridgeRevision = Candidate.Revision;
    PendingXPRewardCount = Max(PendingXPRewardCount, Candidate.ReceivedXPRewards);
    PendingManaRewardCount = Max(PendingManaRewardCount, Candidate.ReceivedManaRewards);
    PendingGearRewardCount = Max(PendingGearRewardCount, Candidate.ReceivedGearRewards);

    UnlockState.Revision = Candidate.Revision;
    UnlockState.UnlockedHeroes = Candidate.UnlockedHeroes;
    UnlockState.UnlockedDefenses = Candidate.UnlockedDefenses;
    UnlockState.UnlockedAbilities = Candidate.UnlockedAbilities;
    UnlockState.UnlockedMaps = Candidate.UnlockedMaps;
    UnlockState.ActiveMaps = Candidate.ActiveMaps;
    UnlockState.UnlockedHeroSkins = Candidate.UnlockedHeroSkins;
    UnlockState.HeroSkinMode = Candidate.HeroSkinMode;
    UnlockState.ActiveHeroes = Candidate.ActiveHeroes;
    UnlockState.LevelSixHeroes = Candidate.LevelSixHeroes;
    UnlockState.MaxEquipmentQuality = Candidate.MaxEquipmentQuality;
    UnlockState.ExperienceMultiplier = Candidate.ExperienceMultiplier;
    UnlockState.LevelCatchUpMultiplier = Candidate.LevelCatchUpMultiplier;
    UnlockState.DifficultyMask = Candidate.DifficultyMask;
    UnlockState.ModeMask = Candidate.ModeMask;
    UnlockState.StartingCrystalRoll = Candidate.StartingCrystalRoll;
    UnlockState.BuildTimeSeconds = Candidate.BuildTimeSeconds;
    UnlockState.DefenseUnitsBonus = Candidate.DefenseUnitsBonus;
    UnlockState.SurvivalStartWave = Candidate.SurvivalStartWave;
    UnlockState.CrystalSkinMask = Candidate.CrystalSkinMask;
    UnlockState.EterniaShardMask = Candidate.EterniaShardMask;
    UnlockState.bShopsanity = Candidate.bShopsanity;
    UnlockState.bRandomGearPets = Candidate.bRandomGearPets;
    UnlockState.bTavernThemes = Candidate.bTavernThemes;
    UnlockState.TavernThemeMask = Candidate.TavernThemeMask;
    UnlockState.ReceivedXPRewards = Candidate.ReceivedXPRewards;
    UnlockState.ReceivedManaRewards = Candidate.ReceivedManaRewards;
    UnlockState.ReceivedGearRewards = Candidate.ReceivedGearRewards;
    RememberSessionUnlocks();

    ApplyPendingFillerRewards();
    ApplyOwnedMapVisibility();
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
        UpdateGlobalHeroModifiers(PC);
    CorrectLockedActiveHeroes();
    `log("AP:FILE_STATE_APPLIED revision=" $ APFileBridgeRevision);
}

function ApplyAPBuildTime()
{
    local UI_BuildTimer TimerUI;
    local DunDefGameReplicationInfo GRI;
    local int Bonus;
    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none) return;
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none) return;
    TimerUI = UI_BuildTimer(class'DunDefViewportClient'.static.GetViewportClient().GetActiveUISceneFromClass(class'UI_BuildTimer'));
    if(TimerUI == none || GRI.IsInCombatPhase)
    {
        APLastBuildTimer = none;
        APAppliedBuildBonus = 0;
        return;
    }
    if(TimerUI != APLastBuildTimer || GRI.WaveNumber != APLastTimerWave)
    {
        APLastBuildTimer = TimerUI;
        APLastTimerWave = GRI.WaveNumber;
        APAppliedBuildBonus = 0;
    }
    if(!GRI.DoUseBuildTimer() || int(GRI.CurrentGameDifficulty) < 3 || TimerUI.bFinishedBuildPhase ||
        TimerUI.TotalBuildTime <= 0.5 || GRI.ForceMaxBuildTime >= 0) return;
    Bonus = UnlockState.BuildTimeSeconds - APAppliedBuildBonus;
    if(Bonus > 0)
    {
        TimerUI.TotalBuildTime += Bonus;
        APAppliedBuildBonus += Bonus;
        `log("AP:BUILD_TIME_ADDED seconds=" $ Bonus $ " wave=" $ GRI.WaveNumber);
    }
}

function int GetAPExperienceMultiplier()
{
    if(UnlockState == none)
        return 1;

    switch(UnlockState.ExperienceMultiplier)
    {
        case 2:
        case 4:
        case 6:
        case 8:
        case 10:
            return UnlockState.ExperienceMultiplier;
    }
    return 1;
}

function int GetAPLevelCatchUpMultiplier()
{
    if(UnlockState == none)
        return 1;

    switch(UnlockState.LevelCatchUpMultiplier)
    {
        case 2:
        case 4:
        case 6:
        case 8:
        case 10:
            return UnlockState.LevelCatchUpMultiplier;
    }
    return 1;
}

function int GetAPEffectiveHeroLevel(DunDefHero Hero)
{
    local int EffectiveLevel;

    if(Hero == none)
        return 0;
    EffectiveLevel = Clamp(Hero.HeroLevel, 0, Hero.GetLevelCap());
    while(EffectiveLevel < Hero.GetLevelCap() &&
        Hero.HeroExperience >= Hero.GetExpRequiredForNextLevel(EffectiveLevel))
        EffectiveLevel++;
    return EffectiveLevel;
}

function int GetAPHighestOwnedHeroLevel()
{
    local DunDefHeroManager Manager;
    local DataListEntryInterface HeroEntry;
    local DunDefHero Hero;
    local int HighestLevel;

    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none)
        return 0;
    foreach Manager.LocalLoadedHeroes(HeroEntry)
    {
        Hero = DunDefHero(HeroEntry);
        if(Hero != none && IsOwnedHero(Hero))
            HighestLevel = Max(HighestLevel, GetAPEffectiveHeroLevel(Hero));
    }
    return HighestLevel;
}

function int FindAPExperienceTracker(DunDefHero Hero)
{
    local int Index;

    for(Index = 0; Index < APExperienceTrackers.Length; Index++)
    {
        if(APExperienceTrackers[Index].Hero == Hero)
            return Index;
    }
    return INDEX_NONE;
}

function SetAPExperienceBaseline(DunDefHero Hero)
{
    local APHeroExperienceTracker NewTracker;
    local int Index;

    if(Hero == none)
        return;

    Index = FindAPExperienceTracker(Hero);
    if(Index == INDEX_NONE)
    {
        NewTracker.Hero = Hero;
        NewTracker.LastExperience = Hero.HeroExperience;
        APExperienceTrackers.AddItem(NewTracker);
    }
    else
    {
        APExperienceTrackers[Index].LastExperience = Hero.HeroExperience;
    }
}

function ApplyAPExperienceMultiplier()
{
    local DunDefPlayerController PC;
    local DunDefHero Hero;
    local APHeroExperienceTracker NewTracker;
    local int Index;
    local int EarnedExperience;
    local int BonusExperience;
    local int Multiplier;
    local int BaseMultiplier;
    local int CatchUpMultiplier;
    local int HighestLevel;
    local int EffectiveLevel;
    local int CatchUpTargetLevel;
    local int CatchUpMaximumExperience;
    local int CatchUpMaximumBonus;
    local bool bCatchUpActive;

    if(WorldInfo.NetMode != NM_Standalone)
        return;

    if(!IsStableAPWorld())
        return;
    BaseMultiplier = GetAPExperienceMultiplier();
    CatchUpMultiplier = GetAPLevelCatchUpMultiplier();
    HighestLevel = GetAPHighestOwnedHeroLevel();
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(!IsStableLocalController(PC))
            continue;

        Hero = PC.MyHero;
        if(Hero == none || !IsOwnedHero(Hero))
            continue;

        Index = FindAPExperienceTracker(Hero);
        if(Index == INDEX_NONE)
        {
            NewTracker.Hero = Hero;
            NewTracker.LastExperience = Hero.HeroExperience;
            APExperienceTrackers.AddItem(NewTracker);
            continue;
        }

        if(Hero.HeroExperience <= APExperienceTrackers[Index].LastExperience)
        {
            APExperienceTrackers[Index].LastExperience = Hero.HeroExperience;
            continue;
        }

        EarnedExperience = Hero.HeroExperience - APExperienceTrackers[Index].LastExperience;
        Multiplier = BaseMultiplier;
        EffectiveLevel = GetAPEffectiveHeroLevel(Hero);
        CatchUpTargetLevel = Min(HighestLevel, Hero.GetLevelCap());
        bCatchUpActive = CatchUpMultiplier > 1 && CatchUpMultiplier >= BaseMultiplier &&
            EffectiveLevel < CatchUpTargetLevel;
        if(bCatchUpActive)
        {
            Multiplier = CatchUpMultiplier;
            // Total XP at this threshold is exactly the amount needed to reach
            // the highest hero's current level, never the following level.
            CatchUpMaximumExperience = Hero.GetExpRequiredForNextLevel(CatchUpTargetLevel - 1);
        }
        if(Multiplier > 1)
        {
            if(bCatchUpActive)
            {
                CatchUpMaximumBonus = Max(0, CatchUpMaximumExperience - Hero.HeroExperience);
                // Compare before multiplying so an unusually large XP award
                // cannot overflow the 32-bit bonus calculation.
                if(EarnedExperience > CatchUpMaximumBonus / (Multiplier - 1))
                    BonusExperience = CatchUpMaximumBonus;
                else
                    BonusExperience = EarnedExperience * (Multiplier - 1);
            }
            else
                BonusExperience = EarnedExperience * (Multiplier - 1);
            Hero.AddExperience(BonusExperience);
            `log("AP:EXPERIENCE_MULTIPLIED earned=" $ EarnedExperience $
                " bonus=" $ BonusExperience $ " multiplier=" $ Multiplier $
                " catch_up=" $ bCatchUpActive $ " highest_level=" $ HighestLevel $
                " total=" $ Hero.HeroExperience);
            if(DunDefHUD(PC.myHUD) != none)
                DunDefHUD(PC.myHUD).NotifyExperienceChange();
        }
        // Record the post-multiplier total so the added XP is never multiplied
        // again on the next timer tick.
        APExperienceTrackers[Index].LastExperience = Hero.HeroExperience;
    }
}

function bool ApplyLiveUnlockSnapshot(string Snapshot)
{
    local array<string> Fields;
    local array<string> NewHeroes;
    local array<string> NewDefenses;
    local array<string> NewAbilities;
    local array<string> NewMaps;
    local array<string> NewActiveMaps;
    local array<string> NewSkins;
    local array<string> NewActiveHeroes;
    local array<string> NewLevelSixHeroes;
    local int NewRevision;
    local int ReceivedXPRewards;
    local int ReceivedManaRewards;
    local string NewSeedIdentity;
    local DunDefPlayerController PC;

    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none)
        return false;

    ParseStringIntoArray(Snapshot, Fields, "|", false);
    // Reject mismatched mode/mapping BEFORE rewards or revision shortcuts.
    if(UnlockState.bChaosLoadouts)
    {
        if(Fields.Length != 26 || Fields[0] != "APSTATE12" ||
            Fields[25] != UnlockState.ChaosMappingToken || Len(Fields[25]) != 32)
            return false;
    }
    else if(Fields.Length != 25 || Fields[0] != "APSTATE11") return false;
    if(Fields[10] == "-" ||
        Fields[22] == "-" || int(Fields[23]) < 0 || int(Fields[23]) > 2 ||
        (int(Fields[12]) != 1 && int(Fields[12]) != 2 && int(Fields[12]) != 4 &&
            int(Fields[12]) != 6 && int(Fields[12]) != 8 && int(Fields[12]) != 10) ||
        int(Fields[14]) < 1 || int(Fields[14]) > 63 || (int(Fields[14]) & 1) == 0 ||
        int(Fields[15]) < 0 || int(Fields[15]) > 127 ||
        int(Fields[16]) < 0 || int(Fields[16]) >= 1000000000 ||
        int(Fields[17]) < 0 || int(Fields[17]) > 200 ||
        int(Fields[18]) < 0 || int(Fields[18]) > 1000000 ||
        int(Fields[19]) < 0 || int(Fields[19]) > 67108863 ||
        int(Fields[20]) < 0 || int(Fields[20]) > 30 || int(Fields[20]) % 5 != 0 ||
        int(Fields[21]) < -1 || int(Fields[21]) > 25)
    {
        `warn("AP:REJECTED_LIVE_UNLOCK_SNAPSHOT reason=invalid_format");
        return false;
    }

    NewSeedIdentity = Fields[1];
    if(NewSeedIdentity == "" || UnlockState.SeedIdentity == "" ||
        NewSeedIdentity != UnlockState.SeedIdentity)
    {
        `warn("AP:REJECTED_LIVE_UNLOCK_SNAPSHOT reason=wrong_or_missing_seed_restart_required");
        return false;
    }

    // Reward counters are cumulative only within one seed/team/slot identity.
    // A different seed must begin at zero even though this TC config persists.
    if(RewardState != none && RewardState.AppliedSeedIdentity != NewSeedIdentity)
    {
        RewardState.AppliedSeedIdentity = NewSeedIdentity;
        RewardState.AppliedXPRewards = 0;
        RewardState.AppliedManaRewards = 0;
        RewardState.AppliedGearRewards = 0;
        RewardState.BestGearQuality = 0.0;
        RewardState.BestGearExtraRarity = -0.1;
        RewardState.BestGearRandomizerMultiplier = 1.0;
        RewardState.BestGearScaleScore = 0.0;
        RewardState.SaveConfig();
        PendingXPRewardCount = 0;
        PendingManaRewardCount = 0;
        PendingGearRewardCount = 0;
        UnlockState.Revision = -1;
        `log("AP:REWARD_SEED_CHANGED identity=" $ NewSeedIdentity);
    }

    NewRevision = int(Fields[2]);
    ReceivedXPRewards = Max(0, int(Fields[8]));
    ReceivedManaRewards = Max(0, int(Fields[9]));
    PendingXPRewardCount = Max(PendingXPRewardCount, ReceivedXPRewards);
    PendingManaRewardCount = Max(PendingManaRewardCount, ReceivedManaRewards);
    PendingGearRewardCount = Max(PendingGearRewardCount, int(Fields[18]));
    UnlockState.CrystalSkinMask = int(Fields[19]);
    ApplyPendingFillerRewards();

    if(NewRevision <= UnlockState.Revision)
        return true;

    if(Fields[3] != "-")
        ParseStringIntoArray(Fields[3], NewHeroes, ",", true);
    if(Fields[4] != "-")
        ParseStringIntoArray(Fields[4], NewDefenses, ",", true);
    if(Fields[5] != "-")
        ParseStringIntoArray(Fields[5], NewAbilities, ",", true);
    if(Fields[6] != "-")
        ParseStringIntoArray(Fields[6], NewMaps, ",", true);
    ParseStringIntoArray(Fields[22], NewActiveMaps, ",", true);
    if(Fields[24] != "-") ParseStringIntoArray(Fields[24], NewSkins, ",", true);
    ParseStringIntoArray(Fields[10], NewActiveHeroes, ",", true);
    if(Fields[13] != "-")
        ParseStringIntoArray(Fields[13], NewLevelSixHeroes, ",", true);

    UnlockState.Revision = NewRevision;
    APFileBridgeRevision = Max(APFileBridgeRevision, NewRevision);
    UnlockState.UnlockedHeroes = NewHeroes;
    UnlockState.UnlockedDefenses = NewDefenses;
    UnlockState.UnlockedAbilities = NewAbilities;
    UnlockState.UnlockedMaps = NewMaps;
    UnlockState.ActiveMaps = NewActiveMaps;
    UnlockState.UnlockedHeroSkins = NewSkins;
    UnlockState.HeroSkinMode = int(Fields[23]);
    UnlockState.ActiveHeroes = NewActiveHeroes;
    UnlockState.LevelSixHeroes = NewLevelSixHeroes;
    UnlockState.ExperienceMultiplier = int(Fields[11]);
    UnlockState.LevelCatchUpMultiplier = int(Fields[12]);
    UnlockState.MaxEquipmentQuality = int(Fields[7]);
    UnlockState.DifficultyMask = int(Fields[14]);
    UnlockState.ModeMask = int(Fields[15]);
    UnlockState.StartingCrystalRoll = int(Fields[16]);
    UnlockState.BuildTimeSeconds = int(Fields[17]);
    UnlockState.DefenseUnitsBonus = int(Fields[20]);
    UnlockState.SurvivalStartWave = int(Fields[21]);
    UnlockState.ReceivedXPRewards = ReceivedXPRewards;
    UnlockState.ReceivedManaRewards = ReceivedManaRewards;
    UnlockState.ReceivedGearRewards = int(Fields[18]);
    RememberSessionUnlocks();
    ApplyOwnedMapVisibility();

    `log("AP:LIVE_UNLOCK_REFRESH revision=" $ UnlockState.Revision $ " heroes=" $ UnlockState.UnlockedHeroes.Length $
        " defenses=" $ UnlockState.UnlockedDefenses.Length $ " abilities=" $ UnlockState.UnlockedAbilities.Length $
        " maps=" $ UnlockState.UnlockedMaps.Length);

    // Defense and map checks consult UnlockState at use time. Reapply ability
    // modifiers immediately because DD1 caches disabled ability classes.
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        UpdateGlobalHeroModifiers(PC);
    }

    CorrectLockedActiveHeroes();
    return true;
}

function RememberSessionUnlocks()
{
    local APViewportClient Viewport;
    Viewport = APViewportClient(class'DunDefViewportClient'.static.GetViewportClient());
    if(Viewport != none) Viewport.RememberUnlockState(UnlockState);
}

function ApplyPendingGearReward()
{
    local DunDefPlayerController PC;
    local DunDefHeroManager Manager;
    local DunDefHero Hero;
    local HeroEquipment Equipment;
    local DunDefDroppedEquipment Drop;
    local Vector Position, HitLocation, HitNormal;
    local Rotator Facing;

    if(!IsStableAPWorld() || WorldInfo.Pauser != none ||
        RewardState == none || UnlockState == none ||
        RewardState.AppliedSeedIdentity != UnlockState.SeedIdentity ||
        RewardState.AppliedGearRewards >= PendingGearRewardCount)
        return;
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none || Manager.GetPrimaryPlayer() == none) return;
    // Never deliver one copy per split-screen player.
    PC = DunDefPlayerController(Manager.GetPrimaryPlayer().Actor);
    if(!IsStableLocalController(PC) || PC.Pawn == none || PC.Pawn.bDeleteMe ||
        PC.Pawn.Controller != PC || PC.Pawn.Health <= 0)
        return;
    if(DunDefGameReplicationInfo(WorldInfo.GRI).bDoLevelVictory ||
        DunDefGameReplicationInfo(WorldInfo.GRI).bIsGameOver) return;
    Hero = PC.MyHero;
    if(Hero == none || Hero != Manager.GetActiveHero(PC.Player) || !IsOwnedHero(Hero)) return;
    // Backpressure avoids flooding the floor after a long offline session.
    if(class'DunDefDroppedEquipment'.static.GetNumberOfDroppedEquipment() >= 40) return;
    Facing.Yaw = PC.Rotation.Yaw;
    Position = PC.Pawn.Location + Vector(Facing) * 100 + vect(0,0,35);
    if(Trace(HitLocation, HitNormal, Position, PC.Pawn.Location + vect(0,0,35), false) != none)
        Position = PC.Pawn.Location + vect(0,0,35);
    Equipment = class'APGearReward'.static.RollEquipment(Manager, Hero, RewardState, UnlockState.bRandomGearPets);
    if(Equipment == none) return;
    Drop = Manager.ServerCreateDroppedEquipment(Equipment, none, 0, false, false, Facing, 0, true, Position);
    if(Drop == none || Drop.MyEquipmentObject == none) return;
    // Ground rewards are consumed once spawned, not once picked up.
    RewardState.AppliedGearRewards++;
    RewardState.SaveConfig();
    `log("AP:GEAR_DROP count=" $ RewardState.AppliedGearRewards $ " hero_level=" $ Hero.HeroLevel $
        " required_level=" $ Drop.MyEquipmentObject.GetLevelRequirement());
}

function ApplyPendingFillerRewards()
{
    local DunDefPlayerController PC;
    local DunDefHeroManager HeroManager;
    local DunDefHero Hero;
    local int XPAmount;
    local int PreviousThreshold;
    local int TargetThreshold;
    local int AllocatedPoints;
    local int MissingPoints;
    local int EffectiveLevel;
    local int ManaAmount;
    local HighDigitInt BankReward;
    local bool bEarlyHero;
    local bool bStarterChanged;
    local bool bChanged;

    if(!IsStableAPWorld() || RewardState == none)
        return;

    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none || HeroManager.GetPrimaryPlayer() == none)
        return;

    // AP level and mana rewards belong to the primary local player. Controller
    // iteration order is not stable with split screen and previously allowed
    // player four to consume a reward intended for player one.
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(!IsStableLocalController(PC) || PC.Player != HeroManager.GetPrimaryPlayer())
            continue;

        Hero = PC.MyHero;
        if(Hero == none || Hero != HeroManager.GetActiveHero(PC.Player) || !IsOwnedHero(Hero))
            continue;

        bEarlyHero = UnlockState != none &&
            UnlockState.IsHeroUnlocked(UnlockState.GetHeroKey(Hero)) &&
            UnlockState.ContainsValue(UnlockState.LevelSixHeroes, UnlockState.GetHeroKey(Hero));

        // XP unlocks the NORMAL allocation screen. DoLevelUp alone skips
        // UI_HeroInfoNew.AllocatePointsToStats and silently loses stat points.
        if(bEarlyHero && Hero.HeroLevel <= 1 && Hero.HeroExperience == 0)
        {
            Hero.HeroExperience = Hero.GetExpRequiredForNextLevel(5);
            bStarterChanged = true;
            PC.ClientMessage("Archipelago: Level 6 is ready. Open Hero Info to spend your skill points.");
            `log("AP:EARLY_HERO_LEVEL_SIX_XP hero=" $ UnlockState.GetHeroKey(Hero));
        }

        // Migrate the exact missing-point signature of the previous boost:
        // eleven points skipped from level 1, or twelve from level 0.
        // Native free respec preserves XP/equipment/mana and refunds ALL
        // allocations for the player to reassign; never invent extra points.
        if(bEarlyHero && Hero.HeroLevel >= 6 && Hero.bDidRespec == 0)
        {
            AllocatedPoints = Hero.HeroHealthModifier + Hero.HeroSpeedModifier +
                Hero.HeroDamageModifier + Hero.HeroCastingModifier +
                Hero.HeroAbilityOneModifier + Hero.HeroAbilityTwoModifier +
                Hero.HeroDefenseHealthModifier + Hero.HeroDefenseAttackRateModifier +
                Hero.HeroDefenseDamageModifier + Hero.HeroDefenseAreaOfEffectModifier;
            MissingPoints = Hero.GetStatPointsFromLevelUps(Hero.HeroLevel, 0) - AllocatedPoints;
            if(MissingPoints == 11 || MissingPoints == 12)
            {
                Hero.DoRespec(true);
                bStarterChanged = true;
                PC.ClientMessage("Archipelago: Missing starting points repaired. Reassign your refunded points in Hero Info.");
                `log("AP:EARLY_HERO_POINTS_REPAIRED missing=" $ MissingPoints);
            }
        }

        if(bStarterChanged)
        {
            HeroManager.SaveForPlayer(HeroManager.GetPrimaryPlayer());
            if(DunDefHUD(PC.myHUD) != none)
                DunDefHUD(PC.myHUD).NotifyExperienceChange();
        }

        // Do not calculate a reward against the temporarily low
        // level while the player is allocating the starter/refunded points.
        if(bEarlyHero && Hero.HeroLevel < 6 &&
            Hero.HeroExperience >= Hero.GetExpRequiredForNextLevel(5))
        {
            SetAPExperienceBaseline(Hero);
            return;
        }

        while(RewardState.AppliedXPRewards < PendingXPRewardCount)
        {
            // Received counts are level units, including unspent level-ups.
            EffectiveLevel = Hero.HeroLevel;
            while(EffectiveLevel < Hero.GetLevelCap() &&
                Hero.HeroExperience >= Hero.GetExpRequiredForNextLevel(EffectiveLevel))
                EffectiveLevel++;
            XPAmount = 0;
            if(EffectiveLevel < Hero.GetLevelCap())
            {
                PreviousThreshold = EffectiveLevel > 0 ? Hero.GetExpRequiredForNextLevel(EffectiveLevel - 1) : 0;
                TargetThreshold = Hero.GetExpRequiredForNextLevel(EffectiveLevel);
                XPAmount = Max(0, TargetThreshold - PreviousThreshold);
            }
            Hero.AddExperience(XPAmount);
            RewardState.AppliedXPRewards++;
            bChanged = true;
        }

        if(RewardState.AppliedManaRewards < PendingManaRewardCount)
        {
            ManaAmount = Min(8192, PendingManaRewardCount - RewardState.AppliedManaRewards) * 25000;
            // AddBankMana takes a float and can round large integer awards.
            // Use its native wide-integer banking path directly instead.
            SetHighIntValue(BankReward, ManaAmount);
            PC.AddBankedMana(BankReward);
            RewardState.AppliedManaRewards += ManaAmount / 25000;
            bChanged = true;
        }

        if(bChanged)
        {
            RewardState.SaveConfig();
            HeroManager.SaveForPlayer(HeroManager.GetPrimaryPlayer());
            `log("AP:FILLER_REWARDS_APPLIED xp_count=" $ RewardState.AppliedXPRewards $
                " mana_count=" $ RewardState.AppliedManaRewards);
        }
        if(bStarterChanged || bChanged)
            SetAPExperienceBaseline(Hero);
        return;
    }
}

function ApplyOwnedMapVisibility()
{
    local DunDefHeroManager HeroManager;
    local CampaignLevelEntryObject LevelEntry;

    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none)
        return;

    class'APMapMenu'.static.ApplyCDDifficultyGate(UnlockState, WorldInfo);

    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none)
        return;

    foreach HeroManager.CampaignLevelEntryObjects(LevelEntry)
    {
        if(LevelEntry == none)
            continue;

        // The slot controls its campaign roster; challenges remain the original twelve.
        if(!UnlockState.IsRandomizerMap(LevelEntry.MyLevelEntry.EntryIdentifierTag))
        {
            LevelEntry.MyLevelEntry.IsHidden = true;
            `log("AP:HIDDEN_OUT_OF_SCOPE_MAP tag=" $ LevelEntry.MyLevelEntry.EntryIdentifierTag);
            continue;
        }
        LevelEntry.MyLevelEntry.IsHidden = false;
        class'APMapMenu'.static.ApplyEntry(UnlockState, LevelEntry);

        // Preserve DD1's native fresh-save presentation for unowned entries.
        // Only force AP-owned maps visible, and remove ordinary next-map
        // progress so victory cannot bypass AP ownership.
        if(UnlockState.IsMapUnlocked(LevelEntry.MyLevelEntry.EntryIdentifierTag))
        {
            LevelEntry.AlwaysUnlocked = true;
            LevelEntry.MyLevelEntry.AlwaysUnlocked = true;
            LevelEntry.MyLevelEntry.bHiddenIfLocked = false;
            LevelEntry.MyLevelEntry.ForceShowInMissionSetup = false;
            LevelEntry.MyLevelEntry.HiddenUnlessUnlocked.Length = 0;
            `log("AP:REVEALED_OWNED_MAP tag=" $ LevelEntry.MyLevelEntry.EntryIdentifierTag);
        }
        else
        {
            LevelEntry.AlwaysUnlocked = false;
            LevelEntry.MyLevelEntry.AlwaysUnlocked = false;
            // Keep the active campaign rows in mission setup. DD1's
            // disabled-entry renderer supplies the ??? label while the AP map
            // item remains absent.
            LevelEntry.MyLevelEntry.bHiddenIfLocked = false;
            LevelEntry.MyLevelEntry.ForceShowInMissionSetup = false;
            HeroManager.RemoveLocalProgress(LevelEntry.MyLevelEntry.EntryIdentifierTag);
            `log("AP:REMOVED_NATIVE_MAP_PROGRESS tag=" $ LevelEntry.MyLevelEntry.EntryIdentifierTag);
        }
    }
}

function ConfigureHeroOwnership()
{
    if(UnlockState == none)
        return;
    SetTimer(0.25, true, 'CorrectLockedActiveHeroes');
}

function bool IsOwnedHero(DunDefHero Hero)
{
    local string HeroKey;

    if(Hero == none || UnlockState == none || !class'APTavernThemes'.static.IsSeedLicensed(UnlockState))
        return false;

    HeroKey = UnlockState.GetHeroKey(Hero);
    return HeroKey != "" && UnlockState.ContainsValue(UnlockState.ActiveHeroes, HeroKey) &&
        UnlockState.IsHeroUnlocked(HeroKey) &&
        class'APHeroSkins'.static.IsAllowed(UnlockState, Hero, Hero.CurrentCostumeIndex) &&
        class'APHeroEntitlements'.static.IsHeroLicensed(HeroKey);
}

function DunDefHero FindAvailableOwnedHero(LocalPlayer LP)
{
    local DunDefHeroManager HeroManager;
    local DataListEntryInterface HeroEntry;
    local DunDefHero Candidate;
    local int UserID;

    if(LP == none)
        return none;
    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none)
        return none;
    Candidate = HeroManager.GetActiveHero(LP);
    if(IsOwnedHero(Candidate))
        return Candidate;
    UserID = HeroManager.GetUserIDOfPlayer(LP);
    foreach HeroManager.LocalLoadedHeroes(HeroEntry)
    {
        Candidate = DunDefHero(HeroEntry);
        if(Candidate != none && Candidate.UserID == UserID &&
            (Candidate.ActivePlayer == none || Candidate.ActivePlayer == LP) &&
            IsOwnedHero(Candidate))
            return Candidate;
    }
    return none;
}

function bool IsAPHeroGameplayWorld()
{
    local DunDefMapInfo MapInfo;

    if(WorldInfo.NetMode != NM_Standalone)
        return false;
    MapInfo = DunDefMapInfo(WorldInfo.GetMapInfo());
    return MapInfo != none && (MapInfo.IsGameplayLevel || MapInfo.IsLobbyLevel);
}

// Outgoing worlds/controllers remain alive briefly during seamless travel.
// Never mutate saved heroes or deliver rewards through those stale objects.
function bool IsStableAPWorld()
{
    local main Game;
    if(bAPReturningToMenu || !IsAPHeroGameplayWorld() ||
        WorldInfo != class'Engine'.static.GetCurrentWorldInfo() ||
        WorldInfo.IsInSeamlessTravel() || WorldInfo.IsPreparingMapChange() ||
        WorldInfo.NextURL != "" || DunDefMapInfo(WorldInfo.GetMapInfo()).IsLoadingLevel ||
        DunDefGameReplicationInfo(WorldInfo.GRI) == none)
        return false;
    Game = main(WorldInfo.Game);
    return Game != none && !Game.SwappingPlayerControllers;
}

function bool IsStableLocalController(DunDefPlayerController PC)
{
    local LocalPlayer LP;
    local DunDefViewportClient Viewport;
    if(PC == none || PC.bDeleteMe || PC.WorldInfo != WorldInfo ||
        PC.bWaitingForHeroInitialization || PC.bCurrentlySwappingHero)
        return false;
    LP = LocalPlayer(PC.Player);
    Viewport = class'DunDefViewportClient'.static.GetViewportClient();
    return LP != none && LP.Actor == PC && Viewport != none &&
        Viewport.GetIndexOfLocalPlayer(LP) != INDEX_NONE;
}

function bool CanEmitAPGameplayEvents()
{
    local DunDefPlayerController PC;
    local bool bHasPlayableHero;
    local DunDefGameReplicationInfo GRI;
    local string MissionTag;

    if(bAPReturningToMenu || !IsAPHeroGameplayWorld() || UnlockState == none ||
        UnlockState.SeedIdentity == "")
        return false;
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none || !UnlockState.IsDifficultyUnlocked(int(GRI.CurrentGameDifficulty)))
        return false;
    MissionTag = class'DunDefHeroManager'.static.GetHeroManager().GetCurrentCampaignLevelEntry().EntryIdentifierTag;
    if(!UnlockState.IsMapUnlocked(MissionTag) ||
        (GRI.IsInfiniteWaveMode && !GRI.bIsSpecialMission && !UnlockState.IsSurvivalUnlocked(MissionTag)))
        return false;
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(!PC.IsLocalPlayerController())
            continue;
        if(PC.MyHero == none)
            continue;
        if(!IsOwnedHero(PC.MyHero))
            return false;
        bHasPlayableHero = true;
    }
    return bHasPlayableHero;
}

function RejectUnavailableHero(DunDefPlayerController PC, DunDefHero Hero)
{
    local DunDefPlayer InvalidPawn;
    local DunDefGameReplicationInfo GRI;
    local string HeroKey;
    local LocalPlayer LP;
    local DunDefViewportClient Viewport;
    local int PlayerIndex;

    // No title-screen hero creation/preview checks here. Only reject an
    // actual selected hero about to enter, or already inside, playable Local.
    if(!IsStableAPWorld() || !IsStableLocalController(PC) || Hero == none)
        return;

    // A newly added or travelling secondary player can temporarily point at a
    // stale hero while DD1 rebuilds its local-player list. Never punish the
    // primary session for that secondary-player state. Remove only the invalid
    // split player after the spawn/swap call stack has finished; the player can
    // then be re-added and choose an unlocked hero normally.
    LP = LocalPlayer(PC.Player);
    Viewport = class'DunDefViewportClient'.static.GetViewportClient();
    if(LP != none && Viewport != none)
        PlayerIndex = Viewport.GetIndexOfLocalPlayer(LP);
    else
        PlayerIndex = INDEX_NONE;
    if(PlayerIndex == INDEX_NONE || class'DunDefHeroManager'.static.GetHeroManager() == none ||
        class'DunDefHeroManager'.static.GetHeroManager().GetPrimaryPlayer() == none)
        return;
    if(LP != class'DunDefHeroManager'.static.GetHeroManager().GetPrimaryPlayer())
    {
        if(UnlockState != none)
            HeroKey = UnlockState.GetHeroKey(Hero);
        PC.ClientMessage("This split-screen hero is not available in this Archipelago seed. Removing only this player.");
        QueueSplitPlayerRemoval(LP);
        `warn("AP:SPLIT_HERO_REMOVAL player=" $ PlayerIndex $ " hero=" $ HeroKey);
        return;
    }

    bAPReturningToMenu = true;
    APDeniedHeroController = PC;
    if(UnlockState != none)
        HeroKey = UnlockState.GetHeroKey(Hero);
    if(HeroKey != "" && !class'APHeroEntitlements'.static.IsHeroLicensed(HeroKey))
        APDeniedHeroReason = "Archipelago cannot verify DLC ownership for " $
            UnlockState.GetHeroDisplayName(HeroKey) $ ". Returning to the main menu.";
    else
        APDeniedHeroReason = "This hero is not unlocked and active in this Archipelago seed. Returning to the main menu.";
    `warn("AP:HERO_ENTRY_REJECTED hero=" $ HeroKey $ " map=" $ WorldInfo.GetMapName() $
        " revision=" $ UnlockState.Revision $ " reason=" $ APDeniedHeroReason);
    PC.ClientMessage(APDeniedHeroReason);

    // Stop checks and passive pet effects while the menu transition is
    // pending. Attack pets do not consult the WeaponsEnabled override.
    if(EventBridge != none)
    {
        EventBridge.Destroy();
        EventBridge = none;
    }
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI != none)
    {
        GRI.bDisableFamiliarAbilities = true;
        GRI.bDisableWeaponry = true;
    }
    ClearTimer('CorrectLockedActiveHeroes');
    ClearTimer('ApplyAPExperienceMultiplier');
    ClearTimer('DisplayNextAPMessage');

    InvalidPawn = DunDefPlayer(PC.Pawn);
    if(InvalidPawn != none && !IsOwnedHero(InvalidPawn.GetHero()))
    {
        // Destroy the runtime pawn, not its saved hero, equipment or profile.
        // Do not use damage/death, which can invoke normal death/save effects.
        PC.UnPossess();
        InvalidPawn.Destroy();
    }

    // Leave the stock RestartPlayer/hero-swap call stack before travelling.
    // No retry loop: this runs once, with no invalid pawn able to respawn.
    SetTimer(0.01, false, 'ReturnRejectedHeroToMenu');
}

function QueueSplitPlayerRemoval(LocalPlayer LP)
{
    local int Index;

    if(LP == none)
        return;
    for(Index = 0; Index < APPendingSplitPlayerRemoval.Length; Index++)
    {
        if(APPendingSplitPlayerRemoval[Index] == LP)
            return;
    }
    APPendingSplitPlayerRemoval.AddItem(LP);
    SetTimer(0.05, false, 'RemoveRejectedSplitPlayers');
}

function RemoveRejectedSplitPlayers()
{
    local DunDefViewportClient Viewport;
    local DunDefHeroManager Manager;
    local DunDefPlayerController PC;
    local LocalPlayer LP;
    local int Index;

    Viewport = class'DunDefViewportClient'.static.GetViewportClient();
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(!IsStableAPWorld() || Viewport == none || Manager == none)
    {
        APPendingSplitPlayerRemoval.Length = 0;
        return;
    }

    for(Index = APPendingSplitPlayerRemoval.Length - 1; Index >= 0; Index--)
    {
        LP = APPendingSplitPlayerRemoval[Index];
        if(LP == none) continue;
        PC = DunDefPlayerController(LP.Actor);
        if(IsStableLocalController(PC) && LP != Manager.GetPrimaryPlayer() &&
            Viewport.GetIndexOfLocalPlayer(LP) > 0 &&
            Manager.GetActiveHero(LP) != none && !IsOwnedHero(Manager.GetActiveHero(LP)))
            Viewport.RemovePlayer(LP);
    }
    APPendingSplitPlayerRemoval.Length = 0;
}

function ReturnRejectedHeroToMenu()
{
    local DunDefPlayerController PC;

    PC = APDeniedHeroController;
    APDeniedHeroController = none;
    if(PC == none)
        return;
    PC.QuitToMainMenu(true);
}



function CorrectLockedActiveHeroes()
{
    local DunDefHeroManager HeroManager;
    local PlayerController PC;
    local LocalPlayer LP;
    local DunDefHero CurrentHero;
    local DunDefHero Candidate;

    if(!IsStableAPWorld())
        return;
    ApplyPendingFillerRewards();

    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none)
        return;

    foreach WorldInfo.AllControllers(class'PlayerController', PC)
    {
        LP = LocalPlayer(PC.Player);
        if(!IsStableLocalController(DunDefPlayerController(PC)))
            continue;

        CurrentHero = HeroManager.GetActiveHero(LP);
        if(IsOwnedHero(CurrentHero))
            continue;

        Candidate = FindAvailableOwnedHero(LP);

        if(Candidate != none)
        {
            HeroManager.SetActiveHero(Candidate, LP);
            PC.ClientMessage("Archipelago: Switched to an unlocked hero.");
        }
        else if(CurrentHero != none && IsAPHeroGameplayWorld())
        {
            RejectUnavailableHero(DunDefPlayerController(PC), CurrentHero);
            return;
        }
    }
}

event Destroyed()
{
    if(MoonbaseDefenseUnits!=none) MoonbaseDefenseUnits.Restore();
    if(FileSnapshotBridge != none) FileSnapshotBridge.Destroy();
    if(ReverseListener != none)
    {
        ReverseListener.Close();
        ReverseListener.Destroy();
        ReverseListener = none;
    }
    if(ChaosRuntime != none)
    {
        ChaosRuntime.Destroy();
        ChaosRuntime=none;
    }
    if(InboundLink != none)
    {
        InboundLink.Close();
        InboundLink.Destroy();
        InboundLink = none;
    }

    if(EventBridge != none)
    {
        EventBridge.Destroy();
        EventBridge = none;
    }

    super.Destroyed();
}

function UpdateGlobalHeroModifiers(DunDefPlayerController ThePC)
{
    local DunDefPlayerAbility Ability;
    local DunDefPlayerAbility_BuildTower BuildAbility;
    local string AbilityKey;
    local string DefenseKey;
    local string HeroKey;
    local bool HeroUnlocked;


    if(WorldInfo.NetMode != NM_Standalone || ThePC == none || ThePC.MyHero == none || UnlockState == none)
    {
        return;
    }

    HeroKey = UnlockState.GetHeroKey(ThePC.MyHero);
    if(UnlockState.bChaosLoadouts)
    {
        ApplyChaosLoadout(ThePC);
        return;
    }
    HeroUnlocked = IsOwnedHero(ThePC.MyHero);

    // Per-instance GRI checks enforce AP ownership. Shared ability classes
    // must not be disabled globally (stances, curses and beams reuse them).
    foreach ThePC.PlayerAbilities(Ability)
    {
        // AP grants replace level-based unlock announcements only.
        Ability.bWasUnderRequiredLevel = false;
        Ability.ClearTimer('LocalNotifyUnlock');
        AbilityKey = UnlockState.GetAbilityKey(Ability, HeroKey);
        if(AbilityKey != "")
        {
            // In Archipelago, receiving the ability replaces DD1's normal
            // hero-level unlock. Mana, phase, cooldown, and other gameplay
            // restrictions still apply.
            if(HeroUnlocked && UnlockState.IsAbilityUnlocked(AbilityKey))
            {
                Ability.RequiredHeroLevel = 0;
            }
        }

        BuildAbility = DunDefPlayerAbility_BuildTower(Ability);
        if(BuildAbility != none && BuildAbility.TowerArchetype != none)
        {
            DefenseKey = UnlockState.GetDefenseKey(BuildAbility.TowerArchetype, HeroKey);
            if(DefenseKey != "" && HeroUnlocked && UnlockState.IsDefenseUnlocked(DefenseKey))
            {
                // The AP item is the complete permission to build this
                // defense, even when vanilla would require a higher level.
                Ability.RequiredHeroLevel = 0;
            }
        }
    }

}


function bool CanSpawnHero(Controller NewPlayer)
{
    local DunDefPlayerController PC;
    local DunDefHero Hero;
    local DunDefHero Candidate;
    local DunDefHeroManager HeroManager;
    local LocalPlayer LP;
    local APChaosConfig Chaos;
    local string ChaosReason;

    // Direct/manual launch must pass the same whole-roster ownership and
    // mapping checks as the menu, in both public and private builds.
    if(UnlockState != none && UnlockState.bChaosLoadouts)
    {
        Chaos = new(self) class'APChaosConfig';
        if(!Chaos.Validate(UnlockState,ChaosReason))
        {
            if(LastChaosFailure != ChaosReason) `warn("AP:CHAOS_SPAWN_BLOCKED " $ ChaosReason);
            LastChaosFailure=ChaosReason;
            return false;
        }
    }

    if(IsAPHeroGameplayWorld())
    {
        if(bAPReturningToMenu)
            return false;
        PC = DunDefPlayerController(NewPlayer);
        if(PC != none && PC.IsLocalPlayerController())
        {
            // Read the selected hero without initializing or restarting a pawn.
            Hero = PC.MyHero;
            HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
            LP = LocalPlayer(PC.Player);
            if(HeroManager != none && LP != none)
            {
                Candidate = HeroManager.GetActiveHero(LP);
                if(IsOwnedHero(Candidate) && LP.Actor == PC && PC.GetDunDefPRI() != none)
                {
                    PC.PrivateSetHero(Candidate);
                    Hero = Candidate;
                }
            }
            if(Hero != none)
            {
                if(UnlockState == none)
                    UnlockState = new(self) class'APUnlockState';
                if(!IsOwnedHero(Hero))
                {
                    // The correction timer repairs/rejects only stable players.
                    // SetActiveHero here recursively calls RestartPlayer from
                    // inside SpawnDefaultPawnFor and can corrupt split travel.
                    return false;
                }
            }
        }
    }
    return true;
}
static function APGameRuntime GetForWorld(WorldInfo W, optional bool bCreate)
{
    local APGameRuntime Runtime;
    if(W == none || W.NetMode != NM_Standalone)
        return none;
    foreach W.DynamicActors(class'APGameRuntime', Runtime)
        return Runtime;
    if(bCreate)
        return W.Spawn(class'APGameRuntime');
    return none;
}
