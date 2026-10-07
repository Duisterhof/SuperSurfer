---
name: experiment-report
description: Write or revise a standalone experiment explanation from its code, protocol and measured results.
---

Explain the experiment so an advisor can assess it without opening another page.
Write a compact overview first; put configuration, derivations and provenance in
expandable details. Aim for 250–400 words in the overview, adding detail when the
method needs it. Shortness must not remove information needed to judge the work.

Use the actual implementation and recorded evidence. Explain:

- The question and why this experiment is useful.
- The base model and the exact intervention. Define names such as “compact”.
- Inputs, predicted outputs, learned and frozen components, training losses,
  and what changes between training and deployment.
- The matched control, data split, training budget and evaluation cohort.
- Measurements with units and denominators, uncertainty and completion status.
- What the evidence supports, what remains unresolved, and the next decision.

Distinguish offline error, oracle diagnostics, provisional success rates and
completed comparisons. Mark missing evidence explicitly. An operational success
or passing test is not an experimental result. Avoid repeating all historical
failures, process IDs, review hashes and log messages in the scientific story.

Prefer concrete sentences, familiar words and meaningful tables. Remove staging,
inflated claims, filler and repeated conclusions; preserve technical meaning.
Apply ASD-STE100 principles: short sentences, active voice, and consistent names.
Give each technical term one meaning and define it on first use. State the actor
and condition for each action. Keep necessary scientific terms and complete
sentences. This is style guidance, not a claim of compliance with the standard.
Use simple SVG or Mermaid diagrams when they clarify information flow, training
versus inference, or the intervention. Label arrows and define symbols. A diagram
should explain the method, not merely decorate the page.

Before publishing, read the overview as a new reader. Can you explain what was
changed, how the model learns and acts, which comparison is valid, and what the
result means? Check those answers against the source. Populated fields and a
rendering test do not establish explanation quality. Show dates in the viewer's
timezone; retain machine-readable timestamps underneath.

Adapted guidance:

- [Scientific Writing](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-writing/SKILL.md)
- [Writing Clearly and Concisely](https://github.com/obra/the-elements-of-style/blob/master/skills/writing-clearly-and-concisely/SKILL.md)
- [Humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md)
- [ASD-STE100](https://www.asd-ste100.org/STE_faq.html)
