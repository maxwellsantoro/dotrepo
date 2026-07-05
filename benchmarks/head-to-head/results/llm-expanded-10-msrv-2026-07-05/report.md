# dotrepo benchmark — head-to-head

| metric | github | dotrepo |
|---|---|---|
| scored questions | 85 | 85 |
| accuracy (correct / all) | 70.6% | 100.0% |
| precision (correct / answered) | 95.2% | 100.0% |
| coverage (answered / all) | 74.1% | 100.0% |
| **confidently wrong** (count) | 3 | 0 |
| **confidently-wrong rate** | 3.5% | 0.0% |
| abstained | 22 | 0 |
| approx tokens over wire | 99357 | 53840 |
| total latency (ms) | 7874.4 | 97.2 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 34.2% | 100.0% |
| buried confidently-wrong | 3 | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
