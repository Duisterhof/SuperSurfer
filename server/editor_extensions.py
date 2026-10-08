"""Bounded, cached Open VSX catalogue reads; installation remains explicit."""
import json
import re
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from .surfboards import SurfboardError

_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*')
_VERSION = re.compile(r'[0-9][A-Za-z0-9.+_-]{0,100}')

class ExtensionCatalog:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    def search(self, query, offset=0):
        if not isinstance(query, str) or len(query) > 160 or any(ord(c) < 32 for c in query):
            raise SurfboardError('Search extensions using up to 160 characters')
        query = query.strip()
        if isinstance(offset, str) and offset.isdigit(): offset = int(offset)
        if type(offset) is not int or not 0 <= offset <= 1000:
            raise SurfboardError('Extension search offset must be between 0 and 1000')
        if not query: return {'extensions': [], 'total': 0, 'offset': offset, 'next_offset': offset, 'more': False}
        key = (query, offset)
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < 300: return cached[1]
        params = urlencode({'query': query, 'size': 20, 'offset': offset, 'sortBy': 'relevance'})
        try:
            with urlopen('https://open-vsx.org/api/-/search?' + params, timeout=15) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024: raise ValueError('Oversized catalogue')
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get('extensions'), list): raise ValueError('Invalid catalogue')
        except (OSError, ValueError, TimeoutError) as error:
            raise SurfboardError('Open VSX extension search is unavailable. Check the workspace connection and try again.', 502) from error
        rows = []
        for row in data['extensions'][:20]:
            if not isinstance(row, dict) or not isinstance(row.get('namespace'), str) or not isinstance(row.get('name'), str): continue
            identity = str(row.get('namespace', '')) + '.' + str(row.get('name', ''))
            version = str(row.get('version', ''))
            if not _ID.fullmatch(identity) or not _VERSION.fullmatch(version): continue
            count = row.get('downloadCount', 0)
            rows.append({'id': identity, 'name': str(row.get('displayName') or row['name'])[:200],
                         'description': str(row.get('description') or '')[:600], 'version': version,
                         'downloads': count if type(count) is int and count >= 0 else 0,
                         'url': 'https://open-vsx.org/extension/' + row['namespace'] + '/' + row['name']})
        total = data.get('totalSize', len(rows))
        if type(total) is not int or total < 0: total = len(rows)
        result = {'extensions': rows, 'total': total, 'offset': offset, 'next_offset': offset + len(data['extensions']), 'more': offset + len(data['extensions']) < min(total, 1020)}
        with self.lock:
            if len(self.cache) >= 32: self.cache.pop(next(iter(self.cache)))
            self.cache[key] = (time.monotonic(), result)
        return result
