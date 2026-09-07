class APViewportClient extends APLocalViewportClient;

var APUnlockState MenuUnlockState;
var bool bShowedAPStartingItems;
var float APStartupNoticeDelay;
var bool bInstalledAPInputGuard;
var delegate<HandleInputKey> PreviousInputKeyHandler;

struct APButtonGuard
{
    var UIObject Button;
    var DunDefUIScene Scene;
    var delegate<UIObject.OnClicked> OriginalClick;
};

var array<APButtonGuard> APButtonGuards;

function APUnlockState GetMenuUnlockState()
{
    local APGameInfo APGame;

    if(GetCurrentWorldInfo() != none)
        APGame = APGameInfo(GetCurrentWorldInfo().Game);
    // Use the live snapshot, not the startup object's copy, during play.
    if(APGame != none)
        return APGame.UnlockState;

    // Frontend fallback is the seed configuration loaded at game startup.
    // Switching seeds requires a new game process; do not reuse this for play.
    if(MenuUnlockState == none)
        MenuUnlockState = new(self) class'APUnlockState';
    return MenuUnlockState;
}

function string GetHeroBlockReason(DunDefHero Hero, bool bCreating)
{
    local APUnlockState Permissions;
    local string HeroKey;

    Permissions = GetMenuUnlockState();
    if(Permissions == none)
        return "Archipelago is waiting for this seed's hero permissions.";
    HeroKey = Permissions.GetHeroKey(Hero);
    if(HeroKey == "")
        return "Archipelago cannot identify this hero in the current game build.";
    if(!class'APHeroEntitlements'.static.IsHeroLicensed(HeroKey))
        return "Archipelago cannot verify DLC ownership for " $
            Permissions.GetHeroDisplayName(HeroKey) $ ". This hero is unavailable.";

    // Owned heroes may be created/customized before their AP item arrives.
    // The original creation callbacks still check native hero/costume locks.
    if(bCreating)
        return "";
    if(!Permissions.ContainsValue(Permissions.ActiveHeroes, HeroKey))
        return Permissions.GetHeroDisplayName(HeroKey) $ " is not active in this seed.";
    if(!Permissions.IsHeroUnlocked(HeroKey))
        return Permissions.GetHeroDisplayName(HeroKey) $ " has not been unlocked in Archipelago yet.";
    return "";
}

function DunDefHero GetCreatingHero(UI_CreateHeroBase Scene)
{
    local DunDefHeroManager HeroManager;

    if(Scene == none)
        return none;
    HeroManager = Scene.GetHeroManager();
    if(HeroManager == none || Scene.selectedClass < 0 ||
        Scene.selectedClass >= HeroManager.HeroTemplates.Length)
        return none;
    return HeroManager.HeroTemplates[Scene.selectedClass];
}

function string GetSceneHeroBlockReason(DunDefUIScene Scene)
{
    local UI_HeroSelection Selection;
    local UI_SwapHero Swap;
    local UI_CreateHeroBase Creation;

    Creation = UI_CreateHeroBase(Scene);
    if(Creation != none)
        return GetHeroBlockReason(GetCreatingHero(Creation), true);
    Selection = UI_HeroSelection(Scene);
    if(Selection != none && Selection.HeroDataList != none)
        return GetHeroBlockReason(Selection.HeroDataList.GetSelectedEntry(), false);
    Swap = UI_SwapHero(Scene);
    if(Swap != none && Swap.HeroDataList != none)
        return GetHeroBlockReason(Swap.HeroDataList.GetSelectedEntry(), false);
    return "Archipelago cannot identify the selected hero.";
}

function ShowHeroBlockReason(string Reason, optional LocalPlayer PlayerOwner)
{
    if(Reason == "" || GetActiveUISceneFromClass(class'UI_MessageBox', PlayerOwner) != none)
        return;
    class'DunDefSceneClient'.static.ShowDunDefMessageBox(
        'APHeroUnavailable', "Archipelago Hero Unavailable", Reason, MBT_OK, PlayerOwner);
}

function GuardHeroButton(UIObject Button, DunDefUIScene Scene)
{
    local int Index;
    local APButtonGuard Guard;

    if(Button == none || Scene == none)
        return;
    Index = APButtonGuards.Find('Button', Button);
    if(Index == INDEX_NONE)
    {
        Guard.Button = Button;
        Guard.Scene = Scene;
        APButtonGuards.AddItem(Guard);
        Index = APButtonGuards.Length - 1;
    }
    // Creation changes its callbacks when moving between stages. Preserve
    // the current original handler rather than replacing the stage logic.
    if(Button.OnClicked != APHeroButtonClicked)
    {
        APButtonGuards[Index].OriginalClick = Button.OnClicked;
        Button.OnClicked = APHeroButtonClicked;
    }
}

