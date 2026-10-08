'use strict';
// Monaco and its language workers ship with the app. No CDN or remote loader.
const fs = require('node:fs');
const path = require('node:path');
const esbuild = require('esbuild');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'ui/vendor/monaco');
fs.mkdirSync(output, {recursive:true});
const base = {absWorkingDir:root, bundle:true, format:'esm', platform:'browser', target:'es2022', minify:true, legalComments:'linked', loader:{'.ttf':'file'}, assetNames:'[name]-[hash]'};
esbuild.buildSync({...base, stdin:{contents:`
  globalThis.MonacoEnvironment = {
    getWorker(_moduleId, label) {
      const language = ({json:'json',css:'css',scss:'css',less:'css',html:'html',handlebars:'html',razor:'html',typescript:'ts',javascript:'ts'})[label] || 'editor';
      return new Worker(new URL(language + '.worker.js', import.meta.url), {type:'module'});
    }
  };
  export * from 'monaco-editor';
`,resolveDir:root,sourcefile:'supersurfer-monaco.js'}, outfile:path.join(output,'editor.js')});
for (const [name,entry] of Object.entries({editor:'editor/editor.worker',json:'language/json/json.worker',css:'language/css/css.worker',html:'language/html/html.worker',ts:'language/typescript/ts.worker'})) {
  esbuild.buildSync({...base,entryPoints:[path.join(root,'node_modules/monaco-editor/esm/vs',entry+'.js')],outfile:path.join(output,name+'.worker.js')});
}
for (const name of ['LICENSE','ThirdPartyNotices.txt']) {
  fs.copyFileSync(path.join(root,'node_modules/monaco-editor',name),path.join(output,name));
}
const version = JSON.parse(fs.readFileSync(path.join(root,'node_modules/monaco-editor/package.json'),'utf8')).version;
fs.writeFileSync(path.join(output,'version.json'),JSON.stringify({monaco:version})+'\n');
console.log('Bundled Monaco editor and local language workers.');
const spelling=path.join(root,'ui/vendor/spelling');fs.mkdirSync(spelling,{recursive:true});
esbuild.buildSync({...base,entryPoints:[path.join(root,'ui/latex-spelling.worker.js')],outfile:path.join(spelling,'worker.js')});
for(const name of ['index.aff','index.dic','license'])fs.copyFileSync(path.join(root,'node_modules/dictionary-en',name),path.join(spelling,name));
esbuild.buildSync({absWorkingDir:root,bundle:true,format:'cjs',platform:'node',target:'node20',minify:true,legalComments:'linked',entryPoints:['editor_extension/spelling-source.js'],outfile:'editor_extension/spelling.cjs'});
for(const [from,to]of [['index.aff','dictionary.aff'],['index.dic','dictionary.dic'],['license','DICTIONARY-LICENSE']])fs.copyFileSync(path.join(root,'node_modules/dictionary-en',from),path.join(root,'editor_extension',to));
