class APGameInfo extends main;

var APEventBridge EventBridge;
var APUnlockState UnlockState;
var APInboundLink InboundLink;
var APRewardState RewardState;
var int PendingXPRewardCount;
var int PendingManaRewardCount;
var array<string> APMessageQueue;

struct APHeroExperienceTracker
{
    var DunDefHero Hero;
    var int LastExperience;
};
var array<APHeroExperienceTracker> APExperienceTrackers;

function QueueAPMessage(string Message)
{
    if(WorldInfo.NetMode != NM_Standalone || Message == "")
        return;
    if(APMessageQueue.Length < 100)
        APMessageQueue.AddItem(Left(Message, 240));
    if(!IsTimerActive('DisplayNextAPMessage'))
        DisplayNextAPMessage();
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

static event class<GameInfo> SetGameType(string MapName, string Options, string Portal)
{
    local class<GameInfo> SelectedGameType;

    SelectedGameType = super.SetGameType(MapName, Options, Portal);

    // DD1's main.SetGameType() intentionally falls back to UDKGame.main for
    // ordinary campaign maps, ignoring the standard ?game= URL option. Keep
    // explicit challenge/special-mode selections, but replace that ordinary
    // fallback with the Local-only Archipelago subclass.
    if(SelectedGameType == class'main')
    {
        return class'APGameInfo';
    }

    return SelectedGameType;
}

simulated event PostBeginPlay()
{
    super.PostBeginPlay();

    if(WorldInfo.NetMode == NM_Standalone)
    {
        `log("AP:INITIALIZED map=" $ WorldInfo.GetMapName() $ " mode=LOCAL_STANDALONE");
        UnlockState = new(self) class'APUnlockState';
        RewardState = new(self) class'APRewardState';
        ApplyOwnedMapVisibility();
        ConfigureHeroOwnership();
        SetTimer(0.10, true, 'ApplyAPExperienceMultiplier');
        `log("AP:UNLOCK_STATE revision=" $ UnlockState.Revision $ " slot=" $ UnlockState.Slot $
            " heroes=" $ UnlockState.UnlockedHeroes.Length $ " defenses=" $ UnlockState.UnlockedDefenses.Length $
            " abilities=" $ UnlockState.UnlockedAbilities.Length $ " maps=" $ UnlockState.UnlockedMaps.Length $
            " max_quality=" $ UnlockState.MaxEquipmentQuality $
            " experience_multiplier=" $ GetAPExperienceMultiplier());
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
    }
    else
    {
        // The prototype must never operate in an online/networked session.
        `warn("AP:DISABLED_NON_LOCAL map=" $ WorldInfo.GetMapName());
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

    if(WorldInfo.NetMode != NM_Standalone)
        return;

    Multiplier = GetAPExperienceMultiplier();
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(!PC.IsLocalPlayerController())
            continue;

        Hero = PC.GetHero();
        if(Hero == none)
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
        if(Multiplier > 1)
        {
            BonusExperience = EarnedExperience * (Multiplier - 1);
            Hero.AddExperience(BonusExperience);
            `log("AP:EXPERIENCE_MULTIPLIED earned=" $ EarnedExperience $
                " bonus=" $ BonusExperience $ " multiplier=" $ Multiplier $
                " total=" $ Hero.HeroExperience);
            if(DunDefHUD(PC.myHUD) != none)
                DunDefHUD(PC.myHUD).NotifyExperienceChange();
        }
        // Record the post-multiplier total so the added XP is never multiplied
        // again on the next timer tick.
        APExperienceTrackers[Index].LastExperience = Hero.HeroExperience;
    }
}

