# Recovery requests stalled behind historical status scans

Production had 1,267 native runs. Every 50-run page repeated the full workspace's
projects, agents, hosts and GPU scan, with a five-second socket deadline. A linked
contrastive recovery child existed natively but fresh scoped lookups reported it
missing after status refresh failures. The recurring SR42 owner's submission was
also blocked before durable submission.

The adapter now reads workspace metadata once, then retrieves remaining complete
run contracts through bounded `run.list` pages. It retains count, empty-page and
duplicate checks and preserves the previous timestamped snapshot on failure. Read
RPCs use a bounded 25-second timeout; source verification keeps its 120-second
limit. No launch, ownership, source-review or allocation checks change.

Validation: five status-pagination tests and thirteen recovery tests passed.
Restricted-sandbox fixture initialization timed out; the identical suite passed
outside that sandbox. A read-only production snapshot returned all 1,267 native
run IDs, no duplicates or omissions, including the linked contrastive child, in
13.74 seconds. No credentials, scientific data or private source are included here.
