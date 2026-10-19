class APMoonbaseDefenseUnits extends Object;

// Moonbase's native Kismet continuously computes its core-dependent DU limit.
// Preserve that entire calculation; replace only its terminal write to the GRI
// so the HUD and enforcement always receive base + AP bonus together.
var DunDef_SeqAct_SetTowerUnits NativeWriter;
var SeqVar_Int NativeLimit;
var bool WasDisabled;

function bool BindWriter(DunDef_SeqAct_SetTowerUnits Candidate)
{
    local int I,J;
    local SeqVar_Int Limit;
    if(Candidate==none || Candidate.InputLinks.Length!=1 || Candidate.InputLinks[0].bDisabled)
        return false;
    // Never suppress downstream gameplay. The retail Moonbase writer is a leaf.
    for(I=0;I<Candidate.OutputLinks.Length;I++)
        if(Candidate.OutputLinks[I].Links.Length!=0) return false;
    for(I=0;I<Candidate.VariableLinks.Length;I++)
        if(Candidate.VariableLinks[I].PropertyName=='newTowerUnits')
        {
            if(Candidate.VariableLinks[I].LinkedVariables.Length!=1) return false;
            Limit=SeqVar_Int(Candidate.VariableLinks[I].LinkedVariables[0]);
            if(Limit==none || Limit.IntValue<=0) return false;
            J=I;
            break;
        }
    if(Limit==none || Candidate.VariableLinks[J].bWriteable) return false;
    NativeWriter=Candidate; NativeLimit=Limit;
    WasDisabled=Candidate.InputLinks[0].bDisabled;
    Candidate.InputLinks[0].bDisabled=true;
    return true;
}

function bool ReadBase(WorldInfo World, out int Base)
{
    local array<Sequence> Roots;
    local Sequence Root;
    local array<SequenceObject> Objects;
    local SequenceObject Obj;
    local DunDef_SeqAct_SetTowerUnits Candidate;
    // GetMapName() returns the display title once the level is running.
    if(World==none || Caps(World.GetMapName(true))!="CR4ZY_MOONBASE") return false;
    if(NativeWriter==none)
    {
        Roots=World.GetAllRootSequences();
        foreach Roots(Root)
        {
            if(Root==none) continue;
            Objects.Length=0;
            Root.FindSeqObjectsByClass(class'DunDef_SeqAct_SetTowerUnits',true,Objects);
            foreach Objects(Obj)
            {
                Candidate=DunDef_SeqAct_SetTowerUnits(Obj);
                if(Candidate!=none && Candidate.Name=='DunDef_SeqAct_SetTowerUnits_0' &&
                    Candidate.ParentSequence!=none &&
                    Candidate.ParentSequence.Name=='Cinematics_CrystalDeath_DUchangers_etc' &&
                    BindWriter(Candidate)) break;
            }
            if(NativeWriter!=none) break;
        }
    }
    if(NativeWriter==none || NativeLimit==none) return false;
    Base=Max(0,NativeLimit.IntValue);
    return true;
}

function Restore()
{
    if(NativeWriter!=none && NativeWriter.InputLinks.Length==1)
        NativeWriter.InputLinks[0].bDisabled=WasDisabled;
    NativeWriter=none; NativeLimit=none;
}
