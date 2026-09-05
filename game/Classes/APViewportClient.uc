class APViewportClient extends DunDefViewportClient;

var APUnlockState MenuUnlockState;
var bool bShowedAPStartingItems;
var float APStartupNoticeDelay;

event Tick(float DeltaTime)
{
    local UI_HeroSelection HeroScene;
    local DunDefHero SelectedHero;
    local string HeroKey;
    local bool HeroOwned;
    local array<DunDefUIScene> MessageScenes;
    local DunDefUIScene MessageScene;
    local string MessageTag;

    super.Tick(DeltaTime);

    if(MenuUnlockState == none)
        MenuUnlockState = new(self) class'APUnlockState';

    // DD1 can bypass character selection when a seed already has a hero.
    // Show the starting permissions after the initial UI has settled instead
    // of tying the notice to one particular menu scene.
    if(!bShowedAPStartingItems)
    {
        APStartupNoticeDelay += DeltaTime;
        if(APStartupNoticeDelay >= 3.0)
        {
            bShowedAPStartingItems = true;
            class'DunDefSceneClient'.static.ShowDunDefMessageBox(
                'APStartingItems',
                "Archipelago Starting Items",
                "Starting Hero: " $ MenuUnlockState.GetStartingHeroDisplayName() $ "\n" $
                    "Starting Map: " $ MenuUnlockState.GetStartingMapDisplayName(),
                MBT_OK);
        }
    }

    // A fresh DD1 save queues many owned-DLC mission/hero/costume popups.
    // They carry randomized tags with these stable prefixes. Suppress only
    // those notices inside the AP conversion; ordinary warnings remain.
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

    HeroScene = UI_HeroSelection(GetActiveUISceneFromClass(class'UI_HeroSelection'));
    if(HeroScene == none || HeroScene.ConfirmButton == none)
        return;

    SelectedHero = HeroScene.HeroDataList.GetSelectedEntry();
    HeroKey = MenuUnlockState.GetHeroKey(SelectedHero);
    HeroOwned = HeroKey != "" && MenuUnlockState.IsHeroUnlocked(HeroKey);

    // Creation, editing, skins, deletion, and hero information remain available.
    // Only confirming a locked class for Local play is disabled.
    HeroScene.ConfirmButton.SetEnabled(HeroOwned, HeroScene.GetPlayerOwnerIndex());
}
