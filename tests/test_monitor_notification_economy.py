"""Retire exact queued monitor noise while preserving real instructions/history."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager
from aml.notifications import changed


class MonitorMessageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = Manager(Path(self.temp.name))
        self.store = self.manager.store
        self.store.execute("INSERT INTO projects VALUES('p','fixture','/tmp','',1,1,0,1)")
        for identity in ('owner', 'other'):
            self.store.execute("""INSERT INTO agents(id,project_id,name,role,backend,cwd,executable,created)
                VALUES(?,'p',?,'worker','codex','/tmp','/bin/true',1)""", (identity, identity))

    async def asyncTearDown(self):
        if self.manager is not None:
            await self.manager.close()
        self.temp.cleanup()

    def identity(self, key):
        row = self.store.get('messages', key)
        return dict(id=key, sha256=hashlib.sha256(row['content'].encode()).hexdigest())

    async def ack(self, messages):
        return await self.manager.call('message.acknowledge', dict(agent='owner', messages=messages, reason='Superseded monitor snapshot'))

    async def notify(self, content='', attention=False):
        return await self.manager.call('agent.notify', dict(agent='owner', key='fixture', content=content, requires_attention=attention))

    async def test_ack_keeps_real_user_root_instructions_and_history(self):
        monitor = self.store.message('owner', 'user', 'legacy monitor exact snapshot')
        user = self.store.message('owner', 'user', 'implement latest MFU')
        root = self.store.message('owner', 'root', 'reviewed source receipt')
        result = await self.ack([self.identity(monitor)])
        self.assertEqual(result['acknowledged'], [monitor])
        self.assertEqual(self.store.get('messages', monitor)['content'], 'legacy monitor exact snapshot')
        for key in (user, root):self.assertEqual(self.store.get('messages', key)['status'], 'queued')
        self.assertEqual(self.store.get('agents', 'owner')['status'], 'idle')
        again = await self.ack([self.identity(monitor)])
        self.assertEqual(again['acknowledged'], [])
        self.assertEqual(again['already_acknowledged'], [monitor])
        self.assertEqual(len(self.store.rows("SELECT * FROM events WHERE kind='message.acknowledged'")), 1)

    async def test_active_or_finished_messages_are_never_acknowledged(self):
        first = self.store.message('owner', 'monitor', 'queued')
        active = self.store.message('owner', 'monitor', 'active')
        for status in ('dispatched', 'completed'):
            self.store.execute('UPDATE messages SET status=? WHERE id=?', (status, active))
            with self.assertRaises(ValueError):await self.ack([self.identity(first), self.identity(active)])
            self.assertEqual(self.store.get('messages', first)['status'], 'queued')
            self.assertEqual(self.store.get('messages', active)['status'], status)

    async def test_wrong_agent_or_changed_content_rejects_entire_batch(self):
        first = self.store.message('owner', 'monitor', 'snapshot')
        foreign = self.store.message('other', 'monitor', 'foreign')
        with self.assertRaises(ValueError):await self.ack([self.identity(first), self.identity(foreign)])
        self.assertEqual(self.store.get('messages', first)['status'], 'queued')
        identity = self.identity(first)
        self.store.execute('UPDATE messages SET content=? WHERE id=?', ('new evidence', first))
        with self.assertRaises(ValueError):await self.ack([identity])
        self.assertEqual(self.store.get('messages', first)['status'], 'queued')

    async def test_healthy_checks_do_not_create_messages(self):
        for _ in range(20):self.assertFalse((await self.notify())['queued'])
        self.assertEqual(self.store.rows('SELECT * FROM messages'), [])

    async def test_attention_coalesces_one_pending_and_deduplicates(self):
        real = self.store.message('owner', 'user', 'preserve my instruction')
        first = await self.notify('new failure', True)
        second = await self.notify('new failure with receipt', True)
        self.assertEqual(first['id'], second['id'])
        duplicate = await self.notify('new failure with receipt', True)
        self.assertFalse(duplicate['queued'])
        self.assertEqual(self.store.get('messages', first['id'])['sender'], 'monitor')
        self.assertEqual(self.store.get('messages', real)['content'], 'preserve my instruction')
        self.assertEqual(len(self.store.rows("SELECT * FROM messages WHERE sender='monitor'")), 1)

    async def test_quiet_recovery_retires_only_pending_typed_alert(self):
        pending = await self.notify('failure', True)
        real = self.store.message('owner', 'user', 'keep MFU work')
        await self.notify()
        self.assertEqual(self.store.get('messages', pending['id'])['status'], 'acknowledged')
        self.assertEqual(self.store.get('messages', real)['status'], 'queued')
        active = await self.notify('different alert', True)
        self.store.execute("UPDATE messages SET status='dispatched' WHERE id=?", (active['id'],))
        await self.notify()
        self.assertEqual(self.store.get('messages', active['id'])['status'], 'dispatched')

    async def test_startup_acknowledges_before_any_dispatch(self):
        import aml.service as service
        from unittest.mock import patch
        monitor = self.store.message('owner', 'user', 'old monitor snapshot')
        user = self.store.message('owner', 'user', 'latest MFU instruction')
        self.store.execute("UPDATE agents SET status='paused'")
        plan = Path(self.temp.name)/'ack.json'
        plan.write_text(json.dumps(dict(agent='owner', messages=[self.identity(monitor)], reason='Explicit monitor cleanup')))
        await self.manager.close()
        self.manager = None
        observed = []
        class FixtureManager(Manager):
            async def message_dispatch_loop(inner, stop):
                observed.append(inner.store.get('messages', monitor)['status'])
                observed.append(inner.store.get('messages', user)['status'])
                stop.set()
        with patch.object(service, 'Manager', FixtureManager):
            await service.serve(Path(self.temp.name), acknowledge_messages=plan)
        self.assertEqual(observed, ['acknowledged', 'queued'])
        self.manager = Manager(Path(self.temp.name))

    async def test_monitor_key_cannot_overwrite_a_user_message(self):
        self.store.message('owner', 'user', 'real instruction', 'monitor:fixture')
        with self.assertRaises(ValueError):await self.notify('replacement', True)
        self.assertEqual(self.store.rows('SELECT * FROM messages')[0]['content'], 'real instruction')


class AttentionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cursor = Path(self.temp.name)/'cursor.json'

    def observe(self, status='running', marker=None, summary=False, transport=0, now=0):
        return changed(self.cursor, [('run', status, summary, False, marker or [('progress.jsonl', 10)])], transport, now=now)

    def test_first_scan_and_migration_do_not_replay_historical_jobs(self):
        self.cursor.write_text(json.dumps({'signature':[['run','running',False,False,False]],'activity':{}}))
        self.assertFalse(self.observe(status='failed')[0])
        self.assertFalse(self.observe(status='failed', now=300)[0])

    def test_healthy_progress_and_new_markers_never_wake_a_model(self):
        for step in range(20):self.assertFalse(self.observe(marker=[('progress.jsonl',step)],now=step*300)[0])

    def test_failure_and_result_completion_notify_once(self):
        self.observe()
        self.assertEqual(self.observe(status='failed',now=300)[1], [['run_failed','run','failed']])
        self.assertFalse(self.observe(status='failed',now=600)[0])
        self.assertEqual(self.observe(status='succeeded',now=900)[1], [['result_ready','run']])
        self.assertFalse(self.observe(status='succeeded',summary=True,now=1200)[0])
        self.assertFalse(self.observe(status='succeeded',summary=True,now=1500)[0])

    def test_transient_transport_failure_and_healthy_recovery_are_quiet(self):
        self.observe()
        self.assertFalse(self.observe(transport=124,now=300)[0])
        self.assertFalse(self.observe(transport=124,now=600)[0])
        self.assertTrue(self.observe(transport=124,now=900)[0])
        self.assertFalse(self.observe(transport=124,now=1200)[0])
        self.assertFalse(self.observe(now=1300,marker=[('progress.jsonl',11)])[0])

    def test_unchanged_json_markers_preserve_stall_clock(self):
        self.observe()
        self.assertFalse(self.observe(now=1500)[0])
        self.assertEqual(self.observe(now=1801)[1], [['run_stalled','run']])
        self.assertFalse(self.observe(now=2100)[0])
        self.assertFalse(self.observe(now=2200,marker=[('progress.jsonl',12)])[0])

    def test_transport_failures_for_only_retired_runs_do_not_wake_model(self):
        self.observe(status='succeeded',summary=True)
        for step in range(1,8):self.assertFalse(self.observe(status='succeeded',summary=True,transport=124,now=step*300)[0])


if __name__ == '__main__':unittest.main()
