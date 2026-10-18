# Pending Stanford placement dependency

The existing flexible six-GPU request remained PENDING(Resources), never started.
A fresh test-only three-GPU placement was immediately feasible. The deployed
recovery tool could repair source after failure but could not change a pending
allocation. No reservation or trainer progress was inferred from that estimate.

The bounded repair adds pending-only cancellation and one linked replacement.
It retains exact-source PR review, owner grant, data/science and recovery budget.
Regression fixtures cover lost replies and concurrent starts/stops without a live
cluster, credentials, private paths or scientific launches.

The original pending job later started and failed during pre-CUDA scratch
selection: one local root was absent and the other had no available bytes.
The pending-only guard correctly rejected it. The follow-through extends
confirmed-failed retry with bounded typed resources and an unchanged reviewed
command except physical ranks. It preserves the same lineage, data and budget;
no cancellation or scientific source change is required.
