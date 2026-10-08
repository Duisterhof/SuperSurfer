"""Plain Markdown checklists, edited with the same revision checks as source."""
import os
import re
from .project_artifacts import _open_dirs
from .surfboards import SurfboardError

LIMIT = 128 * 1024
CHECK = re.compile(r'^(\s*(?:[-*+]|\d+\.)\s+\[)([ xX])(\]\s+)(.*)$')


def location(service, project_id, experiment_id=None):
    project = service.lookup('projects', project_id)
    if experiment_id is not None:
        item = service.store.experiment(experiment_id)
        if item['project_id'] != project['id']:
            raise SurfboardError('This checklist belongs to another project', 403)
    path = 'todos/' + (experiment_id or 'project') + '.md'
    mapped, relative = service.artifacts.editor_target(project, 'artifact:' + path)
    return project, mapped, relative


def read(service, project_id, experiment_id=None):
    project, mapped, path = location(service, project_id, experiment_id)
    try:
        record = service.code.read(mapped, path)
        markdown, revision = record['content'], record['revision']
        if markdown is None or len(markdown.encode('utf-8')) > LIMIT:
            raise SurfboardError('To-do Markdown exceeds the 128 KiB text limit', 413)
    except (FileNotFoundError, SurfboardError) as error:
        if isinstance(error, SurfboardError) and error.status != 404: raise
        markdown, revision = '# To-dos\n\n', None
    items, fence = [], None
    for index, line in enumerate(markdown.splitlines()):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            value = marker.group(1)
            if fence is None: fence = value
            elif value[0] == fence[0] and len(value) >= len(fence): fence = None
            continue
        match = CHECK.match(line)
        if match and fence is None:
            items.append({'line': index, 'checked': match[2].lower() == 'x', 'text': match[4]})
    return {'project_id': project_id, 'experiment_id': experiment_id, 'markdown': markdown, 'revision': revision,
            'items': items, 'editor_path': 'artifact:' + path, 'absolute_path': str(service.artifacts.root(project) / path)}


def save(service, fields):
    if service.read_only: raise SurfboardError('Read-only workspace: checklist cannot be changed', 403)
    if set(fields) != {'project_id', 'experiment_id', 'markdown', 'revision'}:
        raise SurfboardError('Checklist save requires project, work item, Markdown and revision')
    markdown = fields['markdown']
    if not isinstance(markdown, str) or len(markdown.encode('utf-8')) > LIMIT:
        raise SurfboardError('To-do Markdown exceeds the 128 KiB limit', 413)
    project, mapped, path = location(service, fields['project_id'], fields['experiment_id'])
    root = service.artifacts._root_fd(project, create=True)
    try:
        directory = _open_dirs(root, ('todos',), create=True)
        os.close(directory)
    finally: os.close(root)
    service.code.save(mapped, path, markdown, fields['revision'])
    return read(service, fields['project_id'], fields['experiment_id'])
