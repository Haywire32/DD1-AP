class APLocalViewportClient extends DunDefViewportClient;

var bool bAPSessionRejected;

function bool IsAPLocalSession()
{
    local WorldInfo WI;
    local DunDefHeroManager Manager;

    if(bAPSessionRejected)
        return false;
    WI = class'Engine'.static.GetCurrentWorldInfo();
    Manager = class'DunDefHeroManager'.static.GetHeroManager();
    if((WI != none && WI.NetMode != NM_Standalone) ||
        (Manager != none && (Manager.CurrentMultiplayerMode == MPM_RANKED ||
            Manager.bRankedRemoteConnectionActive)))
    {
        bAPSessionRejected = true;
        ConsoleCommand("quit");
        return false;
    }
    return true;
}

event FirstTick()
{
    if(!IsAPLocalSession())
        return;
    super.FirstTick();
    ApplyAPOnlineGuards();
}

event Tick(float DeltaTime)
{
    if(!IsAPLocalSession())
        return;
    ApplyAPOnlineGuards();
    super.Tick(DeltaTime);
    ApplyAPOnlineGuards();
}

function ApplyAPOnlineGuards()
{
    local OnlineSubsystem OnlineSub;
    local WorldInfo WI;
    local PlayerController PC;
    local LocalPlayer LP;
    local UI_MainMenu Menu;

    OnlineSub = class'GameEngine'.static.GetOnlineSubsystem();
    WI = class'Engine'.static.GetCurrentWorldInfo();
    if(OnlineSub != none && OnlineSub.GameInterface != none)
    {
        OnlineSub.GameInterface.ClearGameInviteAcceptedDelegate(0, PlayerOneInvited);
        OnlineSub.GameInterface.ClearGameInviteAcceptedDelegate(1, PlayerTwoInvited);
        OnlineSub.GameInterface.ClearGameInviteAcceptedDelegate(2, PlayerThreeInvited);
        OnlineSub.GameInterface.ClearGameInviteAcceptedDelegate(3, PlayerFourInvited);
        if(WI != none)
        {
            foreach WI.LocalPlayerControllers(class'PlayerController', PC)
            {
                LP = LocalPlayer(PC.Player);
                if(LP != none)
                    OnlineSub.GameInterface.ClearGameInviteAcceptedDelegate(
                        LP.ControllerId, PC.OnGameInviteAccepted);
            }
        }
    }
    if(!HasFirstTicked)
        return;
    Menu = UI_MainMenu(GetActiveUISceneFromClass(class'UI_MainMenu'));
    if(Menu != none && Menu.MultiplayerButton != none)
    {
        Menu.MultiplayerButton.SetEnabled(false, 0);
        Menu.MultiplayerButton.OnClicked = RejectAPOnlineClick;
        // The menu's keyboard/controller handler can activate its focused
        // control directly, without going through the button's OnClicked.
        Menu.OnInterceptRawInputKey = GuardAPMainMenuInput;
        if(Menu.GetFocusedControl(true, 0) == Menu.MultiplayerButton)
            Menu.PlayButton.SetFocus(none, 0);
    }
}

function bool RejectAPOnlineClick(UIScreenObject Sender, int PlayerIndex)
{
    return true;
}

function bool GuardAPMainMenuInput(const out InputEventParameters EventParms)
{
    local UI_MainMenu Menu;
    if(!IsAPLocalSession())
        return true;
    Menu = UI_MainMenu(GetActiveUISceneFromClass(class'UI_MainMenu'));
    if(Menu == none)
        return true;
    if(Menu.GetFocusedControl(true, 0) == Menu.MultiplayerButton)
    {
        Menu.PlayButton.SetFocus(none, 0);
        return true;
    }
    return Menu.OnReceivedInputKey(EventParms);
}

// Ignore native invite callbacks even before the next tick removes delegates.
function CreatePlayerForInvte(int ControllerID,
    const out OnlineGameSearchResult InviteResult) {}
function PlayerOneInvited(const out OnlineGameSearchResult InviteResult) {}
function PlayerTwoInvited(const out OnlineGameSearchResult InviteResult) {}
function PlayerThreeInvited(const out OnlineGameSearchResult InviteResult) {}
function PlayerFourInvited(const out OnlineGameSearchResult InviteResult) {}
