# dotrepo benchmark — head-to-head

| metric | github | dotrepo |
|---|---|---|
| scored questions | 40 | 40 |
| accuracy (correct / all) | 65.0% | 47.5% |
| precision (correct / answered) | 89.7% | 82.6% |
| coverage (answered / all) | 72.5% | 57.5% |
| **confidently wrong** (count) | 2 | 0 |
| **confidently-wrong rate** | 5.0% | 0.0% |
| abstained | 11 | 17 |
| approx tokens over wire | 66807 | 19145 |
| total latency (ms) | 2847.3 | 1613.8 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 22.2% | 44.4% |
| buried confidently-wrong | 2 | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
