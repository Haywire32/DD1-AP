// Informational only: no selectable widget and no new input interception.
class APHeroRosterPresentation extends APShopPresentation;

function DrawRoster(Canvas C, UIPanel_DataList HeroList, APUnlockState Permissions)
{
    local string Line, Lines[4], Key;
    local int Count, Row, I;
    local float X, Y, W, H, TextW, TextH, Scale, LineHeight;
    local Font PreviousFont;
    if(Permissions == none || !HeroList.IsVisible(true)) return;
    Count = 0;
    Row = 0;
    foreach Permissions.ActiveHeroes(Key)
    {
        if(!Permissions.IsHeroUnlocked(Key)) continue;
        Row = Count / 4;
        if(Row > 3) break;
        if(Lines[Row] != "") Lines[Row] $= ", ";
        Lines[Row] $= Permissions.GetHeroDisplayName(Key);
        Count++;
    }
    if(Count == 0) Lines[0] = "Waiting for Archipelago...";
    Lines[0] = "Unlocked heroes: " $ Lines[0];
    ScreenBounds(HeroList, X, Y, W, H);
    if(W <= 0 || H <= 0) return;
    PreviousFont = C.Font;
    C.Font = class'DunDefViewportClient'.default.GlobalSmallFontReference;
    LineHeight = H * 0.044;
    // Above the hero grid, following the scene's projection in each viewport.
    for(I = 0; I <= Row; I++)
    {
        Line = Lines[I];
        C.TextSize(Line, TextW, TextH);
        Scale = FMin(LineHeight / FMax(1.0, TextH), W * 0.92 / FMax(1.0, TextW));
        C.SetDrawColor(245, 220, 140, 255);
        C.SetPos(X + (W - TextW * Scale) * 0.5, Y - (Row - I + 1) * LineHeight);
        C.DrawTextShadowed(Line,,Scale,Scale,false);
    }
    C.Font = PreviousFont;
}
