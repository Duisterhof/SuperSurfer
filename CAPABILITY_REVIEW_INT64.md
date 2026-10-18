# Combined Results and Stanford capability review

The original October 17, 2026 review compared the bounded `ReportTail` GraphQL
scalar correction with installed source
`c2c4275fb28a5f3462f384d43d0491e265dc647a`. The supplemental review covers the
bounded initial `ReportRun` response-size fallback atop
`2ed14a257c0f48e5163bc81c5a3317decb3f135d` (SuperSurfer 0.1.43). Both corrections
retain existing roles, tools and scientific-execution capabilities. Both skill
version markers remain 0.1.43, matching `package.json`.

A further bounded review covers recovery of the PR53 preference bridge from
`ce9299cf76510f6adf57c8924d4735dbb6d07beb` onto
`4ccc89875e6f46ad432cd1f55f9eb2219a345535`. This review examines source behavior;
it does not establish a deployed or native persistence test result.

The combined review includes the explicitly authorized flexible Stanford backend
from PR56 source `8234c3fff1d711f2cf75708cd66ff7e6e1eca422`, preserved as
`2d69a1b60e33f958caa0bf8eb1d395e147875d14` after the Results preference recovery.
This adds a bounded resource profile, not a role/tool or autonomous launch grant.

Source review covered `server/agent_tools.py` role definitions and scoped tool
schemas, `server/app.py` role/native-owner context, `server/results.py`
report/source identities, `server/result_data.py`
read-only queries and cached/stale response behavior, `server/wandb.py` error
classification, and the exact allocation contracts in `server/slurm.py` and
`engine/aml/slurm_bridge.py`. The new capability is advertised by
`engine/aml/service.py` and required by `server/app.py` before creation.
Existing Stanford `seven_l40s_training_v1`, PSC/smoke, compute ownership,
exact-source PR requirements, held preparation, explicit queue requests and
autonomous suggestions remain unchanged. Native sessions without scoped queue
tools retain their limitation; software repair grants no bypass or new owner.

| Skill reviewed | Actual boundary and warranted guidance change |
| --- | --- |
| Manager | May queue only an explicitly assigned registered experiment; cannot deploy SuperSurfer. Flexible placement requires actual user authorization, installed capability and exact scientific admission, without replacing the submission owner. |
| Research lead | Can dispatch requested work, but has no prepare/queue/wakeup tool. Flexible resources create no initial queue authority or replacement scientific assignment. |
| Experiment worker | Owns its scoped implementation and explicitly authorized queue/recovery. Scientific source must validate actual ranks, precision, global batch and full-state compatibility; a manager-owned submission stays single-owner. |
| Host onboarding | Bounded setup supports the existing authorized task. Flexible resource bounds do not prove account access, VRAM, scientific compatibility or allocated locality, and a test-only estimate reserves nothing. |
| Results | Preserves report revisions/source bindings, bounded reader diagnosis, sampled-density limits and scale/legend preferences. Flexible hardware comparisons must name actual type/ranks/batch/exposure; estimates and missing metrics are not measured outcomes. |

`single_node_training_v1` requires installed
`run.stanford_slurm.training.flexible.v1`, one node with 1–8 GPUs of one explicit
type, account `viscam`, partition `viscam` or `sc-loprio`, and walltime from 1 to
86,400 seconds. CPU and RAM limits are four CPUs and 16 GiB per GPU.
`until_stopped` and `allow_preemption` must be true with 120 seconds of TERM grace;
smoke flags and `max_updates` are excluded. Exact-source PR, registered control
host with no physical GPUs, scientific rank/batch/precision admission, allocated
local-scratch checks, one managed submission owner, uncertain-intent deduplication
and unchanged retry resources remain required. Existing stops remain binding.
The profile does not adapt model code, certify hardware or permit autonomous runs,
direct scheduling, other-job cancellation, deployment or silent resource changes.

The combined five-skill review removes older wording that implied the fixed
seven-L40S profile was the only production option, states flexible bounds without
applying walltime per GPU, and keeps scientific admission separate from transport
validation. The Results reader and preference guidance remains intact. This review
does not certify any scientific rank implementation or deployed backend.

The fallback keeps the 8 MiB transport limit. Only its specific oversize error
retries the initial 1,500-sample overview at 500 then 100 samples. Declared
source/key identities, the recent 100-step tail, 1,500-sample sparse held-out
reads and cache/stale handling remain unchanged. Exhaustion and unrelated errors
remain errors; a smaller successful overview is sampled evidence, not complete
history or proof that older metric samples are fresh. The Results skill documents
this limitation.

Preference source review covered `ui/results-client.js`, `ui/results-live.js`,
`desktop/main.cjs`, `desktop/preload.cjs` and `desktop/preferences.cjs`, plus the
recovered preferences, training022 browser and windows016 Electron test sources.
The bridge keys scale by experiment/report and hidden legend choices by plot,
source URL, metric, split, axis and filter identity. The trusted parent validates
the selected opaque frame/instance and bounded values before storing preferences;
desktop IPC checks its owning trusted window and preserves preferences during
ordinary navigation writes. Storage is outside the opaque iframe, with native
preferences independent of changing local connection ports. No credential or
general storage API is added to report content. The Results skill now distinguishes
these viewing choices from measurements and requires actual persistence checks
before reporting success. Their role/tool, setup and execution boundaries remain
unchanged by the preference bridge.

No tool, source writer, run, agent, wakeup, allocation or deployment was created
or changed by this review. The five skills now describe the additional bounded
Slurm profile without changing permissions, source verification or ownership.
The app fix and
its regression tests, package, PR and deployment decision remain with the parent
software task owner.

Validation completed October 17, 2026:

- `python3 scripts/check-agent-skills.py`: exit 0, “All agent capability skills match this release.”
- `python3 -m unittest discover -s tests -p 'test_agent_skills.py' -v`: all four tests passed.
- Scoped `git diff --check`: exit 0.
- Both 0.1.43 markers and all 71 local Markdown links/anchors in the five reviewed skills validated; the Results diagnosis and flexible-placement anchors exist.

These checks validate shipped guidance and its packaging contract. They do not
claim an authenticated W&B integration test, scientific measurement or deployment.
