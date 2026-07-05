# dotrepo benchmark — head-to-head

| metric | dotrepo |
|---|---|
| scored questions | 40 |
| accuracy (correct / all) | 82.5% |
| precision (correct / answered) | 86.8% |
| coverage (answered / all) | 95.0% |
| **confidently wrong** (count) | 0 |
| **confidently-wrong rate** | 0.0% |
| abstained | 2 |
| approx tokens over wire | 27040 |
| total latency (ms) | 34.6 |

### Buried fields only (dotrepo's thesis)

| metric | dotrepo |
|---|---|
| buried accuracy | 66.7% |
| buried confidently-wrong | 0 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
