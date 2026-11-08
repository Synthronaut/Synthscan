"""Exact SynthStrings HUD labels; never rewrite mission prose or item identities."""
SHORT_LABELS={
    'actor_species_creature_valakkar_juvenile':'Vlk Jr',
    'actor_species_creature_valakkar_juvenile_irradiated':'Irr Vlk Jr',
}
def compact_mining_labels(text):
    result=[];changed=0
    for line in text.splitlines(keepends=True):
        left,sep,value=line.partition('=')
        label=SHORT_LABELS.get(left.lstrip('\ufeff').casefold()) if sep else None
        if label is not None:
            ending='\r\n' if value.endswith('\r\n') else '\n' if value.endswith('\n') else ''
            new=left+'='+label+ending;changed+=new!=line;line=new
        result.append(line)
    return ''.join(result),changed
