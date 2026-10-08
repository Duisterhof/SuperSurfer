"""Validate user-selected context without reading or changing repository files."""
from copy import deepcopy
from pathlib import Path
from .code_editor import _parts
from .surfboards import SurfboardError


def attachments(service, scope, value):
    if value is None:
        return [], ''
    if not isinstance(value, list) or len(value) > 8:
        raise SurfboardError('Attach up to eight context items')
    info = service._chat_scope(scope)
    if 'agent' in info:
        raise SurfboardError('Attachments require a SuperSurfer-owned conversation', 409)
    rows, ids = [], set()
    for item in value:
        required = {'id', 'kind', 'project_id', 'path', 'label', 'text'}
        if not isinstance(item, dict) or set(item) != required:
            raise SurfboardError('Invalid context attachment fields')
        limits = {'id': 80, 'kind': 10, 'project_id': 150, 'path': 4096, 'label': 300, 'text': 40000}
        if any(not isinstance(item[key], str) or not item[key] or len(item[key]) > limit or '\0' in item[key]
               for key, limit in limits.items()):
            raise SurfboardError('Invalid or oversized context attachment')
        if item['id'] in ids or item['kind'] not in {'file', 'code', 'diff', 'pdf'}:
            raise SurfboardError('Invalid context identity or kind')
        ids.add(item['id'])
        if scope != 'manager' and item['project_id'] != info.get('project_id'):
            raise SurfboardError('This attachment belongs to another project', 403)
        _parts(item['path'])
        project = service.lookup('projects', item['project_id'])
        row = deepcopy(item)
        row['absolute_path'] = str(Path(project['repo']) / row['path'])
        rows.append(row)
    context = ''.join('\n\n[Attached '+row['kind']+' context: '+row['label']+'\nWorkspace path: '+row['absolute_path']+']\n'+row['text'] for row in rows)
    if len(context) > 64000:
        raise SurfboardError('Attached context exceeds 64,000 characters; select a smaller excerpt')
    return rows, context
