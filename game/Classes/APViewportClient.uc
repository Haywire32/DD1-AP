class APViewportClient extends APLocalViewportClient;

var APUnlockState MenuUnlockState;
var APSeedPresentation SeedPresentation;
var APDisplayRepair DisplayRepair;
var APChaosStats ChaosStats;
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
var APShopState ShopState;
var APShopPresentation ShopPresentation;
var APShopTooltipGuard ShopTooltipGuard;
var array<APShopView> ShopViews;
var array<APSurvivalSelection> SurvivalViews;
var array<APMapMenu> MapViews;
var APHeroRosterPresentation HeroRosterPresentation;
var float APSkinRefreshDelay;
var WorldInfo APCostumeWorld;
var float APNextNativeAwardScan;

static function float GetSafeAPGamma(float Value)
{
    // Early private builds inherited a zero viewport gamma. DD1 copies that
    // into new profiles and reapplies it after loading, ignoring DisplayGamma
    // in Engine.ini. Repair only that invalid value, not valid user settings.
    if(!(Value > 0.0)) return 2.2;
    return Value;
}

function SetGamma(float Value)
{
    super.SetGamma(GetSafeAPGamma(Value));
}

function APMapMenu GetMapView(UI_GameSetup Scene)
{
    local int I;
    local APMapMenu View;
    for(I = MapViews.Length - 1; I >= 0; I--)
    {
        if(!IsSceneInstanceOpened(MapViews[I].Scene)) MapViews.Remove(I, 1);
        else if(MapViews[I].Scene == Scene) return MapViews[I];
    }
    View = new(self) class'APMapMenu';
    View.Scene = Scene;
    MapViews.AddItem(View);
    return View;
}

function APSurvivalSelection GetSurvivalView(UI_GameSetup Scene)
{
    local int I;
    local APSurvivalSelection View;
    for(I = SurvivalViews.Length - 1; I >= 0; I--)
    {
        if(!IsSceneInstanceOpened(SurvivalViews[I].Scene)) SurvivalViews.Remove(I, 1);
        else if(SurvivalViews[I].Scene == Scene) return SurvivalViews[I];
    }
    View = new(self) class'APSurvivalSelection';
    View.Scene = Scene;
    SurvivalViews.AddItem(View);
    return View;
}

function APShopView GetShopView(UI_Shop Scene)
{
    local int I;
    local APShopView View;
    for(I = ShopViews.Length - 1; I >= 0; I--)
    {
        if(!IsSceneInstanceOpened(ShopViews[I].Scene))
        {
            ShopViews[I].RestoreIcons();
            ShopViews.Remove(I, 1);
        }
        else if(ShopViews[I].Scene == Scene) return ShopViews[I];
    }
    View = new(self) class'APShopView';
    View.Scene = Scene;
    for(I = 0; I < 3 && I < Scene.EquipmentItemButtons.Length; I++)
        View.CategoryNames[I] = Scene.EquipmentItemButtons[I].DisplayString;
    ShopViews.AddItem(View);
    return View;
}

function bool APShopSwitchClicked(UIScreenObject Sender, int PlayerIndex)
{
    local UI_Shop Scene;
    local APShopView View;
    local int I;
    Scene = UI_Shop(UIObject(Sender).GetScene());
    if(Scene == none || Scene.bShowingDeletionConfirmation) return true;
    View = GetShopView(Scene);
    if(Scene.ServicesPanel.IsVisible())
    {
        Scene.NotifyWidgetClicked(Scene.ItemShopButton);
        return true;
    }
    View.bArchipelago = !View.bArchipelago;
    Scene.LastSelectedEntry = none;
    if(Scene.myEquipmentInfoScene != none)
    {
        Scene.myEquipmentInfoScene.CloseScene();
        Scene.myEquipmentInfoScene = none;
    }
    if(!View.bArchipelago)
    {
        View.UpdateCategories(false);
        View.RestoreIcons();
        for(I = 0; I < 3 && I < Scene.EquipmentItemButtons.Length; I++)
            Scene.EquipmentItemButtons[I].DisplayString = View.CategoryNames[I];
        Scene.RefreshEquipmentList();
    }
    UpdateAPShop();
    return true;
}

