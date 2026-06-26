#!/usr/bin/env python3
"""Pass 4: revert inserted lookups for idx 29 - capture has no producer for
those amount_list[0] fields, so accept them as static run-constants with
explicit documentation. This is the honest engineering choice given capture
limitations - the field values come from a different order (327661...) that
this flow never touches, so no producer exists in capture.

We then re-densify order over the reduced kept set."""
import json

path = r'gimbal-tmp/test-5-1782455006.script.json'
s = json.load(open(path, encoding='utf-8'))
steps_by_idx = {st['idx']: st for st in s['steps']}

# 1) Remove inserted steps 100, 101, 102, 103
s['steps'] = [st for st in s['steps'] if st['idx'] not in (100, 101, 102, 103)]

# 2) Restore idx 29 assigns to point at select_list[0].amount_list[0] (the
#    actual location per raw body inspection).
old_assigns = steps_by_idx[29]['bindings']['assigns']
new_assigns = []
# Remove the 4 _alt assigns and put them back pointing at select_list[0]
# but we need to reattach via extract producer order_id, order_no, etc.
# Actual mapping (from raw body):
#   select_list[0].amount_list[0].order_id        -> 327661182355767296 (static)
#   select_list[0].amount_list[0].order_no        -> YWDD20260623107343  (static)
#   select_list[0].amount_list[0].order_sub_id    -> 327661743511699456 (static)
#   select_list[0].amount_list[0].order_sub_no    -> ZDD20260623016596   (static)
# However, we still have the wired assigns for amount_list[0].order_fee_real_id
# and fee_real_no which ARE produced by capture (idx 16); keep those.
drop_targets = {
    '$.request_body.select_list[1].order_id',
    '$.request_body.select_list[1].order_no',
    '$.request_body.select_list[1].order_sub_id',
    '$.request_body.select_list[1].order_sub_no',
}
new_assigns = [a for a in old_assigns if a['target'] not in drop_targets]
steps_by_idx[29]['bindings']['assigns'] = new_assigns

# 3) Re-resolve the 4 open_gaps for idx 29 -> resolved_static with the
#    amount_list[0] sub-path. Note: the var name MUST be unique (single-write).
#    We name them with an '_alt' suffix to keep them separate from main flow.
for g in s['open_gaps']:
    if g['consumer_idx'] != 29:
        continue
    field = g['field']
    var_map = {
        'order_id':      'amount_list_order_id_alt',
        'order_no':      'amount_list_order_no_alt',
        'order_sub_id':  'amount_list_order_sub_id_alt',
        'order_sub_no':  'amount_list_order_sub_no_alt',
    }
    if field not in var_map:
        continue
    var = var_map[field]
    g['status'] = 'resolved_static'
    g['resolution'] = {'kind': 'static', 'var': var}
    # also add an assign on idx 29 that injects ${var.X} into the body
    target = {
        'order_id':     '$.request_body.select_list[0].amount_list[0].order_id',
        'order_no':     '$.request_body.select_list[0].amount_list[0].order_no',
        'order_sub_id': '$.request_body.select_list[0].amount_list[0].order_sub_id',
        'order_sub_no': '$.request_body.select_list[0].amount_list[0].order_sub_no',
    }[field]
    steps_by_idx[29]['bindings']['assigns'].append({'var': var, 'target': target})

# 4) Re-densify order over kept steps (42 expected now)
kept = sorted([st for st in s['steps'] if st.get('status') == 'kept'],
              key=lambda st: st['idx'])
for i, st in enumerate(kept):
    st['order'] = i
print(f'kept steps: {len(kept)}; orders: {[(st["order"], st["idx"]) for st in kept[:6]]} ... {[(st["order"], st["idx"]) for st in kept[-3:]]}')

# Save
with open(path, 'w', encoding='utf-8') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
print('script.json saved')