"""Disposable real editor/agent-review service; no production workspace."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import agent_edits
from test_editor_service import EditorServiceTests
fixture=EditorServiceTests();fixture.setUp()
fixture.service.codex.account=lambda:{'account':{'type':'chatgpt'},'login_required':False}
fixture.service.codex.decide_change=lambda scope,key,receipt:agent_edits.decide(fixture.edits_db,scope,key,receipt)
scope='project:'+fixture.pid
for name in ('main.py','accepted.py','conflict.py','native.py','native-dirty.py'):
    (fixture.repository/name).write_text('new\nuser tail\n')
    fixture.record(scope,name,'@@ -1 +1 @@\n-old\n+new\n',item_id=name)
(fixture.repository/'chunks.py').write_text('new one\nseparator\nnew two\nuser tail\n')
fixture.record(scope,'chunks.py','@@ -1 +1 @@\n-old one\n+new one\n@@ -3 +3 @@\n-old two\n+new two\n',item_id='chunks.py')
(fixture.repository/'native-chunks.py').write_text('new one\nseparator\nnew two\nuser tail\n')
fixture.record(scope,'native-chunks.py','@@ -1 +1 @@\n-old one\n+new one\n@@ -3 +3 @@\n-old two\n+new two\n',item_id='native-chunks.py')
item=fixture.service.action('experiment.create',{'project_id':fixture.pid,'name':'Archive test','summary':'Organize this task'})
print(json.dumps({'port':fixture.server.server_port,'directory':str(fixture.service.directory),'project_id':fixture.pid,'scope':scope,'repo':str(fixture.repository),'item_id':item['id']}),flush=True)
try:sys.stdin.read()
finally:fixture.tearDown()
