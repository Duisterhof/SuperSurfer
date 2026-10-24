"""Retained checkpoint helper and binding checks use isolated files only."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from server import sr42_remote
from server.recurring_sr42 import METHODS, PR, PROJECT, REVISION, ScheduleError
from server.sr42_adapter import SR42Adapter


class RemotePinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / 'training'
        checkpoints = self.output / 'checkpoints'; checkpoints.mkdir(parents=True)
        self.checkpoint = checkpoints / '000001000-evaluation.pt'
        self.checkpoint.write_bytes(b'checkpoint fixture')
        self.seal = self.checkpoint.with_suffix('.json')
        self.seal.write_text(json.dumps({'step': 1000, 'sha256': sr42_remote.digest(self.checkpoint)}))
        self.config = self.root / 'config.json'; self.config.write_text('{}')
        self.payload = {'operation': 'pin', 'training_output': str(self.output), 'config': str(self.config),
                        'config_sha256': sr42_remote.digest(self.config), 'python': '/fixture/python',
                        'expected_config': {}, 'data_bindings': {}, 'revision': REVISION, 'protocol_sha256': 'b' * 64}

    def tearDown(self): self.tmp.cleanup()

    def invoke(self, payload):
        stream = io.StringIO()
        with redirect_stdout(stream): sr42_remote.main(payload)
        return json.loads(stream.getvalue().split('SUPERSURFER_SR42:')[1])

    @patch('server.sr42_remote.subprocess.run', return_value=SimpleNamespace(returncode=0))
    def test_pin_survives_trainer_retention_and_cpu_check_disables_cuda(self, run):
        pin = self.invoke(self.payload)
        self.assertTrue(self.checkpoint.with_suffix('.retain').exists())
        self.checkpoint.unlink(); self.seal.unlink()
        self.assertEqual(pin['sha256'], sr42_remote.digest(pin['path']))
        self.assertEqual('', run.call_args.kwargs['env']['CUDA_VISIBLE_DEVICES'])
        self.assertIn("map_location='cpu'", run.call_args.args[0][2])

    @patch('server.sr42_remote.subprocess.run', return_value=SimpleNamespace(returncode=1, stderr='wrong recipe'))
    def test_checkpoint_binding_failure_never_returns_a_pin(self, run):
        with self.assertRaisesRegex(ValueError, 'binding validation failed'):
            self.invoke(self.payload)

    def test_pin_subprocess_uses_python36_compatible_arguments(self):
        def python36_run(args, input, universal_newlines, stdout, stderr, timeout, env):
            self.assertTrue(universal_newlines)
            self.assertEqual('', env['CUDA_VISIBLE_DEVICES'])
            return SimpleNamespace(returncode=0)
        with patch('server.sr42_remote.subprocess.run', python36_run):
            self.assertEqual(1000, self.invoke(self.payload)['step'])

    def test_changed_config_and_sha_fail_closed(self):
        self.config.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'config bytes changed'): self.invoke(self.payload)
        self.config.write_text('{}'); self.checkpoint.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'does not match seal'): self.invoke(self.payload)

    def test_atomic_receipt_interruption_leaves_no_corrupt_final_name(self):
        path = self.root / 'receipt.json'
        with patch('server.sr42_remote.os.replace', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError): sr42_remote.publish(path, b'{}')
        self.assertFalse(path.exists())
        self.assertFalse(list(self.root.glob('*.partial')))
        sr42_remote.publish(path, b'{}'); sr42_remote.publish(path, b'{}')
        with self.assertRaises(ValueError): sr42_remote.publish(path, b'{"changed":1}')

    def test_symlinked_checkpoint_is_rejected(self):
        target = self.root / 'other'; self.checkpoint.rename(target); self.checkpoint.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlinks'): self.invoke(self.payload)


class PartialTransferTests(unittest.TestCase):
    def test_existing_partial_copy_is_resumed_and_revalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = b'retained checkpoint'; seal = b'{}'
            digest = lambda data: hashlib.sha256(data).hexdigest()
            pin = {'sha256': digest(checkpoint), 'seal_sha256': digest(seal), 'step': 1000,
                   'path': '/fixture/000001000-evaluation.pt', 'seal': '/fixture/000001000-evaluation.json',
                   'source_host_id': 'source'}
            cache = root / 'private-external-cache'; cache.mkdir(mode=0o700)
            local = cache / pin['sha256']; local.mkdir()
            (local / Path(pin['path']).name).write_bytes(b'partial')
            copied = []
            def copy(source, path, destination, target, cancelled):
                copied.append((source, path, destination, target))
                if destination is None:
                    Path(target).write_bytes(checkpoint if path.endswith('.pt') else seal)
            service = SimpleNamespace(directory=root, lookup=lambda kind,key,**kw: {'id':key},
                nodes=SimpleNamespace(copy=copy), shutdown=SimpleNamespace(is_set=lambda:False),
                store=SimpleNamespace(get=lambda key,default=None:default))
            adapter = SR42Adapter(service)
            def remote(host, payload):
                if payload['operation'] == 'inspect': return {'files': {}}
                if payload['operation'] == 'finalize':
                    return {'checkpoint':'/staged/checkpoint.pt','seal':'/staged/checkpoint.json','readiness':'/staged/readiness.json'}
                return {}
            adapter.remote = remote
            binding = {'host_id':'destination','inspection':{'operation':'inspect'},'evidence':{'files':{},'readiness':{}},
                       'python':'/python','runtime':'/runtime','torch_home':'/torch','runtime_identity':'c'*64,
                       'data':'/data','repo':'/repo','python_packages':{}}
            with patch.dict('os.environ', {'SUPERSURFER_SR42_CACHE': str(cache)}):
                result = adapter.prepare('mse', pin, binding)
            self.assertFalse((root / 'sr42-pins').exists())
            cache.chmod(0o755)
            with patch.dict('os.environ', {'SUPERSURFER_SR42_CACHE': str(cache)}):
                with self.assertRaisesRegex(ScheduleError, 'private'):
                    adapter.prepare('mse', pin, binding)
            self.assertEqual(checkpoint, (local / Path(pin['path']).name).read_bytes())
            self.assertEqual(4, len(copied))
            self.assertEqual('evaluation', result['job_type'])
            self.assertEqual(1, result['gpu_count'])
            self.assertEqual(PR, result['pr_url'])


if __name__ == '__main__': unittest.main()
