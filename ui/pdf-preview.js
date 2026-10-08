/* A local, selectable PDF view. Compilation and agent messaging belong to callers. */
let pdfLibrary;
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sameOriginURL=value=>{const url=new URL(value,location.href);if(url.origin!==location.origin||!['http:','https:'].includes(url.protocol))throw new Error('PDF previews must come from this workspace.');return url.href;};
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));

export function createPdfPreview(options={}) {
 let root=null,record=null,document=null,loadingTask=null,renderTask=null,textLayer=null,observer=null,abort=null;
 let epoch=0,renderEpoch=0,page=1,scale='fit',error='',loading=false,selection=null,width=0,height=0,resizeTimer=null;
 const key=value=>value?.build_id||value?.pdf_url||value?.url||'';
 const current=token=>root&&token===epoch;
 const disposeTask=task=>{try{task?.destroy()?.catch(()=>{});}catch{}};
 const controls=()=>root?.querySelector('.pdf-controls');
 async function library(){pdfLibrary??=import('/vendor/pdfjs/pdf.mjs').then(module=>{module.GlobalWorkerOptions.workerSrc='/vendor/pdfjs/pdf.worker.mjs';return module;}).catch(error=>{pdfLibrary=null;throw error;});return pdfLibrary;}
 function showStatus(){if(!root)return;
  const status=root.querySelector('.pdf-status');status.classList.toggle('error',!!error);status.hidden=!error&&!loading&&(!record?.stale||options.showStaleStatus===false);
  status.textContent=error|| (loading?'Loading PDF…':record?.stale?'Showing the last compiled PDF. Source files or the latest build may differ.':'');
  const empty=root.querySelector('.pdf-empty');empty.hidden=!!document||loading;empty.innerHTML=error?`<strong>PDF preview unavailable</strong><span>${escape(error)}</span><button type="button" data-pdf="retry">Retry</button>`:'<strong>Your compiled document</strong><span>Compile saved source to see a PDF here. Select text in the PDF to discuss it with your agent.</span>';
  root.querySelector('[data-pdf-page]').value=page;root.querySelector('[data-pdf-page]').max=document?.numPages||1;root.querySelector('.pdf-page-count').textContent='/ '+(document?.numPages||'—');
  for(const button of controls().querySelectorAll('button,input,select'))button.disabled=!document||loading;
  root.querySelector('[data-pdf="previous"]').disabled=!document||loading||page<=1;root.querySelector('[data-pdf="next"]').disabled=!document||loading||page>=document.numPages;
  root.querySelector('[data-pdf-zoom]').value=String(scale);
  const download=root.querySelector('.pdf-download');let href='';try{if(record?.download_url||record?.pdf_url||record?.url)href=sameOriginURL(record.download_url||record.pdf_url||record.url);}catch{}
  download.hidden=!href;download.href=href||'#';download.download=(record?.source_path||record?.main_file||'document').split('/').at(-1).replace(/\.tex$/i,'')+'.pdf';
  root.querySelector('.pdf-source').textContent=record?.title||record?.source_path||record?.main_file||'PDF preview';
  const diagnostics=root.querySelector('.pdf-diagnostics'),items=Array.isArray(record?.diagnostics)?record.diagnostics:[];diagnostics.hidden=!items.length;
  diagnostics.innerHTML=items.slice(0,30).map(item=>`<button type="button" data-pdf-diagnostic="${items.indexOf(item)}" ${!item.path||!options.onSource?'disabled':''}><span>${escape(item.path||item.severity||'Build')}${item.line?':'+Number(item.line):''}</span>${escape(item.message||'')}</button>`).join('');
 }
 function clearSelection(removeRange=false){if(removeRange&&root?.contains(window.getSelection()?.anchorNode))window.getSelection()?.removeAllRanges();selection=null;root?.querySelector('.pdf-selection')?.setAttribute('hidden','');}
 function updateSelection(){if(!root||!document)return;const selected=window.getSelection(),layer=root.querySelector('.textLayer');
  if(!selected?.rangeCount||selected.isCollapsed||!layer?.contains(selected.anchorNode)||!layer.contains(selected.focusNode)){clearSelection();return;}
  const text=selected.toString().trim();if(!text){clearSelection();return;}
  selection={source:'pdf',build_id:record.build_id,source_path:record.source_path||record.main_file,page,text:text.slice(0,16000),...(text.length>16000?{truncated:true}:{})};
  const button=root.querySelector('.pdf-selection');button.hidden=!options.onSelection;button.title=`Add selected PDF text from page ${page} to your agent message (⌘/Ctrl I)`;
 }
 function askSelection(){if(selection&&options.onSelection)Promise.resolve(options.onSelection({...selection})).catch(failure=>{error=failure.message||String(failure);showStatus();});}
 async function draw(){if(!document||!root)return;const mounted=epoch,request=++renderEpoch;renderTask?.cancel();textLayer?.cancel();renderTask=null;textLayer=null;clearSelection(true);
  try{const pdfPage=await document.getPage(page);if(!current(mounted)||request!==renderEpoch)return;
   const viewport=root.querySelector('.pdf-viewport'),natural=pdfPage.getViewport({scale:1}),factor=scale==='fit'?clamp((viewport.clientWidth-36)/natural.width,.2,3):scale==='page'?clamp(Math.min((viewport.clientWidth-36)/natural.width,(viewport.clientHeight-30)/natural.height),.2,3):Number(scale),view=pdfPage.getViewport({scale:factor});
   const stage=root.querySelector('.pdf-sheet');stage.style.width=view.width+'px';stage.style.height=view.height+'px';stage.style.setProperty('--total-scale-factor',view.scale);stage.dataset.page=page;
   const canvas=window.document.createElement('canvas'),layer=window.document.createElement('div');layer.className='textLayer';stage.replaceChildren(canvas,layer);stage.hidden=false;
   const density=Math.min(devicePixelRatio||1,2),ratio=Math.min(density,Math.sqrt(16_000_000/(view.width*view.height)));canvas.width=Math.floor(view.width*ratio);canvas.height=Math.floor(view.height*ratio);canvas.style.width=view.width+'px';canvas.style.height=view.height+'px';
   const lib=await library();if(!current(mounted)||request!==renderEpoch)return;
   renderTask=pdfPage.render({canvas,viewport:view,transform:ratio!==1?[ratio,0,0,ratio,0,0]:null,annotationMode:lib.AnnotationMode.DISABLE});
   textLayer=new lib.TextLayer({textContentSource:pdfPage.streamTextContent(),container:layer,viewport:view});
   await Promise.all([renderTask.promise,textLayer.render()]);if(!current(mounted)||request!==renderEpoch)return;renderTask=null;error='';showStatus();
  }catch(failure){if(current(mounted)&&request===renderEpoch&&!['RenderingCancelledException','AbortException'].includes(failure.name)){error=failure.message||String(failure);showStatus();}}
 }
 async function load(next,{force=false}={}) {
  if(!root)return false;
  if(!force&&record&&key(next)===key(record)&&(document||loading)){record={...next};showStatus();return !!document;}
  const previousSource=record?.source_path||record?.main_file;record={...next};const token=++epoch;++renderEpoch;abort?.abort();renderTask?.cancel();textLayer?.cancel();disposeTask(loadingTask);disposeTask(document?.loadingTask);document=null;renderTask=textLayer=loadingTask=null;clearSelection(true);
  if(previousSource!==(record.source_path||record.main_file))page=1;
  root.querySelector('.pdf-sheet').hidden=true;root.querySelector('.pdf-sheet').replaceChildren();error='';loading=false;
  const url=record.pdf_url||record.url;if(!url){showStatus();return false;}
  loading=true;showStatus();abort=new AbortController();
  try{const safeURL=sameOriginURL(url),lib=await library();if(!current(token))return false;
   const bytes=options.loadBytes?await options.loadBytes(safeURL,{signal:abort.signal}):await fetch(safeURL,{signal:abort.signal,credentials:'same-origin'}).then(async response=>{if(!response.ok)throw new Error(`PDF could not be loaded (${response.status}). Refresh the build and try again.`);return new Uint8Array(await response.arrayBuffer());});
   if(!current(token))return false;
   loadingTask=lib.getDocument({data:bytes instanceof Uint8Array?bytes:new Uint8Array(bytes),cMapUrl:'/vendor/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/vendor/pdfjs/standard_fonts/',wasmUrl:'/vendor/pdfjs/wasm/',iccUrl:'/vendor/pdfjs/iccs/',isEvalSupported:false,enableXfa:false});
   loadingTask.onPassword=()=>{disposeTask(loadingTask);if(current(token)){loading=false;error='Password-protected PDFs cannot be previewed here.';showStatus();}};
   const pdf=await loadingTask.promise;if(!current(token)){disposeTask(pdf.loadingTask);return false;}document=pdf;loadingTask=null;page=clamp(page,1,pdf.numPages);loading=false;showStatus();await draw();return !error;
  }catch(failure){if(current(token)&&failure.name!=='AbortError'){loading=false;error=failure.message||String(failure);showStatus();}return false;}
 }
 function changePage(value){if(!document)return;page=clamp(Math.round(Number(value)||1),1,document.numPages);root.querySelector('.pdf-viewport').scrollTop=0;showStatus();draw();}
 function click(event){const button=event.target.closest('[data-pdf],[data-pdf-diagnostic]');if(!button)return;
  if(button.dataset.pdfDiagnostic!==undefined){const item=record?.diagnostics?.[Number(button.dataset.pdfDiagnostic)];if(item?.path)options.onSource?.({path:item.path,line:item.line||1,column:item.column||1});return;}
  switch(button.dataset.pdf){case'previous':changePage(page-1);break;case'next':changePage(page+1);break;case'ask':askSelection();break;case'retry':load(record,{force:true});break;case'zoom-out':case'zoom-in':{const sheet=root.querySelector('.pdf-sheet'),base=Number(sheet.style.getPropertyValue('--total-scale-factor'))||1;scale=String(clamp(base*(button.dataset.pdf==='zoom-in'?1.2:1/1.2),.2,3));const select=root.querySelector('[data-pdf-zoom]');if(![...select.options].some(o=>o.value===scale))select.add(new Option(Math.round(Number(scale)*100)+'%',scale));showStatus();draw();break;}}
 }
 function keydown(event){const active=window.document.activeElement;if(active&&!root?.contains(active)&&active.matches('input,textarea,[contenteditable=true]'))return;if(event.key==='Escape'&&selection){clearSelection();window.getSelection()?.removeAllRanges();}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='i'&&selection){event.preventDefault();askSelection();}}
 function unmount(){++epoch;++renderEpoch;clearTimeout(resizeTimer);abort?.abort();renderTask?.cancel();textLayer?.cancel();disposeTask(loadingTask);disposeTask(document?.loadingTask);observer?.disconnect();observer=null;window.document.removeEventListener('selectionchange',updateSelection);window.document.removeEventListener('keydown',keydown);if(root){root.onclick=null;root.onchange=null;root.replaceChildren();root.classList.remove('pdf-preview');}root=null;record=null;document=loadingTask=renderTask=textLayer=null;selection=null;}
 return {async mount(element,next={}){if(root===element&&root.querySelector('.pdf-viewport'))return load(next);unmount();root=element;page=1;scale='fit';root.classList.add('pdf-preview');root.innerHTML=`<header class="pdf-controls"><span class="pdf-source">PDF preview</span><div class="pdf-navigation"><button type="button" data-pdf="previous" aria-label="Previous PDF page">‹</button><input type="number" min="1" value="1" data-pdf-page aria-label="PDF page"><span class="pdf-page-count">/ —</span><button type="button" data-pdf="next" aria-label="Next PDF page">›</button></div><div class="pdf-zoom"><button type="button" data-pdf="zoom-out" aria-label="Zoom PDF out">−</button><select data-pdf-zoom aria-label="PDF zoom"><option value="fit">Fit width</option><option value="page">Fit page</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.5">150%</option><option value="2">200%</option></select><button type="button" data-pdf="zoom-in" aria-label="Zoom PDF in">+</button></div><a class="pdf-download" download hidden title="Download compiled PDF">↓</a></header><div class="pdf-status" role="status" hidden></div><div class="pdf-diagnostics" hidden></div><div class="pdf-viewport" tabindex="0" aria-label="PDF document"><div class="pdf-empty"></div><div class="pdf-sheet" hidden></div></div><button type="button" class="pdf-selection" data-pdf="ask" hidden>Ask about selection ↗</button>`;root.onclick=click;root.onchange=event=>{if(event.target.hasAttribute('data-pdf-page'))changePage(event.target.value);if(event.target.hasAttribute('data-pdf-zoom')){scale=event.target.value;draw();}};root.querySelector('.pdf-selection').onpointerdown=event=>event.preventDefault();window.document.addEventListener('selectionchange',updateSelection);window.document.addEventListener('keydown',keydown);width=root.clientWidth;height=root.clientHeight;observer=new ResizeObserver(()=>{if(!root)return;const changed=Math.abs(root.clientWidth-width)>=2||(scale==='page'&&Math.abs(root.clientHeight-height)>=2);width=root.clientWidth;height=root.clientHeight;if(!changed)return;clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(document&&['fit','page'].includes(scale))draw();},120);});observer.observe(root);return load(next);},setDocument:load,unmount,dispose:unmount,page(){return page;}};
}
