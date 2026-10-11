"""Profile a disposable workspace without accounts, model calls or GPU probes.

Run from the repository root: python3 tests/profile-performance.py 40 --profile
"""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import statistics
import sys
import time

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from test_conversations import ConversationTests
from server.codex import CodexBridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tasks', nargs='?', type=int, default=40)
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    if not 12 <= args.tasks <= 5000:
        parser.error('Choose 12 to 5000 synthetic tasks.')
    fixture = ConversationTests()
    fixture.setUp()
    service = fixture.service
    try:
        fixture.manager.data['tasks'] = [
            {'id': 'task' + str(i), 'project_id': 'p1', 'name': 'E' + str(i + 30),
             'briefing': 'Compare trained methods', 'findings': 'Pending measured evidence'}
            for i in range(args.tasks)
        ]
        service.aml.invalidate()
        items = service.state()['experiments']
        service.codex = CodexBridge(service.directory / 'codex', service.context_provider)
        for i in range(12):
            scope = 'manager' if i == 0 else 'project:p1' if i == 1 else 'experiment:' + items[i - 2]['id']
            chat = service.codex._new_chat(scope, {'role': 'worker', 'name': 'Fixture worker', 'cwd': str(fixture.repo)})
            chat['messages'] = [
                {'id': 'm' + str(j), 'role': 'user' if j % 3 == 0 else 'assistant',
                 'text': 'Measured training evidence and context. ' * 60, 'created': 100 + j}
                for j in range(600)
            ]
            service.codex._chats[scope] = chat
            service.codex._save(chat)
        experiment_id = items[0]['id']
        scope = 'experiment:' + experiment_id
        cases = {
            'state': service.state,
            'chat-full': lambda: service.chat(scope),
            'chat-recent80': lambda: service.chat(scope, message_limit=80),
            'agent-directory': lambda: service.experiment_agents(experiment_id),
            'context': lambda: service.context_provider(scope),
        }
        for name, operation in cases.items():
            operation()
            times = []
            for _ in range(5):
                start = time.perf_counter()
                result = operation()
                times.append((time.perf_counter() - start) * 1000)
            print(json.dumps({'case': name, 'tasks': args.tasks,
                              'median_ms': round(statistics.median(times), 2),
                              'max_ms': round(max(times), 2),
                              'payload_bytes': len(json.dumps(result).encode())}), flush=True)
        if args.profile:
            profile = cProfile.Profile()
            profile.runcall(service.state)
            pstats.Stats(profile).sort_stats('cumulative').print_stats(20)
    finally:
        fixture.tearDown()


if __name__ == '__main__':
    main()
