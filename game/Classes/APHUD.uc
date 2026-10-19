// Only filter the vanilla crystal-award message. AP owns crystal skins;
// ordinary achievement and level-up messages must remain visible.
class APHUD extends DunDefHUD;

function DrawHUD()
{
    local APGameRuntime Runtime;
    super.DrawHUD();
    if(PlayerOwner==none || PlayerOwner.IsInState('InCinematic')) return;
    Runtime=class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime!=none && Runtime.Traps!=none) Runtime.Traps.DrawChickenHUD(self);
}

// Spawn cannot use a base-class archetype for a derived HUD. Copy the hero's
// designer settings BEFORE native PostBeginPlay opens its UI scene instead.
function CopyHeroTemplate(DunDefHUD TemplateHUD)
{
    if(TemplateHUD == none) return;
    PlayerHUDSceneTemplate = TemplateHUD.PlayerHUDSceneTemplate;
    PlayerHUDSceneTemplateLobby = TemplateHUD.PlayerHUDSceneTemplateLobby;
    PlayerHUDSceneTemplateGamepad = TemplateHUD.PlayerHUDSceneTemplateGamepad;
    ActivationTextScale = TemplateHUD.ActivationTextScale;
    ActivationIconScale = TemplateHUD.ActivationIconScale;
    DeathStringColor = TemplateHUD.DeathStringColor;
    ReachedLevelCapMessageString = TemplateHUD.ReachedLevelCapMessageString;
    ReachedDemoLevelCapMessageString = TemplateHUD.ReachedDemoLevelCapMessageString;
    ReachedLevelCapMessageColor = TemplateHUD.ReachedLevelCapMessageColor;
    MsgPlayerTextColor = TemplateHUD.MsgPlayerTextColor;
    MsgPlayerNameColors = TemplateHUD.MsgPlayerNameColors;
    PrimaryActivationKeybind = TemplateHUD.PrimaryActivationKeybind;
    AlternateActivationKeybind = TemplateHUD.AlternateActivationKeybind;
    PrimaryActivationColor = TemplateHUD.PrimaryActivationColor;
    SecondaryActivationColor = TemplateHUD.SecondaryActivationColor;
    LootWeaponIcon = TemplateHUD.LootWeaponIcon;
    LootPetIcon = TemplateHUD.LootPetIcon;
    LootArmorIcon = TemplateHUD.LootArmorIcon;
    LootAccessoryIcon = TemplateHUD.LootAccessoryIcon;
}

simulated event PostBeginPlay()
{
    local DunDefPlayerController PC;
    PC = DunDefPlayerController(Owner);
    if(PC != none && PC.GetHero() != none)
        CopyHeroTemplate(PC.GetHero().GetPlayerTemplate().HudTemplate);
    super.PostBeginPlay();
}

function LocalizedMessage(class<LocalMessage> InMessageClass,
    PlayerReplicationInfo RelatedPRI_1, string CriticalString, int Switch,
    float Position, float LifeTime, int FontSize, color DrawColor,
    optional object OptionalObject, optional Surface Icon,
    optional bool bLeftJustified, optional float TextScale=1.0)
{
    local DunDefAchievementManager Achievements;
    if(WorldInfo.NetMode == NM_Standalone && InMessageClass == class'DunDefAchievementMessage')
    {
        Achievements = class'DunDefAchievementManager'.static.GetAchievementManager();
        if(Achievements != none && Achievements.UnlockedCoreMessageString != "" &&
            InStr(CriticalString, Achievements.UnlockedCoreMessageString) == 0)
            return;
    }
    super.LocalizedMessage(InMessageClass, RelatedPRI_1, CriticalString, Switch,
        Position, LifeTime, FontSize, DrawColor, OptionalObject, Icon, bLeftJustified, TextScale);
}
