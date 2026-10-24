# Native SR42 placement and temporary-directory failure

Redacted diagnostic: the automatic evaluator request had verified inputs staged
on a bound destination but omitted host_id and used the whole project pool.
The preferred candidate was a different machine. After same-run placement was
corrected through the managed queue, execution failed before any scene with:

> Warp NVRTC_ERROR_COMPILATION: name of directory for temporary files is too long

The simulator derives TMPDIR as output/processes/NNN/tmp. The old output lived
inside a host/method/full-checkpoint-SHA staging directory. The adapter now keeps
that staging directory and full-SHA checkpoint/seal provenance intact while using
a fresh UUID output under a short node-local scratch path. The complete derived
TMPDIR is bounded to 90 ASCII bytes for either method and three-digit scene IDs.
The reviewed evaluator creates the output exclusively, so an existing directory
is never reused.

The request now carries its bound host alongside use_project_pool=true. Service
validation first resolves the ordinary pool contracts, then restricts only the
request to that host. Missing or ineligible hosts fail closed. Paths, package
requirements, source staging, GPU masks, PR checks and idempotent queue IDs remain.
No saved pool or recovery ownership is changed.

Eight regression tests cover the complete adapter-to-Service queue path, the
nondefault destination, exact eligibility, hostless behavior, backend mismatch,
short output paths, retained full-SHA provenance and fresh attempts. Read-only
validation of the actual saved pool confirmed the bound destination is eligible
and retains its configured GPU mask with the requested runtime/data overrides.
Private run IDs, host IDs and checkpoint values are omitted.

A CPU-only NVRTC 12.8 probe compiled a tiny kernel with a 90-byte TMPDIR without
loading a CUDA driver or executing a kernel. The tiny probe also passes at the
old path length, so it is not a reproduction of the complete Warp compilation.
No production deployment, job mutation or simulator/GPU execution is included.
