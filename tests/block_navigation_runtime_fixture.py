"""Owned block navigation through the real service; isolated synthetic records."""
import json
from pathlib import Path
import sys
import threading
sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'tests')]
from test_conversations import ConversationTests
from server.app import create_server

fixture = ConversationTests(); fixture.setUp()
service = fixture.service
service.store.put('account_setup_complete', True)
project = service.lookup('projects', 'p1')
report = service.results.publish(fixture.exp['id'], {'title': 'Current fixture Results', 'html': '<h1>Exact current fixture evidence</h1>'})
packet = json.dumps({'type': 'supersurfer:block:open-results', 'request_id': 'fixture-open',
                     'experiment_id': fixture.exp['id'], 'result_id': report['id']})
block = service.view_blocks.publish(project, {'title': 'Fixture comparison',
    'html': '<h1>Grouped fixture comparison</h1><button onclick=\'parent.postMessage(' + packet + ',"*")\'>Open current Results</button>'})
state = service.surfboard('p1')
board = state['board']
board['pages'] = {'project': [{'id': 'overview', 'title': 'Overview', 'tiles': [
    {'id': 'comparison', 'kind': 'html', 'block_id': block['id'], 'span': 12, 'height': 500}]}]}
proposal = service.action('surfboard.draft', {'project_id': 'p1', 'board': board,
    'expected_version': state['version'], 'expected_draft_version': (state.get('draft') or {}).get('draft_version', 0)})
service.action('surfboard.apply', {'project_id': 'p1', 'expected_version': proposal['version'], 'expected_draft_version': proposal['draft']['draft_version']})
server = create_server(service, port=0)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(json.dumps({'port': server.server_port, 'directory': str(service.directory), 'project': 'p1',
                  'experiment': fixture.exp['id'], 'result': report['id']}), flush=True)
try: sys.stdin.read()
finally:
    server.shutdown(); server.server_close(); fixture.tearDown()