event PostRender(Canvas C)
{
    local array<DunDefUIScene> Scenes;
    local DunDefUIScene ActiveScene;
    local UI_Shop Scene;
    local UI_HeroSelection Selection;
    local UI_SwapHero Swap;
    local UIPanel_DataList HeroList;
    if(HeroRosterPresentation == none) HeroRosterPresentation = new(self) class'APHeroRosterPresentation';
    Scenes = GetActiveUIScenesFromClass(class'DunDefUIScene');
    foreach Scenes(ActiveScene)
    {
        if(!ActiveScene.IsTopLevelScene()) continue;
        Selection = UI_HeroSelection(ActiveScene);
        Swap = UI_SwapHero(ActiveScene);
        HeroList = none;
        if(Selection != none && !Selection.bShowingDeletionConfirmation) HeroList = Selection.HeroDataList;
        if(Swap != none && !Swap.bShowingDeletionConfirmation) HeroList = Swap.HeroDataList;
        if(HeroList != none) HeroRosterPresentation.DrawRoster(C, HeroList, GetMenuUnlockState());
    }
    // Draw the AP shop additions before DD1's normal viewport pass.  The shop
    // is already on screen here, while the stock sword cursor is drawn later
    // by the parent, so the cursor remains visible over the AP logo.
    if(ShopState != none && ShopState.bEnabled)
    {
        if(ShopPresentation == none) ShopPresentation = new(self) class'APShopPresentation';
        Scenes = GetActiveUIScenesFromClass(class'UI_Shop');
        foreach Scenes(ActiveScene)
        {
            Scene = UI_Shop(ActiveScene);
            if(Scene != none && Scene.IsTopLevelScene() && GetShopView(Scene).bArchipelago)
                ShopPresentation.Draw(C, Scene, ShopState);
        }
    }
    super.PostRender(C);
}

function APShopState GetShopState()
{
    local APUnlockState Permissions;
    if(ShopState == none) ShopState = new(self) class'APShopState';
    Permissions = GetMenuUnlockState();
    if(Permissions != none) ShopState.bEnabled = Permissions.bShopsanity;
    return ShopState;
}

function bool APShopButtonClicked(UIScreenObject Sender, int PlayerIndex)
{
    local UI_Shop Scene;
    local APShopEquipment Token;
    local HeroEquipment Equipment;
    Scene = UI_Shop(UIObject(Sender).GetScene());
    if(Scene == none || !GetShopState().bEnabled) return true;
    if(!GetShopView(Scene).bArchipelago)
        return Scene.NotifyWidgetClicked(UIObject(Sender));
    if(Sender == Scene.ConfirmDeletionButton)
    {
        Token = APShopEquipment(Scene.ConfirmBuyEquipmentItem);
        GetShopState().Purchase(Token, DunDefPlayerController(Scene.PlayerOwner.Actor));
        Scene.NotifyWidgetClicked(Scene.CancelDeletionButton);
        GetShopState().RefreshInventory();
        Scene.EquipmentDataList.InitFromDataListProvider(ShopState, GetShopView(Scene).SelectedCategory(),,,,,false,,,true);
        return true;
    }
    if(Sender == Scene.BuyItemButton)
    {
        Equipment = Scene.EquipmentDataList.GetSelectedEntry();
        Token = APShopEquipment(Equipment);
        if(Token != none && GetShopState().Available(Token.PurchaseIndex))
            Scene.ShowDeletionConfirmation(Token);
        return true;
    }
    // AP purchases are not ordinary equipment: no locking or equipment popup.
    return true;
}

function bool APShopPlatinumClicked(UIScreenObject Sender, int PlayerIndex)
{
    local UI_Shop Scene;
    Scene=UI_Shop(UIObject(Sender).GetScene());
    if(Scene == none || Scene.bShowingDeletionConfirmation || !GetShopState().bPlatinum || !GetShopView(Scene).bArchipelago) return true;
    GetShopView(Scene).SelectPlatinum();
    UpdateAPShop();
    return true;
}

