class APSeedPresentation extends Object config(DD1ArchipelagoPresentation);

var config array<string> NoticeSeeds;
var config array<string> CrystalProfiles;

function bool ShouldShowNotice(APUnlockState State)
{
    if(State == none || State.SeedIdentity == "") return false;
    if(NoticeSeeds.Find(State.SeedIdentity) != INDEX_NONE) return false;
    NoticeSeeds.AddItem(State.SeedIdentity);
    SaveConfig();
    return State.UnlockedHeroes.Length <= 1;
}

function ApplyStartingCrystal(APUnlockState State)
{
    local DunDefHeroManager Manager;
    local LocalPlayer Player;
    local CoreUnlockInfo Unlocks;
    local CrystalCoreOptions Options;
    local array<int> Candidates;
    local int I, J, UserID, Chosen, Allowed;
    local string ProfileKey;
    local bool bBaseCrystal, bChanged, bNewProfile;

    if(State == none || State.SeedIdentity == "") return;
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none) return;
    Player = Manager.GetPrimaryPlayer();
    if(Player == none) return;
    UserID = Manager.GetUserIDOfPlayer(Player);
    // A new save has no CoreUnlockEntries yet. GetCoreUnlockInfo and
    // GetCrystalCoreSettings safely provide the default records in that case.

    // Base-game achievement rewards only; no Shards, DLC or later challenge cores.
    // Core zero is the ordinary crystal. Other candidates must have requirements
    // entirely within the original achievement range.
    for(I = 0; I < Manager.CrystalCores.Length; I++)
    {
        bBaseCrystal = I == 0 || Manager.CrystalCores[I].neededAchievements.Length > 0;
        for(J = 0; J < Manager.CrystalCores[I].neededAchievements.Length; J++)
            if(Manager.CrystalCores[I].neededAchievements[J] > EA_ALL_ACCOMPLISHMENTS)
                bBaseCrystal = false;
        if(bBaseCrystal) Candidates.AddItem(I);
    }
    if(Candidates.Length == 0) return;
    Chosen = Candidates[State.StartingCrystalRoll % Candidates.Length];

    // Prevent the normal unconditional default crystal from becoming a second
    // starting skin. This only changes the AP session's in-memory template.
    if(Chosen != 0 && Manager.CrystalCores[0].neededAchievements.Length == 0)
        Manager.CrystalCores[0].neededAchievements.AddItem(EA_ALL_ACCOMPLISHMENTS);

    ProfileKey = State.SeedIdentity $ "|" $ UserID;
    bNewProfile = CrystalProfiles.Find(ProfileKey) == INDEX_NONE;
    Unlocks = Manager.GetCoreUnlockInfo(UserID);
    if(Chosen >= ArrayCount(Unlocks.CoreUnlocks)) return;
    for(I = 0; I < ArrayCount(Unlocks.CoreUnlocks); I++)
    {
        Allowed = 0;
        if(I == Chosen || (I < 26 && Candidates.Find(I) != INDEX_NONE && (State.CrystalSkinMask & (1 << I)) != 0))
            Allowed = 1;
        if(Unlocks.CoreUnlocks[I] != Allowed) bChanged = true;
        Unlocks.CoreUnlocks[I] = Allowed;
    }
    Options = Manager.GetCrystalCoreSettings(UserID);
    if(bNewProfile || Options.coreIndex < 0 || Options.coreIndex >= ArrayCount(Unlocks.CoreUnlocks) ||
        Unlocks.CoreUnlocks[Options.coreIndex] == 0)
    {
        Options.coreIndex = Chosen;
        bChanged = true;
    }
    if(!bChanged) return;
    Manager.AddCoreUnlockInfo(Unlocks, UserID);
    Manager.AddCrystalCoreSettings(Options, UserID);
    Manager.SaveForPlayer(Player);
    if(bNewProfile)
    {
        CrystalProfiles.AddItem(ProfileKey);
        SaveConfig();
    }
    `log("AP:STARTING_CRYSTAL index=" $ Chosen $ " name=" $ Manager.CrystalCores[Chosen].coreName);
}
