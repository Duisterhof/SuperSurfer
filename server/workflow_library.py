"""Named Surfboards and reviewed, atomic updates of their task snapshots.

The library contains definitions, never conversations, jobs, or credentials.
A preview is an immutable receipt; apply rechecks every input before committing.
"""
from copy import deepcopy
import hashlib
import json
import time
import uuid

from .surfboards import SurfboardError, compile_board, compile_pages, configured_limits, diff_summary, template, validate


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def merge(base, local, incoming, path='', conflicts=None):
    """Three-way merge, matching graph/page lists by identity rather than position."""
    conflicts = conflicts if conflicts is not None else []
    if local == base or local == incoming:
        return deepcopy(incoming)
    if incoming == base:
        return deepcopy(local)
    if all(isinstance(v, dict) for v in (base, local, incoming)):
        result = {}
        missing = object()
        for key in sorted(set(base) | set(local) | set(incoming)):
            b, l, n = (v.get(key, missing) for v in (base, local, incoming))
            p = path + '/' + key
            if l == b:
                value = n
            elif n == b or l == n:
                value = l
            elif missing in (b, l, n):
                conflicts.append(p)
                value = l
            else:
                value = merge(b, l, n, p, conflicts)
            if value is not missing:
                result[key] = deepcopy(value)
        return result
    if all(isinstance(v, list) and all(isinstance(row, dict) and 'id' in row for row in v) for v in (base, local, incoming)):
        result = merge(*({row['id']: row for row in v} for v in (base, local, incoming)), path, conflicts)
        base_ids, local_ids, new_ids = ([r['id'] for r in rows] for rows in (base, local, incoming))
        common = set(base_ids) & set(local_ids) & set(new_ids)
        b_order, l_order, n_order = ([key for key in ids if key in common] for ids in (base_ids, local_ids, new_ids))
        if l_order != b_order and n_order != b_order and l_order != n_order:
            conflicts.append(path + '/order')
        preferred = local_ids if l_order != b_order and n_order == b_order else new_ids
        order = preferred + [key for key in local_ids + new_ids if key not in preferred]
        order = list(dict.fromkeys(order))
        return [result[key] for key in order if key in result]
    conflicts.append(path or '/')
    return deepcopy(local)