function UpdateAPShop()
{
    local array<DunDefUIScene> Scenes;
    local DunDefUIScene ActiveScene;
    local UI_Shop Scene;
    local APShopEquipment Token;
    local HeroEquipment Equipment;
    local UIScriptWidget_EquipmentIconButton Button;
    local bool Changed;
    local int Index;
    local HUDPrefabContainer Overlay;
    local DunDefPlayerController ShopPC;
    local APShopView View;
    if(ShopTooltipGuard==none) ShopTooltipGuard=new(self) class'APShopTooltipGuard';
    ShopTooltipGuard.RestoreReusedOverlays();
    if(!GetShopState().bEnabled) return;
    Changed = ShopState.RefreshInventory();
    ShopState.RepairJournal(class'APGameRuntime'.static.GetForWorld(GetCurrentWorldInfo()));
    Scenes = GetActiveUIScenesFromClass(class'UI_Shop');
    foreach Scenes(ActiveScene)
    {
        Scene = UI_Shop(ActiveScene);
        if(Scene.EquipmentDataList == none) continue;
        View = GetShopView(Scene);
        View.CreateSwitch();
        View.UpdateCategories(ShopState.bPlatinum);
        if(View.PlatinumButton != none) View.PlatinumButton.OnClicked=APShopPlatinumClicked;
        if(View.SwitchButton != none)
        {
            View.SwitchButton.OnClicked = APShopSwitchClicked;
            View.SwitchButton.DisplayString = View.bArchipelago ? "Normal Shop" : "Archipelago Shop";
            View.SwitchButton.SetVisibility(!Scene.bShowingDeletionConfirmation);
            SetAPButtonEnabled(View.SwitchButton, !Scene.bShowingDeletionConfirmation, Scene.GetPlayerOwnerIndex());
        }
        Scene.BuyItemButton.OnClicked = APShopButtonClicked;
        Scene.ConfirmDeletionButton.OnClicked = APShopButtonClicked;
        Scene.LockButton.OnClicked = APShopButtonClicked;
        Scene.ItemInfoButton.OnClicked = APShopButtonClicked;
        if(!View.bArchipelago) continue;
        View.RememberIcons();
        if(Scene.EquipmentItemButtons.Length >= 3)
        {
            Scene.EquipmentItemButtons[0].DisplayString = "Bronze";
            Scene.EquipmentItemButtons[1].DisplayString = "Silver";
            Scene.EquipmentItemButtons[2].DisplayString = "Gold";
        }
        // An unselected list is normal; rebuilding it every tick steals tab clicks.
        if(Changed || Scene.EquipmentDataList.theDataListProvider != ShopState
            || Scene.EquipmentDataList.DataSetType != View.SelectedCategory())
            Scene.EquipmentDataList.InitFromDataListProvider(ShopState, View.SelectedCategory(),,,,,false,,,true);
        Scene.BuyItemButton.OnClicked = APShopButtonClicked;
        Scene.ConfirmDeletionButton.OnClicked = APShopButtonClicked;
        Scene.LockButton.OnClicked = APShopButtonClicked;
        Scene.ItemInfoButton.OnClicked = APShopButtonClicked;
        SetAPButtonEnabled(Scene.LockButton, false, Scene.GetPlayerOwnerIndex());
        SetAPButtonEnabled(Scene.ItemInfoButton, false, Scene.GetPlayerOwnerIndex());
        Equipment = Scene.EquipmentDataList.GetSelectedEntry();
        Token = APShopEquipment(Equipment);
        SetAPButtonEnabled(Scene.BuyItemButton, Token != none && ShopState.Available(Token.PurchaseIndex)
            && DunDefPlayerController(Scene.PlayerOwner.Actor).GetBankedManaItemBox() >= Token.GetShopWorth(), Scene.GetPlayerOwnerIndex());
        if(Token == none) Token = ShopState.Tokens[Clamp(View.SelectedCategory(), 0, ShopState.CategoryCount()-1) * 3];
        if(Scene.BankDescriptionLabel != none) Scene.BankDescriptionLabel.SetValue("Banked Mana");
        ShopPC = DunDefPlayerController(Scene.PlayerOwner.Actor);
        if(ShopPC != none && ShopPC.HUDScene != none)
            foreach ShopPC.HUDScene.containers(Overlay)
                if(Overlay != none && APShopEquipment(Overlay.associatedObject) != none)
                    ShopTooltipGuard.HideTokenOverlay(Overlay);
        for(Index = 0; Index < Scene.EquipmentDataList.Buttons_DataListEntry.Length; Index++)
        {
            Button = UIScriptWidget_EquipmentIconButton(Scene.EquipmentDataList.Buttons_DataListEntry[Index]);
            if(Button == none) continue;
            Button.bAllowDragging = false;
            Button.bDrawTextName = true;
            Button.bIsQualityOutlineEnabled = false;
            Button.bUseTooltip = false;
            Button.bWrapText = true;
            if(Button.MyDataContainer != none) Button.MyDataContainer.bCompareStats = false;
            Button.ComparisonToolTipFocusTime = 999999;
            Button.LockedOverlay = none;
        }
    }
}

