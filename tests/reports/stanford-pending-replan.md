# Pending Stanford placement dependency

The existing flexible six-GPU request remained PENDING(Resources), never started.
A fresh test-only three-GPU placement was immediately feasible. The deployed
recovery tool could repair source after failure but could not change a pending
allocation. No reservation or trainer progress was inferred from that estimate.

The bounded repair adds pending-only cancellation and one linked replacement.
It retains exact-source PR review, owner grant, data/science and recovery budget.
Regression fixtures cover lost replies and concurrent starts/stops without a live
cluster, credentials, private paths or scientific launches.
