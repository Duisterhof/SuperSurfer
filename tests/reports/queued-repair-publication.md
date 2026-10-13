# Queued source repair and publication receipts

A project lead could identify an available GPU model, but the original queued
job had a model-specific source guard. No tool could update its reviewed commit
without replacing the queued run. A recovery worker also could not execute its
own configured Results check. Separately, starting/retrying a publication check
scanned repository source before creating/returning an execution receipt, allowing
slow I/O to exhaust the agent HTTP timeout.

The regression fixtures cover in-place exact-source repair, held review failures,
retries, concurrent cancellation, previously attempted runs and owner authority.
A deliberately blocked source scan verifies immediate durable receipts, responsive
status and duplicate-free retries. No research jobs or account credentials appear
in these fixtures or this report.
