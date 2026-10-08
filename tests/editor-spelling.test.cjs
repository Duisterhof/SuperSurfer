const test=require('node:test'),assert=require('node:assert/strict');
test('LaTeX checks prose and preserves offsets, excluding math, identifiers and code',async()=>{
 const {latexWords,latexProse}=await import('../ui/latex-prose.js');
 const source=String.raw`\documentclass{article}
\usepackage{madeupstyle}
\begin{document}
This is misspeled prose and \textbf{bold misspeled words}.
\section{Another headding} \citep{madeupkey} \label{madeuplabel}
$madeupmath + x$ and \(othermath\) and \[displaymath\].
\href{https://madeupurl.invalid}{Readable headding}
\begin{align} madeupmath &= x \\ y&=z \end{align}
\begin{minted}{python} print('madeupcode') \end{minted}
\verb|madeupcode| \includegraphics[width=10cm]{madeuppath}
% ignoredcommment
\end{document}`;
 const words=latexWords(source);const values=words.map(w=>w.word);
 assert.ok(values.includes('misspeled'));assert.ok(values.includes('headding'));assert.ok(values.includes('Readable'));
 for(const word of ['madeupstyle','madeupkey','madeuplabel','madeupmath','othermath','displaymath','madeupcode','madeuppath','ignoredcommment','document','python','textbf','section'])assert.ok(!values.includes(word),word);
 for(const item of words)assert.equal(source.slice(item.offset,item.offset+item.length),item.word);
 assert.equal(latexProse(source).length,source.length);
});
test('Coordination stays compact without swallowing a direct user turn',async()=>{
 const {groupChatChecks,renderChatTimeline}=await import('../ui/chat-checks.js');
 const messages=[{id:'u',role:'user',text:'Explain the run'},{id:'s',role:'system',agent_sender:{name:'Manager'},steering:true,turn_id:'t',text:'Cached connectivity failure.'},{id:'r',role:'assistant',turn_id:'t',text:'Your requested explanation.'}];
 const rows=groupChatChecks(messages);assert.equal(rows[1].category,'coordination');assert.equal(rows[2].type,'message');
 const markup=renderChatTimeline(messages,{renderMessage:m=>'<p>'+m.text+'</p>',escape:String,date:String});assert.match(markup,/Agents · 1 update/);assert.match(markup,/Manager/);assert.doesNotMatch(markup,/<details[^>]+ open/);
 const chain=groupChatChecks([{...messages[1],assignment:true,steering:false},messages[2],{id:'u2',role:'user',text:'New request'}, {id:'r2',role:'assistant',turn_id:'t',text:'Direct reply'}]);assert.equal(chain[0].checks[0].messages.length,2);assert.equal(chain[2].type,'message');
});
test('LaTeX save on another page coalesces while a build runs and ignores source code',async()=>{
 const {createLatexAutoCompile}=await import('../ui/latex-auto.js');let calls=[],reads=0,release,settings={latex_auto_compile:true};
 const held=new Promise(resolve=>release=resolve);global.localStorage={getItem:()=>null};
 const compiler=createLatexAutoCompile({editorSettings:{get:()=>settings},api:async()=>{reads++;await held;return {blocks:[{node_id:'latex',main_file:'paper/main.tex'}],capabilities:{available:true},builds:[]};},action:async(op,params)=>{calls.push(params);return {build_id:'build'};}});
 assert.equal(compiler.saved({projectId:'p1',path:'main.py'}),undefined);assert.equal(reads,0);
 const first=compiler.saved({projectId:'p1',experimentId:'t1',path:'paper/main.tex'});compiler.saved({projectId:'p1',experimentId:'t1',path:'paper/references.bib'});release();await first;
 assert.equal(calls.length,1);assert.equal(calls[0].experiment_id,'t1');assert.equal(calls[0].main_file,'paper/main.tex');
 settings.latex_auto_compile=false;await compiler.saved({projectId:'p1',path:'main.tex'});assert.equal(calls.length,1);
});
