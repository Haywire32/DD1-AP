// Native HUDWidgetScene pools equipment prefabs without resetting visibility.
// Restore only overlays hidden by AP before they are reused for real gear.
class APShopTooltipGuard extends Object;
var array<HUDPrefabContainer> HiddenByAP;

function HideTokenOverlay(HUDPrefabContainer Overlay)
{
    if(Overlay==none || APShopEquipment(Overlay.associatedObject)==none) return;
    if(HiddenByAP.Find(Overlay)==INDEX_NONE && Overlay.IsVisible())
        HiddenByAP.AddItem(Overlay);
    Overlay.SetVisibility(false);
}

function RestoreReusedOverlays()
{
    local int I;
    for(I=HiddenByAP.Length-1; I>=0; I--)
    {
        if(HiddenByAP[I]==none) { HiddenByAP.Remove(I,1); continue; }
        if(APShopEquipment(HiddenByAP[I].associatedObject)!=none) continue;
        HiddenByAP[I].SetVisibility(true);
        HiddenByAP.Remove(I,1);
    }
}
