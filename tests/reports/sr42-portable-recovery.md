# Portable SR42 recovery binding

A healthy reviewed training successor used `--data {data}` in its portable
request and a concrete `/scratch/inputs` in its selected host contract. Its
predecessor used that concrete path directly. Recovery binding rejected the
literal template against the predecessor despite matching actual input paths.

The adapter now resolves only the selected host's command and checks it against
the portable template and runtime/data contract metadata. It never guesses a
candidate or resolves remote symlinks on the service host. Concrete arguments
cannot change. Legacy concrete predecessors remain supported. Both discovery
and recovery use this command, including the actual Python executable.

The existing reviewed-source, project/experiment, configuration bytes, remote
content bindings, ranks, checkpoint directory and retained SHA checks remain.
Missing selected contracts, unresolved/unknown placeholders and contradictory
commands fail closed. No stored run, scientific recipe or allocation is edited.

Validation: 814 Python tests (3 skipped), 54 Node tests (49 passed, 5 skipped),
agent-skill check and remote service build. Ten new regression tests exercise
matching resolved inputs, changed paths, missing/ambiguous contracts, discovery,
source/content rejection, ranks, checkpoint directory and SHA. Tests use isolated
fixtures; no production job is launched. Independent review and deployed binding
receipts are recorded separately by the operator.