function ApplyLiveUnlockSnapshot(string Snapshot)
{
    local array<string> Fields;
    local array<string> NewHeroes;
    local array<string> NewDefenses;
    local array<string> NewAbilities;
    local array<string> NewMaps;
    local int NewRevision;
    local int ReceivedXPRewards;
    local int ReceivedManaRewards;
    local string NewSeedIdentity;
    local DunDefPlayerController PC;

    if(WorldInfo.NetMode != NM_Standalone || UnlockState == none)
        return;

    ParseStringIntoArray(Snapshot, Fields, "|", false);
    if(Fields.Length != 10 || Fields[0] != "APSTATE3")
    {
        `warn("AP:REJECTED_LIVE_UNLOCK_SNAPSHOT reason=invalid_format");
        return;
    }

    NewSeedIdentity = Fields[1];
    if(NewSeedIdentity == "")
    {
        `warn("AP:REJECTED_LIVE_UNLOCK_SNAPSHOT reason=missing_seed_identity");
        return;
    }

    // Reward counters are cumulative only within one seed/team/slot identity.
    // A different seed must begin at zero even though this TC config persists.
    if(RewardState != none && RewardState.AppliedSeedIdentity != NewSeedIdentity)
    {
        RewardState.AppliedSeedIdentity = NewSeedIdentity;
        RewardState.AppliedXPRewards = 0;
        RewardState.AppliedManaRewards = 0;
        RewardState.SaveConfig();
        PendingXPRewardCount = 0;
        PendingManaRewardCount = 0;
        UnlockState.Revision = -1;
        `log("AP:REWARD_SEED_CHANGED identity=" $ NewSeedIdentity);
    }

    NewRevision = int(Fields[2]);
    ReceivedXPRewards = Max(0, int(Fields[8]));
    ReceivedManaRewards = Max(0, int(Fields[9]));
    PendingXPRewardCount = Max(PendingXPRewardCount, ReceivedXPRewards);
    PendingManaRewardCount = Max(PendingManaRewardCount, ReceivedManaRewards);
    ApplyPendingFillerRewards();

    if(NewRevision <= UnlockState.Revision)
        return;

    if(Fields[3] != "-")
        ParseStringIntoArray(Fields[3], NewHeroes, ",", true);
    if(Fields[4] != "-")
        ParseStringIntoArray(Fields[4], NewDefenses, ",", true);
    if(Fields[5] != "-")
        ParseStringIntoArray(Fields[5], NewAbilities, ",", true);
    if(Fields[6] != "-")
        ParseStringIntoArray(Fields[6], NewMaps, ",", true);

    UnlockState.Revision = NewRevision;
    UnlockState.UnlockedHeroes = NewHeroes;
    UnlockState.UnlockedDefenses = NewDefenses;
    UnlockState.UnlockedAbilities = NewAbilities;
    UnlockState.UnlockedMaps = NewMaps;
    UnlockState.MaxEquipmentQuality = int(Fields[7]);
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
}

function ApplyPendingFillerRewards()
{
    local DunDefPlayerController PC;
    local DunDefHero Hero;
    local int XPAmount;
    local int PreviousThreshold;
    local int TargetThreshold;
    local int AllocatedPoints;
    local int MissingPoints;
    local bool bEarlyHero;
    local bool bStarterChanged;
    local bool bChanged;

    if(WorldInfo.NetMode != NM_Standalone || RewardState == none)
        return;

    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
    {
        if(!PC.IsLocalPlayerController())
            continue;

        Hero = PC.GetHero();
        if(Hero == none)
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
            class'DunDefHeroManager'.static.GetHeroManager().SaveForPlayer(LocalPlayer(PC.Player));
            if(DunDefHUD(PC.myHUD) != none)
                DunDefHUD(PC.myHUD).NotifyExperienceChange();
        }

        // Do not calculate a two-level reward against the temporarily low
        // level while the player is allocating the starter/refunded points.
        if(bEarlyHero && Hero.HeroLevel < 6 &&
            Hero.HeroExperience >= Hero.GetExpRequiredForNextLevel(5))
        {
            SetAPExperienceBaseline(Hero);
            return;
        }

        while(RewardState.AppliedXPRewards < PendingXPRewardCount)
        {
            PreviousThreshold = Hero.GetExpRequiredForNextLevel(Max(0, Hero.HeroLevel - 1));
            TargetThreshold = Hero.GetExpRequiredForNextLevel(Min(Hero.GetLevelCap(), Hero.HeroLevel + 1));
            XPAmount = Max(0, TargetThreshold - PreviousThreshold);
            Hero.AddExperience(XPAmount);
            RewardState.AppliedXPRewards++;
            bChanged = true;
            PC.ClientMessage("Archipelago: Two hero levels received (" $ XPAmount $ " XP).");
        }

        while(RewardState.AppliedManaRewards < PendingManaRewardCount)
        {
            PC.AddBankMana(25000, true);
            RewardState.AppliedManaRewards++;
            bChanged = true;
            PC.ClientMessage("Archipelago: 25,000 bank mana received.");
        }

        if(bChanged)
        {
            RewardState.SaveConfig();
            class'DunDefHeroManager'.static.GetHeroManager().SaveForPlayer(LocalPlayer(PC.Player));
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

    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none)
        return;

    foreach HeroManager.CampaignLevelEntryObjects(LevelEntry)
    {
        if(LevelEntry == none)
            continue;

        // This first version contains only the 12 original campaign maps.
        // Remove bonus, DLC, challenge-campaign, and other out-of-scope maps
        // from mission setup while retaining the launch guard as a backstop.
        if(!UnlockState.IsRandomizerMap(LevelEntry.MyLevelEntry.EntryIdentifierTag))
        {
            LevelEntry.MyLevelEntry.IsHidden = true;
            `log("AP:HIDDEN_OUT_OF_SCOPE_MAP tag=" $ LevelEntry.MyLevelEntry.EntryIdentifierTag);
            continue;
        }

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
            // Keep every one of the 12 campaign rows in mission setup. DD1's
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

    if(Hero == none || UnlockState == none)
        return false;

    HeroKey = UnlockState.GetHeroKey(Hero);
    return HeroKey != "" && UnlockState.IsHeroUnlocked(HeroKey);
}

