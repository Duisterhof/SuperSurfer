(function () {
  'use strict';
  const builtins = new Set(['light', 'dark', 'system']);
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const catalog = new Map();
  const appliedVariables = new Set();
  let preference = 'system', error = null, loading = false;
  const selectionId = id => String(id).startsWith('vscode:') ? String(id) : 'vscode:' + String(id);
  function normalize(raw) {
    if (!raw || typeof raw.id !== 'string' || !raw.id || typeof raw.name !== 'string' || !raw.colors || typeof raw.colors !== 'object') return null;
    const colors = {};
    for (const [key, value] of Object.entries(raw.colors)) {
      if (typeof value === 'string' && CSS.supports('color', value)) colors[key] = value;
    }
    return { id: selectionId(raw.id), name: raw.name, type: ['dark', 'light', 'hcDark', 'hcLight'].includes(raw.type) ? raw.type : 'dark', colors };
  }
  function merge(descriptors) {
    for (const raw of descriptors || []) { const theme = normalize(raw); if (theme) catalog.set(theme.id, theme); }
  }
  function cache() {
    try { localStorage.setItem('supersurfer-vscode-themes', JSON.stringify([...catalog.values()])); } catch {}
  }
  try {
    const saved = localStorage.getItem('supersurfer-theme');
    if (builtins.has(saved) || typeof saved === 'string' && saved.startsWith('vscode:')) preference = saved;
    const savedThemes = JSON.parse(localStorage.getItem('supersurfer-vscode-themes') || '[]');
    if (Array.isArray(savedThemes)) merge(savedThemes);
  } catch {}
  function tokens(theme) {
    const dark = theme.type === 'dark' || theme.type === 'hcDark', c = theme.colors;
    const pick = (keys, fallback) => keys.map(key => c[key]).find(Boolean) || fallback;
    const bg = pick(['editor.background'], dark ? '#1f1f1f' : '#ffffff');
    const fg = pick(['editor.foreground', 'foreground'], dark ? '#cccccc' : '#333333');
    const sidebar = pick(['sideBar.background'], dark ? '#181818' : '#f3f3f3');
    const panel = pick(['panel.background', 'editorWidget.background'], bg);
    const muted = pick(['descriptionForeground', 'sideBarSectionHeader.foreground'], dark ? '#9d9d9d' : '#616161');
    const line = pick(['panel.border', 'sideBar.border', 'widget.border'], dark ? '#343434' : '#e5e5e5');
    const border = pick(['input.border', 'dropdown.border', 'contrastBorder'], dark ? '#454545' : '#cecece');
    const accent = pick(['textLink.foreground', 'focusBorder'], dark ? '#4daafc' : '#006ab1');
    const soft = pick(['editorWidget.background', 'list.hoverBackground'], dark ? '#252526' : '#f3f3f3');
    const input = pick(['input.background', 'dropdown.background'], dark ? '#313131' : '#ffffff');
    const warning = pick(['editorWarning.foreground', 'terminal.ansiYellow'], dark ? '#cca700' : '#895503');
    const danger = pick(['errorForeground', 'editorError.foreground', 'terminal.ansiRed'], dark ? '#f48771' : '#a1260d');
    const values = {
      '--bg': bg, '--text': fg, '--sidebar': sidebar, '--soft': soft, '--muted': muted,
      '--line': line, '--strong-line': border, '--green': accent, '--red': danger, '--orange': warning,
      '--theme-sidebar-text': pick(['sideBar.foreground'], fg),
      '--theme-panel': panel, '--theme-title': pick(['titleBar.activeBackground'], bg),
      '--theme-title-text': pick(['titleBar.activeForeground'], fg),
      '--theme-input': input, '--theme-input-text': pick(['input.foreground', 'dropdown.foreground'], fg),
      '--theme-placeholder': pick(['input.placeholderForeground'], muted),
      '--theme-hover': pick(['list.hoverBackground'], soft),
      '--theme-selection': pick(['list.activeSelectionBackground'], dark ? '#04395e' : '#cce8ff'),
      '--theme-selection-text': pick(['list.activeSelectionForeground'], fg),
      '--theme-button': pick(['button.background'], dark ? '#0078d4' : '#007acc'),
      '--theme-button-text': pick(['button.foreground'], '#ffffff'),
      '--theme-button-hover': pick(['button.hoverBackground'], dark ? '#026ec1' : '#0062a3'),
      '--theme-secondary': pick(['button.secondaryBackground'], soft),
      '--theme-secondary-text': pick(['button.secondaryForeground'], fg),
      '--theme-focus': pick(['focusBorder'], accent),
      '--theme-badge': pick(['badge.background'], soft),
      '--theme-badge-text': pick(['badge.foreground'], fg),
      '--theme-code': pick(['textCodeBlock.background', 'editorWidget.background'], soft),
      '--theme-quote': pick(['textBlockQuote.background'], soft),
      '--theme-quote-border': pick(['textBlockQuote.border'], accent),
      '--theme-warning-bg': pick(['inputValidation.warningBackground'], soft),
      '--theme-warning-border': pick(['inputValidation.warningBorder'], warning),
      '--theme-error-bg': pick(['inputValidation.errorBackground'], soft),
      '--theme-error-border': pick(['inputValidation.errorBorder'], danger),
      '--theme-success': pick(['editorGutter.addedBackground', 'terminal.ansiGreen', 'charts.green'], accent),
      '--theme-progress': pick(['progressBar.background'], accent),
      '--theme-toast': pick(['notifications.background'], panel),
      '--theme-toast-text': pick(['notifications.foreground'], fg),
      '--theme-active-tab': pick(['tab.activeForeground'], fg),
      '--theme-inactive-tab': pick(['tab.inactiveForeground'], muted),
      '--theme-tab-border': pick(['tab.activeBorderTop', 'tab.activeBorder', 'activityBar.activeBorder'], accent),
      '--theme-chart-grid': pick(['charts.lines'], line),
      '--theme-chart-text': pick(['charts.foreground'], muted),
    };
    ['green', 'yellow', 'blue', 'orange', 'purple', 'red'].forEach((name, index) => {
      const ansi = {green:'Green',yellow:'Yellow',blue:'Blue',orange:'Yellow',purple:'Magenta',red:'Red'}[name];
      values['--theme-chart-' + (index + 1)] = pick(['charts.' + name, 'terminal.ansi' + ansi], [accent,warning,'#569cd6','#ce9178','#b180d7',danger][index]);
    });
    return values;
  }
  function apply() {
    const root = document.documentElement, theme = catalog.get(preference);
    for (const key of appliedVariables) root.style.removeProperty(key);
    appliedVariables.clear();
    const dark = theme ? theme.type === 'dark' || theme.type === 'hcDark' : preference === 'dark' || preference !== 'light' && media.matches;
    root.dataset.theme = dark ? 'dark' : 'light';
    root.style.colorScheme = root.dataset.theme;
    if (theme) {
      root.dataset.vscodeTheme = theme.id;
      for (const [key, value] of Object.entries(tokens(theme))) { root.style.setProperty(key, value); appliedVariables.add(key); }
    } else delete root.dataset.vscodeTheme;
    window.dispatchEvent(new CustomEvent('supersurfer-theme', { detail: preference }));
  }
  function setPreference(value) {
    if (!builtins.has(value) && !catalog.has(value)) return;
    preference = value; error = null;
    try { localStorage.setItem('supersurfer-theme', value); } catch {}
    apply();
    if (window.superSurferDesktop?.setTheme) window.superSurferDesktop.setTheme(value).catch(reason => { error = reason.message || String(reason); apply(); });
  }
  async function refreshThemes() {
    loading = true;
    const sources = [fetch('/themes.json').then(response => { if (!response.ok) throw new Error('Theme catalog unavailable'); return response.json(); })];
    if (window.superSurferDesktop?.listThemes) sources.push(window.superSurferDesktop.listThemes());
    const results = await Promise.allSettled(sources);
    for (const result of results) if (result.status === 'fulfilled') merge(result.value.themes || []);
    loading = false; cache(); apply();
  }
  async function importTheme() {
    if (!window.superSurferDesktop?.importTheme) return null;
    const raw = await window.superSurferDesktop.importTheme();
    if (!raw) return null;
    const theme = normalize(raw);
    if (!theme) throw new Error('The selected file did not contain a supported VS Code color theme.');
    catalog.set(theme.id, theme); cache(); setPreference(theme.id); return theme;
  }
  window.superSurferTheme = {
    get preference() { return preference; },
    get themes() { return [...catalog.values()].sort((a,b) => a.name.localeCompare(b.name)); },
    get loading() { return loading; },
    get error() { return error || (preference.startsWith('vscode:') && !catalog.has(preference) && !loading ? 'The saved theme is unavailable. System appearance is shown until you select a theme.' : null); },
    setPreference, refreshThemes, importTheme,
  };
  media.addEventListener('change', () => { if (preference === 'system' || !builtins.has(preference) && !catalog.has(preference)) apply(); });
  apply();
  refreshThemes();
  if (window.superSurferDesktop?.getTheme) {
    window.superSurferDesktop.getTheme().then(value => {
      if (builtins.has(value) || typeof value === 'string' && value.startsWith('vscode:')) { preference = value; try { localStorage.setItem('supersurfer-theme', value); } catch {} apply(); }
    }).catch(() => {});
  }
})();
