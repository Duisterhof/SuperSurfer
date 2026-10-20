# Stanford flexible queue admission diagnostic

Sanitized reproduction of a live scheduler observation, October 20, 2026.
No credentials, host addresses, workspace paths, account names or research data
are included.

## Reproduction

1. Submit a reviewed, ready four-GPU Stanford `single_node_training_v1` job.
2. While its cluster allocation is pending, submit a second authorized four-GPU
   flexible job. Both fit the aggregate eight-GPU allowance.
3. Schedule the queue.

## Observed behavior

The second request remained ready and queued without an allowance-specific wait
reason. The manager skipped every Stanford request while any other Stanford
allocation was starting, running, cancelling or unreachable. That exclusion was
inherited from the older exclusive smoke and fixed seven-GPU profiles.

## Expected and verified behavior

Two flexible four-GPU requests can be submitted concurrently, including across
projects. A third request waits with `stanford_gpu_limit`. Cancelling and
uncertain allocations retain their share until terminal confirmation. Legacy
profiles remain exclusive. Exact-source review, explicit authorization and all
other cluster admission constraints continue to apply.

The isolated service-to-scheduler regression uses a mocked cluster transport:
two four-GPU admissions, a blocked third, uncertain-state accounting and release
after confirmed cancellation. It launches no real cluster job.
