# Three-handoff cap

Redacted diagnostic excerpt, October 12, 2026.

The running Tulip service used the 0.1.43 handler that rejected a fourth distinct
experiment with: “At most three distinct experiment handoffs are allowed per user
turn; this experiment may already have been handed off”. Both the manager and
project-lead tools used that handler; tool descriptions and skills repeated the cap.

Two isolated fixture regressions reproduce the fourth-handoff failure before the
fix. After removing only the count guard, both roles dispatch four distinct
experiments in one user turn. Repeating a previous dispatch remains rejected,
even after its worker becomes idle. Busy/foreign/scheduled work remains rejected;
a later user turn can send the next assignment to the same worker. The fixtures
observe no run launches. No live handoffs or GPU actions were issued for testing.

The separate limit on creating new worker conversations is outside this change.
