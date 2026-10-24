"""Build a reviewed additive SR42 overlay; never install or restart a service.

The exact deployed base file hashes are supplied by --expected-base-manifest.
This makes a changed installation fail closed instead of silently dropping fixes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parents[1]
FILES = ['server/app.py', 'server/agent_tools.py', 'server/surfboards.py',
         'server/operations_workspace.py', 'agent_skills/supersurfer-worker/SKILL.md']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(base, output, expected):
    actual = {name: digest(base / name) for name in FILES}
    if actual != expected:
        raise ValueError('Installed base differs from the explicitly reviewed manifest')
    if output.exists():
        raise ValueError('Use a fresh isolated output directory')
    shutil.copytree(base, output, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    def edit(name, before, after):
        path = output / name
        value = path.read_text()
        if value.count(before) != 1:
            raise ValueError('Ambiguous or missing overlay anchor in ' + name + ': ' + before[:60])
        path.write_text(value.replace(before, after))
    edit('server/app.py', 'from .wakeups import Wakeups',
         'from .wakeups import Wakeups\nfrom .recurring_sr42 import RecurringSR42')
    edit('server/app.py', 'self.recovery = RunRecovery(self)',
         'self.recovery = RunRecovery(self)\n        self.recurring_sr42 = RecurringSR42(self)\n        self.sr42_thread = None')
    edit('server/app.py', 'self.wakeup_thread.start()',
         'self.wakeup_thread.start()\n            self.sr42_thread = threading.Thread(target=self._sr42_loop, name="supersurfer-native-sr42", daemon=True)\n            self.sr42_thread.start()')
    edit('server/app.py', '    def _wakeup_loop(self):',
         '    def _sr42_loop(self):\n        while not self.shutdown.wait(30):\n            self.recurring_sr42.tick()\n\n    def _wakeup_loop(self):')
    edit('server/app.py', '            if name == "supersurfer_message_agent":',
         '            if name == "supersurfer_configure_recurring_sr42":\n                return self.recurring_sr42.receipt(self.recurring_sr42.configure(scope, arguments))\n            if name == "supersurfer_message_agent":')
    edit('server/app.py', '        self.nodes.close()',
         '        if self.sr42_thread:\n            self.sr42_thread.join(timeout=30)\n        self.nodes.close()')
    edit('server/app.py', 'threads = (self.operations_thread,', 'threads = (self.sr42_thread, self.operations_thread,')
    edit('server/app.py', '"configure_worker_wakeup", "inspect_project_compute"',
         '"configure_worker_wakeup", "configure_recurring_sr42", "inspect_project_compute"')
    tool_source = (SOURCE / 'server/agent_tools.py').read_text()
    tool = tool_source[tool_source.index('SR42_TOOL = {'):tool_source.index('WAKEUP_TOOL = {')]
    edit('server/agent_tools.py', 'WAKEUP_TOOL = {', tool + 'WAKEUP_TOOL = {')
    edit('server/agent_tools.py', '*WORKER_COMPUTE_TOOLS, WAKEUP_TOOL,', '*WORKER_COMPUTE_TOOLS, WAKEUP_TOOL, SR42_TOOL,')
    edit('server/agent_tools.py', 'OPERATIONS_TOOLS = [', 'OPERATIONS_TOOLS = [\n    SR42_TOOL,')
    edit('server/operations_workspace.py', '            run = None',
         '            if name == "supersurfer_configure_recurring_sr42":\n                return self.recurring_sr42.receipt(self.recurring_sr42.configure(scope, arguments))\n            run = None')
    edit('server/operations_workspace.py', 'name == "supersurfer_recover_run" and arguments.get("action", "status") == "status")',
         'name == "supersurfer_recover_run" and arguments.get("action", "status") == "status") or (\n                name == "supersurfer_configure_recurring_sr42" and arguments.get("action") == "status")')
    edit('server/surfboards.py', '"queue_run", "configure_worker_wakeup"',
         '"queue_run", "configure_worker_wakeup", "configure_recurring_sr42"')
    edit('server/surfboards.py', '("timer", "configure_worker_wakeup"),',
         '("timer", "configure_worker_wakeup"), ("timer", "configure_recurring_sr42"),')
    edit('server/surfboards.py', 'EXPERIMENT_TOOLS | {"prepare_run", "queue_run"}',
         'EXPERIMENT_TOOLS | {"prepare_run", "queue_run", "configure_recurring_sr42"}')
    skill = (SOURCE / 'agent_skills/supersurfer-worker/SKILL.md').read_text().split('## Native two-baseline SR42 recurrence')[1]
    path = output / 'agent_skills/supersurfer-worker/SKILL.md'
    path.write_text(path.read_text() + '\n\n## Native two-baseline SR42 recurrence' + skill)
    additions = ['server/recurring_sr42.py', 'server/sr42_adapter.py', 'server/sr42_remote.py']
    for name in additions:
        shutil.copy2(SOURCE / name, output / name)
    changed = FILES + additions
    manifest = {'base_directory': str(base), 'base_sha256': actual,
                'overlay_sha256': {name: digest(output / name) for name in changed},
                'unchanged_files_preserved': True,
                'note': 'Prepared only. No service, database, run, host or allocation changed.'}
    (output / 'sr42-overlay-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-base-manifest', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.base.resolve(), args.output.resolve(), json.loads(args.expected_base_manifest.read_text()))
    print(json.dumps(result, indent=2))
