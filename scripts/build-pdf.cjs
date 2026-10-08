'use strict';
// PDF rendering and selectable text stay local, including fonts and workers.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),source=path.join(root,'node_modules/pdfjs-dist'),output=path.join(root,'ui/vendor/pdfjs');
fs.mkdirSync(output,{recursive:true});
for(const name of ['pdf.mjs','pdf.worker.mjs'])fs.copyFileSync(path.join(source,'legacy/build',name),path.join(output,name));
for(const directory of ['cmaps','standard_fonts','wasm','iccs'])fs.cpSync(path.join(source,directory),path.join(output,directory),{recursive:true});
fs.copyFileSync(path.join(source,'LICENSE'),path.join(output,'LICENSE'));
// Keep Mozilla's matching text geometry styles; the surrounding viewer is ours.
const css=fs.readFileSync(path.join(source,'web/pdf_viewer.css'),'utf8'),start=css.indexOf('.textLayer {'),end=css.indexOf('.textLayerImages {',start);
if(start<0||end<0)throw new Error('PDF.js TextLayer CSS changed; inspect before upgrading.');
fs.writeFileSync(path.join(output,'text-layer.css'),'/* Mozilla and individual contributors. Apache-2.0; see LICENSE. */\n'+css.slice(start,end));
fs.writeFileSync(path.join(output,'version.json'),JSON.stringify({pdfjs:JSON.parse(fs.readFileSync(path.join(source,'package.json'),'utf8')).version})+'\n');
console.log('Bundled PDF.js, selectable text, fonts and local worker.');
