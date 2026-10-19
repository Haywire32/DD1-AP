class APHeroSkins extends Object;

// Stop the native map scripts from re-granting outfits that AP deliberately
// locks again. Operate at the source, including scripts using stock controllers.
// Keep hero-unlock entries and sequence output links intact.
static function SilenceNativeAwards(APUnlockState State, WorldInfo W)
{
    local array<Sequence> Roots;
    local Sequence Root;
    local array<SequenceObject> Objects;
    local SequenceObject Entry;
    local DunDef_SeqAct_UnlockCostumes Action;
    local DunDef_SeqAct_UnlockMission MissionAction;
    local DunDefAchievementManager Achievements;
    local APViewportClient Viewport;
    local array<DunDefUIScene> Scenes;
    local DunDefUIScene Scene;
    local array<UIObject> Children;
    local UIObject Child;
    local int I, Removed;
    if(W == none || W.NetMode != NM_Standalone || State == none ||
        State.SeedIdentity == "") return;
    class'APAchievementManager'.static.Install(State,W);
    // Crystal awards play directly through WorldInfo, before the HUD can
    // filter their text. AP owns crystal skins even when hero skins are off.
    Achievements = class'DunDefAchievementManager'.static.GetAchievementManager();
    if(Achievements != none) Achievements.UnlockedCoreSound = none;
    Viewport = APViewportClient(class'DunDefViewportClient'.static.GetViewportClient());
    if(Viewport != none && Viewport.APCostumeWorld != W)
    {
        Viewport.APCostumeWorld = W;
        Viewport.APNextNativeAwardScan = 0;
    }
    if(Viewport != none)
    {
        // MenuLevel populates the SAME root with its DLC prefab after startup.
        // A root scanned while empty is not permanently complete. Rescan on
        // real time (also while paused), without walking the graph every frame.
        if(W.RealTimeSeconds < Viewport.APNextNativeAwardScan) return;
        Viewport.APNextNativeAwardScan = W.RealTimeSeconds + 0.25;
    }
    Roots = W.GetAllRootSequences();
    // Main-menu DLC grants live in UI sequences, not world root sequences.
    if(Viewport != none)
    {
        Scenes = Viewport.GetActiveUIScenesFromClass(class'DunDefUIScene');
        foreach Scenes(Scene)
        {
            if(Scene != none && Scene.EventProvider != none && Scene.EventProvider.EventContainer != none)
                Roots.AddItem(Scene.EventProvider.EventContainer);
            if(Scene == none) continue;
            // Widgets can own independent event containers; these are not
            // necessarily children of the scene's top-level UI sequence.
            Children = Scene.GetChildren(true);
            foreach Children(Child)
                if(Child.EventProvider != none && Child.EventProvider.EventContainer != none)
                    Roots.AddItem(Child.EventProvider.EventContainer);
        }
    }
    foreach Roots(Root)
    {
        if(Root == none) continue;
        Objects.Length = 0;
        Root.FindSeqObjectsByClass(class'DunDef_SeqAct_UnlockCostumes', true, Objects);
        foreach Objects(Entry)
        {
            Action = DunDef_SeqAct_UnlockCostumes(Entry);
            if(Action == none) continue;
            // Also silence mixed hero/costume actions. The cue is attached
            // to the action, not the popup, and can play before UI cleanup.
            Action.bNotifyUser = false;
            Action.GivenCostumeSound = none;
            for(I = Action.GiveCostumeEntries.Length - 1; I >= 0; I--)
            {
                if(State.HeroSkinMode != 0 && !Action.GiveCostumeEntries[I].bIsHeroUnlock)
                {
                    Action.GiveCostumeEntries.Remove(I, 1);
                    Removed++;
                }
            }
            if(Action.GiveCostumeEntries.Length == 0)
            {
                Action.bNotifyUser = false;
                Action.GivenCostumeSound = none;
            }
        }
        // Native DLC mission grants play UnlockedSoundCue even with bNotify
        // false. Preserve the grant and sequence links, mute BOTH channels.
        Objects.Length = 0;
        Root.FindSeqObjectsByClass(class'DunDef_SeqAct_UnlockMission', true, Objects);
        foreach Objects(Entry)
        {
            MissionAction = DunDef_SeqAct_UnlockMission(Entry);
            if(MissionAction == none) continue;
            MissionAction.bNotify = false;
            MissionAction.UnlockedSoundCue = none;
        }
    }
    if(Removed > 0) `log("AP:COSTUME_NATIVE_GRANTS_SUPPRESSED count=" $ Removed $ " map=" $ W.GetMapName());
}

static function bool IsAllowed(APUnlockState State, DunDefHero Hero, int CostumeIndex, optional bool bIsTemplate)
{
    local DunDefHero Template;
    local string Key;
    local int AppID, CostumeID;
    if(State == none || Hero == none) return false;
    if(State.HeroSkinMode == 0 || CostumeIndex == 0) return true;
    // Creation menus and HeroTemplates contain archetypes, not saved hero
    // instances. Asking an archetype for its template returns the class default.
    Template = bIsTemplate ? Hero : Hero.GetCurrentHeroTemplate();
    if(Template == none || CostumeIndex < 0 || CostumeIndex >= Template.HeroCostumes.Length) return false;
    Key = State.GetTemplateHeroKey(Template);
    if(!State.ContainsValue(State.ActiveHeroes, Key) ||
        !class'APHeroEntitlements'.static.IsHeroLicensed(Key)) return false;
    CostumeID = Template.HeroCostumes[CostumeIndex].CostumeUniqueID;
    AppID = Template.HeroCostumes[CostumeIndex].SteamAppIDToCheck;
    // These two legacy template fields incorrectly reference Halloween;
    // their native descriptions/store links identify Thanksgiving instead.
    if(CostumeID == 202 || CostumeID == 402) AppID = 203700;
    if(AppID > 0 && !class'APHeroEntitlements'.static.IsDLCAppLicensed(AppID)) return false;
    return State.ContainsValue(State.UnlockedHeroSkins, Key $ "." $ CostumeID);
}

static function Apply(APUnlockState State, DunDefViewportClient Viewport)
{
    local DunDefHeroManager Manager;
    local DunDefHero Template;
    local LocalPlayer LP;
    local OptionsInfo Options;
    local int I, UserID, Existing, CostumeID;
    local bool bAllowed, bChanged;
    if(State == none || State.SeedIdentity == "" || State.HeroSkinMode == 0 || Viewport == none) return;
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none) return;
    foreach Viewport.Outer.GamePlayers(LP)
    {
        if(LP == none) continue;
        UserID = Manager.GetUserIDOfPlayer(LP);
        Options = Manager.GetOptionsInfo(UserID);
        bChanged = false;
        foreach Manager.HeroTemplates(Template)
        {
            if(Template == none) continue;
            for(I = 1; I < Template.HeroCostumes.Length; I++)
            {
                CostumeID = Template.HeroCostumes[I].CostumeUniqueID;
                if(CostumeID <= 0) continue;
                bAllowed = IsAllowed(State, Template, I, true);
                Existing = Options.fixedSizeOptions.CustomeUnlocks.Find(CostumeID);
                if(bAllowed && Existing == INDEX_NONE)
                {
                    Options.fixedSizeOptions.CustomeUnlocks.AddItem(CostumeID);
                    bChanged = true;
                }
                else if(!bAllowed && Existing != INDEX_NONE)
                {
                    Options.fixedSizeOptions.CustomeUnlocks.RemoveItem(CostumeID);
                    bChanged = true;
                }
            }
        }
        // AP saves are already isolated by seed. No vanilla profile or DLC
        // template is modified, and native per-costume stats stay intact.
        if(bChanged) Manager.AddOptionsInfo(Options, UserID);
    }
}
