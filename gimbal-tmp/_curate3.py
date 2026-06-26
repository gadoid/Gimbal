#!/usr/bin/env python3
"""Pass 3: fix inserted step 102/103 wiring - remove ${var.x} from request_body."""
import json

path = r'gimbal-tmp/test-5-1782455006.script.json'
s = json.load(open(path, encoding='utf-8'))
steps_by_idx = {st['idx']: st for st in s['steps']}

# Step 102 and 103 currently have request_body with ${var.order_id_alt}.
# This causes two validator violations:
#   - static/dynamic: ${var.X} where X is an extract target
#   - wiring: the assign that should inject is shadowed by the template.
#
# Fix: keep request_body.order_id as a real value (the captured example from
# idx 9's request body), and rely on the assign strategy (source $.order_id_alt,
# target $.request_body.order_id) to overwrite at runtime. Assembly will not
# strip it; inject_static_into_body only acts on static_vars.
#
# To make the scenario replays even when order_id_alt has not been produced
# yet (defensive), use a placeholder string. In practice, because step 102/103
# are ordered AFTER idx 100 (which produces order_id_alt) in dense order, the
# assign will execute and overwrite before the request fires.

# Sample captured body for orderDetail (idx 3): {"order_id":"328781401086230528"}
for idx in (102, 103):
    st = steps_by_idx[idx]
    st['request_body'] = {'order_id': ''}  # empty - will be injected by assign
    # decision_reason updated for clarity
    st['decision_reason'] = (
        f'inserted lookup step; request body.order_id is injected at runtime '
        f'via assign strategy sourced from $.order_id_alt (produced by idx 100).'
        + (' Pulls order_sub_no for the second order.' if idx == 103
           else ' Pulls order_sub_id for the second order.')
    )

# Save
with open(path, 'w', encoding='utf-8') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
print('script.json updated')