"""Local message delivery must not wait behind a slow remote status batch."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager


class DispatchDuringSSHTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_dispatch_proceeds_while_tick_waits_for_remote_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(Path(directory))
            entered, release, delivered, stop = (asyncio.Event() for _ in range(4))
            async def slow_status(*args, **kwargs):
                entered.set()
                await release.wait()
            with patch.object(manager, 'reconcile_runs', side_effect=slow_status), \
                 patch.object(manager, 'schedule_runs', new_callable=AsyncMock) as schedule, \
                 patch.object(manager, 'dispatch_messages', side_effect=delivered.set):
                tick = asyncio.create_task(manager.tick())
                await entered.wait()
                dispatch = asyncio.create_task(manager.message_dispatch_loop(stop))
                try:
                    await asyncio.wait_for(delivered.wait(), .5)
                    self.assertFalse(tick.done(), 'The remote batch must still be blocked')
                    schedule.assert_not_awaited()
                finally:
                    stop.set()
                    release.set()
                    await asyncio.gather(tick, dispatch)
                    await manager.close()

    async def test_dispatch_error_is_recorded_without_losing_loop_or_sending_ssh(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Mock()
            manager = Manager(Path(directory), transport=transport)
            stop = asyncio.Event()
            with patch.object(manager, 'dispatch_messages', side_effect=RuntimeError('fixture failure')):
                task = asyncio.create_task(manager.message_dispatch_loop(stop))
                await asyncio.sleep(.01)
                stop.set()
                await task
                event = manager.store.one("SELECT data FROM events WHERE kind='manager.error'")
                self.assertIn('message_dispatch', event['data'])
                transport.request.assert_not_called()
            await manager.close()


if __name__ == '__main__':
    unittest.main()
