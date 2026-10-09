'use strict';
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const { packager } = require('@electron/packager');
const root = path.resolve(__dirname, '..');
const version = require('../package.json').version;
require('./build-remote.cjs');
(async () => {
  const platform = process.env.SUPERSURFER_PLATFORM || 'darwin';
  const arch = process.env.SUPERSURFER_ARCH || (platform === 'darwin' ? 'arm64' : process.arch);
  const apps = await packager({
    dir: root, name: 'SuperSurfer', platform, arch,
    electronVersion: require('../package.json').devDependencies.electron,
    appBundleId: 'research.supersurfer.desktop', appCategoryType: 'public.app-category.developer-tools',
    out: path.join(root, 'dist'), overwrite: true, asar: false,
    icon: path.join(root, platform === 'darwin' ? 'desktop/icon.icns' : 'desktop/icon.png'),
    ignore: [/^\/dist(?:\/|$)/, /^\/tests(?:\/|$)/, /^\/\.git(?:\/|$)/, /^\/\.pytest_cache(?:\/|$)/, /^\/node_modules(?:\/|$)/, /__pycache__/],
    darwinDarkModeSupport: true,
    // Renaming/repacking Electron invalidates its original bundle signature.
    // Seal native Mac builds locally; this does not provide Developer ID trust.
    osxSign: platform === 'darwin' && process.platform === 'darwin' ? {
      identity: '-', identityValidation: false,
      preAutoEntitlements: false, preEmbedProvisioningProfile: false,
      // Ad-hoc identities have no Team ID for hardened-runtime library validation.
      optionsForFile: () => ({ hardenedRuntime: false }),
      continueOnError: false,
    } : undefined,
  });
  for (const folder of apps) {
    if (platform === 'linux') {
      const archive = path.join(root, 'dist', `SuperSurfer-${version}-linux-${arch}.tar.gz`);
      execFileSync('tar', ['-czf', archive, '-C', path.dirname(folder), path.basename(folder)]);
      console.log(archive);
      continue;
    }
    const archive = path.join(root, 'dist', `SuperSurfer-${version}-mac-${arch}.zip`);
    if (fs.existsSync(archive)) fs.unlinkSync(archive);
    if (process.platform === 'darwin') execFileSync('ditto', ['-c', '-k', '--sequesterRsrc', '--keepParent', path.join(folder, 'SuperSurfer.app'), archive]);
    else execFileSync('zip', ['-q', '-r', '-y', archive, 'SuperSurfer.app'], { cwd: folder });
    console.log(archive);
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
