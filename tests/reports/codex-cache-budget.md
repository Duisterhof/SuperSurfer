# Cached context interrupted implementation

A Codex Astra implementation turn was stopped after 11 responses. Its receipt reported 1,004,982 input tokens, including 984,320 cached input tokens, plus 5,225 output tokens. The standard policy counted all 1,010,207 raw tokens against a one-million allowance. Only Luna had cache-aware accounting.

New supported Codex Astra/Sol reservations charge this receipt as 124,319 internal budget units. This is not a monetary estimate. Old receipts retain their original accounting; unknown models and other providers retain conservative behavior. Standard time, tool, response, daily and workspace limits remain, with a new ten-million raw-token backstop. Unit tests replay the reported counters and check alias isolation and raw ceiling enforcement.
