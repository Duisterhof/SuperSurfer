"""Exact-source staging accepts node Git caches without touching existing refs."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import time
import types
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'engine/aml/runner.py'
spec = importlib.util.spec_from_file_location('supersurfer_fixture_runner', path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BareSourceStagingTests(unittest.TestCase):
    def test_reviewed_pack_enters_bare_cache_without_moving_refs_and_supports_detached_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';cache=root/'cache.git'
            def git(repo,*args,input=None):
                return subprocess.check_output(['git','-C',str(repo),*args],input=input,stderr=subprocess.PIPE)
            source.mkdir();git(source,'init','-q');git(source,'config','user.email','fixture@example.invalid');git(source,'config','user.name','Fixture')
            (source/'code.py').write_text('original\n');git(source,'add','.');git(source,'commit','-qm','Original')
            subprocess.run(['git','clone','--bare','-q',str(source),str(cache)],check=True)
            original_refs=git(cache,'show-ref');original_config=(cache/'config').read_bytes()
            (source/'code.py').write_text('reviewed\n');git(source,'add','.');git(source,'commit','-qm','Reviewed')
            revision=git(source,'rev-parse','HEAD').decode().strip()
            pack=git(source,'pack-objects','--stdout','--revs',input=(revision+'\n').encode())
            url='https://github.com/example/research/pull/8'
            spec={'repo':str(cache),'revision':revision,'config':{'pr_url':url,'review_repository':'example/research',
                'review_receipt':{'pr_url':url,'repository':'example/research','number':8,'revision':revision,'head_sha':revision,'checked_at':time.time()}}}
            output=io.StringIO()
            with patch.object(runner.sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(pack))),patch.object(runner.sys,'stdout',output):
                runner.receive_source(spec)
            self.assertTrue(json.loads(output.getvalue().splitlines()[-1])['ready'])
            self.assertEqual(git(cache,'show-ref'),original_refs)
            self.assertEqual((cache/'config').read_bytes(),original_config)
            checkout=root/'isolated-run';git(cache,'worktree','add','--detach',str(checkout),revision)
            self.assertEqual((checkout/'code.py').read_text(),'reviewed\n')
            bad={**spec,'config':{**spec['config'],'review_receipt':{**spec['config']['review_receipt'],'revision':'0'*40}}}
            with self.assertRaisesRegex(ValueError,'PR receipt'):runner.receive_source(bad)


if __name__=='__main__':unittest.main()
