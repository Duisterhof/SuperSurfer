#!/usr/bin/env python3
"""Deterministic native Codex protocol fixture. Never contacts a model."""
import json, os, pathlib, sys, threading, time, uuid
if sys.argv[1:3] == ['debug','models']:
 print(json.dumps({'models':[]}));sys.exit(0)
root=pathlib.Path(os.environ['CODEX_HOME']);root.mkdir(exist_ok=True,parents=True)
file=root/'fixture-threads.json'
try: threads=json.loads(file.read_text())
except FileNotFoundError: threads={}
lock=threading.RLock(); pending={}
def emit(x):
 with lock: print(json.dumps(x),flush=True)
def event(method,params):emit({'method':method,'params':params})
def save():
 with lock:file.write_text(json.dumps(threads))
def finish(tid,turn,text):
 if turn['status']!='inProgress':return
 item={'id':str(uuid.uuid4()),'type':'agentMessage','text':text,'phase':'final_answer'}
 event('item/started',{'threadId':tid,'turnId':turn['id'],'item':item})
 event('item/completed',{'threadId':tid,'turnId':turn['id'],'item':item})
 turn['items'].append(item);turn['status']='completed';save()
 event('turn/completed',{'threadId':tid,'turn':turn})
def call_tool(tid, turn, tool, args, callback):
 cid='tool-'+str(uuid.uuid4())
 item={'id':cid,'type':'dynamicToolCall','namespace':None,'tool':tool,'arguments':args,'status':'inProgress','contentItems':None,'success':None}
 pending[cid]=(tid,turn,item,callback)
 event('item/started',{'threadId':tid,'turnId':turn['id'],'item':item})
 emit({'id':cid,'method':'item/tool/call','params':{'threadId':tid,'turnId':turn['id'],'callId':cid,'namespace':None,'tool':tool,'arguments':args}})
def work(tid,turn,text):
 time.sleep(1)
 if 'slow' in text.lower():time.sleep(8)
 if turn['status']!='inProgress':return
 def done(message):finish(tid,turn,message+'\n\nIntegration fixture · no model inference.')
 def read_result(state):
  if 'Request:' in text or 'workflow edit' in text.lower():
   board=state['draft']['board'] if state.get('draft') else state['board']
   for node in board['nodes']:
    if node['kind']=='agent':node['label']='Frontend developer'
   def apply(draft):
    call_tool(tid,turn,'apply_surfboard',{'expected_version':draft['version'],'expected_draft_version':draft['draft']['draft_version']},lambda _:done('Renamed the agent to **Frontend developer**. The live Surfboard has updated. Your tests-before-preview requirement is unchanged.'))
   call_tool(tid,turn,'propose_surfboard',{'board':board,'expected_version':state['version'],'expected_draft_version':(state.get('draft') or {}).get('draft_version',0)},apply)
  elif 'finish' in text.lower():
   def complete(_):
    call_tool(tid,turn,'finish_workflow',{'summary':'The required check passed for the current source.'},lambda _:done('The required checks passed. The workflow is finished; automatic continuation has stopped.'))
   def checked(result):
    if result.get('status')=='succeeded':complete(result)
    elif result.get('status') in ['failed','cancelled']:done('The check failed; review its result.')
    else:
     time.sleep(.2)
     call_tool(tid,turn,'run_board_action',{'node_id':'checks','operation':'status','execution_id':result['id']},checked)
   call_tool(tid,turn,'run_board_action',{'node_id':'checks','operation':'start','request_id':'fixture-check-'+uuid.uuid4().hex},checked)
  else:done('I read the attached Surfboard in this same native conversation. It requires tests before preview and sends failures back to the developer.')
 if 'workflow' in text.lower() or 'Request:' in text:call_tool(tid,turn,'read_surfboard',{},read_result)
 else:done('The task continued on the host while the editor was closed. Reconnecting restored this same conversation.')
