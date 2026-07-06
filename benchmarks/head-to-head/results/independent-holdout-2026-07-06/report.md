# dotrepo benchmark — head-to-head

_Run configuration: github: extractor=llm, provider=openrouter, model=google/gemma-4-26b-a4b-it; dotrepo: base_url=https://dotrepo.org._

| metric | github | dotrepo |
|---|---|---|
| scored questions | 96 | 96 |
| accuracy (correct / all) | 92.7% | 51.0% |
| precision (correct / answered) | 96.7% | 96.1% |
| coverage (answered / all) | 95.8% | 53.1% |
| **confidently wrong** (count) | 2 | 2 |
| **confidently-wrong rate** | 2.1% | 2.1% |
| abstained | 4 | 45 |
| approx tokens over wire | 120935 | 39542 |
| total latency (ms) | 46514.0 | 2176.8 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo |
|---|---|---|
| buried accuracy | 78.8% | 27.3% |
| buried confidently-wrong | 2 | 2 |

_A win for dotrepo is: higher buried accuracy AND fewer confidently-wrong answers AND fewer tokens. If it doesn't clear all three, it isn't paying rent._

## Cohort readout

### holdout_unindexed

| metric | github | dotrepo |
|---|---|---|
| scored questions | 35 | 35 |
| accuracy | 97.1% | 0.0% |
| answer rate | 100.0% | 0.0% |
| confidently wrong | 1 | 0 |
| buried scored questions | 12 | 12 |
| buried accuracy | 91.7% | 0.0% |
| buried confidently wrong | 1 | 0 |

_For the frozen unindexed holdout, dotrepo's target is a 0% answer rate and zero confidently-wrong answers. Accuracy is not interpreted as a product score because abstention is the intended behavior._

### indexed_independent

| metric | github | dotrepo |
|---|---|---|
| scored questions | 61 | 61 |
| accuracy | 90.2% | 80.3% |
| answer rate | 93.4% | 83.6% |
| confidently wrong | 1 | 2 |
| buried scored questions | 21 | 21 |
| buried accuracy | 71.4% | 42.9% |
| buried confidently wrong | 1 | 2 |
