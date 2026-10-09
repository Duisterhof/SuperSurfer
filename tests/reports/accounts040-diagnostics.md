# SuperSurfer 0.1.40 reviewed synthetic diagnostics

This report contains only disposable fixture behavior. No real workspace logs,
credentials, source, host aliases or private research data are included.

## Reproduction

1. Open a fresh workspace with a synthetic signed-out provider account.
2. Confirm the previous onboarding default selected Codex rather than asking for a provider.
3. Open Settings: the previous page emphasized Codex, placed other accounts lower
   in the form, and had no sign-out control.
4. Open a task with two editor/results panels and several report tabs. Panel
   removal previously required explicit Rearrange; task tab removal was indirect.
5. Publish a report for an initial synthetic attempt, then add another attempt.
   The report catalog alone did not establish coverage of the new attempt.

## Checked result

The new provider picker saves all three role defaults only after verified sign-in.
Settings has all three provider rows and native idle-guarded sign-out. Source,
thread history and existing session ownership are retained. Disposable browser
checks cover Codex, Cursor-only and Claude-only configurations.

Pages and blocks now have direct removal controls; presentation-only saves retain
files, notes, reports and jobs. Report tabs reorder and remove/restore with a
revision guard. A known unsaved Monaco model survives panel removal and re-add.

Research attempt changes create/reopen a saved Results checkpoint. The service
rejects missing/stale report coverage and premature checkpoint completion;
explicit unavailable measurements remain valid, and no inference values are
invented. Scientific correctness requires the role's actual evidence review.

The fixture suite does not claim a real new-account authentication callback or
macOS launch. Those external checks remain listed in VALIDATION.md.
