"""Durable admission quotas plus runtime circuit breakers, shared by all providers.

Automatic inference is prohibited. User turns reserve their entire allowance
before dispatch. Reservations are not refunded: restarts, missing usage and new
threads cannot manufacture credit. Provider usage notifications are post-response,
so runtime token/call interruption can overshoot by an in-flight response.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

AUTOMATIC_REASON = 'Automatic agent calls are disabled to control token use. Work is saved; open the owning chat and send a message to continue.'
TURN_TOKENS = 1_000_000
TURN_CALLS = 24
TURN_SECONDS = 900
WORKSPACE_TOKENS = 60_000_000
EXPENSIVE_WORKSPACE_TOKENS = 20_000_000
LOCAL_WORKSPACE_TOKENS = 20_000_000
AGENT_TOKENS = 4_000_000
WINDOW_SECONDS = 86400
CONTEXT_CHARS = 48_000
TOOL_CHARS = 12_000
LUNA_ACCOUNTING = 'luna_cached_0.1_v1'
LUNA_RAW_TOKENS = 20_000_000
CODEX_ACCOUNTING = 'codex_cached_0.1_v1'
CACHE_ACCOUNTING = {LUNA_ACCOUNTING, CODEX_ACCOUNTING}
CACHE_MODELS = {'gpt-6-astra', 'gpt-6-sol', 'gpt-6.1-sol', 'gpt-5.6-sol'}

POLICIES = {
    'standard': dict(tokens=TURN_TOKENS, calls=TURN_CALLS, tools=40, seconds=TURN_SECONDS, agent_limit=AGENT_TOKENS),
    'luna': dict(tokens=2_000_000, calls=96, tools=120, seconds=3600, agent_limit=12_000_000,
                 accounting_policy=LUNA_ACCOUNTING, cached_input_weight=0.1, raw_token_limit=LUNA_RAW_TOKENS),
}


def policy_name(model, provider='codex', bucket='paid'):
    # Only the actual resolved Codex catalog ID gets the larger allowance.
    # Aliases on other providers and unknown/legacy models remain conservative.
    return 'luna' if bucket == 'paid' and provider == 'codex' and model == 'gpt-6-luna' else 'standard'


def charge(row):
    """Only reservations that captured the new policy receive a cache discount."""
    raw = row['input_tokens'] + row['output_tokens']
    if row.get('accounting_policy') not in CACHE_ACCOUNTING or row.get('accounting_warning'):
        return raw
    cached = row['cached_input_tokens']
    if not 0 <= cached <= row['input_tokens']:
        return raw
    return raw - cached + (cached + 9) // 10

class RepeatedToolError(ValueError):
    """Reject a repeated mutation without cancelling unrelated authorized work."""


def is_status_poll(name, arguments):
    # Provider dynamic tools use a prefix; HTTP tools use the short name.
    name = name.removeprefix("supersurfer_")
    # Explicit read operations only; mutations retain duplicate protection.
    return (name in {"status", "inspect_project_compute", "inspect_run", "get_run", "inspect_run_status", "inspect_compute_host", "check_available_node"}
            or (name in {"recover_run", "acquire_new_node", "check_available_node"}
                and arguments.get("action", arguments.get("operation", "status" if name == "recover_run" else None)) in {"status", "inspect"}))


class BudgetError(ValueError):
    status = 429

class AgentBudget:
    def __init__(self, path, clock=time.time):
        self.clock, self.lock = clock, threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        Path(path).chmod(0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, created REAL NOT NULL, tokens INTEGER NOT NULL, data TEXT NOT NULL)')
        self.db.execute("CREATE TABLE IF NOT EXISTS tool_calls (reservation TEXT, fingerprint TEXT, created REAL)")
        self.db.commit()

    def reserve(self, scope, source, bucket="paid", *, model=None, provider='codex'):
        if bucket not in {"paid", "local"}:
            raise BudgetError("Unknown inference budget")
        if source != 'user':
            raise BudgetError(AUTOMATIC_REASON)
        now = self.clock()
        policy = policy_name(model, provider, bucket)
        limits = POLICIES[policy]
        workspace_limit = LOCAL_WORKSPACE_TOKENS if bucket == 'local' else WORKSPACE_TOKENS
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                used, own = self.db.execute("SELECT COALESCE(SUM(tokens),0), COALESCE(SUM(CASE WHEN scope=? THEN tokens ELSE 0 END),0) FROM reservations WHERE created>? AND COALESCE(json_extract(data, '$.bucket'), 'paid')=?", (scope, now-WINDOW_SECONDS, bucket)).fetchone()
                expensive = self.db.execute("SELECT COALESCE(SUM(tokens),0) FROM reservations WHERE created>? AND COALESCE(json_extract(data, '$.bucket'), 'paid')='paid' AND COALESCE(json_extract(data, '$.policy'), 'standard')!='luna'", (now-WINDOW_SECONDS,)).fetchone()[0]
                allowance = min(limits['tokens'], workspace_limit - used, limits['agent_limit'] - own) if bucket == "local" or policy == "luna" else limits['tokens']
                if (allowance < (65536 if bucket == "local" or policy == "luna" else limits['tokens']) or used + allowance > workspace_limit
                        or own + allowance > limits['agent_limit']
                        or bucket == 'paid' and policy != 'luna' and expensive + allowance > EXPENSIVE_WORKSPACE_TOKENS):
                    raise BudgetError('Agent usage allowance exhausted for the rolling 24-hour window. Training and telemetry continue; no model turn was started.')
                row = dict(id=uuid.uuid4().hex, bucket=bucket, policy=policy, model=model, provider=provider,
                           scope=scope, created=now, deadline=now+limits['seconds'], seconds=limits['seconds'],
                           tokens=allowance, calls=limits['calls'], tools=limits['tools'], agent_limit=limits['agent_limit'],
                           input_tokens=0, cached_input_tokens=0, output_tokens=0,
                           responses=0, last_total=None, reason=None)
                row.update(accounting_policy=limits.get('accounting_policy', 'raw_tokens_v1'),
                           raw_token_limit=limits.get('raw_token_limit'), charged_units=0, raw_tokens=0)
                if provider == 'codex' and bucket == 'paid' and model in CACHE_MODELS:
                    row.update(accounting_policy=CODEX_ACCOUNTING, raw_token_limit=10_000_000)
                self.db.execute('INSERT INTO reservations VALUES(?,?,?,?,?)', (row['id'],scope,now,allowance,json.dumps(row)))
                self.db.commit()
                return row
            except BaseException:
                self.db.rollback(); raise

    def observe(self, reservation, total, last=None):
        """Deduplicate cumulative provider counters; never add the total twice."""
        with self.lock, self.db:
            raw = self.db.execute('SELECT data FROM reservations WHERE id=?', (reservation,)).fetchone()
            if not raw: raise BudgetError('Missing durable agent allowance; stopping inference.')
            row = json.loads(raw[0])
            names = ('inputTokens','cachedInputTokens','outputTokens')
            if not isinstance(total,dict) or any(type(total.get(k,0)) is not int or total.get(k,0)<0 for k in names):
                raise BudgetError('Invalid provider usage; stopping inference.')
            values = [total.get(k,0) for k in names]
            previous = row['last_total']
            if previous != values:
                if previous is None and last and (not isinstance(last, dict) or any(type(last.get(k, 0)) is not int or last.get(k, 0) < 0 for k in names)):
                    raise BudgetError('Invalid last-response usage; stopping inference.')
                delta = [max(0,a-b) for a,b in zip(values,previous)] if previous is not None else [int((last or {}).get(k,0)) for k in names]
                # First notification normally has a last-response breakdown. If
                # absent, charge the cumulative total conservatively.
                if previous is None and not last: delta = values
                if values[1] > values[0] or delta[1] > delta[0]:
                    # Keep the original reported cumulative tuple for diagnosis,
                    # but never create discount credit from inconsistent cache.
                    row['accounting_warning'] = 'Cached input exceeded reported input; this reservation uses conservative raw-token charging.'
                    delta = [delta[0], 0, delta[2]]
                for key,value in zip(('input_tokens','cached_input_tokens','output_tokens'),delta): row[key] += max(0,value)
                row['responses'] += 1
                row['last_total'] = values
            row['raw_tokens'] = row['input_tokens'] + row['output_tokens']
            row['charged_units'] = charge(row)
            if row.get('raw_token_limit') and row['raw_tokens'] >= row['raw_token_limit']:
                row['reason'] = f"This turn reached its raw-token ceiling ({row['raw_tokens']:,}/{row['raw_token_limit']:,}). Unfinished work is saved."
            elif row['charged_units'] >= row['tokens']:
                unit = 'budget units' if row.get('accounting_policy') in CACHE_ACCOUNTING else 'raw tokens'
                row['reason'] = f"This turn reached its usage allowance ({row['charged_units']:,}/{row['tokens']:,} {unit}). Unfinished work is saved."
            elif row['responses'] >= row.get('calls', TURN_CALLS):
                row['reason'] = f"This turn reached its response-count allowance ({row['responses']}/{row.get('calls', TURN_CALLS)} responses). Unfinished work is saved."
            if self.clock() >= row['deadline']: row['reason'] = f"This turn reached its {row.get('seconds', TURN_SECONDS) // 60}-minute time allowance."
            self.db.execute('UPDATE reservations SET data=?,tokens=MAX(tokens,?) WHERE id=?',(json.dumps(row),row['charged_units'],reservation))
            return row

    def settle(self, reservation):
        # Release unused reservation only after confirmed completion with usage.
        # Interrupted/unknown deliveries retain their entire allowance.
        with self.lock, self.db:
            raw=self.db.execute("SELECT data FROM reservations WHERE id=?",(reservation,)).fetchone()
            if not raw: return
            row=json.loads(raw[0])
            if row.get("last_total") is not None and row.get("responses",0)>0:
                row["settled"]=True
                row['charged_units'] = charge(row)
                self.db.execute("UPDATE reservations SET tokens=?, data=? WHERE id=?",(max(1,row['charged_units']),json.dumps(row),reservation))

    def tool(self, reservation, name, arguments):
        fingerprint = hashlib.sha256(json.dumps([name,arguments],sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                raw = self.db.execute("SELECT data FROM reservations WHERE id=?",(reservation,)).fetchone()
                if not raw: raise BudgetError("No active usage allowance.")
                row = json.loads(raw[0])
                count,same = self.db.execute("SELECT COUNT(*), COALESCE(SUM(fingerprint=?),0) FROM tool_calls WHERE reservation=?",(fingerprint,reservation)).fetchone()
                if row.get("reason"):
                    raise BudgetError(row["reason"])
                if self.clock() >= row["deadline"]:
                    raise BudgetError("Agent time allowance exhausted. Unfinished work is saved.")
                if count >= row.get('tools', 40):
                    raise BudgetError(f"This turn reached its tool-call allowance ({count}/{row.get('tools', 40)} calls). Unfinished work is saved.")
                if same >= 3 and not is_status_poll(name, arguments):
                    raise RepeatedToolError("This identical action was already requested three times. Inspect its existing receipt or change the action; this turn remains active.")
                self.db.execute("INSERT INTO tool_calls VALUES(?,?,?)",(reservation,fingerprint,self.clock()))
                self.db.commit()
            except BaseException:
                self.db.rollback(); raise

    def summary(self):
        with self.lock:
            rows = [{**json.loads(r[0]), 'reserved': r[1]} for r in self.db.execute('SELECT data,tokens FROM reservations WHERE created>?',(self.clock()-WINDOW_SECONDS,))]
        local_rows = [r for r in rows if r.get('bucket') == 'local']
        rows = [r for r in rows if r.get('bucket', 'paid') == 'paid']
        return dict(local_reserved_tokens=sum(r['reserved'] for r in local_rows), local_workspace_limit=LOCAL_WORKSPACE_TOKENS,
                    expensive_reserved_tokens=sum(r['reserved'] for r in rows if r.get('policy', 'standard') != 'luna'),
                    expensive_workspace_limit=EXPENSIVE_WORKSPACE_TOKENS, policies=POLICIES,
                    automatic_model_calls=False, window_hours=24, workspace_limit=WORKSPACE_TOKENS,
                    agent_limit=AGENT_TOKENS, turn_token_limit=TURN_TOKENS, turn_response_limit=TURN_CALLS,
                    turn_seconds=TURN_SECONDS, reserved_tokens=sum(r['reserved'] for r in rows),
                    input_tokens=sum(r['input_tokens'] for r in rows), cached_input_tokens=sum(r['cached_input_tokens'] for r in rows),
                    output_tokens=sum(r['output_tokens'] for r in rows),
                    charged_units=sum(charge(r) for r in rows), budget_unit_label='budget units (not currency)',
                    accounting='New Luna reservations charge uncached input + output + ceil(cached input × 0.1), with a separate 20M raw-token ceiling. Legacy and other-model reservations retain raw charging. Admission reserves full allowances; provider usage is reported after responses, so interruption may include one in-flight response.')

    def close(self):
        with self.lock: self.db.close()
