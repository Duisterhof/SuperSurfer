---
name: supersurfer-results
description: Build or revise an experiment Results page from measured runs, starting with overlaid train and validation/test curves comparing methods, followed by the user's requested domain-specific visualizations.
metadata:
  supersurfer-version: '0.1.19'
---

# Experiment results

Reviewed for SuperSurfer 0.1.19. Apply when creating, improving or interpreting
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
`result_id` when revising the page; this publishes saved content, not a live
W&B subscription, so describe whether charts are snapshots or explicitly refreshed. JavaScript and WebGL are allowed in the sandbox; assets must be inline
or available over an appropriate HTTPS URL. An authenticated W&B or Rerun embed
may refuse framing, so supply a working source link and a useful local plot or
preview. Do not replace requested figures with bare W&B group links. Never embed
tokens, local filesystem URLs or app credentials.

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
work: HTML updates have no version check, so coordinate before replacing a page
that another worker is editing.

Desktop windows restore their own workspace and selected tab. Reopening a saved
Results page does not refresh a published snapshot or request a new publication.
A release or larger result pane is also not an instruction to rewrite existing
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
refresh behavior in a compact provenance section. The built-in W&B view is sampled;
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
without requiring a republish. Use responsive plots and wrapping legends; a
figure that only works after closing the chat is not a usable in-app comparison. Describe unavailable evidence precisely;
do not claim a screenshot or interactive test was performed unless it was.
