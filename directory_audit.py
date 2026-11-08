"""Reject unusable directory identities; keep diagnostics outside the results list."""
import math
import re


def display_name(value):
    return (isinstance(value,str) and bool(value.strip()) and any(c.isalnum() for c in value)
            and value.strip().upper() not in {'PLACEHOLDER','UNINITIALIZED','DEFAULT','UNNAMED'}
            and not value.strip().startswith('@')
            and not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',value.strip()))


def validate(rows):
    seen=set();errors=[]
    for row in rows:
        identity=row.get('id')
        valid_id=isinstance(identity,str) and bool(identity)
        if not valid_id or identity in seen:errors.append(dict(id=identity,reason='Missing or duplicate row identity'))
        if valid_id:seen.add(identity)
        if not display_name(row.get('name')):errors.append(dict(id=identity,reason='Unresolved display name'))
        if not isinstance(row.get('kind'),str) or not row['kind'] or not isinstance(row.get('category'),str) or not row['category']:errors.append(dict(id=identity,reason='Missing type/category'))
        for blueprint in row.get('finder_blueprints',[]):
            if not display_name(blueprint.get('name')):errors.append(dict(id=identity,reason='Unresolved linked blueprint name'))
            for material in blueprint.get('materials',[]):
                amount=material.get('amount')
                if type(amount) not in (float,int) or not math.isfinite(amount) or amount<=0:errors.append(dict(id=identity,reason='Invalid recipe quantity'))
    if errors:raise ValueError('Directory audit failed: '+str(errors[:8]))
    return dict(rows=len(rows),unique_ids=len(seen),blank_names=0,duplicate_ids=0,invalid_recipe_quantities=0)
