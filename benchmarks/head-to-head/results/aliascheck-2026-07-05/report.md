# dotrepo benchmark — head-to-head

| metric | github | dotrepo |
|---|---|---|
| scored questions | 40 | 40 |
| accuracy (correct / all) | 67.5% | 72.5% |
| precision (correct / answered) | 93.1% | 87.9% |
| coverage (answered / all) | 72.5% | 82.5% |
| **confidently wrong** (count) | 1 | 0 |
| **confidently-wrong rate** | 2.5% | 0.0% |
| abstained | 11 | 7 |
| approx tokens over wire | 66807 | 23606 |
| total latency (ms) | 2909.9 | 66.7 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 27.8% | 44.4% |
| buried confidently-wrong | 1 | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
