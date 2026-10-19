class APDisplayRepair extends Object config(DD1ArchipelagoDisplayRepair);

var config bool bRepairedEarlyChaosDisplay;

static function bool HasZeroedDefaults(CDTSettingsManager Settings)
{
    // Several unrelated defaults were all zero in prototypes 01-03. A user
    // merely disabling bloom/post processing must not trigger a settings reset.
    return Settings != none && Settings.numSigFigsHVFormat == 0 &&
        Settings.AlphaAtHighHealth == 0 && Settings.HighHealthThreshold == 0 &&
        Settings.TinyMapSizeScale == 0 && Settings.maxUpgradeDisplayLevel == 0 &&
        Settings.TowerSFXScale == 0;
}

static function RestoreDisplayFields(CDTSettingsManager Settings, out OptionsInfo Options)
{
    // Only rendering controls; keep resolution, controls, volume and gameplay.
    Settings.BloomScale = 1.0;
    Settings.bEnableMotionBlur = true;
    Settings.bEnableDOF = true;
    Settings.bEnableSSAO = true;
    Settings.bTowersUseDynamicLighting = true;
    Options.fixedSizeOptions.Gamma = 2.2;
    Options.fixedSizeOptions.SaturationIntensity = 0.75;
    Options.fixedSizeOptions.PostProcessing = true;
}

function Apply(APViewportClient Viewport, APUnlockState Permissions)
{
    local DunDefHeroManager Manager;
    local LocalPlayer Player;
    local OptionsInfo Options;
    local int UserID;

    if(!class'APBuildProfile'.static.IsPrivateChaosBuild() || bRepairedEarlyChaosDisplay ||
        Permissions == none || !Permissions.bChaosLoadouts || Permissions.SeedIdentity == "" ||
        Viewport == none || !Viewport.HasFirstTicked || Viewport.theSceneClient == none ||
        !HasZeroedDefaults(Viewport.MySettings)) return;
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none) return;
    Player = Manager.GetPrimaryPlayer();
    if(Player == none) return;
    UserID = Manager.GetUserIDOfPlayer(Player);
    if(!Manager.HasOptionsInfo(UserID)) return;

    Options = Manager.GetOptionsInfo(UserID);
    RestoreDisplayFields(Viewport.MySettings, Options);
    // The native chain builder reads the saved options before enabling effects.
    // Update that record first, then explicitly rebuild even if the viewport's
    // cached EnablePostProcessing flag already says true.
    Manager.AddOptionsInfo(Options, UserID);
    Viewport.MySettings.SaveConfig();
    Viewport.Gamma = Options.fixedSizeOptions.Gamma;
    Viewport.SetGamma(Viewport.Gamma);
    if(class'Engine'.static.AllowFloatingPointRenderTargets())
    {
        DunDefSceneClient(Viewport.theSceneClient).EnablePostProcessing();
        Viewport.EnablePostProcessing = true;
    }
    Viewport.SetSaturation(Options.fixedSizeOptions.SaturationIntensity);
    Viewport.SetBloomScale(Viewport.MySettings.BloomScale);
    Viewport.SetMotionBlur(Viewport.MySettings.bEnableMotionBlur);
    Viewport.SetDOF(Viewport.MySettings.bEnableDOF);
    Viewport.SetSSAO(Viewport.MySettings.bEnableSSAO);
    Manager.SaveForPlayer(Player);
    bRepairedEarlyChaosDisplay = true;
    SaveConfig();
    `log("AP:DISPLAY_REPAIR restored early Chaos display defaults once");
}
