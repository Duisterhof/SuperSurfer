# Results histories fail to refresh

Observed on SuperSurfer 0.1.43 on Linux, 2026-10-16.

Opening an experiment's Results page left new training and validation curves
empty and older cached curves stale. The source status reported W&B HTTP 400.
The ordinary W&B metrics view uses the same incompatible history range types.

The initial sampled-history query succeeded with the authenticated W&B account.
The follow-up query for recent samples and sparse validation failed validation:

```text
Variable "$min_step" of type "Int!" used in position expecting type "Int64".
Variable "$max_step" of type "Int!" used in position expecting type "Int64".
```

Changing the history bound declarations to `Int64!` returned 96 actual history
rows including four held-out EEF points in the same live run. No account change,
new run, summary-derived point, or replacement writer was needed.

Regression coverage rejects incompatible variable declarations for both custom
Results histories (with and without sparse validation) and the built-in metrics
view. Existing tests check preservation of cached values on genuine failures.

This report deliberately excludes private project names, run IDs, credentials,
and research measurements. The failure is the GraphQL variable type contract.
