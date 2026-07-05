# dotrepo benchmark — head-to-head

| metric | dotrepo |
|---|---|
| scored questions | 85 |
| accuracy (correct / all) | 94.1% |
| precision (correct / answered) | 95.2% |
| coverage (answered / all) | 98.8% |
| **confidently wrong** (count) | 4 |
| **confidently-wrong rate** | 4.7% |
| abstained | 1 |
| approx tokens over wire | 53510 |
| total latency (ms) | 60.3 |

### Buried fields only (dotrepo's thesis)

| metric | dotrepo |
|---|---|
| buried accuracy | 86.8% |
| buried confidently-wrong | 4 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._
