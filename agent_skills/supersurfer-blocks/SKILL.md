---
name: supersurfer-blocks
description: Publish requested reusable HTML views with copied project assets, then place their durable identities on scoped SuperSurfer pages without changing execution authority.
metadata:
  supersurfer-version: '0.1.36'
---

# Reusable HTML blocks

Reviewed for SuperSurfer 0.1.36. Use for a user-requested persistent custom view,
such as a failure-video comparison, GIF gallery or interactive explanation.
The library is workspace-wide: already-published views can be reused across
projects, independently of a Results block's experiment data-sharing selection.
Publish only the explicitly intended content; ordinary source access does not
permit exposing credentials, private service state or unrequested private data.
Presentation grants no execution tools, launch permission or new agent scope.

## Publish and arrange

1. `list_view_blocks` reads library metadata, publishing projects, current versions
   and temporary preview URLs. Pass `block_id` to read the publishing project's
   current HTML, version and published asset names for an edit in this or a later
   conversation. Other projects may use a published view but cannot read its
   editable source through that operation. Reuse a suitable existing block when
   possible; listing is not a request to revise another project's publication. Manager
   supplies `project_id`; project/task roles keep their fixed project scope.
2. `publish_view_block` requires an active user-origin task, not a scheduled check
   or peer update. Supply `title`, `html` and optional `assets`: a mapping from
   HTML-relative names to existing repository-relative or returned `artifact:`
   paths in the publishing project. Ordinary source files remain unchanged.
   The service copies safe regular assets, rejecting symlinks, hard links, secret
   paths and files that change during copying. Use at most 32 assets, 1 MiB UTF-8
   HTML, 512 MiB per asset and 1 GiB total assets. Titles are 1–100 characters;
   the library holds at most 500 block identities.
3. Use relative resources, for example `<video controls src="clips/failure.mp4">`
   with `assets={"clips/failure.mp4":"outputs/failure.mp4"}`. Declare every resource
   needed by the view. `index.html` is reserved. Include readable captions, units,
   provenance and honest unavailable states. Do not invent scientific measurements
   or substitute a link for a usable requested visualization. Check actual media
   playback; browser codec support varies, so retain a clear download fallback.
4. `read_view_layout`, then `update_view_layout` with an existing page's tile
   `{id, kind: "html", block_id, span: 12, height: 600}`. Use current layout and
   board versions and preserve unrelated pages, tile IDs and nested split trees.
   Multiple HTML tiles may share one page, within the normal 16-tile limit.
   Moving, resizing or detaching a block view does not publish it again or launch
   work. Separate-window controls remain user GUI actions, not agent tools.

## Revisions and snapshots

For an update, reuse the block's `id` and exact current `version`. Only its
publishing project can revise it. Read with `list_view_blocks({block_id})` first,
then preserve unrelated HTML and use its returned version. Resolve a conflict by
rereading that source and reconciling the intended change; never overwrite another
project's block.

The update supplies complete new HTML, not a partial patch or live filesystem
binding. **Omit `assets` to preserve the previous copied media** in the new immutable
version; no original repository paths are needed for an HTML-only edit. A supplied
`assets` map replaces the entire resource set, and an explicit empty map removes
all media. Include every wanted mapping when replacing resources. Returned
`asset_names` identify publication names, not original source paths; do not guess
repository paths or copy private library state to reconstruct them. Editing an
original image, video or HTML file does not update its published immutable copy.

Keep the returned `block_id` in page configuration. A preview URL is a temporary
bearer capability, valid for at most one hour or until service restart; do not
commit it, expose it in diagnostic exports or treat it as a permanent public link.
Reopening obtains a new capability for the current version. Existing loaded views
retain their immutable version until reopened; new opens resolve the current
publication. Local chart interactions and unsaved editor text are not synchronized
across windows. A lost response from a new publication is uncertain: inspect the
library before publishing another block; do not claim creation is idempotent.

## Sandbox and evidence

The HTML frame has an opaque sandbox origin, scripts/downloads enabled and no
app API, filesystem, parent access or app credentials. Copied local asset requests
are allowed only under that exact immutable publication's loopback capability
prefix. Relative module imports and data/model loads can therefore use declared
assets, including a copied local 3D library, JSON or model file. Public capability
assets provide CORS access for the opaque frame; this does not expose app APIs,
other publications, private state or credentials.

Declare and copy every required resource; use relative URLs or inline data.
External live fetches, including direct W&B history access, remain unavailable.
Do not promise arbitrary CDN scripts, remote images or unrestricted networking;
unsupported workers, browser APIs or library features still require actual checks.
HTTPS iframes are permitted, but embedded services can require sign-in or prohibit
framing. Preserve an ordinary source link and usable local findings when needed.
No automatic public hosting, live-source bridge or external sharing is provided.

Use the results skill and `publish_training_results` for live measured training
and actual held-out curves. A reusable gallery can show copied fixed evidence
with its exact source/run/checkpoint and extraction date; it does not become a
new W&B writer, fresh measurement or shared execution gate. Keep Code, Full VS
Code, Terminal, Ports, PDFs and Results separate where their existing views
satisfy the request. Reuse the block only when its content and publication scope
match the user's intended view.
