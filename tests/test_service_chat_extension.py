"""The VS Code client opens and creates conversations through the real HTTP API."""
import json
from pathlib import Path
import shutil
import subprocess
import threading
import unittest

from server.app import create_server
import test_conversations as conversations


class ServiceChatExtensionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the extension client')
    def test_existing_and_new_folder_chat_use_real_api_without_inference(self):
        fixture = conversations.ConversationTests()
        fixture.setUp()
        server = create_server(fixture.service, port=0)
        (fixture.service.directory / 'service.json').write_text(json.dumps({'port': server.server_port}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        repo = fixture.root / 'ordinary-folder'
        repo.mkdir()
        try:
            script = r'''
const assert=require('node:assert/strict');
const {Service}=require('./native_extension/service.cjs');
const {ServiceAgents}=require('./native_extension/service-agents.cjs');
(async()=>{
 const api=new ServiceAgents(new Service(process.argv[1]));
 const before=await api.list();assert.ok(before[0].agents.length);
 const original=before[0].agents[0];assert.equal((await api.chat(original.scope)).scope,original.scope);
 const one=await api.newChat(process.argv[2]);assert.equal(one.repo,process.argv[2]);
 const two=await api.newChat(process.argv[2]);assert.notEqual(two.scope,one.scope);assert.equal(two.project_id,one.project_id);
 const chat=await api.chat(one.scope);assert.equal(chat.busy,false);
 const projects=await api.list();assert.equal(projects.filter(p=>p.id===one.project_id).length,1);
 const board=await api.board(one);assert.ok(board.board.nodes.length);
 console.log(JSON.stringify({one,two}));
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
            result = subprocess.run(['node', '-e', script, str(fixture.service.directory), str(repo)],
                                    cwd=Path(__file__).resolve().parent.parent, text=True, capture_output=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([], fixture.service.codex.sent)
            self.assertFalse(any(op != 'status' for op, _ in fixture.manager.calls))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            fixture.tearDown()
