class APShopEquipment extends HeroEquipment;


var int PurchaseIndex;
var APShopState Shop;
var transient APShopLogo IconArtwork;

function string GetFullEquipmentName()
{
    return Shop == none ? "Archipelago" : Shop.ItemLabel(PurchaseIndex);
}

function string GetEquipmentName() { return GetFullEquipmentName(); }

function HighDigitInt GetShopWorth()
{
    local HighDigitInt Value;
    SetHighIntValue(Value, Shop.Price(PurchaseIndex));
    return Value;
}

function Surface GetEquipmentIcon()
{
    if(IconArtwork == none) IconArtwork=new(self) class'APShopLogo';
    return IconArtwork.GetIcon();
}

function float GetIconDrawScale()
{
    return Super.GetIconDrawScale()*0.85;
}

defaultproperties
{
    bIsShopEquipment=true
    bIsLocked=true
    bDontUseLevelName=true
    bCanBeEquipped=false
    UserEquipmentName="Archipelago"
}
