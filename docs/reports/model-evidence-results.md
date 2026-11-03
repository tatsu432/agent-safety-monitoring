# Exploratory model-based evidence review

The local 120B reviewer produced 29 validated proposals and 28 supported interpretations.
All references are model-suggested, not human-verified. Exact source-span validation does not establish semantic correctness. The sample contains 30 selected attacks.

| Method | References | Fully retained | Partly retained | Missing | Cited |
| --- | ---: | ---: | ---: | ---: | ---: |
| average | 304 | not applicable | not applicable | not applicable | 143 |
| eae | 304 | 9 | 9 | 286 | 12 |
| mrt | 304 | not applicable | not applicable | not applicable | 168 |
| single | 304 | not applicable | not applicable | not applicable | 100 |
| think | 304 | not applicable | not applicable | not applicable | 134 |

Exact quotation containment applies only to EaE; citation omission does not prove misunderstanding. The reviewer selects passages up to 800 characters, so partial coverage may still include the decisive content. Retention is conditional on the model's fallible references. Cited counts match source steps, not necessarily the specific span within each cited step.

## Evidence replacement

Eligible selected records: 24; task groups: 22. Status counts: {"budget_exceeded": 4, "unresolved": 2, "valid": 24}.
Mean expected-alert change: -2.8 percentage points (pointwise 95% task-bootstrap interval -13.4 to 5.8).
This is a selected-sample, post-hoc diagnostic using the original policy, not a full-system TPR or a human-verified evidence study.
