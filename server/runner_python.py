"""Discover/verify the standalone runner interpreter, separate from project Python."""
import json
import shlex
import subprocess
import sys

from .compute import ComputeError, SSH_OPTIONS

_VERSION = 'import json,sys; print(json.dumps({"path":sys.executable,"version":list(sys.version_info[:3])}))'
# This discovery program deliberately works with Python 3.6 system installations.
_DISCOVER = r'''
import getpass,json,os,pathlib,shutil,subprocess,sys
if sys.version_info >= (3,9):
 print(json.dumps({'path':sys.executable,'version':list(sys.version_info[:3])}));sys.exit(0)
home=str(pathlib.Path.home());user=getpass.getuser()
candidates=[shutil.which('python3.'+str(v)) for v in range(14,8,-1)]
candidates += [base+'/'+env+'/bin/python' for base in [home,'/data/'+user] for env in ['miniforge3','miniconda3','anaconda3']]
seen=set();tried=0
for candidate in candidates:
 if not candidate or candidate in seen or not os.path.isfile(candidate) or not os.access(candidate,os.X_OK):continue
 seen.add(candidate);tried+=1
 if tried>8:break
 try:
  p=subprocess.run([candidate,'-I','-c',VERSION],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=2)
  result=json.loads(p.stdout)
  if p.returncode==0 and result['version'] >= [3,9,0]:print(json.dumps(result));sys.exit(0)
 except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):pass
print(json.dumps({'error':'No Python 3.9+ runner interpreter found. Select an existing Python 3.9+ executable or create a separate environment for the runner. AML itself does not need installing on the host.'}))
'''

def resolve_runner_python(target, configured):
    if not isinstance(configured,str) or not configured.strip() or len(configured)>4096 or any(ord(c)<32 for c in configured) or configured.startswith('-'):
        raise ComputeError('Runner Python must be auto or an executable name/path')
    auto=configured=='auto'
    script=('VERSION = '+repr(_VERSION)+'\n'+_DISCOVER) if auto else _VERSION
    executable=('python3' if target else sys.executable) if auto else configured
    argv=[executable,'-I','-c',script]
    command=['ssh',*SSH_OPTIONS,'--',target,shlex.join(argv)] if target else argv
    try:
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=25)
        if result.returncode or len(result.stdout)>16000:
            raise ComputeError('Runner Python check failed: '+(result.stderr.strip()[-1000:] or 'No interpreter response'),503)
        value=json.loads(result.stdout)
        if value.get('error'):raise ComputeError(value['error'],409)
        version=value.get('version')
        if not isinstance(version,list) or len(version)!=3 or any(type(v) is not int for v in version) or not isinstance(value.get('path'),str) or not value['path'].startswith('/'):
            raise ValueError('Invalid interpreter report')
        if version<[3,9,0]:raise ComputeError('Runner Python '+'.'.join(map(str,version))+' is too old; AML needs Python 3.9+. Choose auto or a compatible executable. The project training environment is independent.',409)
        return value['path']
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ComputeError('Cannot verify runner Python on this host: '+str(exc),503) from exc
    except (ValueError,TypeError) as exc:
        if isinstance(exc,ComputeError):raise
        raise ComputeError('Host returned an invalid runner Python report',503) from exc
