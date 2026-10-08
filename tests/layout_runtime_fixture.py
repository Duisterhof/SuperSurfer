import json
from pathlib import Path
import sys
import subprocess
import threading
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from test_conversations import ConversationTests
from server.app import create_server
fixture=ConversationTests();fixture.setUp()
fixture.service.codex.account=lambda:{'account':{'type':'chatgpt'},'login_required':False}
projects={'research':'p1'}
for workflow in ('software','web'):
    row=fixture.service.action('project.add',{'name':workflow+'-studio','repo':str(fixture.root/workflow),'surfboard_template':workflow})
    projects[workflow]=row['id']
items={'research':fixture.exp['id']}
for workflow,pid in projects.items():
    repo=Path(fixture.service.lookup('projects',pid)['repo'])
    subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
    (repo/'README.md').write_text('# '+workflow+' fixture\nA local test project.\n')
    (repo/'main.py').write_text('print("hello")\n')
    if workflow!='research':
        items[workflow]=fixture.service.action('experiment.create',{'project_id':pid,'name':'Build '+workflow,'summary':'Implement a working preview'})['id']
server=create_server(fixture.service,port=0)
print(json.dumps({'port':server.server_port,'directory':str(fixture.service.directory),'projects':projects,'items':items}),flush=True)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:sys.stdin.read()
finally:server.shutdown();server.server_close();fixture.tearDown()
