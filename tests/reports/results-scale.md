# Results scale reset — redacted reproduction

- Open a standard training Results report with measured positive values.
- Change **Y scale** from **Linear** to **Log**.
- Open Overview, then return to Results.
- Before this fix: the selector and Plotly axis reset to Linear.
- Expected: this report retains Log; other reports retain their own choices.

The renderer recreated its controls for each document. The Results frame has an
opaque sandbox origin and cannot persist local storage itself. Changing only the
report template would also leave already-published reports unfixed. Desktop SSH
connections can receive a new loopback port after restart, so origin-local
storage alone cannot provide desktop restart persistence.

Regression fixtures use fabricated report IDs, measurements and account URLs.
No user conversations, project paths, authentication material or research data
are included. Browser coverage exercises the actual renderer and sandbox bridge;
native coverage uses isolated desktop profiles and simulated host connections.
