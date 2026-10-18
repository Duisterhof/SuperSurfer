from unittest.mock import AsyncMock,patch
from test_slurm_queue import SlurmQueueTests
import test_queue_recovery as fixtures
from server import agent_tools

class StanfordQueueTests(SlurmQueueTests):
    def queue(self,params=None):
        arguments=params or self.params
        if arguments.get('backend')=='slurm':
            arguments['backend']='stanford_slurm'
            arguments['slurm'].update(account='viscam',partition='viscam',gpu_type='a5000',cpus_per_task=4,memory_gib=32)
        agent_tools.validate_arguments(agent_tools.QUEUE_TOOL,arguments)
        return fixtures.QueueRecoveryTests.queue(self,arguments)

    def test_single_aggregate_allocation(self):
        first=self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(return_value={'state':'running','job_id':'123','slurm_state':'RUNNING'})) as transport:
            self.wait(self.manager.schedule_runs())
            self.params['request_id']='stanford-second-test-20261017'
            self.params['name']='second-stanford-smoke'
            second=self.queue()
            self.wait(self.manager.schedule_runs())
            self.assertEqual(transport.call_count,1)
            self.assertEqual(self.db('get','runs',second['run_id'])['status'],'queued')

    def test_old_manager_rejected_before_run_creation(self):
        from server.app import APIError
        original=self.service.aml.call
        def call(op,*args,**kwargs):
            value=original(op,*args,**kwargs)
            if op=='ping':value['capabilities'].remove('run.stanford_slurm.v1')
            return value
        with patch.object(self.service.aml,'call',side_effect=call):
            with self.assertRaisesRegex(APIError,'Slurm backend update'):self.prepare()
        self.assertEqual([],self.runs())