function RememberUnlockState(APUnlockState Source)
{
    if(Source == none || Source.SeedIdentity == "") return;
    if(MenuUnlockState == none)
        MenuUnlockState = new(self) class'APUnlockState';
    if(MenuUnlockState.SeedIdentity != Source.SeedIdentity ||
        Source.Revision < MenuUnlockState.Revision) return;
    MenuUnlockState.CopyFrom(Source);
}

function APUnlockState GetTravelUnlockState()
{
    local APUnlockState Fresh;
    // Pin this process to its original seed before refreshing the config cache.
    if(MenuUnlockState == none)
        MenuUnlockState = new(self) class'APUnlockState';
    ConsoleCommand("ReloadCfg DD1Archipelago.APUnlockState");
    Fresh = new(self) class'APUnlockState';
    if(Fresh.SeedIdentity == MenuUnlockState.SeedIdentity &&
        Fresh.Revision > MenuUnlockState.Revision)
        MenuUnlockState.CopyFrom(Fresh);
    return MenuUnlockState;
}

function APUnlockState GetMenuUnlockState()
{
    local APGameRuntime APGame;

    if(GetCurrentWorldInfo() != none)
        APGame = class'APGameRuntime'.static.GetForWorld(GetCurrentWorldInfo());
    // Use the live snapshot, not the startup object's copy, during play.
    if(APGame != none && APGame.UnlockState != none)
        return APGame.UnlockState;

    // The session snapshot survives travel and returning to hero selection.
    // Switching seeds still requires a new process.
    if(MenuUnlockState == none)
        MenuUnlockState = new(self) class'APUnlockState';
    return MenuUnlockState;
}

function string GetHeroBlockReason(DunDefHero Hero, bool bCreating)
{
    local APUnlockState Permissions;
    local string HeroKey;
    local APChaosConfig Chaos;
    local string ChaosReason;

    Permissions = GetMenuUnlockState();
    if(Permissions == none)
        return "Archipelago is waiting for this seed's hero permissions.";
    HeroKey = bCreating ? Permissions.GetTemplateHeroKey(Hero) : Permissions.GetHeroKey(Hero);
    if(HeroKey == "")
        return "Archipelago cannot identify this hero in the current game build.";
    if(!class'APHeroEntitlements'.static.IsHeroLicensed(HeroKey))
        return "Archipelago cannot verify DLC ownership for " $
            Permissions.GetHeroDisplayName(HeroKey) $ ". This hero is unavailable.";

    // Owned heroes may be created/customized before their AP item arrives.
    // The original creation callbacks still check native hero/costume locks.
    if(bCreating)
        return "";
    if(!class'APTavernThemes'.static.IsSeedLicensed(Permissions))
        return "This seed enables tavern themes and requires ownership of all four Lost Eternia Shards DLC parts.";
    if(Permissions.bChaosLoadouts)
    {
        Chaos = new(self) class'APChaosConfig';
        if(!Chaos.Validate(Permissions,ChaosReason)) return ChaosReason;
    }
    if(!Permissions.ContainsValue(Permissions.ActiveHeroes, HeroKey))
        return Permissions.GetHeroDisplayName(HeroKey) $ " is not active in this seed.";
    if(!Permissions.IsHeroUnlocked(HeroKey))
        return Permissions.GetHeroDisplayName(HeroKey) $ " has not been unlocked in Archipelago yet.";
    if(!class'APHeroSkins'.static.IsAllowed(Permissions, Hero, Hero.CurrentCostumeIndex))
        return "This hero skin is locked. Choose an unlocked skin or the default appearance.";
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
    {
        if(!class'APHeroSkins'.static.IsAllowed(GetMenuUnlockState(), GetCreatingHero(Creation), Creation.CurrentCostumeIndex, true))
            return "This hero skin requires its Archipelago unlock and any associated DLC.";
        return GetHeroBlockReason(GetCreatingHero(Creation), true);
    }
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
    // These two buttons normally dispatch to the owning scene. Call that
    // scene directly after authorization so a copied widget delegate cannot
    // retain a template or a previous scene instance as its target.
    if(UI_HeroSelection(APButtonGuards[Index].Scene) != none ||
        UI_SwapHero(APButtonGuards[Index].Scene) != none)
        return APButtonGuards[Index].Scene.NotifyWidgetClicked(UIObject(Sender));
    OriginalClick = APButtonGuards[Index].OriginalClick;
    if(OriginalClick != none)
        return OriginalClick(Sender, PlayerIndex);
    // A default widget delegate may have no stored target. Keep DD1's normal
    // widget-to-scene dispatch in that case instead of dropping the click.
    if(UIScriptWidget_Button(Sender) != none)
        return UIScriptWidget_Button(Sender).ButtonClicked(Sender, PlayerIndex);
    return false;
}