function bool APHeroButtonClicked(UIScreenObject Sender, int PlayerIndex)
{
    local int Index;
    local string Reason;
    local delegate<UIObject.OnClicked> OriginalClick;

    Index = APButtonGuards.Find('Button', UIObject(Sender));
    if(Index == INDEX_NONE)
        return true;
    Reason = GetSceneHeroBlockReason(APButtonGuards[Index].Scene);
    if(Reason != "")
    {
        ShowHeroBlockReason(Reason, APButtonGuards[Index].Scene.PlayerOwner);
        return true;
    }
    OriginalClick = APButtonGuards[Index].OriginalClick;
    if(OriginalClick != none)
        return OriginalClick(Sender, PlayerIndex);
    return false;
}

function int GetInstantHeroOffset(name Key)
{
    switch(Key)
    {
        case 'One': return 0;
        case 'Two': return 1;
        case 'Three': return 2;
        case 'Four': return 3;
        case 'Five': return 4;
        case 'Six': return 5;
        case 'Seven': return 6;
        case 'Eight': return 7;
    }
    return INDEX_NONE;
}

function bool IsHeroConfirmKey(DunDefUIScene Scene, UIObject Button, name Key)
{
    local int Index;

    if(Button == none)
        return false;
    for(Index = 0; Index < Scene.gamepadKeyBindings.Length; Index++)
    {
        if(Scene.gamepadKeyBindings[Index].Key == Key &&
            Scene.gamepadKeyBindings[Index].WidgetToClick == Button &&
            !Scene.gamepadKeyBindings[Index].bDontHandleInput &&
            !Scene.gamepadKeyBindings[Index].bBindingDisabled)
            return true;
    }
    return (Key == 'Enter' || Key == 'SpaceBar' || Key == 'XboxTypeS_A') &&
        Scene.GetFocusedControl(true) == Button;
}

function bool APHandleInputKey(int ControllerId, name Key, EInputEvent EventType,
    float AmountDepressed, optional bool bGamepad)
{
    local DunDefUIScene Scene;
    local UI_HeroSelection Selection;
    local UI_SwapHero Swap;
    local UI_CreateHeroBase Creation;
    local UIPanel_DataList HeroList;
    local UIButton_DataListEntry Entry;
    local LocalPlayer PlayerOwner;
    local int Offset;
    local string Reason;
    local bool bConfirm;

    if(EventType == IE_Released && theSceneClient != none)
    {
        PlayerOwner = FindPlayerByControllerId(ControllerId);
        Scene = DunDefUIScene(theSceneClient.GetActiveScene(PlayerOwner, true));
        Creation = UI_CreateHeroBase(Scene);
        Selection = UI_HeroSelection(Scene);
        Swap = UI_SwapHero(Scene);
        if(Creation != none)
        {
            // These shortcuts call NextState directly, bypassing OnClicked.
            bConfirm = Key == 'Enter' || Key == 'XboxTypeS_A' || Key == 'XboxTypeS_Start' ||
                (Key == 'SpaceBar' && Creation.GetStateName() == 'SelectClass');
        }
        else if(Selection != none && !Selection.bShowingDeletionConfirmation)
        {
            HeroList = Selection.HeroDataList;
            bConfirm = Key == 'XboxTypeS_Start' ||
                IsHeroConfirmKey(Scene, Selection.ConfirmButton, Key);
        }
        else if(Swap != none)
        {
            // Swap's raw number shortcuts remain active even while its
            // deletion confirmation is visible; keep those guarded too.
            HeroList = Swap.HeroDataList;
            bConfirm = !Swap.bShowingDeletionConfirmation &&
                IsHeroConfirmKey(Scene, Swap.SwapButton, Key);
        }

        Offset = GetInstantHeroOffset(Key);
        if(HeroList != none && Offset != INDEX_NONE && HeroList.dataEntries.Length > 0)
        {
            // The shortcut chooses the entry at this page offset, not the
            // currently highlighted hero. Check the exact same target.
            Entry = HeroList.GetButtonAtIndex(Min(Offset, HeroList.dataEntries.Length - 1));
            if(Entry != none)
                Reason = GetHeroBlockReason(DunDefHero(Entry.MyDataListEntry), false);
        }
        else if(bConfirm)
            Reason = GetSceneHeroBlockReason(Scene);
        if(Reason != "")
        {
            ShowHeroBlockReason(Reason, PlayerOwner);
            return true;
        }
    }

    if(PreviousInputKeyHandler != none)
        return PreviousInputKeyHandler(ControllerId, Key, EventType, AmountDepressed, bGamepad);
    return false;
}

