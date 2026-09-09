// Keep the native mission class in the inheritance chain.
class APGameInfo extends main;

event InitGame(string Options, out string ErrorMessage)
{
    if(WorldInfo.NetMode != NM_Standalone)
    {
        ErrorMessage = "Archipelago supports Local play only.";
        ConsoleCommand("quit");
        return;
    }
    super.InitGame(Options, ErrorMessage);
}

event PreLogin(string Options, string Address, out string ErrorMessage)
{
    if(WorldInfo.NetMode != NM_Standalone)
    {
        ErrorMessage = "Archipelago supports Local play only.";
        return;
    }
    super.PreLogin(Options, Address, ErrorMessage);
}

simulated event PostBeginPlay()
{
    super.PostBeginPlay();
    if(WorldInfo.NetMode != NM_Standalone)
    {
        ConsoleCommand("quit");
        return;
    }
    class'APGameRuntime'.static.GetForWorld(WorldInfo, true);
}

function Pawn SpawnDefaultPawnFor(Controller NewPlayer, NavigationPoint StartSpot)
{
    local APGameRuntime Runtime;
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo, true);
    if(Runtime == none || !Runtime.CanSpawnHero(NewPlayer))
        return none;
    return super.SpawnDefaultPawnFor(NewPlayer, StartSpot);
}

function UpdateGlobalHeroModifiers(DunDefPlayerController PC)
{
    local APGameRuntime Runtime;
    super.UpdateGlobalHeroModifiers(PC);
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime != none)
        Runtime.UpdateGlobalHeroModifiers(PC);
}

defaultproperties
{
    PlayerControllerClass=class'APPlayerController'
    GameReplicationInfoClass=class'APGameReplicationInfo'
}

static event class<GameInfo> SetGameType(string MapName, string Options, string Portal)
{
    local class<GameInfo> Selected;
    Selected = super.SetGameType(MapName, Options, Portal);
    if(Selected == class'main')
        return class'APGameInfo';
    if(Selected == class'GameInfo_Special')
        return class'APGameSpecial';
    if(Selected == class'DunDefSpecial.GameInfo_NoTowers')
        return class'APGameNoTowers';
    if(Selected == class'DunDefSpecial.GameInfo_OgreAlly')
        return class'APGameOgreAlly';
    if(Selected == class'DunDefSpecial.GameInfo_RainingGoblins')
        return class'APGameRainingGoblins';
    if(Selected == class'DunDefSpecial.GameInfo_Wizardry')
        return class'APGameWizardry';
    if(Selected == class'DunDefSpecial.GameInfo_ZippyTerror')
        return class'APGameZippy';
    if(Selected == class'DunDefSpecial.GameInfo_Chicken')
        return class'APGameChicken';
    if(Selected == class'DunDefSpecial.GameInfo_Assault')
        return class'APGameAssault';
    if(Selected == class'DunDefSpecial.GameInfo_GoldenTokens')
        return class'APGameTreasure';
    return Selected;
}

function DoWaveSkipping(optional bool bAllowArbritraryWaveSkipping)
{
    local DunDefMapInfo Info;
    if(class'DunDefHeroManager'.static.GetHeroManager().CurrentGameSettings.InfiniteWaveMode)
    {
        // The AP survival pack counts actual waves 1..N, never skipped waves.
        StartWave = 1;
        Info = DunDefMapInfo(WorldInfo.GetMapInfo());
        if(Info != none)
            Info.WaveToStartAt = 1;
    }
    super.DoWaveSkipping(bAllowArbritraryWaveSkipping);
}
