# SuperSurfer 0.1.41 performance and Cursor connection review

Measurements use disposable Linux fixtures, local storage and warm caches. They
exclude real model inference, GitHub checks, data transfer and GPU observation.
Results are observations on this machine, not response-time guarantees.

## Cursor connection

The friend’s exact error and computer are unavailable. Controlled tests cover
missing CLI setup, current JSON status, legacy text status, rejected contradictory
status, unsupported protocol initialization without prompt delivery, delayed other-provider checks, host-bound Terminal commands, a failed
Terminal launch, expired-code retry, reconnect error visibility, sign-in confirmation and provider selection. Cursor Desktop and
the workspace-host CLI are distinct installations.

The installed Cursor CLI, version `2026.10.01-e373342`, completed real ACP v1
initialize/authenticate handshakes using an existing login in 490–541 ms, with
sandbox enabled and disabled. It advertised `cursor_login` and session loading.
No prompt, new OAuth login, sign-out, research task or paid inference was sent.
Fake protocols separately exercise resume, scoped MCP, approvals, questions,
concurrent scopes, stop ownership and uncertain disconnects without replay.

Official behavior follows Cursor’s [CLI installation](https://cursor.com/docs/cli/installation),
[authentication](https://cursor.com/docs/cli/reference/authentication) and
[ACP](https://cursor.com/docs/cli/acp) documentation. Remote sign-in sets
`NO_OPEN_BROWSER=1`; the user opens the link printed by the official CLI locally.
Installation is an explicit fixed Terminal action, not an automatic download.

## Measured read paths

The baseline is main before this release, with 40 synthetic tasks and twelve
600-message transcripts. Five warm calls are measured per operation. The full
chat comparison retains the same 600-message payload; the recent-history row
measures the new default response window separately.

| Operation | Baseline median | Final median |
| --- | ---: | ---: |
| Workspace state | 61.64 ms | 6.97 ms |
| Full chat read, 600 messages | 483.05 ms | 2.50 ms |
| Recent chat read, 80 messages | — | 1.87 ms |
| Agent directory | 60.03 ms | 7.93 ms |
| Context for an actual turn | 375.38 ms | 17.43 ms |

A 200-task fixture measured 28.06 ms for state, 1.82 ms for the recent chat and
59.03 ms for actual-turn context. At 1,000 tasks, the same paths measured
151.66 ms, 1.80 ms and 288.84 ms respectively. This separates work that scales
with the workspace from the bounded chat read.

The browser benchmark uses a 600-message transcript with Markdown and tables.
The four update samples changed from 434/419/439/421 ms (median 427 ms) to
112/91/76/97 ms (median 94 ms). Initial display changed from 349 to 142 ms.
The new default renders 80 recent messages; Show earlier fetches and renders the
next window, preserving older history. An unchanged read returned 304 without
rebuilding chat DOM. These synthetic transcripts contain repeated text, so their
compression ratios should not be treated as real-world bandwidth estimates.

With the actual Code OSS extension host and Vim installed, four selection-to-chat
samples measured 58/87/94/97 ms. The test uses Linux Ctrl+L; native macOS Cmd+L is
configured but was not exercised on a Mac. Selection also reaches chat while a
saved LaTeX file’s compilation callback remains pending.

## Changes and preserved boundaries

- Project lookup avoids unrelated task/context reconstruction; only actual turns
  build their complete context. Task labels come from current saved workflows.
- Compiled Surfboards cache by complete content with a 128-entry bound; public
  results remain independent copies. No cached graph grants stale capabilities.
- Unchanged experiment snapshots perform no SQL writes. External Markdown changes
  still update content and versions.
- Display manager refreshes share timestamped evidence. Explicit fresh checks
  wait and reject unavailable managers. Data and observation time publish atomically; status reads do not add GPU probes.
- Textual HTTP responses compress; authenticated ETags validate scope before 304.
  Binary/range responses retain their offsets. UI memory is capped at 12 response
  entries and eight million JSON characters, and cleared on a token change.
- UI provider status coalesces for ten seconds. Every turn and explicit check
  still use fresh status; account sign-out/send serialization remains intact.
- Assistant text persistence coalesces for 150 ms. Decisions, questions, approvals,
  lifecycle outcomes and graceful shutdown flush immediately. Abrupt termination
  can lose that bounded streaming tail, while uncertain work is not replayed.
- Canceled editor/chat reads cannot apply stale state. Native save/compile callbacks
  do not block the next selection event. Cmd/Ctrl+L outranks Vim’s default binding.
- Native review refreshes preserve an unchanged patch document and supply the
  service-validated path on activation. Six consecutive native mixed-chunk runs
  passed after the fix, including dirty-buffer rejection protection.
- The manager/lead/worker skill entrypoints are 32.7% shorter. Specialist details
  remain in references, with role ownership and authorization rules retained.

## Reproduce

From the repository root, with Node dependencies and browser prerequisites:

```bash
python3 tests/profile-performance.py 40 --profile
python3 tests/profile-performance.py 200
python3 tests/profile-performance.py 1000
node tests/chat-performance.browser.cjs
python3 -m unittest discover -s tests -p test_performance041.py -v
```

The native editor browser scripts also require the verified Code OSS runtime.
A reviewed [synthetic diagnostic export](cursor-performance041-diagnostics.md)
contains no live account records or user transcripts. It is not a diagnostic
export from the friend’s unavailable computer.

## Sustained checks

The 90-minute metadata/read run passes; its final periodic sample contains
19,023 authenticated reads, 13,948 unchanged replies, 18.50 ms median response,
100.43 ms maximum and 49.02 MiB peak RSS. The compiled cache stays at 128 entries.
It cycles synthetic queue saturation (0–200 attempts), task lifecycle, four
workflows, manager outages and external document changes. This long-lived process
loads an earlier optimized read snapshot; subsequent guards are covered by the
final regression suite.

The 60-minute fake-provider run passes 1,678 streaming, scoped approval/question,
stop, concurrency and restart checks without replay. After cleanup, it retains
one thread and four descriptors; observed peak RSS is 31.49 MiB. No actual research
jobs, live account changes or model prompts are used for either sustained run.
