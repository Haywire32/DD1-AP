// Per-open-shop state; the normal inventory remains owned by UI_Shop.
class APShopView extends Object;

var UI_Shop Scene;
var bool bArchipelago;
var string CategoryNames[3];
var UIScriptWidget_Button SwitchButton;
var UIScriptWidget_Button PlatinumButton;
var bool bExtendedCategories, bPlatinumSelected;
var UIScreenValue_Bounds OriginalCategoryPositions[3];

struct SavedIcon
{
    var UIScriptWidget_EquipmentIconButton Button;
    var bool Dragging, TextName, Quality, Tooltip, Wrap, Compare;
    var float CompareTime;
    var Surface LockIcon;
};
var array<SavedIcon> Icons;

function int SelectedCategory()
{
    local int I;
    if(bPlatinumSelected)
    {
        // Native tabs/controller triggers still operate only the original
        // three equipment types. Never expose type 3 to the vanilla inventory.
        for(I=0; I<3; I++)
            if(!Scene.EquipmentItemButtons[I].IsEnabled(Scene.GetPlayerOwnerIndex(),false))
            { bPlatinumSelected=false; break; }
        if(bPlatinumSelected) return 3;
    }
    return Scene.GetSelectedEquipmentItemType();
}

function SelectPlatinum()
{
    local int I;
    if(!bExtendedCategories) return;
    bPlatinumSelected=true;
    for(I=0; I<3; I++) Scene.EquipmentItemButtons[I].SetEnabled(true);
    Scene.LastSelectedEntry=none;
}

static function CopyTierTextStyle(UIScriptWidget_Button Target, UIScriptWidget_Button Style)
{
    Target.TextFont=Style.TextFont;
    Target.TextColor=Style.TextColor;
    Target.TextScale=Style.TextScale;
    Target.bScaleTextByResolution=Style.bScaleTextByResolution;
    Target.bDisplayStringScaleToFit=Style.bDisplayStringScaleToFit;
    Target.DisplayStringPadding=Style.DisplayStringPadding;
    Target.DisplayStringMinScale=Style.DisplayStringMinScale;
    Target.DisplayPostFitScaleMultiplier=Style.DisplayPostFitScaleMultiplier;
    Target.bWrapText=Style.bWrapText;
    Target.TextGradientColor=Style.TextGradientColor;
    Target.DisabledTextColor=Style.DisabledTextColor;
    Target.DisabledTextGradientColor=Style.DisabledTextGradientColor;
    Target.TextShadowScaleMultiplier=Style.TextShadowScaleMultiplier;
}

static function FourTierBounds(float RowLeft, float RowRight, float Gap, int Index, out float Left, out float Width)
{
    Width=(RowRight-RowLeft-3.0*Gap)/4.0;
    Left=RowLeft+Index*(Width+Gap);
}

function UpdateCategories(bool bWantPlatinum)
{
    local UIScriptWidget_Button Style, Button;
    local UIScreenObject Parent;
    local int I;
    local float Left, Right, Top, Height, Gap, ButtonLeft, ButtonWidth;
    bWantPlatinum=bWantPlatinum && bArchipelago;
    if(Scene.EquipmentItemButtons.Length < 3) return;
    if(bWantPlatinum && !bExtendedCategories)
    {
        Style=Scene.EquipmentItemButtons[0];
        Parent=Style.GetParent();
        if(Parent == none) return;
        // Owner-relative right/bottom values are WIDTH/HEIGHT, not endpoints.
        // Use bounds for sizes, and measure the original row before changing it.
        Left=Style.GetPosition(UIFACE_Left,EVALPOS_PercentageOwner);
        Top=Style.GetPosition(UIFACE_Top,EVALPOS_PercentageOwner);
        Height=Style.GetBounds(UIORIENT_Vertical,EVALPOS_PercentageOwner);
        Right=Scene.EquipmentItemButtons[2].GetPosition(UIFACE_Left,EVALPOS_PercentageOwner)
            +Scene.EquipmentItemButtons[2].GetBounds(UIORIENT_Horizontal,EVALPOS_PercentageOwner);
        Gap=FMax(0.0,Scene.EquipmentItemButtons[1].GetPosition(UIFACE_Left,EVALPOS_PercentageOwner)
            -Left-Style.GetBounds(UIORIENT_Horizontal,EVALPOS_PercentageOwner));
        // Layout may not be resolved on the first frame; retry instead of
        // permanently installing zero-size or negative-size category buttons.
        if(Height <= 0.0 || Right-Left <= 3.0*Gap) return;
        if(PlatinumButton == none)
        {
            PlatinumButton=UIScriptWidget_Button(Scene.CreateWidget(Parent,class'UIScriptWidget_Button',,'APShopPlatinum'));
            if(PlatinumButton == none) return;
            PlatinumButton.ButtonBackground=Style.ButtonBackground;
            PlatinumButton.FocusedButtonBackground=Style.FocusedButtonBackground;
            // Native fit-to-box can enlarge text as well as shrink it. Match
            // every stock tab text setting instead of forcing unpadded fitting.
            CopyTierTextStyle(PlatinumButton,Style);
            PlatinumButton.BackgroundColor=Style.BackgroundColor;
            PlatinumButton.FocusedBGColor=Style.FocusedBGColor;
            PlatinumButton.DisabledBGColor=Style.DisabledBGColor;
            PlatinumButton.bUseDisplayString=true;
            PlatinumButton.bIsClickable=true;
            PlatinumButton.DisplayString="Platinum";
            Parent.InsertChild(PlatinumButton);
        }
        for(I=0; I<3; I++) OriginalCategoryPositions[I]=Scene.EquipmentItemButtons[I].Position;
        for(I=0; I<4; I++)
        {
            Button=I == 3 ? PlatinumButton : Scene.EquipmentItemButtons[I];
            FourTierBounds(Left,Right,Gap,I,ButtonLeft,ButtonWidth);
            Button.SetPosition(ButtonLeft,UIFACE_Left,EVALPOS_PercentageOwner);
            Button.SetPosition(Top,UIFACE_Top,EVALPOS_PercentageOwner);
            Button.SetPosition(ButtonWidth,UIFACE_Right,EVALPOS_PercentageOwner);
            Button.SetPosition(Height,UIFACE_Bottom,EVALPOS_PercentageOwner);
            // A new widget has its own render bounds. Do not copy the stock
            // Position struct's resolved flags, which can leave Platinum hidden.
            Button.InvalidateAllPositions(false);
        }
        bExtendedCategories=true;
        Scene.RequestSceneUpdate(false,true,true);
    }
    else if(!bWantPlatinum && bExtendedCategories)
    {
        for(I=0; I<3; I++)
        {
            Button=Scene.EquipmentItemButtons[I];
            Button.Position=OriginalCategoryPositions[I];
            Button.InvalidateAllPositions(false);
        }
        if(bPlatinumSelected)
            for(I=0; I<3; I++) Scene.EquipmentItemButtons[I].SetEnabled(I != 0);
        bPlatinumSelected=false;
        bExtendedCategories=false;
        Scene.RequestSceneUpdate(false,true,true);
    }
    if(PlatinumButton != none)
    {
        PlatinumButton.SetVisibility(bWantPlatinum && !Scene.bShowingDeletionConfirmation);
        if(PlatinumButton.IsEnabled(Scene.GetPlayerOwnerIndex(),false) != (bWantPlatinum && SelectedCategory() != 3))
            PlatinumButton.SetEnabled(bWantPlatinum && SelectedCategory() != 3,Scene.GetPlayerOwnerIndex());
    }
}

