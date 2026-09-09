// Keep the native mission class in the inheritance chain.
class APGameTreasure extends GameInfo_GoldenTokens;

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
    GameReplicationInfoClass=class'APGRITreasure'
}
