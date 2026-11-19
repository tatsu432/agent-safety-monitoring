# Agent safety monitoring

How should a coding-agent safety monitor spend its compute budget to detect harmful
behavior while limiting false alarms? This study compares five procedures on saved
BashArena trajectories using a fixed `gpt-oss-20b` monitor: single review, longer
reasoning, averaging two reviews, extract-and-evaluate (EaE), and sequential plus
hierarchical review (MRT).

The original frozen study and its controlled nested-review follow-up are
complete. On 454 recorded
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

The follow-up finds that repetition improves detection at both native score
scales. Fine-scale detection rises from 31.0% with one review to 85.7% with
five, at 5.0% and 6.1% realized FPR. Five-review detection remains 81–84% after
coarsening the same fine scores. Fine-scale medium-effort review reaches 89.9% detection at 10.5% realized FPR,
while its AUROC remains close to a single low-effort review. The raw archive
includes an extended-thinking
overlay that the frozen monitors did not see.

[Research report](docs/reports/final-report.md) ·
[Results](docs/reports/strengthened-scoring.json) ·
[Methods](docs/methods.md) ·
[Reproduce](docs/reports/analysis-reproduction.md) ·
[Execution status](docs/task_completion/06-strengthen-complete-checkpoint.md)
