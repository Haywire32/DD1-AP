class APSurvivalSelection extends Object;

var UI_GameSetup Scene;
var UIScriptWidget_Button IncreaseButton, DecreaseButton;

static function int EarnedStartingWave(UI_GameSetup Setup)
{
    local DunDefPlayerStats Stats;
    local StatEntry Entry;
    local CampaignLevelEntry Map;
    local int Difficulty, Best;
    Map = Setup.GetSelectedLevelEntry();
    Stats = Setup.GetHeroManager().GetStats(Setup.GetHeroManager().GetUserIDOfPlayer(Setup.GetPlayerOwner()));
    if(Stats == none) return 1;
    for(Difficulty = int(Setup.CurrentDifficulty); Difficulty < EGD_MAX; Difficulty++)
    {
        if(Stats.HasBestOfValue(DDPlayerStat_SurvivalHighWave, Map.EntryIdentifierTag, Difficulty))
        {
            Entry = Stats.GetBestOfEntry(DDPlayerStat_SurvivalHighWave, Map.EntryIdentifierTag, Difficulty);
            Best = Max(Best, Entry.statValue);
        }
    }
    // GetBestStartingWave supplies native per-map/Ruthless caps, but its free
    // baseline (normally wave 8) is NOT a wave the player has actually beaten.
    return Max(1, Min(Best, Setup.GetBestStartingWave()));
}

function int MaximumWave(APUnlockState Permissions)
{
    return Max(Permissions.SurvivalStartWave, EarnedStartingWave(Scene));
}

function UIScriptWidget_Button MakeButton(UIButton Original, name Tag)
{
    local UIScriptWidget_Button Button, Style;
    Style = UIScriptWidget_Button(Original);
    if(Style == none) return none;
    Button = UIScriptWidget_Button(Scene.CreateWidget(Original.GetParent(), class'UIScriptWidget_Button',, Tag));
    if(Button == none) return none;
    Button.ButtonBackground = Style.ButtonBackground;
    Button.FocusedButtonBackground = Style.FocusedButtonBackground;
    Button.BackgroundColor = Style.BackgroundColor;
    Button.FocusedBGColor = Style.FocusedBGColor;
    Button.DisabledBGColor = Style.DisabledBGColor;
    Button.TextFont = Style.TextFont;
    Button.TextColor = Style.TextColor;
    Button.TextScale = Style.TextScale;
    Button.DisplayString = Style.DisplayString;
    Button.bUseDisplayString = Style.bUseDisplayString;
    Button.bIsClickable = true;
    Button.Position = Original.Position;
    Original.GetParent().InsertChild(Button);
    Button.OnClicked = WaveClicked;
    return Button;
}

function bool WaveClicked(UIScreenObject Sender, int PlayerIndex)
{
    local APGameRuntime Runtime;
    local int Direction;
    Runtime = class'APGameRuntime'.static.GetForWorld(Scene.GetWorldInfo());
    if(Runtime == none || Runtime.UnlockState == none) return true;
    Direction = Sender == IncreaseButton ? 1 : -1;
    Scene.SetStartAtWave(Clamp(Scene.GetHeroManager().CurrentGameSettings.StartAtWave + Direction,
        1, MaximumWave(Runtime.UnlockState)));
    `log("AP:SURVIVAL_START selected=" $ Scene.GetHeroManager().CurrentGameSettings.StartAtWave $
        " maximum=" $ MaximumWave(Runtime.UnlockState));
    return true;
}

function Update(APUnlockState Permissions, bool bAllowed)
{
    local int Current, Limit;
    if(IncreaseButton == none) IncreaseButton = MakeButton(Scene.StartAtWaveIncreaseButton, 'APWaveIncrease');
    if(DecreaseButton == none) DecreaseButton = MakeButton(Scene.StartAtWaveDecreaseButton, 'APWaveDecrease');
    if(IncreaseButton == none || DecreaseButton == none) return;
    Scene.StartAtWaveIncreaseButton.SetVisibility(false);
    Scene.StartAtWaveDecreaseButton.SetVisibility(false);
    Scene.waveChangeTimer = 0;
    IncreaseButton.SetVisibility(bAllowed);
    DecreaseButton.SetVisibility(bAllowed);
    if(!bAllowed) return;
    Scene.StartAtWaveLabel.SetVisibility(true);
    Current = Scene.GetHeroManager().CurrentGameSettings.StartAtWave;
    Limit = MaximumWave(Permissions);
    if(Current > Limit || Current < 1) Scene.SetStartAtWave(Clamp(Current, 1, Limit));
    // Avoid rebuilding native focus state every frame.
    if(IncreaseButton.IsEnabled(Scene.GetPlayerOwnerIndex(), false) != (Current < Limit))
        IncreaseButton.SetEnabled(Current < Limit, Scene.GetPlayerOwnerIndex());
    if(DecreaseButton.IsEnabled(Scene.GetPlayerOwnerIndex(), false) != (Current > 1))
        DecreaseButton.SetEnabled(Current > 1, Scene.GetPlayerOwnerIndex());
}
