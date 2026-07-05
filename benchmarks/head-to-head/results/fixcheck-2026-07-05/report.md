# dotrepo benchmark — head-to-head

| metric | github | dotrepo |
|---|---|---|
| scored questions | 40 | 40 |
| accuracy (correct / all) | 72.5% | 47.5% |
| precision (correct / answered) | 82.9% | 82.6% |
| coverage (answered / all) | 87.5% | 57.5% |
| **confidently wrong** (count) | 0 | 0 |
| **confidently-wrong rate** | 0.0% | 0.0% |
| abstained | 5 | 17 |
| approx tokens over wire | 66807 | 18619 |
| total latency (ms) | 3661.9 | 61.7 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 38.9% | 44.4% |
| buried confidently-wrong | 0 | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
