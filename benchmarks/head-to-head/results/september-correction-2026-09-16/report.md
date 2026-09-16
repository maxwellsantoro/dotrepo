# dotrepo benchmark — head-to-head

Response bytes and bytes ÷ 4 are payload measurements/estimates, not model usage. Legacy per-field latency excludes model inference; whole-arm elapsed time includes it. Index maintenance is not included; this report does not establish net end-to-end cost savings.

_Run configuration: github: extractor=heuristic; dotrepo: base_url=http://127.0.0.1:8767; lookup-first: base_url=http://127.0.0.1:8767, fallback={'extractor': 'heuristic'}, max_record_age_days=30, consumer_class=in-repository-reference, model_usage_measured=False, maintenance_cost_included=False._

| metric | github | dotrepo | lookup-first |
|---|---|---|---|
| scored questions | 17 | 17 | 17 |
| accuracy (correct / all) | 47.1% | 58.8% | 70.6% |
| precision (correct / answered) | 61.5% | 90.9% | 92.3% |
| coverage (answered / all) | 76.5% | 64.7% | 76.5% |
| **confidently wrong** (count) | 0 | 0 | 0 |
| **confidently-wrong rate** | 0.0% | 0.0% | 0.0% |
| abstained | 4 | 6 | 4 |
| HTTP requests including prefetch/fallback | 114 | 8 | 84 |
| decoded response bytes including prefetch/fallback | 326618 | 105702 | 170463 |
| response cache hits | 0 | 0 | 0 |
| whole-arm elapsed (ms) | 20523.812 | 29.085 | 8980.303 |

### Buried fields only (dotrepo's thesis)

| metric | github | dotrepo | lookup-first |
|---|---|---|---|
| buried accuracy | 47.1% | 58.8% | 70.6% |
| buried confidently-wrong | 0 | 0 | 0 |

_Adoption evidence needs useful answers without a worse incorrect-answer rate, plus measured latency or cost improvement under comparable conditions, including fallback and maintenance._

## Cohort readout

### holdout_unindexed

| metric | github | dotrepo | lookup-first |
|---|---|---|---|
| scored questions | 5 | 5 | 5 |
| accuracy | 40.0% | 0.0% | 40.0% |
| answer rate | 60.0% | 0.0% | 60.0% |
| confidently wrong | 0 | 0 | 0 |
| buried scored questions | 5 | 5 | 5 |
| buried accuracy | 40.0% | 0.0% | 40.0% |
| buried confidently wrong | 0 | 0 | 0 |

_For the frozen unindexed holdout, dotrepo's target is a 0% answer rate and zero confidently-wrong answers. Accuracy is not interpreted as a product score because abstention is the intended behavior._

### indexed_independent

| metric | github | dotrepo | lookup-first |
|---|---|---|---|
| scored questions | 12 | 12 | 12 |
| accuracy | 50.0% | 83.3% | 83.3% |
| answer rate | 83.3% | 91.7% | 83.3% |
| confidently wrong | 0 | 0 | 0 |
| buried scored questions | 12 | 12 | 12 |
| buried accuracy | 50.0% | 83.3% | 83.3% |
| buried confidently wrong | 0 | 0 | 0 |
