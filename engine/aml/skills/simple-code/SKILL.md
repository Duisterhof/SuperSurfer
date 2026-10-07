---
name: simple-code
description: Simplify training, inference or platform code while preserving its existing behavior and making the execution path easy to follow.
---

Choose readable, explicit code. Reduce the number of concepts a reader must
understand, rather than merely reducing line count. Use descriptive names,
straightforward functions and ordinary control flow. Remove duplicated wrappers,
unused options and abstractions for hypothetical requirements. Keep shared code
where actual configurations share the same behavior.

Preserve the experiment's mathematics, shapes, masking, randomness, checkpoint
meaning and training/inference behavior. Record any intentional change separately.
Check representative numerical behavior and real entry points; do not count
renaming wrappers or tests that repeat the implementation as validation.

Keep a small, explicit configuration for each supported model. Each configuration
needs a README explaining the model, required data/environment, train and inference
commands, checkpoint compatibility and outputs. Supply readable launch scripts
that submit jobs through AML's queue. GPU work starts only after readiness is
marked; a script must not create a hidden scheduler or bypass an allocation.
Use ASD-STE100 principles in READMEs: short sentences, active voice, consistent
terms, and explicit conditions. Define necessary technical terms once. Keep the
explanation complete; do not claim formal compliance with the standard.

Comments explain non-obvious constraints. Remove comments that narrate the chat
history or restate the code. Avoid nested ternaries, compressed one-liners,
unnecessary inheritance, speculative registries and broad exception swallowing.
Report verification limits directly, especially if GPU parity has not been tested.

Adapted guidance:

- [Anthropic Code Simplifier](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md)
- [YAGNI](https://github.com/kayaman/skills/blob/main/yagni-principle/SKILL.md)
- [Simplify](https://github.com/bholmesdev/skills/blob/main/skills/simplify/SKILL.md)
- [ASD-STE100](https://www.asd-ste100.org/STE_faq.html)
