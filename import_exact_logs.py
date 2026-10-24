import json
import time
import os

DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_FILE = os.path.expanduser('~/Downloads/request-logs.json')
STATE_FILE = os.path.join(DIR, 'monitor_state.json')

with open(LOGS_FILE, 'r') as f:
    logs_data = json.load(f)

items = logs_data.get('items', [])
print(f"Importing from {len(items)} log items...")

with open(STATE_FILE, 'r') as f:
    state = json.load(f)

# Reset state
now_sec = time.time()
five_hours_ago = now_sec - 5 * 3600

model_map = {
    'gemini-4-argon-contributor': 'gemini-4-argon',
    'gemini-4-argon': 'gemini-4-argon',
    'glm-5.3': 'glm-5-3',
    'glm-5.3-flash': 'glm-5-3', # or separate
    'deepseek-v4.1-flash': 'deepseek-v4-1-flash',
    'deepseek-v4-pro': 'deepseek-v4-pro',
    'mimo-v2.6-pro': 'mimo-v2-6-pro',
    'mimo-v2.6-flash': 'mimo-v2-6-flash',
    'claude-haiku-5-5': 'claude-haiku-5-5',
    'claude-haiku-5.5': 'claude-haiku-5-5',
    'gpt-6-luna': 'luna-6-low',
    'gpt-5.6-luna': 'luna-6-low',
    'beam-free': 'beam-free',
    'beam': 'beam-free'
}

# Clear existing counters in state
for k in state:
    state[k]['timestamps'] = []
    state[k]['current_req_5h'] = 0
    state[k]['current_spent_usd'] = 0.0

for it in items:
    m_raw = (it.get('model') or it.get('requestedModel') or '').lower()
    target_id = None
    for pattern, s_id in model_map.items():
        if pattern in m_raw:
            target_id = s_id
            break
    
    if target_id and target_id in state:
        cost = float(it.get('cost') or 0.0)
        state[target_id]['current_spent_usd'] = round(state[target_id]['current_spent_usd'] + cost, 4)
        
        started_at = (it.get('startedAt') or 0) / 1000.0
        # Count all inference requests in the 5h window
        if started_at > five_hours_ago:
            state[target_id]['timestamps'].append(started_at)

for k in state:
    state[k]['current_req_5h'] = len(state[k]['timestamps'])

with open(STATE_FILE, 'w') as f:
    json.dump(state, f, indent=2)

print("✅ State successfully synchronized with official OpenCode logs:")
for k, v in state.items():
    if v['current_spent_usd'] > 0 or v['current_req_5h'] > 0:
        print(f"  - {v['name']}: {v['current_req_5h']} req/5h | ${v['current_spent_usd']} spent")
