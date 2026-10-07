'use strict';
// Builds a standalone design study. Its bridge is a local simulation; no host,
// account, app API or credential can be contacted from this preview.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const target=process.argv[2] || path.join(root,'dist','login-designs.html');
let html=fs.readFileSync(path.join(root,'desktop/setup.html'),'utf8');
const css=fs.readFileSync(path.join(root,'desktop/setup.css'),'utf8');
const script=fs.readFileSync(path.join(root,'desktop/setup.js'),'utf8');
html=html.replace(/<meta http-equiv="Content-Security-Policy"[^>]+>/,'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'">');
html=html.replace('<link rel="stylesheet" href="setup.css">',`<style>${css}
.preview-bar{position:relative;z-index:3;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:18px 26px;font-size:11px;color:var(--muted)}.preview-controls{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.preview-bar button{width:auto;min-height:32px;margin:0;padding:7px 14px;border-radius:20px;font-size:11px;box-shadow:none}.preview-bar button[aria-pressed="false"]{background:var(--field);color:var(--ink);border-color:var(--line)}.preview-bar label{display:flex;gap:6px;align-items:center;margin:0 0 0 10px;font-size:11px}.preview-bar input{width:14px;min-height:14px;margin:0;accent-color:var(--accent)}main{min-height:calc(100vh - 110px)}@media(max-width:760px){.preview-bar{padding:14px 22px}.preview-bar>span{width:100%}}
</style>`);
html=html.replace('<div class="titlebar"></div>',`<nav class="preview-bar" aria-label="Design preview"><span>SuperSurfer · Design studies · Preview only</span><div class="preview-controls"><button type="button" data-preview-design="glass" aria-pressed="true">01 Tidal glass</button><button type="button" data-preview-design="observatory" aria-pressed="false">02 Observatory</button><button type="button" data-preview-design="paper" aria-pressed="false">03 Field notes</button><label><input type="checkbox" id="solid-preview">Reduce transparency</label></div></nav>`);
html=html.replace('<script src="setup.js"></script>',`<script>
window.superSurferDesktop={configuration:async()=>({mode:'remote',target:'tulip'}),listHosts:async()=>({hosts:[{name:'Tulip',target:'tulip'},{name:'Trinity',target:'trinity'}]}),onStatus:()=>()=>{},connect:async()=>({error:'Design preview only. No connection was made.'})};
document.querySelectorAll('[data-preview-design]').forEach(button=>button.addEventListener('click',()=>{document.body.dataset.design=button.dataset.previewDesign;document.querySelectorAll('[data-preview-design]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));}));
document.querySelector('#solid-preview').addEventListener('change',event=>document.body.dataset.solid=String(event.target.checked));
${script}</script>`);
fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,html);console.log(target);
