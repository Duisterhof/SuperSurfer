# Custom scientific HTML

Prefer `publish_training_results` for standard training comparisons. Use
`publish_result` for other interactive scientific artifacts or domain-specific
content beyond that renderer. Supply meaningful `title` and HTML up to 2,000,000
UTF-8 bytes. Reuse the existing `result_id`; pass its current `sha256` as optional
`expected_sha256` to reject conflicting HTML edits, and inspect current source
bindings separately. Workers omit `experiment_id`; leads/managers supply it within
their scope. Publishing records results and starts no research work.

The page fills the main pane and scrolls naturally there. Avoid nested fixed-height
scrollers and duplicated app navigation/chat. Give figures a readable background;
the sandbox does not inherit the app theme. Make plot sizes, controls and legends
responsive. Inline assets or use public/CORS-enabled HTTPS resources. JavaScript,
WebGL/3D and HTTPS iframes are allowed; parent/app credentials, local files and
forms are not. Never embed secrets. Authenticated remote embeds may reject framing
or need their own sign-in: provide useful measured fallback content and a source
link. Workspace ChatGPT login does not authenticate W&B/Rerun embeds.

Verify requested media in the real app pane, near the initial comparison where
the user can find it: images/GIFs must load, videos must play, and errors need a
visible fallback/source link. Check clipping and layout with chat open; an element
that exists below a long chart or outside a fixed container may still be invisible.
Retain scene/run/checkpoint provenance. A W&B file-view URL is an HTML page, not
a raw media URL, and cannot be used as video/image src without a real embeddable
resource. No separate private-file or media API is implied by these tools.

## Custom live-source contract

When W&B curves need custom HTML, declare `wandb_sources`: at most six sources
with unique `id`, individual run `url`, and 1–64 exact history `keys` each. Include
actual x-axis and phase-filter keys. For infrequent held-out metrics, add up to
twelve `sparse_metrics: [{key, x_axis}]` entries per source; both keys must be
listed except `_step` may always be an axis. Group/project URLs cannot supply
individual run curves.

The app injects `window.SuperSurferResults` before page scripts. Implement
`SuperSurferResults.subscribe(({sources = [], loading, error}) => { ... })` to
redraw plots and data-derived claims; match sources by ID. Render cached values
while loading, accept individual source completions, and do not clear successful
curves because another source remains pending. Sources include measured `rows`
and available `run_id`, `state`, `fetched_at`, `observed_at`, `checked_at`, `sampled`,
`loading`, `stale` and `error`. A source-level newest sample is not the timestamp
of every metric: use the relevant rows for validation/MFU age. Render labels and
errors as safe text.

The app fetches on opening; `SuperSurferResults.refresh()` requests another refresh.
The iframe cannot select undeclared sources or make arbitrary authenticated calls.
No agent/model turn or polling task is needed. Available cache and partial updates
must preserve original sample/fetch times, with visible source/top-level errors
and stale or incomplete comparisons. Plot bounded sampled rows with real missing
intervals; do not manufacture a curve from summaries or extend it past evidence.

Omitted `wandb_sources` preserves the existing declarations and requires the
replacement HTML to keep its subscription. Explicit `[]` disables live sources
and makes a snapshot; it is not an error-recovery shortcut. Preserve fixed artifact
provenance and existing live bindings when revising layout. Refreshing Results
changes no permissions, tasks, runs or monitoring rules.
