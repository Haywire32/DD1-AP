// Keep native achievement processing, but AP alone grants crystal skins.
// A HUD filter cannot cover stock controllers and all hero-specific HUDs.
class APAchievementManager extends DunDefAchievementManager;

var bool bAPOwnsCrystalSkins;

static function Install(APUnlockState State, WorldInfo W)
{
    local DunDefHeroManager Manager;
    local APAchievementManager Replacement;
    if(State == none || State.SeedIdentity == "" || W == none || W.NetMode != NM_Standalone) return;
    Manager=class'DunDefHeroManager'.static.GetHeroManager();
    if(Manager == none || Manager.TheAchievementManager == none) return;
    Replacement=APAchievementManager(Manager.TheAchievementManager);
    if(Replacement == none)
    {
        // Copy the loaded native archetype's achievement definitions and text.
        // Do not edit the cooked asset or replace achievement/save records.
        Replacement=new(Manager) class'APAchievementManager'(Manager.TheAchievementManager);
        Manager.TheAchievementManager=Replacement;
    }
    Replacement.bAPOwnsCrystalSkins=true;
}

function UnlockCores(DunDefPlayerController forPlayer, EAchievement achievement)
{
    if(bAPOwnsCrystalSkins && class'WorldInfo'.static.GetWorldInfo().NetMode == NM_Standalone) return;
    super.UnlockCores(forPlayer,achievement);
}