function SetAPButtonEnabled(UIObject Button, bool bEnabled, int PlayerIndex)
{
    // SetEnabled changes the UI state stack. Reapplying it while a mouse
    // button is held can discard the pressed state before the release click.
    // Compare this widget only; a modal parent must not trigger repeated resets.
    if(Button != none && Button.IsEnabled(PlayerIndex, false) != bEnabled)
        Button.SetEnabled(bEnabled, PlayerIndex);
}

function UpdateMapMenuNavigation(UI_GameSetup Scene)
{
    local int PlayerIndex;
    local int DifficultyIndex;
    local APGameRuntime APGame;
    local CampaignLevelEntryObject SelectedEntry;
    local bool bSurvivalAllowed;
    if(Scene == none || Scene.MapDataList == none)
        return;
    PlayerIndex = Scene.GetPlayerOwnerIndex();
    // Stock DD1 updates tabs from the selected map. An empty category has no
    // selection, leaving Campaign disabled from the previous category.
    SetAPButtonEnabled(Scene.CampaignMissions, Scene.showingSpecialMissions ||
        Scene.showingDLCCampaign || Scene.showingModMissions ||
        Scene.showingLostMissions, PlayerIndex);
    SetAPButtonEnabled(Scene.SpecialMissions, !Scene.showingSpecialMissions ||
        Scene.showingLostMissions, PlayerIndex);
    SetAPButtonEnabled(Scene.DLCCampaignMissions, !Scene.showingDLCCampaign, PlayerIndex);
    SetAPButtonEnabled(Scene.ModMissions, !Scene.showingModMissions, PlayerIndex);
    SetAPButtonEnabled(Scene.LostQuestsButton, !Scene.showingLostMissions, PlayerIndex);
    // Leave Go to DD1. Its launch handler already requires a selected map;
    // disabling it for an empty tab persists because selection never re-enables it.
    APGame = class'APGameRuntime'.static.GetForWorld(Scene.GetWorldInfo());
    if(APGame == none || APGame.UnlockState == none)
        return;
    GetMapView(Scene).Update(APGame.UnlockState);
    for(DifficultyIndex = 0; DifficultyIndex < Scene.DifficultyButtons.Length; DifficultyIndex++)
    {
        if(Scene.DifficultyButtons[DifficultyIndex] != none)
            SetAPButtonEnabled(Scene.DifficultyButtons[DifficultyIndex],
                APGame.UnlockState.IsDifficultyUnlocked(Scene.DifficultyButtons[DifficultyIndex].CustomDataTwo), PlayerIndex);
    }
    // Fresh profiles default to Medium. Disabling its button does not change
    // the selection; use DD1's setter to synchronize the menu and game settings.
    if(APGame.UnlockState.IsDifficultyUnlocked(0) &&
        !APGame.UnlockState.IsDifficultyUnlocked(int(Scene.CurrentDifficulty)))
        Scene.SetDifficulty(EGD_EASY);
    if(Scene.MapDataList.GetSelectedButton() == none)
        return;
    SelectedEntry = CampaignLevelEntryObject(Scene.MapDataList.GetSelectedButton().MyDataListEntry);
    if(SelectedEntry == none)
        return;
    bSurvivalAllowed = Left(SelectedEntry.MyLevelEntry.EntryIdentifierTag, 4) != "SPEC" &&
        SelectedEntry.MyLevelEntry.EntryIdentifierTag != "CAMPCL" &&
        APGame.UnlockState.IsMapUnlocked(SelectedEntry.MyLevelEntry.EntryIdentifierTag);
    if(Scene.SurvivalCheckBox != none)
    {
        Scene.SurvivalCheckBox.SetVisibility(bSurvivalAllowed);
        SetAPButtonEnabled(Scene.SurvivalCheckBox, bSurvivalAllowed &&
            APGame.UnlockState.IsSurvivalUnlocked(SelectedEntry.MyLevelEntry.EntryIdentifierTag), PlayerIndex);
    }
    if(Scene.SurvivalModePanel != none)
        Scene.SurvivalModePanel.SetVisibility(bSurvivalAllowed);
    SetAPButtonEnabled(Scene.InfiniteWaveCheckbox, bSurvivalAllowed &&
        APGame.UnlockState.IsSurvivalUnlocked(SelectedEntry.MyLevelEntry.EntryIdentifierTag), PlayerIndex);
    if(Scene.PureStrategyCheckbox != none)
        Scene.PureStrategyCheckbox.SetVisibility(false);
    if(APGame.UnlockState.SurvivalStartWave >= 1)
        GetSurvivalView(Scene).Update(APGame.UnlockState, bSurvivalAllowed &&
            APGame.UnlockState.IsSurvivalUnlocked(SelectedEntry.MyLevelEntry.EntryIdentifierTag) &&
            Scene.InfiniteWaveCheckbox.IsChecked());
    else
    {
        // Native SetDifficulty/SelectedLevel hides these until that specific
        // campaign difficulty is beaten. AP already owns the map/mode gate:
        // restore the controls on Insane+ too, without inventing wave records.
        bSurvivalAllowed = bSurvivalAllowed &&
            APGame.UnlockState.IsSurvivalUnlocked(SelectedEntry.MyLevelEntry.EntryIdentifierTag) &&
            Scene.InfiniteWaveCheckbox.IsChecked();
        if(Scene.StartAtWaveLabel != none)
            Scene.StartAtWaveLabel.SetVisibility(bSurvivalAllowed);
        if(Scene.StartAtWaveIncreaseButton != none)
        {
            Scene.StartAtWaveIncreaseButton.SetVisibility(bSurvivalAllowed);
            SetAPButtonEnabled(Scene.StartAtWaveIncreaseButton, bSurvivalAllowed, PlayerIndex);
        }
        if(Scene.StartAtWaveDecreaseButton != none)
        {
            Scene.StartAtWaveDecreaseButton.SetVisibility(bSurvivalAllowed);
            SetAPButtonEnabled(Scene.StartAtWaveDecreaseButton, bSurvivalAllowed, PlayerIndex);
        }
    }
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
    local UIScriptWidget_EquipmentIconButton EquipmentFocus;

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
        // Native free-input scenes look up focus for player zero. In split
        // screen this can leave the owning player's equipment tooltip unfocused.
        // Only repair that display cache, not focus ownership or input routing.
        if(Scene.IsTopLevelScene() && Scene.GetPlayerOwnerIndex() > 0)
        {
            EquipmentFocus = UIScriptWidget_EquipmentIconButton(Scene.GetFocusedControl(true, Scene.GetPlayerOwnerIndex()));
            if(EquipmentFocus != none && EquipmentFocus.GetEquipment() != none &&
                APShopEquipment(EquipmentFocus.GetEquipment()) == none && EquipmentFocus.IsVisible(true))
            {
                Scene.lastFocusedControl = EquipmentFocus;
                if(EquipmentFocus.LastFocusedTime < 0)
                    EquipmentFocus.LastFocusedTime = GetCurrentWorldInfo().RealTimeSeconds;
            }
        }
        UpdateMapMenuNavigation(UI_GameSetup(Scene));
        Selection = UI_HeroSelection(Scene);
        Swap = UI_SwapHero(Scene);
        Creation = UI_CreateHero(Scene);
        InGameCreation = UI_CreateHeroInGame(Scene);
        if(Selection != none && Selection.HeroDataList != none && Selection.ConfirmButton != none)
        {
            GuardHeroButton(Selection.ConfirmButton, Scene);
            Hero = Selection.HeroDataList.GetSelectedEntry();
            // Keep native selection preconditions. APHeroButtonClicked and the
            // keyboard/controller guard deny entry and explain the AP/DLC lock.
            // A disabled button cannot receive a click to display that reason.
            bVanillaAllowed = Hero != none &&
                (Hero.ActivePlayer == none || Hero.ActivePlayer == Scene.PlayerOwner);
            SetAPButtonEnabled(Selection.ConfirmButton, bVanillaAllowed, Scene.GetPlayerOwnerIndex());
        }
        else if(Swap != none && Swap.HeroDataList != none && Swap.SwapButton != none)
        {
            GuardHeroButton(Swap.SwapButton, Scene);
            Hero = Swap.HeroDataList.GetSelectedEntry();
            bVanillaAllowed = Hero != none &&
                Hero != Swap.GetHeroManager().GetActiveHero(Scene.PlayerOwner) &&
                (Hero.ActivePlayer == none || Hero.ActivePlayer == Scene.PlayerOwner);
            SetAPButtonEnabled(Swap.SwapButton, bVanillaAllowed, Scene.GetPlayerOwnerIndex());
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
    local UI_MainMenu MainMenu;
    local DunDefHeroManager Manager;

    if(!IsAPLocalSession())
        return;
    // Suppress native grants before the parent viewport can run DLC checks.
    class'APHeroSkins'.static.SilenceNativeAwards(GetMenuUnlockState(), class'Engine'.static.GetCurrentWorldInfo());
    SuppressNativeUnlockPopups();
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
    if(ChaosStats == none) ChaosStats = new(self) class'APChaosStats';
    ChaosStats.Apply(self,CurrentState);
    if(DisplayRepair == none) DisplayRepair = new(self) class'APDisplayRepair';
    DisplayRepair.Apply(self, CurrentState);
    // Refresh native menu data without querying every costume entitlement
    // every rendered frame. Confirmation still validates the exact costume.
    APSkinRefreshDelay += DeltaTime;
    if(APSkinRefreshDelay >= 0.5)
    {
        APSkinRefreshDelay = 0;
        class'APHeroSkins'.static.Apply(CurrentState, self);
    }
    if(SeedPresentation == none) SeedPresentation = new(self) class'APSeedPresentation';
    SeedPresentation.ApplyStartingCrystal(CurrentState);
    UpdateHeroMenuGuards();
    UpdateAPShop();

    // Press Start establishes the input player. A modal shown over that screen
    // can prevent it from completing, leaving its own OK button unusable.
    // Wait for the actual main menu (not hero selection, which DD1 may skip).
    if(!bShowedAPStartingItems)
    {
        APStartupNoticeDelay += DeltaTime;
        MainMenu = UI_MainMenu(GetActiveUISceneFromClass(class'UI_MainMenu'));
        Manager = class'DunDefHeroManager'.static.GetHeroManager();
        if(APStartupNoticeDelay >= 3.0 && CurrentState != none && CurrentState.SeedIdentity != "" &&
            MainMenu != none && MainMenu.IsTopLevelScene() &&
            MainMenu.TitleSceneTimer == 0 && MainMenu.SceneCloserTimer == -1 &&
            GetActiveUISceneFromClass(class'UI_TitleScreen') == none &&
            Manager != none && Manager.GetPrimaryPlayer() != none)
        {
            bShowedAPStartingItems = true;
            if(SeedPresentation.ShouldShowNotice(CurrentState))
            class'DunDefSceneClient'.static.ShowDunDefMessageBox(
                'APStartingItems',
                "Archipelago Starting Items",
                "Starting Hero: " $ CurrentState.GetStartingHeroDisplayName() $ "\n" $
                    "Starting Map: " $ CurrentState.GetStartingMapDisplayName(),
                MBT_OK, Manager.GetPrimaryPlayer());
        }
    }

    SuppressNativeUnlockPopups();
}

function SuppressNativeUnlockPopups()
{
    local array<DunDefUIScene> MessageScenes;
    local DunDefUIScene MessageScene;
    local string MessageTag;
    local SoundCue NoticeSound;

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
            // These notices were already hidden, but their opening/closing
            // animation sound queues could still play. Do not mute other UI.
            MessageScene.soundQueue.Length = 0;
            MessageScene.soundsInQueue = false;
            foreach MessageScene.SoundsToStopOnDeactivate(NoticeSound)
            {
                if(MessageScene.PlayerOwner != none && MessageScene.PlayerOwner.Actor != none)
                    MessageScene.PlayerOwner.Actor.StopSound(NoticeSound, 0.0);
            }
            MessageScene.CloseScene(,,true);
        }
    }

}

defaultproperties
{
    // TC cooking does not reliably inherit the native DunDef config section.
    // GetDefaultOptions reads these viewport defaults for each new profile.
    Gamma=2.2
    EnablePostProcessing=true
    VolumeSFX=0.5
    VolumeMusic=0.5
}
