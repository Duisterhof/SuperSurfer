# Live Results reader capability review

The original October 17, 2026 review compared the bounded `ReportTail` GraphQL
scalar correction with installed source
`c2c4275fb28a5f3462f384d43d0491e265dc647a`. The supplemental review covers the
bounded initial `ReportRun` response-size fallback atop
`2ed14a257c0f48e5163bc81c5a3317decb3f135d` (SuperSurfer 0.1.43). Both corrections
retain existing roles, tools and scientific-execution capabilities. Both skill
version markers remain 0.1.43, matching `package.json`.

Source review covered `server/agent_tools.py` role definitions and scoped tool
schemas, `server/app.py` role/native-owner context, `server/results.py`
report/source identities, `server/result_data.py`
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
| Results | Publishes within existing scope and preserves report revisions/source bindings. Bounded query/HTTP diagnosis keeps cached observations and true sample ages. The supplemental guidance explains reduced overview density after the specific response-size fallback; HTTP 400 still establishes neither a root cause nor absent measurements. |

The fallback keeps the 8 MiB transport limit. Only its specific oversize error
retries the initial 1,500-sample overview at 500 then 100 samples. Declared
source/key identities, the recent 100-step tail, 1,500-sample sparse held-out
reads and cache/stale handling remain unchanged. Exhaustion and unrelated errors
remain errors; a smaller successful overview is sampled evidence, not complete
history or proof that older metric samples are fresh. A concise Results skill addition documents this
limitation. The other four skills already cover the applicable ownership boundary
and need no additional text for this fallback.

No tool, source writer, run, agent, wakeup, allocation or deployment was created
or changed by this review. No changes were warranted to the five skills' launch,
Slurm, permissions, source-verification or ownership guidance. The app fix and
its regression tests, package, PR and deployment decision remain with the parent
software task owner.

Validation completed October 17, 2026:

- `python3 scripts/check-agent-skills.py`: exit 0, “All agent capability skills match this release.”
- `python3 -m unittest discover -s tests -p 'test_agent_skills.py' -v`: all four tests passed.
- Scoped `git diff --check`: exit 0.
- Both 0.1.43 markers and all 70 local Markdown links/anchors in the five reviewed skills validated; the Results diagnosis anchor exists.

These checks validate shipped guidance and its packaging contract. They do not
claim an authenticated W&B integration test, scientific measurement or deployment.
