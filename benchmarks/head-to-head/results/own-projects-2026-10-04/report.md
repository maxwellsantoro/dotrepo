# Paired task observations

Consumer class: operator-controlled.

Hashes bind supplied logs; this scorer does not independently witness external execution.
No external adoption or net cost benefit is inferred.

| Metric | Source first | Lookup first |
| --- | ---: | ---: |
| attemptedTasks | 8 | 8 |
| completedTask | 5 | 5 |
| failedAttempts | 3 | 5 |
| acceptedWrongAnswer | 0 | 2 |
| policyAcceptedTasks | 0 | 2 |
| fallbackAttempts | 0 | 8 |
| correctFallback | 0 | 3 |
| elapsedMs | 550471.2877919956 | 480411.9627510081 |

Unknown model usage/cost or maintenance allocations remain null in results.json.
Replay elapsed time is not live latency. See per-task rows and bound execution logs.
