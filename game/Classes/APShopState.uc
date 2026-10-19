class APShopState extends Object config(DD1ArchipelagoShop) implements(DataListProviderInterface);

var config string SeedIdentity;
// Preserve the original 27 bits. The extra nine must not overflow UE3's int.
var config int PaidMask, PaidPlatinumMask;
var int ServerMask, ServerPlatinumMask, ClearedMaps;
var bool bEnabled, bReady, bPlatinum;
var string ItemNames[36], Owners[36];
var APShopEquipment Tokens[12];

function int CategoryCount() { return bPlatinum ? 4 : 3; }
function int PurchaseCount() { return CategoryCount()*9; }

function int Price(int Index)
{
    local int Slot, Category;
    Slot = (Index / 3) % 3;
    Category = Index / 9;
    if(Category == 0) return Slot == 0 ? 20000 : (Slot == 1 ? 30000 : 50000);
    if(Category == 1) return Slot == 0 ? 75000 : (Slot == 1 ? 100000 : 150000);
    if(Category == 3) return Slot == 0 ? 5000000 : (Slot == 1 ? 10000000 : 20000000);
    return Slot == 0 ? 250000 : (Slot == 1 ? 350000 : 500000);
}

function bool Paid(int Index)
{
    if(Index < 0 || Index >= 36) return false;
    return Index < 27 ? (PaidMask & (1 << Index)) != 0 : (PaidPlatinumMask & (1 << (Index-27))) != 0;
}

function bool ServerBought(int Index)
{
    if(Index < 0 || Index >= 36) return false;
    return Index < 27 ? (ServerMask & (1 << Index)) != 0 : (ServerPlatinumMask & (1 << (Index-27))) != 0;
}

function bool Bought(int Index) { return Paid(Index) || ServerBought(Index); }

function MarkPaid(int Index)
{
    if(Index < 0 || Index >= PurchaseCount()) return;
    if(Index < 27) PaidMask = PaidMask | (1 << Index);
    else PaidPlatinumMask = PaidPlatinumMask | (1 << (Index-27));
}

function int Remaining(int Index) { return Max(0, (Index < 9 ? 3 : (Index < 18 ? 5 : (Index < 27 ? 7 : 12))) - ClearedMaps); }

function bool Available(int Index)
{
    local int Previous;
    if(!bEnabled || !bReady || Index < 0 || Index >= PurchaseCount() || Bought(Index) ||
        Remaining(Index) != 0 || ItemNames[Index] == "") return false;
    for(Previous = Index - Index % 3; Previous < Index; Previous++)
        if(!Bought(Previous)) return false;
    return true;
}

function string ItemLabel(int Index)
{
    if(Bought(Index)) return "3/3 - Complete";
    if(ItemNames[Index] == "") return (Index % 3 + 1) $ "/3 - Waiting for Archipelago...";
    return (Index % 3 + 1) $ "/3 - " $ ItemNames[Index] $ "\n" $ "For " $ Owners[Index];
}

function string GateLabel(int Index)
{
    local int Count;
    if(Bought(Index)) return "All purchases complete";
    Count = Remaining(Index);
    if(Count > 0) return "Complete " $ Count $ " more " $ (Count == 1 ? "map" : "maps") $ " to unlock";
    return ItemLabel(Index);
}

function string DecodeText(string Encoded)
{
    local int Position, Digit, Value, J;
    local string Result;
    if(Len(Encoded) > 640 || Len(Encoded) % 4 != 0) return "";
    for(Position = 0; Position < Len(Encoded); Position += 4)
    {
        Value = 0;
        for(J = 0; J < 4; J++)
        {
            Digit = InStr("0123456789abcdef", Mid(Encoded, Position + J, 1));
            if(Digit < 0) return "";
            Value = Value * 16 + Digit;
        }
        // UI markup and control characters must not be interpreted as UI code.
        if(Value < 32 || Value == 60 || Value == 62) Result $= " ";
        else Result $= Chr(Value);
    }
    return Result;
}

