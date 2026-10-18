const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../ui/block-navigation.js'),'utf8');
test('owned same-project block can open Results; unknown frames, origins and cross-project targets cannot',async()=>{
 const {connectBlockNavigation}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 let listener;const opened=[],replies=[],source={postMessage:packet=>replies.push(packet)};
 const cleanup=connectBlockNavigation({listen:{addEventListener:(type,fn)=>listener=fn,removeEventListener:()=>listener=null},frames:()=>[{contentWindow:source,dataset:{blockProject:'p1'}}],projectId:()=>'p1',experiment:id=>({id,project_id:id==='foreign'?'p2':'p1'}),open:async(item,id)=>opened.push([item.id,id])});
 const packet={type:'supersurfer:block:open-results',request_id:'navigation-v1',experiment_id:'study',result_id:'report'};
 const send=(data=packet,extra={})=>listener({origin:'null',source,data,...extra});
 send(packet,{origin:'https://outside.test'});send(packet,{source:{}});send({...packet,experiment_id:'foreign'});send({...packet,op:'run.cancel'});
 assert.deepEqual(opened,[]);send();await Promise.resolve();assert.deepEqual(opened,[['study','report']]);
 send({type:'supersurfer:block:capabilities',request_id:'probe'});assert.ok(replies.some(p=>p.request_id==='probe'&&p.supported));
 assert.ok(replies.some(p=>p.error?.includes('limited to this project')));cleanup();assert.equal(listener,null);
});
