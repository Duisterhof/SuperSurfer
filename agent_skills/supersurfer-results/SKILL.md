---
name: supersurfer-results
description: Build or revise an experiment Results page with live W&B train and validation/test comparisons across methods, followed by the user's requested domain-specific visualizations and identified static artifacts.
metadata:
  supersurfer-version: '0.1.21'
---

# Experiment results

Reviewed for SuperSurfer 0.1.21. Apply when creating, improving or interpreting
an experiment's Results tab. Use the experiment's real runs, W&B history and
artifacts. The output is a research comparison, not a progress report or an
interface demo. Respect the requested methods, splits, checkpoints and visuals.

## Lead with the comparison

Lead with overlaid training and actual held-out curves comparing methods. Use
one plot when metric definitions match, or aligned panels for different
quantities; never place training loss and a test success rate on an unlabeled
shared scale. Use one consistent color per method and
line style for split, for example solid training and dashed validation. Keep
legends readable and consistent across plots. Show loss first when that is the
meaningful shared training signal; also show the domain's primary quality metric.

Label the actual split: validation and test are not interchangeable. If test
was measured only once, show its point or a compact final-results comparison;
do not fabricate a test curve. If a requested method, training curve or held-out
split is unavailable, label the gap beside the plot and state the source checked.
Before declaring a gap, check the recorded runs and artifact sources and ask
the owning worker directly when it can supply the missing evidence. Show the
available measured comparison rather than a polished empty dashboard. A request
to report results does not authorize another run to fill a missing curve.

Choose comparable axes: optimizer steps, examples/tokens seen, or elapsed training
time. Label units, global batch and any important difference in training budget.
Do not silently equate steps from different batch sizes. Overlay only compatible
metric definitions and protocols; split incomparable quantities into labeled
panels. Do not silently average different evaluation conditions, checkpoints or cohorts
together; identify any intended aggregate and its weighting.

Keep raw observations accessible. If smoothing helps, show a faint raw trace and
name the smoothing setting. Never extend a line beyond observed data or bridge
a long missing interval as though it was measured. Plot seeds separately or show
an explicitly defined aggregate with the number of independent runs and justified
uncertainty. One training seed cannot establish variability across independent
runs; distinguish that from uncertainty computed from evaluation trials and
state the sampling unit.

## Add the requested scientific evidence

After the main curves, include each visualization the user asked for. For a VLA
experiment this might be task-level success with trial denominators, matched
success/failure videos, predicted versus actual trajectories, temporal alignment,
or an interactive 3D/Rerun view. Select examples by an explicit rule and identify
their task/scene/checkpoint; do not cherry-pick flattering cases without disclosure.
Show corresponding examples side by side when comparing methods.

Use `publish_result` with `title` and `html` for a self-contained HTML page
with plots and interactive widgets (at most 2,000,000 UTF-8 bytes). Reuse its
`result_id` when revising the page. Link W&B training curves through the live
source contract below; fixed evaluation artifacts, videos and sealed reports
may remain clearly identified snapshots. JavaScript and WebGL are allowed in the sandbox; assets must be inline
or available over an appropriate HTTPS URL. An authenticated W&B or Rerun embed
may refuse framing, so supply a working source link and a useful local plot or
preview. Do not replace requested figures with bare W&B group links. Never embed
tokens, local filesystem URLs or app credentials. Workspace ChatGPT sign-in
enables model work on that host; it does not authenticate a W&B/Rerun embed or
grant the Results sandbox account access. The live-source bridge fetches only
declared history through the workspace's W&B account. Diagnose failed W&B access
separately from agent sign-in; preserve measured fallback data and report the
source error without requesting credentials in chat or bypassing the sandbox.

## Keep training curves connected to W&B

Declare `wandb_sources` when publishing: at most six individual W&B run sources,
each with a unique `id`, an individual run `url` and 1–64 exact history `keys`.
Group or project links cannot supply a run's curve. Include the actual x-axis
key when using a logged optimizer step, epoch or other axis instead of `_step`.
For infrequent validation/test samples, add `sparse_metrics` entries with `key`
and `x_axis`; both must be declared keys, except `_step` is always allowed as an
axis. At most twelve sparse metrics are accepted per source. This prevents the
ordinary training-history sample from hiding infrequent held-out measurements.

The app injects `window.SuperSurferResults` into live report documents before
their scripts. Implement `SuperSurferResults.subscribe(({sources = [], loading,
error}) => { ... })` in the HTML and redraw the plots and data-derived claims
from each update. Match sources by their declared IDs, not array position.
Each source supplies `rows`, `run_id`, `state`, `fetched_at`, `observed_at`,
`checked_at`, `sampled`, `stale` and `error` when available. Handle initial
loading and empty/error sources without erasing useful prior curves. A source
declaration alone does not make hard-coded arrays, headline numbers or captions
current. Use ordinary safe text rendering for source names and errors.

Every Results opening fetches fresh declared history; the report can also call
`SuperSurferResults.refresh()` for an in-page refresh control. An agent turn,
republish or worker wakeup is unnecessary for curve freshness. This is refresh
on opening or request, not a promise of continuous polling while the page stays
open. The iframe cannot select new sources, access app credentials, read local
files or use an arbitrary authenticated API. Add or change sources through the
scoped `publish_result` tool, never by embedding tokens or fetching a private
API directly from the report.