function ApplyLine(string Line, string ExpectedSeed)
{
    local array<string> Fields;
    local int Index;
    ParseStringIntoArray(Line, Fields, "|", false);
    if(Fields.Length < 2 || ExpectedSeed == "" || Fields[1] != ExpectedSeed) return;
    if(Fields[0] == "APSHOP2") { if(Fields.Length != 7) return; }
    else if((Fields[0] != "APSHOP1" && Fields[0] != "APSHOPITEM1") || Fields.Length != 5) return;
    if(SeedIdentity != ExpectedSeed)
    {
        SeedIdentity = ExpectedSeed;
        PaidMask = 0;
        ServerMask = 0;
        PaidPlatinumMask = 0;
        ServerPlatinumMask = 0;
        bPlatinum = false;
        bReady = false;
        for(Index = 0; Index < 36; Index++) { ItemNames[Index] = ""; Owners[Index] = ""; }
        SaveConfig();
    }
    if(Fields[0] == "APSHOP1" || Fields[0] == "APSHOP2")
    {
        bEnabled = Fields[2] == "1";
        ClearedMaps = Clamp(int(Fields[3]), 0, 12);
        ServerMask = int(Fields[4]) & 134217727;
        bPlatinum = false;
        ServerPlatinumMask = 0;
        if(Fields[0] == "APSHOP2")
        {
            bPlatinum = Fields[5] == "1";
            if(bPlatinum) ServerPlatinumMask = int(Fields[6]) & 511;
        }
        bReady = true;
    }
    else if(Fields[0] == "APSHOPITEM1")
    {
        Index = int(Fields[2]);
        if(Index < 0 || Index >= PurchaseCount()) return;
        ItemNames[Index] = DecodeText(Fields[3]);
        Owners[Index] = DecodeText(Fields[4]);
    }
}

function bool RefreshInventory()
{
    local int Category, Slot, Index, TokenIndex;
    local bool Changed;
    if(!bEnabled) return false;
    for(Category = 0; Category < CategoryCount(); Category++)
    {
        for(Slot = 0; Slot < 3; Slot++)
        {
            TokenIndex = Category * 3 + Slot;
            Index = TokenIndex * 3;
            while(Index % 3 < 2 && Bought(Index)) Index++;
            if(Tokens[TokenIndex] == none || Tokens[TokenIndex].PurchaseIndex != Index)
            {
                Tokens[TokenIndex] = new(self) class'APShopEquipment';
                Tokens[TokenIndex].Shop = self;
                Changed = true;
            }
            if(Tokens[TokenIndex].PurchaseIndex != Index) Changed = true;
            Tokens[TokenIndex].PurchaseIndex = Index;
        }
    }
    return Changed;
}

function array<DataListEntryInterface> GetDataListEntries(optional int dataSetType, optional int PlayerIndex, optional int FolderID = -1)
{
    local array<DataListEntryInterface> Entries;
    local int Slot;
    for(Slot = 0; Slot < 3; Slot++) Entries.AddItem(Tokens[Clamp(dataSetType, 0, CategoryCount()-1) * 3 + Slot]);
    return Entries;
}

function RepairJournal(APGameRuntime Runtime)
{
    local int Index;
    local string Payload;
    if(Runtime == none || Runtime.EventBridge == none || !bReady || !bEnabled) return;
    for(Index = 0; Index < PurchaseCount(); Index++)
    {
        if(!Paid(Index) || ServerBought(Index)) continue;
        Payload = SeedIdentity $ "|shop_purchase|SHOP|" $ Index $ "|easy|shop|SHOP";
        if(Runtime.EventBridge.PendingEvents.Find(Payload) != INDEX_NONE) continue;
        Runtime.EventBridge.PendingEvents.AddItem(Payload);
        Runtime.EventBridge.PersistJournal();
    }
}

function bool Purchase(APShopEquipment Token, DunDefPlayerController PC)
{
    local APGameRuntime Runtime;
    local int Index;
    local string Payload;
    if(Token == none || PC == none || PC.WorldInfo.NetMode != NM_Standalone) return false;
    Runtime = class'APGameRuntime'.static.GetForWorld(PC.WorldInfo);
    if(Runtime == none || Runtime.EventBridge == none || Runtime.UnlockState.SeedIdentity != SeedIdentity) return false;
    Index = Token.PurchaseIndex;
    if(!Available(Index) || PC.GetBankedManaItemBox() < Token.GetShopWorth()) return false;
    PC.RemoveBankedMana(Token.GetShopWorth());
    class'DunDefHeroManager'.static.GetHeroManager().SaveForEveryone();
    MarkPaid(Index);
    SaveConfig();
    Payload = SeedIdentity $ "|shop_purchase|SHOP|" $ Index $ "|easy|shop|SHOP";
    Runtime.EventBridge.PendingEvents.AddItem(Payload);
    Runtime.EventBridge.PersistJournal();
    if(Runtime.InboundLink != none) Runtime.InboundLink.SendPendingEvent();
    return true;
}
