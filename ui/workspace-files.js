export const isArtifact=path=>String(path||'').startsWith('artifact:');
export function workspacePath(repo,projectId,path=''){
 const root=String(repo||'').replace(/\/$/,'');
 return isArtifact(path)?root+'/.SuperSurfer/projects/'+projectId+'/artifacts/'+path.slice(9):root+(path?'/'+path:'');
}
