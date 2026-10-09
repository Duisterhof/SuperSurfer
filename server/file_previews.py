"""Short-lived, scoped repository media capabilities using safe file descriptors."""
import mimetypes,os,secrets,threading,time
from pathlib import Path
from urllib.parse import quote
from .code_editor import _parts,_regular,FILE_FLAGS
from .surfboards import SurfboardError

class FilePreviews:
    def __init__(self,service):self.service=service;self.lock=threading.RLock();self.tokens={}
    def create(self,project,path):
        mime=mimetypes.guess_type(path)[0] or ''
        if not mime.startswith(('image/','video/','audio/')):raise SurfboardError('Choose an image, video or audio file')
        mapped,relative=self.service.code_file_target(project,path)
        parts=_parts(relative)
        with self.service.code._parent(mapped,parts) as (_,parent):
            fd=os.open(parts[-1],FILE_FLAGS,dir_fd=parent)
            try:_regular(fd)
            finally:os.close(fd)
        token=secrets.token_urlsafe(32)
        with self.lock:
            now=time.time();self.tokens={key:value for key,value in self.tokens.items() if value['expires']>now}
            if len(self.tokens)>=4096:self.tokens.pop(next(iter(self.tokens)))
            self.tokens[token]={'project_id':project['id'],'repo':project['repo'],'path':path,'mime':mime,'expires':now+3600}
        return {'url':'/file-preview/'+token+'/'+quote(Path(path).name,safe=''),'mime':mime,'path':path}
    def payload(self,token,filename):
        with self.lock:row=self.tokens.get(token)
        if not row or row['expires']<time.time() or filename!=Path(row['path']).name:raise SurfboardError('Media preview expired; reopen the file',404)
        project=self.service.lookup('projects',row['project_id'])
        if project['repo']!=row['repo']:raise SurfboardError('The project folder changed; reopen this file',409)
        mapped,relative=self.service.code_file_target(project,row['path']);parts=_parts(relative)
        with self.service.code._parent(mapped,parts) as (_,parent):fd=os.open(parts[-1],FILE_FLAGS,dir_fd=parent)
        try:
            info=_regular(fd);stream=os.fdopen(fd,'rb');fd=None
            return {'stream':stream,'size':info.st_size,'mime':row['mime'],'filename':filename,'csp':"sandbox; default-src 'none'"}
        finally:
            if fd is not None:os.close(fd)
