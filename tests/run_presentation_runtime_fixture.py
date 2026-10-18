"""Real HTTP/UI integration with isolated fake scheduler; no research jobs."""
import json
from pathlib import Path
import sys
import threading

sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'tests')]
from test_conversations import ConversationTests
from server.app import create_server

fixture = ConversationTests()
fixture.setUp()
service = fixture.service
service.store.put('account_setup_complete', True)
fixture.manager.data['runs'][0]['status'] = 'cancelled'
fixture.manager.data['runs'][0]['config']['backend'] = 'stanford_slurm'
fixture.manager.data['runs'][0]['config']['slurm_status'] = {'job_id': 'fixture-stanford-42', 'slurm_state': 'CANCELLED', 'node_list': 'fixture-viscam-node'}
fixture.manager.data['runs'][0]['config']['supersurfer_experiment_id'] = fixture.exp['id']
fixture.manager.data['runs'][1]['status'] = 'running'
service.aml.invalidate()
server = create_server(service, port=0)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(json.dumps({'port': server.server_port, 'directory': str(service.directory),
                  'experiment': fixture.exp['id']}), flush=True)
try:
    sys.stdin.read()
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
