class APHeroEntitlements extends Object;

// Retail DD1 passed owned/unowned tests on 2026-09-07. DDDK's permissive native
// query is not purchase evidence; require the real Steam provider and reject
// a provider that claims the invalid DLC app ID 0 is owned.
const NativePurchaseCheckVerified = true;

static function int GetDLCAppID(string HeroKey)
{
    switch(HeroKey)
    {
        case "adept":
        case "countess":
        case "ranger":
        case "initiate": return 203701;
        case "barbarian": return 204386;
        case "series_ev": return 208541;
        case "summoner": return 208544;
        case "jester": return 208546;
        case "hermit": return 2470720;
        case "gunwitch": return 3359180;
        case "warden": return 3971330;
        case "guardian": return 4419980;
    }
    return 0;
}

static function bool IsHeroLicensed(string HeroKey)
{
    local int AppID;
    local OnlineSubsystem OnlineSub;
    if(HeroKey == "apprentice" || HeroKey == "squire" ||
        HeroKey == "huntress" || HeroKey == "monk")
        return true;

    AppID = GetDLCAppID(HeroKey);
    if(AppID == 0 || !NativePurchaseCheckVerified)
        return false;

    OnlineSub = class'GameEngine'.static.GetOnlineSubsystem();
    if(OnlineSub == none || !OnlineSub.IsA('OnlineSubsystemSteamworks'))
        return false;
    if(class'SaveHelper'.static.IsAppPurchased(0, true))
        return false;

    // Saved HeroUnlocks, development cheats and installed templates are NOT
    // purchase evidence. Use the game's native account entitlement query.
    return class'SaveHelper'.static.IsAppPurchased(65800, false) &&
        class'SaveHelper'.static.IsAppPurchased(AppID, true);
}
