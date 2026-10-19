// Each mission tab has its own cached rows, including the Shards campaign.
class APMapMenu extends Object;

var UI_GameSetup Scene;
var APUnlockState Permissions;
var delegate<UIPanel_DataList.EntryEnabledCheck> PreviousEntryCheck;
var bool bHasPreviousEntryCheck;

static function ApplyCDDifficultyGate(APUnlockState State, WorldInfo W)
{
    local DunDefGameReplicationInfo GRI;
    local int Difficulty, Maximum;
    if(State == none || State.SeedIdentity == "" || W == none ||
        !State.ContainsValue(State.ActiveMaps, "CAMPCL")) return;
    GRI = DunDefGameReplicationInfo(W.GRI);
    if(GRI == none) return;
    // CD is a restricted-difficulty mission. Vanilla checks these caps BEFORE
    // AlwaysUnlocked, deriving them from Shards victories (default is -1).
    // AP already decides whether all required shards/maps have been obtained.
    Maximum = -1;
    if(State.IsMapUnlocked("CAMPCL"))
        for(Difficulty = 0; Difficulty < 6; Difficulty++)
            if(State.IsDifficultyUnlocked(Difficulty)) Maximum = Difficulty;
    GRI.MaxRestrictedMissionDifficulty = Maximum;
    GRI.MaxRestrictedMissionDifficultyHardcore = Maximum;
}

static function ApplyEntry(APUnlockState State, CampaignLevelEntryObject Entry)
{
    local bool bOwned;
    if(State == none || State.SeedIdentity == "" || Entry == none) return;
    bOwned = State.IsMapUnlocked(Entry.MyLevelEntry.EntryIdentifierTag);
    Entry.AlwaysUnlocked = bOwned;
    Entry.MyLevelEntry.AlwaysUnlocked = bOwned;
    Entry.MyLevelEntry.ForceShowInMissionSetup = false;
    if(bOwned)
    {
        Entry.MyLevelEntry.IsHidden = false;
        Entry.MyLevelEntry.bHiddenIfLocked = false;
        Entry.MyLevelEntry.HiddenUnlessUnlocked.Length = 0;
    }
}

function bool EntryAllowed(DataListEntryInterface DataEntry)
{
    local CampaignLevelEntryObject Entry;
    Entry = CampaignLevelEntryObject(DataEntry);
    if(Permissions == none || Entry == none ||
        !Permissions.IsMapUnlocked(Entry.MyLevelEntry.EntryIdentifierTag)) return false;
    return !bHasPreviousEntryCheck || PreviousEntryCheck(DataEntry);
}

function Update(APUnlockState State)
{
    local CampaignLevelEntryObject Entry;
    local UIButton_DataListEntry Button;
    local DataListEntryInterface DataEntry;
    local int PlayerIndex;
    local bool bEnabled;
    local string Label;
    if(Scene == none || Scene.MapDataList == none || State == none || State.SeedIdentity == "") return;
    Permissions = State;
    ApplyCDDifficultyGate(State, Scene.GetWorldInfo());
    PlayerIndex = Scene.GetPlayerOwnerIndex();
    if(Scene.MapDataList.EntryEnabledCheck != EntryAllowed)
    {
        // Copying an empty delegate can bind its default stub in UE3. Retain
        // whether a real callback existed before assigning the AP callback.
        bHasPreviousEntryCheck = Scene.MapDataList.EntryEnabledCheck != none;
        if(bHasPreviousEntryCheck) PreviousEntryCheck = Scene.MapDataList.EntryEnabledCheck;
        Scene.MapDataList.EntryEnabledCheck = EntryAllowed;
    }
    // Work on the entries owned by THIS tab, including rows cached before a
    // receipt. Do not rebuild the list each frame and reset selection/focus.
    foreach Scene.MapDataList.dataEntries(DataEntry)
        ApplyEntry(State, CampaignLevelEntryObject(DataEntry));
    foreach Scene.MapDataList.Buttons_DataListEntry(Button)
    {
        if(Button == none) continue;
        Entry = CampaignLevelEntryObject(Button.MyDataListEntry);
        if(Entry == none) continue;
        ApplyEntry(State, Entry);
        bEnabled = EntryAllowed(Entry) && Entry.GetEntryEnabled(Scene.PlayerOwner,
            Scene.MapDataList.DataSetType, Scene);
        if(Button.IsEnabled(PlayerIndex, false) != bEnabled)
            Button.SetEnabled(bEnabled, PlayerIndex);
        if(Button.FocusOnOtherControl != none &&
            Button.FocusOnOtherControl.IsEnabled(PlayerIndex, false) != bEnabled)
            Button.FocusOnOtherControl.SetEnabled(bEnabled, PlayerIndex);
        Label = bEnabled ? Entry.GetDataString(Scene.MapDataList.DataSetType) : "???";
        if(Button.DisplayString != Label) Button.DisplayString = Label;
    }
    Button = Scene.MapDataList.GetSelectedButton();
    bEnabled = Button != none && EntryAllowed(Button.MyDataListEntry) &&
        Button.MyDataListEntry.GetEntryEnabled(Scene.PlayerOwner, Scene.MapDataList.DataSetType, Scene);
    if(Scene.LaunchButton != none && Scene.LaunchButton.IsEnabled(PlayerIndex, false) != bEnabled)
        Scene.LaunchButton.SetEnabled(bEnabled, PlayerIndex);
}
