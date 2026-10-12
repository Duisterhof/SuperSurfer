"""Real HTTP service with isolated compute/provider fixtures for native UI QA."""
import json
import os
from pathlib import Path
import sys
import threading
sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'tests')]
from test_conversations import ConversationTests
from server.app import create_server
from server.surfboards import template

fixture = ConversationTests()
fixture.setUp()
service = fixture.service
repo = Path(os.environ.get('SS_NATIVE_FIXTURE_REPO', fixture.repo))
repo.mkdir(parents=True, exist_ok=True)
(repo / 'README.md').write_text('# Native workflow fixture\n\nAn isolated project for testing persistent native chats.\n')
project = service.action('project.add', {'name': 'Web app', 'repo': str(repo), 'surfboard_template': 'software'})
board = template('software')
board['name'] = 'Build → Check → Preview'
keep = {'worker', 'code', 'checks', 'preview', 'results'}
board['nodes'] = [n for n in board['nodes'] if n['id'] in keep]
positions = {'worker': (50, 45), 'code': (320, 45), 'checks': (320, 210), 'preview': (50, 210), 'results': (50, 375)}
for node in board['nodes']:
    node['x'], node['y'] = positions[node['id']]
    if node['id'] == 'checks':
        node['label'] = 'Tests must pass'
        node['config']['argv'] = [sys.executable, '-c', 'print("checks passed")']
    if node['id'] == 'preview':
        node['config']['argv'] = [sys.executable, '-c', 'print("preview ready")']
board['edges'] = [e for e in board['edges'] if e['source'] in keep and e['target'] in keep]
state = service.board_record(project['id'])
draft = service.action('surfboard.draft', {'project_id': project['id'], 'board': board, 'expected_version': state['version'], 'expected_draft_version': 0})
service.action('surfboard.apply', {'project_id': project['id'], 'expected_version': state['version'], 'expected_draft_version': draft['draft']['draft_version']})
item = service.action('experiment.create', {'project_id': project['id'], 'name': 'Build the app', 'summary': 'Implement, check, and preview the requested change.'})
server = create_server(service, port=0)
(service.directory / 'service.json').write_text(json.dumps({'port': server.server_port}))
threading.Thread(target=server.serve_forever, daemon=True).start()
info = {'directory': str(service.directory), 'project_id': project['id'], 'experiment_id': item['id'], 'repo': str(repo)}
if os.environ.get('SS_NATIVE_FIXTURE_INFO'):
    Path(os.environ['SS_NATIVE_FIXTURE_INFO']).write_text(json.dumps(info))
print(json.dumps(info), flush=True)
try:
    sys.stdin.read()
finally:
    server.shutdown()
    server.server_close()
    fixture.tearDown()
