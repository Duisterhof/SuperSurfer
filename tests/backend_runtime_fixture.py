"""Isolated app with fake official CLI wires; never reads real account files."""
import json
import os
from pathlib import Path
import sys
import threading
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from test_conversations import ConversationTests
from test_cli_backends import FAKE as CLI_FAKE
from test_codex import FAKE as CODEX_FAKE
from server.backends import BackendRouter
from server.app import create_server
fixture=ConversationTests();fixture.setUp();root=fixture.root
os.environ['SS_TEST_WIRE']=str(root/'cli-wire.jsonl');os.environ['SS_FAKE_LOG']=str(root/'codex-wire.jsonl');os.environ['SS_FAKE_DOC']=str(root/'document.md')
only=sys.argv[sys.argv.index('--only-provider')+1] if '--only-provider' in sys.argv else None
if only not in (None,'cursor','claude'):raise ValueError('Choose cursor or claude')
for name in ('codex','cursor','claude'):
 os.environ['SUPERSURFER_'+name.upper()]=str(root/name)
 if only and name!=only:continue
 binary=root/name;body=CODEX_FAKE if name=='codex' else CLI_FAKE.replace("text=='approval'","text.startswith('approval')").replace("text=='question'","text.startswith('question')").replace("text=='hold'","text.startswith('hold')").replace("text=v['message']['content'];","text=v['message']['content'].splitlines()[0];").replace("backend=os.environ['SS_TEST_PROVIDER'];",f"backend={name!r};")
 binary.write_text('#!'+sys.executable+'\n'+body);binary.chmod(0o700);os.environ['SUPERSURFER_'+name.upper()]=str(binary)
service=fixture.service;service.codex=BackendRouter(service.directory,service.store,service.context_provider,service._chat_scope,service.agent_action)
server=create_server(service,port=0);threading.Thread(target=server.serve_forever,daemon=True).start()
print(json.dumps({'port':server.server_port,'directory':str(service.directory),'project':'p1','experiment':fixture.exp['id']}),flush=True)
try:sys.stdin.read()
finally:server.shutdown();server.server_close();fixture.tearDown()