function CorrectLockedActiveHeroes()
{
    local DunDefHeroManager HeroManager;
    local PlayerController PC;
    local LocalPlayer LP;
    local DunDefHero CurrentHero;
    local DunDefHero Candidate;
    local DataListEntryInterface HeroEntry;
    local int UserID;

    ApplyPendingFillerRewards();

    HeroManager = class'DunDefHeroManager'.static.GetHeroManager();
    if(HeroManager == none)
        return;

    foreach WorldInfo.AllControllers(class'PlayerController', PC)
    {
        LP = LocalPlayer(PC.Player);
        if(LP == none)
            continue;

        CurrentHero = HeroManager.GetActiveHero(LP);
        if(IsOwnedHero(CurrentHero))
            continue;

        UserID = HeroManager.GetUserIDOfPlayer(LP);
        Candidate = none;
        foreach HeroManager.LocalLoadedHeroes(HeroEntry)
        {
            if(DunDefHero(HeroEntry) != none && DunDefHero(HeroEntry).UserID == UserID &&
                IsOwnedHero(DunDefHero(HeroEntry)))
            {
                Candidate = DunDefHero(HeroEntry);
                break;
            }
        }

        if(Candidate != none)
        {
            HeroManager.SetActiveHero(Candidate, LP);
            PC.ClientMessage("Archipelago: Switched to an unlocked hero.");
        }
    }
}

event Destroyed()
{
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

    super.UpdateGlobalHeroModifiers(ThePC);

    if(WorldInfo.NetMode != NM_Standalone || ThePC == none || UnlockState == none)
    {
        return;
    }

    HeroKey = UnlockState.GetHeroKey(ThePC.GetHero());
    HeroUnlocked = HeroKey != "" && UnlockState.IsHeroUnlocked(HeroKey);

    // Clear the current hero's mapped classes first so a later revision or a
    // hero swap can grant an ability that was previously disabled. The same
    // base class is reused by some otherwise unrelated hero abilities.
    foreach ThePC.PlayerAbilities(Ability)
    {
        // AP grants replace level-based unlock announcements only.
        Ability.bWasUnderRequiredLevel = false;
        Ability.ClearTimer('LocalNotifyUnlock');
        AbilityKey = UnlockState.GetAbilityKey(Ability);
        if(AbilityKey != "")
        {
            ThePC.RemoveDisabledAbility(Ability.Class);

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
            DefenseKey = UnlockState.GetDefenseKey(BuildAbility.TowerArchetype);
            if(DefenseKey != "" && HeroUnlocked && UnlockState.IsDefenseUnlocked(DefenseKey))
            {
                // The AP item is the complete permission to build this
                // defense, even when vanilla would require a higher level.
                Ability.RequiredHeroLevel = 0;
            }
        }
    }

    foreach ThePC.PlayerAbilities(Ability)
    {
        AbilityKey = UnlockState.GetAbilityKey(Ability);
        if(AbilityKey != "" && (!HeroUnlocked || !UnlockState.IsAbilityUnlocked(AbilityKey)))
        {
            ThePC.AddDisabledAbility(Ability.Class);
        }
    }

}

defaultproperties
{
    GameReplicationInfoClass=class'APGameReplicationInfo'
}
