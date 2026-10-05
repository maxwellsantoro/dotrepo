# Paired task observations

Consumer class: operator-controlled.

Hashes bind supplied logs; this scorer does not independently witness external execution.
No external adoption or net cost benefit is inferred.

| Metric | Source first | Lookup first |
| --- | ---: | ---: |
| attemptedTasks | 10 | 10 |
| completedTask | 10 | 10 |
| failedAttempts | 0 | 2 |
| acceptedWrongAnswer | 0 | 2 |
| policyAcceptedTasks | 0 | 5 |
| fallbackAttempts | 0 | 7 |
| correctFallback | 0 | 5 |
| elapsedMs | 927.282 | 1066.987 |

Unknown model usage/cost or maintenance allocations remain null in results.json.
Replay elapsed time is not live latency. See per-task rows and bound execution logs.