function CreateSwitch()
{
    local UIScriptWidget_Button Style;
    if(SwitchButton != none || Scene.ItemShopPanel == none) return;
    Style = UIScriptWidget_Button(Scene.ItemShopButton);
    if(Style == none) return;
    // A fresh button avoids cloning the stock tab's callbacks and state tree.
    SwitchButton = UIScriptWidget_Button(Scene.CreateWidget(Scene.ItemShopPanel, class'UIScriptWidget_Button',, 'APShopSwitch'));
    if(SwitchButton == none) return;
    SwitchButton.ButtonBackground = Style.ButtonBackground;
    SwitchButton.FocusedButtonBackground = Style.FocusedButtonBackground;
    SwitchButton.TextFont = Style.TextFont;
    SwitchButton.TextColor = Style.TextColor;
    SwitchButton.TextScale = Style.TextScale;
    SwitchButton.BackgroundColor = Style.BackgroundColor;
    SwitchButton.FocusedBGColor = Style.FocusedBGColor;
    SwitchButton.DisabledBGColor = Style.DisabledBGColor;
    SwitchButton.bUseDisplayString = true;
    SwitchButton.bDisplayStringScaleToFit = true;
    SwitchButton.bIsClickable = true;
    Scene.ItemShopPanel.InsertChild(SwitchButton);
    SwitchButton.SetPosition(0.015, UIFACE_Left, EVALPOS_PercentageOwner);
    SwitchButton.SetPosition(0.225, UIFACE_Top, EVALPOS_PercentageOwner);
    SwitchButton.SetPosition(0.255, UIFACE_Right, EVALPOS_PercentageOwner);
    SwitchButton.SetPosition(0.060, UIFACE_Bottom, EVALPOS_PercentageOwner);
}

function RememberIcons()
{
    local int I;
    local SavedIcon Saved;
    local UIScriptWidget_EquipmentIconButton Button;
    for(I = 0; I < Scene.EquipmentDataList.Buttons_DataListEntry.Length; I++)
    {
        Button = UIScriptWidget_EquipmentIconButton(Scene.EquipmentDataList.Buttons_DataListEntry[I]);
        if(Button == none || Icons.Find('Button', Button) != INDEX_NONE) continue;
        Saved.Button = Button;
        Saved.Dragging = Button.bAllowDragging;
        Saved.TextName = Button.bDrawTextName;
        Saved.Quality = Button.bIsQualityOutlineEnabled;
        Saved.Tooltip = Button.bUseTooltip;
        Saved.Wrap = Button.bWrapText;
        Saved.CompareTime = Button.ComparisonToolTipFocusTime;
        Saved.LockIcon = Button.LockedOverlay;
        if(Button.MyDataContainer != none) Saved.Compare = Button.MyDataContainer.bCompareStats;
        Icons.AddItem(Saved);
    }
}

function RestoreIcons()
{
    local int I;
    local SavedIcon Saved;
    for(I = 0; I < Icons.Length; I++)
    {
        Saved = Icons[I];
        if(Saved.Button == none) continue;
        Saved.Button.bAllowDragging = Saved.Dragging;
        Saved.Button.bDrawTextName = Saved.TextName;
        Saved.Button.bIsQualityOutlineEnabled = Saved.Quality;
        Saved.Button.bUseTooltip = Saved.Tooltip;
        Saved.Button.bWrapText = Saved.Wrap;
        Saved.Button.ComparisonToolTipFocusTime = Saved.CompareTime;
        Saved.Button.LockedOverlay = Saved.LockIcon;
        if(Saved.Button.MyDataContainer != none) Saved.Button.MyDataContainer.bCompareStats = Saved.Compare;
    }
    Icons.Length = 0;
}
