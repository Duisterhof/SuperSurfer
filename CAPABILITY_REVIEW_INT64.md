# Live Results reader capability review

Reviewed October 17, 2026 against installed source
`c2c4275fb28a5f3462f384d43d0491e265dc647a` (SuperSurfer 0.1.43), before the
bounded `ReportTail` GraphQL scalar correction. This is a reader compatibility
bugfix, not a role/tool or scientific-execution capability expansion. Both
existing skill markers remain 0.1.43, matching `package.json`.

Source review covered `server/agent_tools.py` role definitions and scoped tool
schemas, `server/results.py` report/source identities, `server/result_data.py`
read-only queries and cached/stale response behavior, `server/wandb.py` error
classification, and the exact allocation contract in `server/slurm.py`.
Existing Stanford `seven_l40s_training_v1`, compute ownership,
exact-source PR requirements, held preparation, explicit queue requests and
autonomous suggestions remain unchanged. Native sessions without scoped queue
tools retain their limitation; software repair grants no bypass or new owner.

| Skill reviewed | Actual boundary and warranted guidance change |
| --- | --- |
| Manager | May queue only an explicitly assigned registered experiment; cannot deploy SuperSurfer. Reader errors require bounded diagnostics, without dispatching replacement science or rebinding writers. |
| Research lead | Can dispatch requested work, but has no prepare/queue/wakeup tool. Reader unavailability is distinct from unmeasured science and creates no replacement handoff or stopped-work revival authority. |
| Experiment worker | Owns its scoped implementation and explicitly authorized queue/recovery; live refresh needs no wakeup. Reader failure does not justify trainer/logger mutation, writer replacement or a scientific rerun. |
| Host onboarding | Bounded setup supports the existing authorized task; readiness and account access are separate from Results. Query failure alone does not justify node re-onboarding, runtime reinstall or credential rotation. |
| Results | Publishes within existing scope and preserves report revisions/source bindings. Added bounded diagnosis of query/HTTP failures, with cached observations and true sample ages retained, and no assertion that HTTP 400 establishes a root cause or absent measurements. |

No tool, source writer, run, agent, wakeup, allocation or deployment was created
or changed by this review. No changes were warranted to the five skills' launch,
Slurm, permissions, source-verification or ownership guidance. The app fix and
its regression tests, package, PR and deployment decision remain with the parent
software task owner.

Validation completed October 17, 2026:

- `python3 scripts/check-agent-skills.py`: exit 0, “All agent capability skills match this release.”
- `python3 -m unittest discover -s tests -p 'test_agent_skills.py' -v`: all four tests passed.
- Scoped `git diff --check`: exit 0.
- Both 0.1.43 markers and every local Markdown target in the five reviewed skills validated; the new Results diagnosis anchor exists.

These checks validate shipped guidance and its packaging contract. They do not
claim an authenticated W&B integration test, scientific measurement or deployment.
