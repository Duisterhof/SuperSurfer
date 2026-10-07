"""Bounded isolated QA campaign; never connects to the user's workspace or GPUs.

Needs the development dependencies, Chromium, and optional engine test checkout.
Every cycle uses a new seed. Reports are written after each command, including
failures/timeouts. Exits on first failure so its exact fixture/log is retained.
"""
import argparse
from datetime import datetime, timedelta
import html
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument('--hours', type=float, default=6)
parser.add_argument('--interval-minutes', type=float, default=15)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--engine-tests', type=Path)
parser.add_argument('--engine-source', type=Path)
parser.add_argument('--seed', type=int, default=20261006)
args = parser.parse_args()
if not 0 < args.hours <= 12 or not 0 < args.interval_minutes <= 60:
    parser.error('Use a duration up to 12 hours and interval up to 60 minutes')
root = Path(__file__).resolve().parents[1]
out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
started = time.time(); deadline = started + args.hours * 3600
zone = ZoneInfo('America/New_York')
report = {'status': 'running', 'started': datetime.fromtimestamp(started,zone).isoformat(),
          'deadline': datetime.fromtimestamp(deadline,zone).isoformat(), 'root': str(root),
          'seed': args.seed, 'results': [], 'cycle': 0,
          'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()}
stopping = False

def stop(_signum, _frame):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def save():
    report['updated'] = datetime.now(zone).isoformat()
    pending = out / 'report.tmp'; pending.write_text(json.dumps(report, indent=2)); pending.replace(out/'report.json')
    rows = ''.join('<tr><td>'+str(row['cycle'])+'</td><td>'+html.escape(row['name'])+'</td><td>'+str(row['seed'])+'</td><td>'+('PASS' if row['exit']==0 else 'FAIL')+'</td><td>'+str(row['seconds'])+'s</td><td><a href="'+html.escape(row['log'])+'">log</a></td></tr>' for row in report['results'])
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SuperSurfer overnight QA</title><style>body{font:15px system-ui;max-width:1100px;margin:50px auto;padding:0 24px;color:#20313e;background:#f5f8f7}h1{font-weight:550}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #dce4df}a{color:#18576d}code{font-size:12px}</style><h1>SuperSurfer overnight QA</h1><p>Status: <b>'+html.escape(report['status'])+'</b> · Updated '+html.escape(report['updated'])+'</p><p>Started '+html.escape(report['started'])+' · Ends by '+html.escape(report['deadline'])+' (America/New_York)</p><p>Isolated fake agents, loopback servers and SSH; no research runs or user workspace mutations. Each cycle uses fresh random state sequences and shuffled suite order. A failure stops the campaign and preserves its reproduction seed.</p><table><thead><tr><th>Cycle</th><th>Check</th><th>Seed</th><th>Result</th><th>Time</th><th>Evidence</th></tr></thead><tbody>'+rows+'</tbody></table></html>'
    pending = out / 'report-html.tmp';pending.write_text(page);pending.replace(out/'report.html')


def run(name, command, seed, timeout=240):
    filename = f"cycle-{report['cycle']:02d}-{name}.log"
    before = time.monotonic()
    env = {**os.environ, 'SUPERSURFER_QA_SEED': str(seed), 'SUPERSURFER_QA_OUTPUT': str(out), 'SUPERSURFER_SSHD_TEST': '1'}
    with (out / filename).open('w') as log:
        process = subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while process.poll() is None:
                if stopping or time.monotonic()-before > timeout or time.time() >= deadline:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                    code=130 if stopping else 124
                    break
                time.sleep(.2)
            else:code=process.returncode
        except BaseException:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();raise
    row={'cycle':report['cycle'],'name':name,'seed':seed,'exit':code,'seconds':round(time.monotonic()-before,2),'log':filename}
    report['results'].append(row);save();print(('PASS' if code==0 else 'FAIL'),name,'seed',seed,flush=True)
    return code==0

save()
subprocess.run(['node','scripts/preview-login.cjs'],cwd=root,check=True)
try:
    while not stopping and time.time()<deadline:
        report['cycle']+=1;seed=args.seed+report['cycle'];cycle_start=time.time()
        commands=[('python-shuffled',[sys.executable,'scripts/qa-shuffle.py','--seed',str(seed)]),
                  ('node-ssh',['node','--test',*[str(path.relative_to(root)) for path in sorted((root/'tests').glob('*.test.cjs'))]])]
        commands += [(path.stem,['node',str(path)]) for path in sorted((root/'tests').glob('*.browser.cjs'))]
        if report['cycle']==1 or report['cycle']%4==0:
            commands.append(('native-electron',['xvfb-run','-a','node','tests/native-desktop.electron.cjs']))
            if args.engine_tests and args.engine_source:
                commands.append(('engine',[sys.executable,'-m','pytest',str(args.engine_tests),'-o','pythonpath='+str(args.engine_source),'-q']))
        random.Random(seed).shuffle(commands)
        for name, command in commands:
            if stopping or time.time()>=deadline:break
            if not run(name,command,seed):
                report['status']='stopped' if stopping else 'failed';save();raise SystemExit(1)
        save()
        remaining=min(deadline,cycle_start+args.interval_minutes*60)
        while not stopping and time.time()<remaining:time.sleep(min(1,remaining-time.time()))
    report['status']='stopped' if stopping else 'completed';save()
except Exception as error:
    report['status']='error';report['error']=str(error);save();raise
print('Campaign',report['status'],'after',report['cycle'],'cycles',flush=True)
