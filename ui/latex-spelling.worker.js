import nspell from 'nspell';
import {latexWords} from './latex-prose.js';
let spell;
const ready=Promise.all(['index.aff','index.dic'].map(name=>fetch('/vendor/spelling/'+name).then(response=>{if(!response.ok)throw new Error('Dictionary unavailable');return response.text();}))).then(([aff,dic])=>spell=nspell(aff,dic));

self.onmessage=async({data})=>{
 try{await ready;const custom=new Set((data.dictionary||[]).map(word=>word.toLowerCase()));
  const errors=[],suggestions=new Map();for(const item of latexWords(data.text)){if(!custom.has(item.word.toLowerCase())&&!spell.correct(item.word)){if(!suggestions.has(item.word))suggestions.set(item.word,spell.suggest(item.word).slice(0,5));errors.push({...item,suggestions:suggestions.get(item.word)});if(errors.length>=100)break;}}
  self.postMessage({id:data.id,errors});
 }catch(error){self.postMessage({id:data.id,error:error.message});}
};
