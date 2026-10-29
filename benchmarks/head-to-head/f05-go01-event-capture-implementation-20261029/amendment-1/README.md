# Capture wait-deadline correction

Independent review reproduced a live owned child after both pipes reached EOF:
the final wait exceeded the shared deadline, raised TimeoutExpired and lost the
raw receipt. The original counterexample and implementation remain historical.

The final wait now uses the remaining deadline. A wait timeout kills and reaps
the client and returns retained bytes with a timeout error; cancellation during
that wait also cleans up the client. This covers the existing text path and the
new raw path. Two owned shell controls close both pipes while remaining alive,
then require retained output, a timeout receipt and a reaped client. Test cleanup
also contains the historical failure. All 161 focused controls and Ruff passed.

No capture helper, command permission, hidden-gold rule or task oracle changed.
Independent successor review remains required. No upstream/native, container,
network or provider action ran. Actual task and campaign admission remain open.
