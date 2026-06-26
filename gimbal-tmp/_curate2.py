#!/usr/bin/env python3
"""Pass 2: rename duplicate scenario-scope extract vars to satisfy single-write."""
import json
from collections import Counter

path = r'gimbal-tmp/test-5-1782455006.script.json'
s = json.load(open(path, encoding='utf-8'))
steps_by_idx = {st['idx']: st for st in s['steps']}

# Rename plan:
#   order_sub_ids:
#     idx 15 (audit_ids at order[1]) -> step scope (transient, used to pick second
#       sub in confirmList; idx 32 directly extracts a different path for it,
#       so this extract is purely informational). Down-grade to step scope.
#   audit_ids:
#     idx 20 -> keep "audit_ids" (drives consumer idx 21 - the FIRST audit exec)
#     idx 25 -> rename "audit_ids_batch_1" (drives consumer idx 26)
#     idx 36 -> rename "audit_ids_batch_2" (drives consumer idx 37)
#
# ALSO must update consumers' assigns if they reference the renamed var.

renames = {
    15: [('order_sub_ids', 'order_sub_ids', 'step')],  # step-scope downgrade
    25: [('audit_ids', 'audit_ids_batch_1', 'scenario')],
    36: [('audit_ids', 'audit_ids_batch_2', 'scenario')],
}

# Apply producer renames (extract)
for idx, changes in renames.items():
    st = steps_by_idx[idx]
    for ex in st.get('bindings', {}).get('extracts', []):
        for old_var, new_var, new_scope in changes:
            if ex['var'] == old_var:
                ex['var'] = new_var
                ex['scope'] = new_scope

# Apply consumer assigns: rewires idx 26 to use audit_ids_batch_1, idx 37 to
# use audit_ids_batch_2.
consumer_renames = {
    26: ('audit_ids', 'audit_ids_batch_1'),
    37: ('audit_ids', 'audit_ids_batch_2'),
}
for cidx, (old_var, new_var) in consumer_renames.items():
    st = steps_by_idx[cidx]
    for asg in st.get('bindings', {}).get('assigns', []):
        if asg['var'] == old_var:
            asg['var'] = new_var

# Re-audit single-write
writes = Counter()
for st in s['steps']:
    if st.get('status') != 'kept':
        continue
    for ex in st.get('bindings', {}).get('extracts', []):
        if ex.get('scope', 'scenario') == 'scenario':
            writes[ex['var']] += 1
dupes = {v: c for v, c in writes.items() if c > 1}
print('after rename dupes:', dupes)

# Save
with open(path, 'w', encoding='utf-8') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
print('script.json updated')