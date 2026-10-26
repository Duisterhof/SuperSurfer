"""Contract backlog must leave room for live-job control under the SSH cap."""
import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.transport import ContractGate, Transport


class ContractControlProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_contract_backlog_leaves_status_probe_and_launch_progress(self):
        transport = Transport()
        entered, release = asyncio.Event(), asyncio.Event()
        active = peak = contracts = 0

        async def request(host, payload, timeout):
            nonlocal active, peak, contracts
            active += 1
            peak = max(peak, active)
            try:
                if payload['op'] == 'admit':
                    contracts += 1
                    self.assertEqual(contracts, 1)
                    entered.set()
                    await release.wait()
                    contracts -= 1
                return payload['op']
            finally:
                active -= 1

        tasks = []
        with patch.object(transport, '_request', side_effect=request):
            try:
                for index in range(12):
                    tasks.append(asyncio.create_task(transport.request(
                        {'target': f'trinity-{index}'}, {'op': 'admit'})))
                await asyncio.wait_for(entered.wait(), 1)
                for operation in ('status', 'probe', 'launch'):
                    result = await asyncio.wait_for(transport.request(
                        {'target': 'trinity-control'}, {'op': operation}), 1)
                    self.assertEqual(result, operation)
                self.assertEqual(peak, 2)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def test_native_priority_precedes_older_low_priority_waiters(self):
        gate, release, entered = ContractGate(), asyncio.Event(), asyncio.Event()
        order = []

        async def holder():
            async with gate.hold():
                entered.set()
                await release.wait()

        async def waiter(name, priority):
            async with gate.hold(priority):
                order.append(name)

        first = asyncio.create_task(holder())
        await entered.wait()
        low = asyncio.create_task(waiter('low', 0))
        await asyncio.sleep(0)
        high = asyncio.create_task(waiter('high', 20))
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.gather(first, low, high), 1)
        self.assertEqual(order, ['high', 'low'])

    async def test_cancelled_waiter_cannot_block_next_request(self):
        gate = ContractGate()
        async with gate.hold():
            async def wait():
                async with gate.hold(20):
                    self.fail('Cancelled waiter entered')
            task = asyncio.create_task(wait())
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with asyncio.timeout(1):
            async with gate.hold():
                self.assertTrue(gate.held)
        self.assertFalse(gate.held)

    async def test_cancelled_active_contract_releases_gateway_and_contract_slot(self):
        transport, entered = Transport(), asyncio.Event()

        async def request(host, payload, timeout):
            if payload.get('block'):
                entered.set()
                await asyncio.Event().wait()
            return payload['op']

        with patch.object(transport, '_request', side_effect=request):
            task = asyncio.create_task(transport.request(
                {'target': 'trinity-one'}, {'op': 'admit', 'block': True}))
            await entered.wait()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            result = await asyncio.wait_for(transport.request(
                {'target': 'trinity-two'}, {'op': 'admit'}), 1)
            self.assertEqual(result, 'admit')


if __name__ == '__main__':
    unittest.main()
