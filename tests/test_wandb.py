import json
import unittest
from server.wandb import WandBReader, parse_url, parse_target, series_from_runs


class WandBTests(unittest.TestCase):
    def test_urls_cannot_choose_credential_destination(self):
        for url in ['http://wandb.ai/me/test', 'https://wandb.ai.evil.test/me/test', 'https://user@wandb.ai/me/test', 'https://wandb.ai:444/me/test', 'file:///etc/passwd', 'https://wandb.ai/me/test/reports/name']:
            with self.assertRaises(ValueError): parse_url(url)
        self.assertEqual(parse_url('https://wandb.ai/me/test/runs/abc123?workspace=user'), ('me', 'test', 'abc123'))

    def test_sampled_metrics_remove_nan_and_preserve_series(self):
        runs = [{'name': 'a', 'displayName': 'A', 'history': ['{"_step": 2, "loss": 3}', {'_step': 1, 'loss': 5, 'bad': float('nan')}, {'_step': 2, 'loss': 2}, {'_step': 3, 'loss': False}, 'invalid']}]
        series = series_from_runs(runs)
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]['points'], [{'x': 1, 'y': 5}, {'x': 2, 'y': 2}])

    def test_cache_and_query_scope(self):
        calls = []
        def fetch(query, variables):
            calls.append((query, variables))
            return {'project': {'run': {'name': 'a', 'history': []}}}
        reader = WandBReader(fetch)
        for _ in range(2):
            result = reader.metrics('https://wandb.ai/me/project/runs/a')
            self.assertIsNone(result['error'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], {'entity': 'me', 'project': 'project', 'run': 'a'})
        self.assertNotIn('mutation', calls[0][0])

    def test_group_targets_filter_server_side_without_claiming_metrics(self):
        calls = []
        def fetch(query, variables):
            calls.append((query, variables))
            return {'project': {'runs': {'edges': [{'node': {'name': 'metadata', 'history': [], 'state': 'running'}}]}}}
        url = 'https://wandb.ai/me/project/groups/experiment-1'
        target = parse_target(url)
        self.assertEqual({'entity': 'me', 'project': 'project', 'run': None, 'group': 'experiment-1'}, target)
        with self.assertRaises(ValueError): parse_url(url)
        result = WandBReader(fetch).metrics(url)
        self.assertIsNone(result['error'])
        self.assertEqual([], result['series'])
        self.assertEqual(1, len(result['runs']))
        self.assertEqual({'group': 'experiment-1', 'jobType': {'$nin': ['supersurfer-experiment', 'supersurfer-run-metadata']}}, json.loads(calls[0][1]['filters']))
        self.assertIn('filters: $filters', calls[0][0])
        self.assertNotIn('mutation', calls[0][0])

    def test_project_and_group_curves_filter_metadata_before_six_run_limit(self):
        records = [{'name': 'metadata-' + str(i), 'jobType': 'supersurfer-run-metadata', 'history': []} for i in range(8)]
        records += [{'name': 'experiment', 'jobType': 'supersurfer-experiment', 'history': []},
                    {'name': 'prepared-training', 'jobType': 'supersurfer-prepared-run', 'history': [{'_step': 1, 'loss': 2}, {'_step': 2, 'loss': 1}]}]
        def fetch(query, variables):
            filters = json.loads(variables['filters'])
            self.assertIn('filters: $filters', query)
            excluded = filters['jobType']['$nin']
            selected = [record for record in records if record['jobType'] not in excluded][:6]
            return {'project': {'runs': {'edges': [{'node': row} for row in selected]}}}
        for url in ('https://wandb.ai/me/project', 'https://wandb.ai/me/project/groups/experiment-1'):
            result = WandBReader(fetch).metrics(url)
            self.assertIsNone(result['error'])
            self.assertEqual(['prepared-training'], [row['id'] for row in result['runs']])
            self.assertEqual([{'x': 1, 'y': 2}, {'x': 2, 'y': 1}], result['series'][0]['points'])


if __name__ == '__main__': unittest.main()
