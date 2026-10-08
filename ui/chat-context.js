const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const contextMarkup=rows=>(rows||[]).map(row=>`<details class="message-context"><summary>${esc(row.label)}</summary><div>${esc(row.absolute_path||row.path||'')}</div><pre>${esc(row.text)}</pre></details>`).join('');
export function createChatContext({scope,onChange,onPickFile,onError}){
 const drafts=new Map(),container=document.createElement('div');container.className='chat-context-chips';document.querySelector('#chat-input').before(container);
 const add=document.createElement('button');add.type='button';add.className='chat-attach-file';add.title='Attach a workspace file';add.setAttribute('aria-label','Attach a workspace file');add.textContent='+';document.querySelector('#chat-form .composer-footer')?.prepend(add);
 // Composer styles differ by version; keep the control beside the chips as fallback.
 if(!add.isConnected)container.before(add);
 const get=()=>drafts.get(scope())||[];
 const dialog=document.createElement('dialog');dialog.className='modal chat-context-dialog';document.body.append(dialog);
 function render(){container.innerHTML=get().map(row=>`<span class="chat-context-chip"><button type="button" data-context-open="${esc(row.id)}" title="${esc(row.path)}">${esc(row.label)}</button><button type="button" data-context-remove="${esc(row.id)}" aria-label="Remove ${esc(row.label)}">×</button></span>`).join('');onChange?.();}
 container.onclick=event=>{const id=event.target.closest('[data-context-open]')?.dataset.contextOpen,remove=event.target.closest('[data-context-remove]')?.dataset.contextRemove;if(remove){drafts.set(scope(),get().filter(row=>row.id!==remove));render();}if(id){const row=get().find(row=>row.id===id);if(row){dialog.innerHTML=`<div class="modal-body"><strong>${esc(row.label)}</strong><p>${esc(row.path)}</p><pre>${esc(row.text)}</pre><button type="button" class="button">Close</button></div>`;dialog.querySelector('button').onclick=()=>dialog.close();dialog.showModal();}}};
 add.onclick=()=>Promise.resolve(onPickFile()).catch(onError);
 return {render,get,add(row,key=scope()){const rows=drafts.get(key)||[];if(!key)throw new Error('Choose an agent conversation first.');if(rows.length>=8)throw new Error('Attach up to eight items per message.');if(rows.some(old=>old.kind===row.kind&&old.path===row.path&&old.text===row.text))return;drafts.set(key,[...rows,{...row,id:crypto.randomUUID()}]);render();},sent(key,ids){drafts.set(key,(drafts.get(key)||[]).filter(row=>!ids.includes(row.id)));render();},setDisabled(value){add.disabled=value;}};
}