for line in sys.stdin:
 r=json.loads(line);m=r.get('method');p=r.get('params') or {};out={}
 with open(root/'fixture-protocol.jsonl','a') as log:log.write(json.dumps(r)+'\n')
 if not m:
  if r.get('id') in pending:
   tid,turn,item,callback=pending.pop(r['id']);result=r.get('result',{})
   item.update(status='completed',success=result.get('success',False),contentItems=result.get('contentItems',[]));turn['items'].append(item)
   event('item/completed',{'threadId':tid,'turnId':turn['id'],'item':item})
   if not result.get('success'):finish(tid,turn,'The workflow tool failed: '+str(result.get('contentItems'))[:500])
   else:
    try:callback(json.loads(result['contentItems'][0]['text']))
    except Exception as error:finish(tid,turn,'Fixture could not continue: '+str(error))
  continue
 if 'id' not in r:continue
 if m=='initialize':out={'userAgent':'SuperSurfer deterministic fixture','platformFamily':'unix','platformOs':'macos'}
 elif m=='account/read':out={'account':{'type':'chatgpt','email':'fixture@example.invalid','planType':'pro'},'requiresOpenaiAuth':False}
 elif m=='account/rateLimits/read':out={'rateLimits':None,'rateLimitsByLimitId':{}}
 elif m=='config/read':out={'config':{'model':'fixture-codex','model_provider':'openai','model_reasoning_effort':'medium'},'origins':{},'layers':[]}
 elif m=='model/list':out={'data':[{'id':'fixture-codex','model':'fixture-codex','displayName':'Codex · integration fixture','description':'No model inference','isDefault':True,'defaultReasoningEffort':'medium','supportedReasoningEfforts':[{'reasoningEffort':'medium','description':'Fixture'}],'inputModalities':['text'],'supportsPersonality':False}],'nextCursor':None}
 elif m in ['skills/list','hooks/list','mcpServerStatus/list','thread/list','thread/loaded/list']:
  out={'data':list(threads.values()) if m=='thread/list' else [],'nextCursor':None}
 elif m in ['thread/start','thread/resume','thread/read']:
  tid=p.get('threadId') or str(uuid.uuid4());t=threads.setdefault(tid,{'id':tid,'preview':'Native workflow fixture','ephemeral':False,'modelProvider':'openai','createdAt':int(time.time()),'updatedAt':int(time.time()),'status':{'type':'idle'},'cwd':p.get('cwd',str(root)),'cliVersion':'fixture','source':'vscode','turns':[],'name':'Native workflow fixture','path':str(root/(tid+'.jsonl'))});t['tools']=p.get('dynamicTools',t.get('tools',[]));save();out={'thread':t,'model':'fixture-codex','modelProvider':'openai','reasoningEffort':'medium','cwd':t['cwd'],'approvalPolicy':'on-request','sandbox':{'type':'workspaceWrite','writableRoots':[],'networkAccess':False,'excludeTmpdirEnvVar':False,'excludeSlashTmp':False}}
 elif m=='thread/turns/list':out={'data':threads[p['threadId']]['turns'],'nextCursor':None}
 elif m=='turn/start':
  tid=p['threadId'];text='\n'.join(x.get('text','') for x in p['input']);turn={'id':str(uuid.uuid4()),'items':[{'id':str(uuid.uuid4()),'type':'userMessage','content':p['input']}],'status':'inProgress','error':None};threads[tid]['turns'].append(turn);save();out={'turn':turn};event('turn/started',{'threadId':tid,'turn':turn});threading.Thread(target=work,args=(tid,turn,text),daemon=True).start()
 elif m=='turn/interrupt':
  t=threads[p['threadId']]['turns'][-1];t['status']='interrupted';event('turn/completed',{'threadId':p['threadId'],'turn':t})
 elif m=='thread/unsubscribe':out={'status':'unsubscribed'}
 emit({'id':r['id'],'result':out})
