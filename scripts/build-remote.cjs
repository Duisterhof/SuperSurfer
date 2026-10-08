'use strict';
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
require('./build-editor.cjs');
execFileSync('python3', [path.join(__dirname, 'check-agent-skills.py')], { cwd: root, stdio: 'inherit' });
execFileSync('tar', ['--exclude=__pycache__', '--exclude=*.pyc', '-czf', path.join(root, 'desktop', 'remote.tar.gz'), 'server', 'ui', 'agent_skills', 'engine'], { cwd: root });
console.log('Remote service bundled.');
