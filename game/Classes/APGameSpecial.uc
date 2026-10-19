// Keep the native mission class in the inheritance chain.
class APGameSpecial extends GameInfo_Special;

// Native main spawns its controller archetype, not PlayerControllerClass.
// GameInfo.Killed is called by Pawn.Died regardless of that controller class.
function Killed(Controller Killer, Controller KilledPlayer, Pawn KilledPawn, class<DamageType> DamageType)
{
    local APGameRuntime Runtime;
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime != none && Runtime.DeathLink != none)
        Runtime.DeathLink.NotifyDeath(DunDefPlayerController(KilledPlayer), KilledPawn);
    super.Killed(Killer, KilledPlayer, KilledPawn, DamageType);
}

event InitGame(string Options, out string ErrorMessage)
{
    if(WorldInfo.NetMode != NM_Standalone)
    {
        ErrorMessage = "Archipelago supports Local play only.";
        ConsoleCommand("quit");
        return;
    }
    class'APMapLoadCompatibility'.static.Restore(WorldInfo);
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
    HUDType=class'APHUD'
    GameReplicationInfoClass=class'APGameReplicationInfo'
}

// Observe the native crystal-loss path before it changes the GRI to game-over.
function ShowGameOver(int gameOverDescriptionReason)
{
    local APGameRuntime Runtime;
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime != none && Runtime.DeathLink != none)
        Runtime.DeathLink.NotifyGameOver(gameOverDescriptionReason);
    super.ShowGameOver(gameOverDescriptionReason);
}