class WorkflowLibrary:
    def __init__(self, service):
        self.service, self.store, self.boards = service, service.store, service.boards

    def library(self):
        return self.store.get('workflow_library', {'version': 0, 'entries': []})

    def read(self, project_id, experiment_id=None):
        with self.service.action_lock, self.store.lock:
            return self._read(project_id, experiment_id)

    def _read(self, project_id, experiment_id=None):
        self.service.lookup('projects', project_id)
        record = self.service.board_record(project_id, experiment_id)
        key = 'task:' + experiment_id if experiment_id else project_id
        data = self.library()
        items = []
        for row in self.store.db.execute('SELECT id FROM experiments').fetchall():
            item = self.store.experiment(row[0])
            task = self.boards._record('task:' + item['id'])
            items.append({'id': item['id'], 'name': item['name'], 'project_id': item['project_id'], 'archived': item.get('archived', False), 'library_id': task.get('library', {}).get('id')})
        return {'library': data, 'source': record, 'link': self.boards._record(key).get('library'), 'tasks': items,
                'changes': self.store.get('workflow_changes', []), 'setup': self.store.get('workflow_setup:' + key, False)}

    def _write(self, key, value):
        self.store.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, json.dumps(value, allow_nan=False)))

    def _source(self, fields):
        pid, eid = fields['project_id'], fields.get('experiment_id')
        self.service.lookup('projects', pid)
        current = self.service.board_record(pid, eid)
        if current['version'] != fields.get('expected_version') or (current.get('draft') or {}).get('draft_version', 0) != fields.get('expected_draft_version', 0):
            raise SurfboardError('The proposal changed. Refresh and review the latest version.', 409)
        return ('task:' + eid if eid else pid), current

    def _entry(self, fields):
        row = next((r for r in self.library()['entries'] if r['id'] == fields.get('library_id')), None)
        if not row:
            raise SurfboardError('Saved Surfboard not found.', 404)
        version = fields.get('library_version', row['version'])
        snapshot = next((r for r in row['revisions'] if r['version'] == version), None)
        if not snapshot:
            raise SurfboardError('Saved Surfboard revision not found.', 404)
        return row, snapshot

    def save(self, fields):
        key, current = self._source(fields)
        name = fields.get('name', '')
        if not isinstance(name, str) or not name.strip() or len(name) > 160 or any(ord(c) < 32 for c in name):
            raise SurfboardError('Name your Surfboard in 1–160 characters.')
        name = name.strip()
        warnings = []
        board = deepcopy((current.get('draft') or {}).get('board', current['board']))
        # Shared capacity is a project binding, not part of a reusable task template.
        for node in board['nodes']:
            if node['kind'] == 'compute':
                for cap in ('gpu_limit', 'run_limit'):
                    node['config'].pop(cap, None)
            if node['kind'] == 'wandb' and node['config'].get('experiment_ids'):
                node['config'].update(experiment_ids=[], sharing='item')
                warnings.append('Selected experiment IDs were removed from the saved template. Its W&B source uses the current task; review sharing before applying.')
        board['name'] = name
        board = validate(board)
        compile_board(board)
        data = self.library()
        if data['version'] != fields.get('library_revision'):
            raise SurfboardError('The library changed. Refresh before saving.', 409)
        entry = next((r for r in data['entries'] if r['id'] == fields.get('library_id')), None)
        if fields.get('library_id') and not entry:
            raise SurfboardError('Saved Surfboard not found.', 404)
        if not entry:
            entry = {'id': 'board_' + uuid.uuid4().hex[:12], 'version': 0, 'revisions': []}
            data['entries'].append(entry)
        entry.update(name=name, version=entry['version'] + 1)
        entry['revisions'].append({'version': entry['version'], 'board': board, 'saved_at': time.time()})
        data['version'] += 1
        self._write('workflow_library', data)
        return {'entry': entry, 'library': data, 'warnings': warnings}

    def stage(self, fields):
        key, source = self._source(fields)
        entry, revision = self._entry(fields)
        link = self.boards._record(key).get('library')
        local = (source.get('draft') or {}).get('board', source['board'])
        conflicts = []
        board = merge(link['base'], local, revision['board'], conflicts=conflicts) if link and link['id'] == entry['id'] else deepcopy(revision['board'])
        if conflicts:
            raise SurfboardError('Saved version overlaps local edits: ' + ', '.join(conflicts) + '. Refine the current proposal before applying.', 409)
        return self.boards.save_draft(key, board, source['version'], (source.get('draft') or {}).get('draft_version', 0),
            library_source={'id': entry['id'], 'version': revision['version'], 'base': revision['board']})

    def _busy(self, pid, eid):
        for chat in self.service.codex.list_chats():
            if not chat.get('busy') or chat['scope'].startswith('surfboard:'):
                continue
            try:
                info = self.service._chat_scope(chat['scope'])
                if info.get('project_id') == pid and (not eid or info.get('experiment_id') == eid):
                    return True
            except SurfboardError:
                continue
        return False

    def preview(self, fields):
        source_key, source = self._source(fields)
        if fields.get('use_saved'):
            entry, revision = self._entry(fields)
            incoming, link = revision['board'], {'id': entry['id'], 'version': revision['version'], 'base': revision['board']}
        else:
            incoming = (source.get('draft') or {}).get('board', source['board'])
            link = deepcopy((source.get('draft') or {}).get('library_source') or self.boards._record(source_key).get('library'))
            if fields.get('library_id'):
                entry, revision = self._entry(fields)
                link = {'id': entry['id'], 'version': revision['version'], 'base': revision['board']}
        incoming = validate(incoming)
        compile_board(incoming)
        if configured_limits(incoming):
            raise SurfboardError('Edit shared GPU limits in Project compute. Saved task workflows do not change resource budgets.')
        targets = fields.get('targets', [])
        if not isinstance(targets, list) or len(targets) > 512 or any(not isinstance(x, str) for x in targets):
            raise SurfboardError('Choose up to 512 task IDs.')
        targets = list(dict.fromkeys(targets))
        if not targets and not fields.get('future_default'):
            raise SurfboardError('Select this task, existing tasks, or the future-task default.')
        rows = []
        for eid in targets + ([None] if fields.get('future_default') else []):
            item = self.store.experiment(eid) if eid else None
            pid = item['project_id'] if item else fields['project_id']
            self.service.lookup('projects', pid)
            key = 'task:' + eid if eid else pid
            record = self.boards._record(key)
            conflicts = []
            own = key == source_key
            base = (record.get('library') or {}).get('base')
            if not own and not fields.get('use_saved'):
                base = source['board'] if record['board'] == source['board'] else base
            if not own and targets and len(targets) > 1 and (not link or (record.get('library') or {}).get('id') != link['id']):
                conflicts.append('This task is not linked to the selected Surfboard. Apply to it individually first.')
            board = deepcopy(incoming) if (own and not fields.get('use_saved')) or not base else merge(base, record['board'], incoming, conflicts=conflicts)
            if not own and record.get('draft'):
                conflicts.append('An unapplied draft exists; review it before this batch.')
            if self._busy(pid, eid):
                conflicts.append('An agent is working. Retry after its current turn to preserve its instructions.')
            if eid is None:
                # A future default does not rearrange the project's current UI or its capacity.
                for field in ('pages', 'layouts'):
                    if 'project' in record['board'].get(field, {}):
                        board.setdefault(field, {})['project'] = record['board'][field]['project']
                for node in board['nodes']:
                    if node['kind'] == 'compute':
                        node['config'].update(configured_limits(record['board']))
            layout = self.store.get('view_layout:' + eid) if eid else None
            next_layout = deepcopy(layout)
            if layout and layout.get('pages') is not None:
                baseline = compile_pages(base or record['board'])['item']
                next_layout['pages'] = merge(baseline, layout['pages'], compile_pages(board)['item'], '/pages', conflicts)
                next_layout['version'] += 1
            try:
                board = validate(board)
                compile_board(board)
                if next_layout:
                    from .surfboards import validate_pages, validate_layout
                    if next_layout.get('pages') is not None:
                        validate_pages(next_layout['pages'], board, 'item')
                    if next_layout.get('rows') is not None:
                        validate_layout(next_layout['rows'], board, 'item')
            except SurfboardError as error:
                conflicts.append(str(error))
            rows.append({'key': key, 'project_id': pid, 'experiment_id': eid, 'name': item['name'] if item else 'Future tasks in ' + self.service.lookup('projects', pid)['name'],
                         'before': record, 'after': board, 'layout_before': layout, 'layout_after': next_layout,
                         'conflicts': conflicts, 'summary': diff_summary(record['board'], board)})
        receipt = {'id': 'change_' + uuid.uuid4().hex[:16], 'created_at': time.time(), 'source_key': source_key,
                   'source_hash': fingerprint(self.boards._record(source_key)), 'rows': rows, 'link': link,
                   'library_hash': fingerprint(self.library()), 'applied': False}
        self._write('workflow_preview:' + receipt['id'], receipt)
        retained = {row['id'] for row in self.store.get('workflow_changes', [])}
        previews = self.store.db.execute("SELECT key,value FROM kv WHERE key LIKE 'workflow_preview:%'").fetchall()
        stale = sorted(((json.loads(value).get('created_at', 0), key) for key, value in previews if key.split(':', 1)[1] not in retained), reverse=True)[100:]
        for _, key in stale:
            self.store.db.execute('DELETE FROM kv WHERE key=?', (key,))
        return self.public(receipt)

    @staticmethod
    def public(receipt):
        return {k: v for k, v in receipt.items() if k in {'id', 'created_at', 'applied'}} | {
            'targets': [{k: row[k] for k in ('name', 'project_id', 'experiment_id', 'conflicts', 'summary')} for row in receipt['rows']],
            'can_apply': not any(row['conflicts'] for row in receipt['rows'])}

    def apply(self, fields):
        receipt = self.store.get('workflow_preview:' + str(fields.get('preview_id')))
        if not receipt:
            raise SurfboardError('Preview this change before applying it.', 404)
        if receipt['applied']:
            return self.public(receipt)
        if time.time() - receipt['created_at'] > 3600:
            raise SurfboardError('This preview expired. Review the latest workflow first.', 409)
        if fingerprint(self.library()) != receipt['library_hash'] or fingerprint(self.boards._record(receipt['source_key'])) != receipt['source_hash']:
            raise SurfboardError('The proposal or library changed. Preview again.', 409)
        for row in receipt['rows']:
            if row['conflicts'] or self.boards._record(row['key']) != row['before'] or self._busy(row['project_id'], row['experiment_id']):
                raise SurfboardError('A target changed or is busy. Preview again; nothing was applied.', 409)
            if row['experiment_id'] and self.store.get('view_layout:' + row['experiment_id']) != row['layout_before']:
                raise SurfboardError('A task layout changed. Preview again; nothing was applied.', 409)
        for row in receipt['rows']:
            record = deepcopy(row['before'])
            record.setdefault('history', []).append({'version': record['version'], 'board': record['board'], 'replaced_at': time.time()})
            record.update(version=record['version'] + 1, board=row['after'], draft=None)
            record['history'] = record['history'][-30:]
            if receipt['link']:
                record['library'] = {**receipt['link'], 'base': deepcopy(receipt['link']['base'])}
            self._write(self.boards._key(row['key']), record)
            self._write('workflow_setup:' + row['key'], False)
            if row['experiment_id'] and row['layout_after'] is not None:
                self._write('view_layout:' + row['experiment_id'], row['layout_after'])
            row['applied_hash'] = fingerprint(record)
        receipt['applied'] = True
        self._write('workflow_preview:' + receipt['id'], receipt)
        history = self.store.get('workflow_changes', [])
        history.append({'id': receipt['id'], 'at': time.time(), 'count': len(receipt['rows'])})
        self._write('workflow_changes', history[-30:])
        return self.public(receipt)

    def rollback(self, fields):
        receipt = self.store.get('workflow_preview:' + str(fields.get('preview_id')))
        if not receipt or not receipt['applied']:
            raise SurfboardError('Applied change not found.', 404)
        if receipt.get('rolled_back'):
            return {'restored': True}
        for row in receipt['rows']:
            if fingerprint(self.boards._record(row['key'])) != row['applied_hash'] or self._busy(row['project_id'], row['experiment_id']):
                raise SurfboardError('A target changed or is busy; rollback would overwrite newer work.', 409)
            if row['experiment_id'] and self.store.get('view_layout:' + row['experiment_id']) != row['layout_after']:
                raise SurfboardError('A target layout changed; rollback would overwrite newer work.', 409)
        for row in receipt['rows']:
            before = deepcopy(row['before'])
            before.update(version=before['version'] + 2, draft=None)
            self._write(self.boards._key(row['key']), before)
            if row['experiment_id']:
                if row['layout_before'] is None:
                    self.store.db.execute('DELETE FROM kv WHERE key=?', ('view_layout:' + row['experiment_id'],))
                else:
                    self._write('view_layout:' + row['experiment_id'], row['layout_before'])
        receipt['rolled_back'] = True
        self._write('workflow_preview:' + receipt['id'], receipt)
        return {'restored': True}

    def action(self, op, fields):
        if self.service.read_only:
            raise SurfboardError('Read-only workspace.', 403)
        for key in ('expected_version', 'expected_draft_version', 'library_revision', 'library_version'):
            if key in fields and (type(fields[key]) is not int or fields[key] < 0):
                raise SurfboardError('Workflow versions must be nonnegative integers.')
        for key in ('use_saved', 'future_default'):
            if key in fields and type(fields[key]) is not bool:
                raise SurfboardError(key + ' must be true or false.')
        targets = fields.get('targets', [])
        if not isinstance(targets, list) or len(targets) > 512 or any(not isinstance(x, str) or not x for x in targets):
            raise SurfboardError('Choose up to 512 task IDs.')
        if op == 'workflow.stage':
            with self.service.action_lock:
                return self.stage(fields)
        methods = {'workflow.save': self.save, 'workflow.preview': self.preview, 'workflow.apply': self.apply, 'workflow.rollback': self.rollback}
        if op not in methods:
            raise SurfboardError('Unknown workflow action.', 404)
        with self.service.action_lock, self.store.lock:
            if op in {'workflow.save', 'workflow.preview'}:
                self.service.lookup('projects', fields.get('project_id'))
                self.service.board_record(fields['project_id'], fields.get('experiment_id'))
            if op == 'workflow.preview':
                self.service.preserve_task_boards(fields['project_id'])
                for eid in targets:
                    item = self.store.experiment(eid)
                    self.boards.task_key(item['project_id'], eid)
            self.store.db.execute('BEGIN IMMEDIATE')
            try:
                result = methods[op](fields)
                self.store.db.commit()
                return result
            except BaseException:
                self.store.db.rollback()
                raise
