# Repeated compaction diagnostic (redacted)

A persistent worker accepted a launch request but did not submit a job. Its
provider session completed 13 context compactions in approximately 15 minutes,
with only 14 tool calls. Each compaction left 27,521–28,349 tokens; the next
request used 34,639–35,421 input tokens. The service forced a 32,000-token
compaction threshold despite a 475,000-token model window. Repeated summaries
therefore consumed the turn's time allowance without advancing the launch.

Reproduction: choose a thread whose retained instructions/history plus tool
request overhead exceed the forced threshold. Complete one tool call after a
compaction. The next request immediately compacts again.

The fix removes this application override, preserving provider/model defaults
and all separate usage limits, and interrupts repeated low-progress compaction
cycles. Deployment restarts the owned app-server so loaded threads cannot retain
the old runtime override. It does not delete history or replay uncertain tools.
