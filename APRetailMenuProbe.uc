class APRetailMenuProbe extends APViewportClient config(APRetailMenuProbe);

var config string Stage;
var config string Provider;
var config bool OwnsBase;
var config bool OwnsCounterparts;
var config bool OwnsBarbarian;
var config bool OwnsEV;
var config bool OwnsSummoner;
var config bool OwnsInvalidDLC;
var float Elapsed;
var bool bSampled;

event Tick(float DeltaTime)
{
    if(!IsAPLocalSession())
        return;
    if(Stage != "before_menu_tick" && !bSampled && Elapsed == 0)
    {
        Stage = "before_menu_tick";
        SaveConfig();
    }
    super.Tick(DeltaTime);
    if(Elapsed == 0)
    {
        Stage = "after_menu_tick";
        SaveConfig();
    }
    if(!IsAPLocalSession())
        return;
    Elapsed += DeltaTime;
    if(Elapsed >= 12.0 && !bSampled)
    {
        bSampled = true;
        SamplePurchases();
    }
    if(Elapsed >= 18.0)
        ConsoleCommand("quit");
}

function SamplePurchases()
{
    local OnlineSubsystem OnlineSub;
    OnlineSub = class'GameEngine'.static.GetOnlineSubsystem();
    Provider = "none";
    if(OnlineSub != none)
        Provider = string(OnlineSub.Class.Name);
    Stage = "before_native_purchase_query";
    SaveConfig();
    OwnsBase = class'SaveHelper'.static.IsAppPurchased(65800, false);
    OwnsCounterparts = class'SaveHelper'.static.IsAppPurchased(203701, true);
    OwnsBarbarian = class'SaveHelper'.static.IsAppPurchased(204386, true);
    OwnsEV = class'SaveHelper'.static.IsAppPurchased(208541, true);
    OwnsSummoner = class'SaveHelper'.static.IsAppPurchased(208544, true);
    OwnsInvalidDLC = class'SaveHelper'.static.IsAppPurchased(0, true);
    Stage = "menu_and_purchase_query_completed";
    SaveConfig();
}

function bool BlockKey(int ControllerId, name Key, EInputEvent EventType,
    float AmountDepressed, optional bool bGamepad)
{
    if(Key == 'Escape' && EventType == IE_Pressed)
        ConsoleCommand("quit");
    return true;
}
function bool BlockAxis(int ControllerId, name Key, float Delta,
    float DeltaTime, bool bGamepad) { return true; }
function bool BlockChar(int ControllerId, string Unicode) { return true; }

defaultproperties
{
    HandleInputKey=BlockKey
    HandleInputAxis=BlockAxis
    HandleInputChar=BlockChar
}
