// Zoom follows the focused pane; only an unfocused workspace uses app zoom.
export function installPanelZoom({editorFor,globalZoom}) {
 const scales=new WeakMap();
 function zoom(delta,target=document.activeElement){
  const pane=target?.closest?.('[data-live-tile],#chat-panel');
  if(!pane){globalZoom(delta);return;}
  const pdf=pane.querySelector('[data-pdf="'+(delta>0?'zoom-in':'zoom-out')+'"]');
  if(pdf&&delta){pdf.click();return;}
  if(delta===0&&pane.querySelector('[data-pdf-zoom]')){const select=pane.querySelector('[data-pdf-zoom]');select.value='fit';select.dispatchEvent(new Event('change',{bubbles:true}));return;}
  const editor=editorFor(pane.dataset.tileKind);
  if(editor?.command(delta===0?'zoom-reset':delta>0?'zoom-in':'zoom-out'))return;
  const value=delta===0?1:Math.max(.65,Math.min(2,(scales.get(pane)||1)+delta*.1));scales.set(pane,value);
  const body=pane.querySelector('.page-tile-body')||pane;body.style.setProperty('--panel-text-scale',String(value));body.classList.add('panel-text-zoom');
 }
 function key(event,target){if(!(event.metaKey||event.ctrlKey)||event.altKey||!['+','=','-','0'].includes(event.key))return;event.preventDefault();event.stopImmediatePropagation();zoom(event.key==='0'?0:event.key==='-'?-1:1,target||event.target);}
 document.addEventListener('keydown',key,true);
 window.addEventListener('supersurfer-panel-zoom',event=>zoom(event.detail.delta,event.detail.target));
 return {zoom,key};
}
