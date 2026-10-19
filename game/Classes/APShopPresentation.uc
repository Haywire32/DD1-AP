// The existing shop explanation stays panel-anchored. Item artwork is drawn
// natively by each equipment button through APShopEquipment.GetEquipmentIcon.
class APShopPresentation extends Object;


// GetPosition is in the UI canvas coordinate space, not the final screen pixels.
// Project both corners through the scene transform, including aspect-ratio scaling.
function ScreenBounds(UIObject Widget, out float X, out float Y, out float W, out float H)
{
    local Vector A, B;
    A.X = Widget.GetPosition(UIFACE_Left, EVALPOS_PixelViewport, true);
    A.Y = Widget.GetPosition(UIFACE_Top, EVALPOS_PixelViewport, true);
    B.X = Widget.GetPosition(UIFACE_Right, EVALPOS_PixelViewport, true);
    B.Y = Widget.GetPosition(UIFACE_Bottom, EVALPOS_PixelViewport, true);
    A = Widget.Project(A);
    B = Widget.Project(B);
    X = A.X;
    Y = A.Y;
    W = B.X - A.X;
    H = B.Y - A.Y;
}

function Draw(Canvas C, UI_Shop Scene, APShopState Shop)
{
    local HeroEquipment Equipment;
    local APShopEquipment Token;
    local float X, Y, W, H, PanelX, PanelY, PanelW, PanelH;
    local float Scale, TextW, TextH;
    local string Message;
    if(Scene == none || Scene.ItemShopPanel == none || !Scene.ItemShopPanel.IsVisible()
        || Scene.bShowingDeletionConfirmation || Scene.EquipmentDataList == none) return;
    // Use the data list for the three horizontal column centers, and the full
    // shop panel for vertical placement. Both are stable when an item grows
    // on hover and both follow the current window size and aspect ratio.
    ScreenBounds(Scene.EquipmentDataList, X, Y, W, H);
    ScreenBounds(Scene.ItemShopPanel, PanelX, PanelY, PanelW, PanelH);
    if(W <= 0 || H <= 0 || PanelW <= 0 || PanelH <= 0) return;
    Equipment = Scene.EquipmentDataList.GetSelectedEntry();
    Token = APShopEquipment(Equipment);
    if(Token == none) Token = Shop.Tokens[Clamp(Scene.EquipmentDataList.DataSetType, 0, Shop.CategoryCount()-1)*3];
    if(Token == none) return;
    if(Shop.Remaining(Token.PurchaseIndex) > 0) Message = Shop.GateLabel(Token.PurchaseIndex);
    else Message = "Each slot can be purchased three times";

    C.Font = class'DunDefViewportClient'.default.GlobalSmallFontReference;
    C.TextSize(Message, TextW, TextH);
    Scale = FMin(PanelH * 0.038 / FMax(1.0, TextH), W * 0.72 / FMax(1.0, TextW));
    C.SetDrawColor(245, 220, 140, 255);
    C.SetPos(X + (W-TextW*Scale)*0.5, PanelY + PanelH*0.25);
    // SetPos already accounts for half the text width: draw from its left edge.
    C.DrawTextShadowed(Message,,Scale,Scale,false);
}
