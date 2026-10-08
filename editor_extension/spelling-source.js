import nspell from 'nspell';
import {latexWords} from '../ui/latex-prose.js';
import fs from 'node:fs';
import path from 'node:path';
export function activateSpelling(vscode,context){
 const directory=context.extensionPath,spell=nspell(fs.readFileSync(path.join(directory,'dictionary.aff')),fs.readFileSync(path.join(directory,'dictionary.dic')));
 const diagnostics=vscode.languages.createDiagnosticCollection('latex-spelling'),timers=new Map();
 const eligible=doc=>/\.(tex|latex)$/i.test(doc.fileName)&&doc.languageId==='latex';
 function check(doc){if(doc.isClosed||!eligible(doc))return;const config=vscode.workspace.getConfiguration('supersurfer');
  if(!config.get('latexSpellcheck',true)){diagnostics.delete(doc.uri);return;}
  const custom=new Set(config.get('dictionary',[]).map(word=>word.toLowerCase())),rows=[];
  for(const item of latexWords(doc.getText())){if(custom.has(item.word.toLowerCase())||spell.correct(item.word))continue;
   const marker=new vscode.Diagnostic(new vscode.Range(doc.positionAt(item.offset),doc.positionAt(item.offset+item.length)),'Unknown word: '+item.word,vscode.DiagnosticSeverity.Information);marker.source='Spelling';marker.code=item.word;rows.push(marker);if(rows.length>=100)break;}
  diagnostics.set(doc.uri,rows);
 }
 function schedule(doc){if(!eligible(doc))return;clearTimeout(timers.get(doc.uri.toString()));timers.set(doc.uri.toString(),setTimeout(()=>{timers.delete(doc.uri.toString());check(doc);},450));}
 context.subscriptions.push(diagnostics,vscode.workspace.onDidOpenTextDocument(schedule),vscode.workspace.onDidChangeTextDocument(event=>schedule(event.document)),vscode.workspace.onDidCloseTextDocument(doc=>{clearTimeout(timers.get(doc.uri.toString()));timers.delete(doc.uri.toString());diagnostics.delete(doc.uri);}),vscode.workspace.onDidChangeConfiguration(event=>{if(event.affectsConfiguration('supersurfer'))for(const doc of vscode.workspace.textDocuments)schedule(doc);}),{dispose(){for(const timer of timers.values())clearTimeout(timer);}});
 context.subscriptions.push(vscode.languages.registerCodeActionsProvider('latex',{provideCodeActions(doc,range,ctx){const actions=[];for(const diagnostic of ctx.diagnostics.filter(d=>d.source==='Spelling'))for(const text of spell.suggest(diagnostic.code).slice(0,5)){const action=new vscode.CodeAction('Change to “'+text+'”',vscode.CodeActionKind.QuickFix);action.diagnostics=[diagnostic];action.edit=new vscode.WorkspaceEdit();action.edit.replace(doc.uri,diagnostic.range,text);actions.push(action);}return actions;}},{providedCodeActionKinds:[vscode.CodeActionKind.QuickFix]}));
 for(const doc of vscode.workspace.textDocuments)schedule(doc);
}
