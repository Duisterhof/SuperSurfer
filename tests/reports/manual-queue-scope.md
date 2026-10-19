# Manual queue response regression

An authenticated `run.queue` request successfully created and released one run,
then returned HTTP 400 `Unknown conversation scope`. The queue request's durable
`manual:<request_id>` identity was passed to optional Results checkpoint setup.
The operations-profile lookup ran before the existing worker-scope guard; the
real backend router correctly rejected this non-conversation identity.

The regression fixture uses a temporary service, the real backend router and a
fake manager. Before the fix, its HTTP request reproduces the 400. After the fix,
the response is 200 with the created run ID. The same request after service
restart returns that ID as already queued. Exactly one submit, review and ready
occur; no provider chat or model turn is created.

The correction moves optional profile lookup behind the existing experiment /
conversation scope guard and inside the existing best-effort bookkeeping block.
No live run was submitted, released, cancelled or otherwise modified to verify
this fix. This report contains no private transcript or live run payload.
