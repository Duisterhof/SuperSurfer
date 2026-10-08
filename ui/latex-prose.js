/* Preserve offsets while excluding TeX syntax, identifiers and executable/math regions. */
const opaqueEnvironments=new Set(['equation','equation*','align','align*','alignat','alignat*','gather','gather*','multline','multline*','displaymath','math','verbatim','Verbatim','lstlisting','minted','tikzpicture','luacode','luacode*']);
const opaqueCommands=/^(?:cite\w*|[cCvV]ref|[cCpPtTaAeE]ref|ref|eqref|autoref|pageref|label|url|path|includegraphics|input|include|bibliography|bibliographystyle|addbibresource|documentclass|usepackage|RequirePackage|begin|end|newcommand|renewcommand|providecommand|def|newenvironment|renewenvironment|setlength|addtolength|hypersetup|lstset|geometry|vspace|hspace|color|definecolor|textcolor)$/;
export function latexProse(source){
  const out=Array.from(source,()=> ' '); // Work in UTF-16 below: diagnostic offsets must match Monaco.
  out.length=source.length;for(let i=0;i<source.length;i++)out[i]=source[i];
  const mask=(a,b)=>{for(let i=a;i<b;i++)if(source[i]!=='\n'&&source[i]!=='\r')out[i]=' ';};
  const escaped=i=>{let n=0;while(i>0&&source[--i]==='\\')n++;return n%2===1;};
  const balanced=(i,open='{',close='}')=>{let level=1,j=i+1;for(;j<source.length;j++){if(escaped(j))continue;if(source[j]===open)level++;if(source[j]===close&&!--level)return j+1;}return source.length;};
  let i=0;
  while(i<source.length){
    if(source[i]==='%'&&!escaped(i)){const end=source.indexOf('\n',i);mask(i,end<0?source.length:end);i=end<0?source.length:end;continue;}
    if(source[i]==='$'&&!escaped(i)){const delimiter=source.startsWith('$$',i)?'$$':'$';let end=i+delimiter.length;while(end<source.length&&!(source.startsWith(delimiter,end)&&!escaped(end)))end++;end=Math.min(source.length,end+delimiter.length);mask(i,end);i=end;continue;}
    if(source[i]!=='\\'){i++;continue;}
    if(source[i+1]==='('||source[i+1]==='['){const close=source[i+1]==='('? '\\)':'\\]';let end=source.indexOf(close,i+2);end=end<0?source.length:end+2;mask(i,end);i=end;continue;}
    const match=/^\\([A-Za-z@]+)\*?/.exec(source.slice(i));
    if(!match){mask(i,Math.min(i+2,source.length));i+=2;continue;}
    const command=match[1],start=i;mask(i,i+match[0].length);i+=match[0].length;
    if(command==='verb'&&source[i]&&!/\s/.test(source[i])){const end=source.indexOf(source[i],i+1);const stop=end<0?source.length:end+1;mask(start,stop);i=stop;continue;}
    while(/\s/.test(source[i]||'')&&i<source.length)i++;
    if(command==='begin'&&source[i]==='{'){
      const end=balanced(i),environment=source.slice(i+1,end-1);if(opaqueEnvironments.has(environment)){const finish=source.indexOf('\\end{'+environment+'}',end);const stop=finish<0?source.length:finish+environment.length+6;mask(start,stop);i=stop;continue;}
    }
    // Optional arguments contain layout parameters rather than prose.
    while(source[i]==='['){const end=balanced(i,'[',']');mask(i,end);i=end;while(/\s/.test(source[i]||'')&&i<source.length)i++;}
    if(opaqueCommands.test(command)||command==='href'){
      const limit=command==='href'||command==='textcolor'?1:Infinity;let count=0;
      while(source[i]==='{'&&count++<limit){const end=balanced(i);mask(i,end);i=end;while(/\s/.test(source[i]||'')&&i<source.length)i++;}
    }
  }
  // URLs, dimensions and inline code fragments are not prose.
  let result=out.join('');for(const match of result.matchAll(/https?:\/\/\S+|[A-Za-z_]+\d[A-Za-z_\d]*|\d+(?:\.\d+)?(?:pt|cm|mm|em|ex|in)\b/g))mask(match.index,match.index+match[0].length);
  return out.join('');
}
export function latexWords(source){return [...latexProse(source).matchAll(/\b[A-Za-z]+(?:['’][A-Za-z]+)?\b/g)].filter(m=>m[0].length>2&&!/^[A-Z]+$/.test(m[0])).map(m=>({word:m[0],offset:m.index,length:m[0].length}));}