History is bounded and sampled with a separately fetched recent tail; it is
not a complete export of every point. Plot measured rows only. A run summary is
not a curve point. Preserve sparse observations, missing intervals and phase
boundaries; do not convert absent values to zero. `fetched_at` identifies a
successful fetch, `checked_at` a refresh attempt, and `observed_at` the newest
available source sample. That newest sample need not be the latest validation
measurement: use each plotted metric's rows and timestamps for its own age.
Show timestamps in the user's local timezone and label unknown ages honestly.

When a source fails, retain its last successful observations with their original
fetch and sample times, visibly label stale data, and identify partial coverage
when another source succeeds. A top-level refresh error also leaves prior data
stale; never change its age to the failed attempt time. Keep method comparisons,
protocol and phase labels, and the provenance of any fixed fallback when migrating
an existing report. For example, a sealed validation artifact can complement
live training history, but must be identified as that artifact with its checkpoint
and extraction time instead of being relabelled as current W&B validation.

The HTML Results page fills the available main pane inside the existing sandbox.
Build a responsive full-page document whose content scrolls naturally in that
one area; avoid a second fixed-height scrolling dashboard inside it. The app
already supplies the Floating Panels frame: publish the research content without
recreating sidebars, a chat composer or another glass dashboard around the plots.
Give charts and text a legible background of their own; the sandbox does not
inherit the parent app's theme variables. If offering light/dark presentation,
verify both palettes and keep a readable fallback when transparency is reduced.
Size plots to their container, wrap controls and legends, and give 3D/video widgets
sensible responsive dimensions. Put the clear train/held-out comparison before
extended prose so the extra space serves the evidence. Filling the pane does not
grant parent-window, filesystem or authentication access.

Use `publish_markdown_tab` with `title` and `markdown` for detailed protocols,
derivations or analysis beyond the figures. For an existing tab, read with
`page_id`, then update with that ID and its current `version`; reconcile a
conflict rather than overwriting. Keep the main explanation brief with
`update_experiment_brief`, reading its current version before replacing sections.
Reuse existing page/result IDs to improve the page rather than accumulating
slightly different result tabs. Leads/managers supply the registered
`experiment_id` for these tools; leads remain in their project. Workers publish
only within their own experiment and omit `experiment_id`. Preserve concurrent
work by supplying the current result record's `sha256` as `expected_sha256` when
updating HTML; reread and reconcile a conflict. This optional check guards the
HTML revision, so still inspect current source declarations before changing them.
Omitting `wandb_sources` preserves existing declarations, and updates to a live
page must still implement the subscription. An explicit empty array removes live
sources and makes the page a snapshot; do not use it to bypass a rendering error
or a failed fetch.

Desktop windows restore their own workspace and selected tab. Reopening a saved
Results page refreshes its declared W&B sources without dispatching model work;
an undeclared static snapshot remains static. Opening a page authorizes no run,
monitoring task, handoff or extra approval request. A release or larger result
pane is also not an instruction to rewrite existing
results; revise saved pages only within the requested reporting task.
Read current experiment and page records before an authorized revision, preserving
their IDs and any changes made while the desktop was closed. Keep provenance
within the connected workspace; matching experiment names in another window do
not establish that its runs or artifacts belong in this comparison.

## Write only what the evidence supports

Use an informative title, at most a few sentences setting up the comparison,
and short captions explaining the measured difference. Separate observations
from hypotheses. Report the comparison metric, denominator, checkpoint and
uncertainty needed to assess a claim. Say when a result is provisional.

Avoid launch logs, lengthy recaps, congratulatory prose, generic cards, invented
scores, unexplained acronyms and repeated claims that an experiment is important.
MFU, VRAM and throughput support a compute-efficiency question; they do not replace
the primary train/held-out comparison. Scheduler state belongs in Runs.

A retained queue request or recovered draft is not a measurement. Link the actual
run ID once confirmed, and preserve that identity through submission retries;
do not count retries as independent runs, seeds or evidence. If feature-cache
preparation blocks training, state which measured curves are unavailable without
replacing the comparison with queue diagnostics or labelling the research failed.
Have the owning worker resolve its original request through the scoped workflow;
publishing Results never authorizes a replacement run.

Put source run links/IDs, commit/PR, data split, protocol, extraction time and
refresh behavior in a compact provenance section. The W&B history view is sampled;
a latest summary value alone cannot reconstruct a learning curve. If sampled
history and summary disagree, compare their timestamps and metric definitions
before choosing a value, and preserve missing intervals. For live efficiency
figures, use the MFU sample time independently of loss and system timestamps. A
recent page refresh or another metric's update does not refresh an older MFU
measurement; label unknown sample ages instead of implying live data. Keep a reproducible plotting
script or source data reference in the project when practical. Preserve other
workers' edits and unrelated evidence.

Before reporting completion, inspect the rendered page: verify that the leading
curves really compare methods and splits, legend colors/units are consistent,
requested domain visuals are present or explicitly unavailable, and links and
widgets work at the app's normal width, including with the agent panel open
and resized narrower. Check that changing pane width preserves useful labels
and widget controls, and that returning from fullscreen chat restores the report
without requiring a republish. For live curves, reopen Results and exercise
refresh, missing/sparse samples and a source failure: new observations should
reach the plots and current claims, while stale/partial data keeps its true age.
Use responsive plots and wrapping legends; a
figure that only works after closing the chat is not a usable in-app comparison. Describe unavailable evidence precisely;
do not claim a screenshot or interactive test was performed unless it was.