function UpdateHeroMenuGuards()
{
    local array<DunDefUIScene> Scenes;
    local DunDefUIScene Scene;
    local UI_HeroSelection Selection;
    local UI_SwapHero Swap;
    local UI_CreateHero Creation;
    local UI_CreateHeroInGame InGameCreation;
    local DunDefHero Hero;
    local int Index;
    local bool bVanillaAllowed;

    if(theSceneClient == none)
        return;
    for(Index = APButtonGuards.Length - 1; Index >= 0; Index--)
    {
        if(!IsSceneInstanceOpened(APButtonGuards[Index].Scene))
        {
            if(APButtonGuards[Index].Button != none &&
                APButtonGuards[Index].Button.OnClicked == APHeroButtonClicked)
                APButtonGuards[Index].Button.OnClicked = APButtonGuards[Index].OriginalClick;
            APButtonGuards.Remove(Index, 1);
        }
    }

    Scenes = GetActiveUIScenesFromClass(class'DunDefUIScene');
    foreach Scenes(Scene)
    {
        Selection = UI_HeroSelection(Scene);
        Swap = UI_SwapHero(Scene);
        Creation = UI_CreateHero(Scene);
        InGameCreation = UI_CreateHeroInGame(Scene);
        if(Selection != none && Selection.HeroDataList != none && Selection.ConfirmButton != none)
        {
            GuardHeroButton(Selection.ConfirmButton, Scene);
            Hero = Selection.HeroDataList.GetSelectedEntry();
            // These are the original selection/confirmation preconditions.
            // Restore the button on live AP unlock without mutating the hero list.
            bVanillaAllowed = Hero != none &&
                (Hero.ActivePlayer == none || Hero.ActivePlayer == Scene.PlayerOwner);
            Selection.ConfirmButton.SetEnabled(bVanillaAllowed &&
                GetHeroBlockReason(Hero, false) == "", Scene.GetPlayerOwnerIndex());
        }
        else if(Swap != none && Swap.HeroDataList != none && Swap.SwapButton != none)
        {
            GuardHeroButton(Swap.SwapButton, Scene);
            Hero = Swap.HeroDataList.GetSelectedEntry();
            bVanillaAllowed = Hero != none &&
                Hero != Swap.GetHeroManager().GetActiveHero(Scene.PlayerOwner) &&
                (Hero.ActivePlayer == none || Hero.ActivePlayer == Scene.PlayerOwner);
            Swap.SwapButton.SetEnabled(bVanillaAllowed &&
                GetHeroBlockReason(Hero, false) == "", Scene.GetPlayerOwnerIndex());
        }
        else if(Creation != none)
        {
            // Never enable creation/costume buttons ourselves. The callbacks
            // retain vanilla purchase, costume, naming and editing checks.
            GuardHeroButton(Creation.class_OkButton, Scene);
            GuardHeroButton(Creation.color_NextButton, Scene);
            GuardHeroButton(Creation.name_NextButton, Scene);
        }
        else if(InGameCreation != none)
            GuardHeroButton(InGameCreation.class_OkButton, Scene);
    }
}

event Tick(float DeltaTime)
{
    local APUnlockState CurrentState;
    local array<DunDefUIScene> MessageScenes;
    local DunDefUIScene MessageScene;
    local string MessageTag;

    if(!IsAPLocalSession())
        return;
    super.Tick(DeltaTime);
    if(!IsAPLocalSession())
        return;

    if(!bInstalledAPInputGuard)
    {
        PreviousInputKeyHandler = HandleInputKey;
        HandleInputKey = APHandleInputKey;
        bInstalledAPInputGuard = true;
    }
    CurrentState = GetMenuUnlockState();
    UpdateHeroMenuGuards();

    // DD1 can bypass character selection when a seed already has a hero.
    // Show the starting permissions after the initial UI has settled instead
    // of tying the notice to one particular menu scene.
    if(!bShowedAPStartingItems)
    {
        APStartupNoticeDelay += DeltaTime;
        if(APStartupNoticeDelay >= 3.0 && CurrentState != none)
        {
            bShowedAPStartingItems = true;
            class'DunDefSceneClient'.static.ShowDunDefMessageBox(
                'APStartingItems',
                "Archipelago Starting Items",
                "Starting Hero: " $ CurrentState.GetStartingHeroDisplayName() $ "\n" $
                    "Starting Map: " $ CurrentState.GetStartingMapDisplayName(),
                MBT_OK);
        }
    }

    // A fresh DD1 save queues many owned-DLC mission/hero/costume popups.
    // They carry randomized tags with these stable prefixes. Suppress only
    // those notices inside the AP conversion; ordinary warnings remain.
    if(theSceneClient == none)
        return;
    MessageScenes = GetActiveUIScenesFromClass(class'UI_MessageBox');
    foreach MessageScenes(MessageScene)
    {
        MessageTag = string(MessageScene.SceneTag);
        if(Left(MessageTag, 15) == "UnlockedMission" ||
            Left(MessageTag, 15) == "UnlockedCostume" ||
            Left(MessageTag, 12) == "UnlockedHero")
        {
            `log("AP:SUPPRESSED_DLC_UNLOCK_NOTICE tag=" $ MessageTag);
            MessageScene.CloseScene();
        }
    }

}
