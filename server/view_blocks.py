"""Versioned reusable HTML views. Published assets are copied, never live paths."""
import io,json,mimetypes,os,re,secrets,shutil,threading,time,uuid
from pathlib import Path
from urllib.parse import quote
from .surfboards import SurfboardError
from .code_editor import _parts,_regular,FILE_FLAGS
from .project_artifacts import _sensitive

def copy_snapshot(stream,target):
    info=_regular(stream.fileno());remaining=info.st_size
    with target.open('xb') as output:
        while remaining:
            chunk=stream.read(min(1024*1024,remaining))
            if not chunk:raise SurfboardError('Asset changed during publication; retry after its writer finishes',409)
            output.write(chunk);remaining-=len(chunk)
    final=_regular(stream.fileno())
    if stream.read(1) or (final.st_size,final.st_mtime_ns,final.st_ctime_ns)!=(info.st_size,info.st_mtime_ns,info.st_ctime_ns):raise SurfboardError('Asset changed during publication; retry after its writer finishes',409)
    os.chmod(target,0o600)

class ViewBlocks:
    def __init__(self,service):
        self.service=service;self.root=service.directory/'view-blocks';self.lock=threading.RLock();self.tokens={}
    def publish(self,project,fields):
        if set(fields)-{'id','version','title','html','assets'} or not {'title','html'}<=set(fields):raise SurfboardError('Publish title, html, optional assets, and id/version for an update')
        html=fields['html'];title=fields['title'];assets=fields.get('assets',{})
        if not isinstance(html,str) or not 1<=len(html.encode())<=1024*1024:raise SurfboardError('HTML must contain 1–1048576 bytes')
        if not isinstance(title,str) or not 1<=len(title.strip())<=100:raise SurfboardError('Choose a title of 1–100 characters')
        if not isinstance(assets,dict) or len(assets)>32:raise SurfboardError('Declare at most 32 asset names mapped to repository paths')
        identity=fields.get('id') or 'block_'+uuid.uuid4().hex[:16]
        if not isinstance(identity,str) or not re.fullmatch(r'block_[a-f0-9]{16}',identity):raise SurfboardError('Choose an existing block ID or omit id for a new block')
        with self.lock:
            rows=self.service.store.get('view_blocks',{})
            old=rows.get(identity)
            if old and old['project_id']!=project['id']:raise SurfboardError('Only the publishing project can revise this block',403)
            expected=fields.get('version',0)
            if type(expected) is not int or expected!=(old['version'] if old else 0):raise SurfboardError('Block changed; list blocks and retry with its current version',409)
            if not old and len(rows)>=500:raise SurfboardError('The workspace block library is full')
            self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
            folder=self.root/uuid.uuid4().hex;folder.mkdir(mode=0o700)
            names=['index.html'];total=0
            try:
                (folder/'index.html').write_text(html,encoding='utf-8');os.chmod(folder/'index.html',0o600)
                if old and 'assets' not in fields:
                    for name in old['assets']:
                        if name=='index.html':continue
                        parts=_parts(name)
                        with self.service.code._parent({'repo':str(self.root/old['folder'])},parts) as (_,parent):fd=os.open(parts[-1],FILE_FLAGS,dir_fd=parent)
                        with os.fdopen(fd,'rb') as stream:
                            _regular(stream.fileno());target=folder.joinpath(*parts);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                            copy_snapshot(stream,target)
                        names.append(name)
                for name,source in assets.items():
                    parts=_parts(name)
                    if name=='index.html' or _sensitive(parts):raise SurfboardError('Choose an ordinary nonsecret asset name')
                    if not isinstance(source,str) or _sensitive(_parts(source.removeprefix('artifact:'))):raise SurfboardError('Do not publish credentials or private service state')
                    mapped,relative=self.service.code_file_target(project,source)
                    with self.service.code._parent(mapped,_parts(relative)) as (_,parent):fd=os.open(_parts(relative)[-1],FILE_FLAGS,dir_fd=parent)
                    with os.fdopen(fd,'rb') as stream:
                        info=_regular(stream.fileno());total+=info.st_size
                        if info.st_size>512*1024*1024 or total>1024*1024*1024:raise SurfboardError('Published assets exceed the size limit')
                        target=folder.joinpath(*parts);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                        copy_snapshot(stream,target)
                    names.append(name)
                row={'id':identity,'version':expected+1,'title':title.strip(),'project_id':project['id'],'folder':folder.name,'assets':names,'updated':time.time()}
                rows[identity]=row;self.service.store.put('view_blocks',rows)
            except BaseException:shutil.rmtree(folder);raise
            return self.public(row)
    def public(self,row):
        token=secrets.token_urlsafe(32);now=time.time()
        with self.lock:
            self.tokens={key:value for key,value in self.tokens.items() if value['expires']>now}
            if len(self.tokens)>=4096:self.tokens.pop(next(iter(self.tokens)))
            self.tokens[token]={'row':dict(row),'expires':now+3600}
        return {key:row[key] for key in ('id','version','title','project_id','updated')}|{'url':'/view-block/'+token+'/index.html'}
    def list(self):
        with self.lock:return {'blocks':[self.public(row) for row in self.service.store.get('view_blocks',{}).values()]}
    def source(self,project,identity):
        row=self.service.store.get('view_blocks',{}).get(identity)
        if not row:raise SurfboardError('Block not found',404)
        if row['project_id']!=project['id']:raise SurfboardError('Only the publishing project can edit this block',403)
        with self.lock:
            payload=self.payload(self.public(row)['url'].split('/')[2],'index.html')
            with payload['stream'] as stream:html=stream.read(1024*1024+1).decode('utf-8')
        return {**self.public(row),'html':html,'asset_names':[name for name in row['assets'] if name!='index.html'],'reuse_assets':'Omit assets when updating to preserve copied media. An explicit assets map replaces them.'}
    def open(self,identity):
        row=self.service.store.get('view_blocks',{}).get(identity)
        if not row:raise SurfboardError('Block not found; choose a published block',404)
        return self.public(row)
    def payload(self,token,name):
        with self.lock:cap=self.tokens.get(token)
        if not cap or cap['expires']<time.time():raise SurfboardError('Block preview expired; reopen the view',404)
        row=cap['row']
        if name not in row['assets']:raise SurfboardError('Asset was not published with this block',404)
        parts=_parts(name);folder=self.root/row['folder']
        # Owned immutable publication paths contain no user-controlled symlinks.
        with self.service.code._parent({'repo':str(folder)},parts) as (_,parent):fd=os.open(parts[-1],FILE_FLAGS,dir_fd=parent)
        try:
            info=_regular(fd);stream=os.fdopen(fd,'rb');fd=None
            csp="sandbox allow-scripts allow-downloads; default-src 'none'; script-src 'unsafe-inline' {block_assets}; style-src 'unsafe-inline' {block_assets}; img-src data: blob: {block_assets}; media-src blob: {block_assets}; font-src {block_assets}; frame-src https:; connect-src {block_assets}; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
            return {'stream':stream,'size':info.st_size,'mime':mimetypes.guess_type(name)[0] or 'application/octet-stream','filename':parts[-1],'csp':csp}
        finally:
            if fd is not None:os.close(fd)
