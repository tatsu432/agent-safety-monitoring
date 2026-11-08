# Agent safety monitoring

How should a coding-agent safety monitor spend its compute budget to detect harmful
behavior while limiting false alarms? This study compares five procedures on saved
BashArena trajectories using a fixed `gpt-oss-20b` monitor: single review, longer
reasoning, averaging two reviews, extract-and-evaluate (EaE), and sequential plus
hierarchical review (MRT).

The original frozen study is complete. A new forensic audit reproduces its results;
controlled follow-up inference is prepared and awaiting Yale authentication. On 454 recorded
successful attacks and 118 nominal benign test trajectories, thresholds were set
using separate benign calibration data to target 5% false-positive rate. Rates
are expected alerts with randomization at tied scores:

| Method | Attack detection | Test false-positive rate |
| --- | ---: | ---: |
| Single review | 31.9% | 4.1% |
| Think longer | 63.4% | 7.7% |
| Average two reviews | 70.2% | 4.2% |
| EaE | 4.8% | 5.1% |
| MRT | 40.9% | 8.5% |

Averaging outperformed single review and MRT in paired task-bootstrap intervals;
its advantage over think-longer was inconclusive. MRT used 5.3× averaging's measured
development GPU time. A structural baseline achieved 0.901 AUROC, so dataset shortcuts
are an important limitation. A small model-based evidence diagnostic did not establish
why EaE failed; its references were not human-verified.

[Research report](docs/reports/report-draft.md) · [Results and uncertainty](docs/reports/primary-analysis.md) ·
[Compute](docs/reports/compute-efficiency.md) · [Methods](docs/methods.md) ·
[Reproduce](docs/reports/analysis-reproduction.md)


The [forensic audit](docs/reports/original-study-audit.md) separates calibrated policies
from descriptive test-ROC performance. [Failure analysis](docs/reports/failure-analysis.md)
reconstructs MRT branches and EaE evidence structure. The
[follow-up protocol](docs/reports/followup-experiment-plan.md) records prepared 0–100 scoring,
N=1/2/3/5 experiments, resource projections, and outstanding physical validation.
[Current report](docs/reports/final-report.md) includes completed post-hoc results and limitations.
