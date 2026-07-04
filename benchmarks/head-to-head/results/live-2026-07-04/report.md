# dotrepo benchmark — head-to-head

| metric | github | dotrepo |
|---|---|---|
| scored questions | 40 | 40 |
| accuracy (correct / all) | 72.5% | 45.0% |
| precision (correct / answered) | 82.9% | 78.3% |
| coverage (answered / all) | 87.5% | 57.5% |
| **confidently wrong** (count) | 0 | 1 |
| **confidently-wrong rate** | 0.0% | 2.5% |
| abstained | 5 | 17 |
| approx tokens over wire | 66807 | 18888 |
| total latency (ms) | 4042.4 | 1247.6 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 38.9% | 44.4% |
| buried confidently-wrong | 0 | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
