# Terminal and embedded editor shortcut regression

## Reports

In 0.1.42, Cmd +/− in the terminal did not resize terminal text. Cmd+B while
editing inside Code OSS did not toggle SuperSurfer’s navigation. New compact
editors could briefly show their internal file explorer.

## Cause

The iframe shortcut bridge intercepted zoom but always executed editor font
commands. Sidebar keyboard events remained inside the iframe. The iframe became
visible before asynchronous extension commands closed native navigation.

## Fix and reproduction checks

Zoom carries an explicit editor/terminal target. Terminal font changes use the
pane’s generated workspace settings, preserving shared user settings. Zero restores
the pre-zoom override or inheritance. Iframe sidebar shortcuts reach the existing
SuperSurfer handlers. Compact panes wait for explicit bridge readiness after native
sidebars close; Full VS Code retains its normal navigation.

The real Code OSS fixture exercises Control and Meta plus, minus and reset,
source-font/panel-width isolation, standalone terminal isolation, sidebar toggles,
clean startup, source editing, navigation, terminal cwd and selection-to-chat.
Unit checks cover target validation, readiness and inherited/explicit font reset.
All evidence uses generated test projects; no account or private project data is included.
