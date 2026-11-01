# Frozen monitoring study: initial results

Completed November 1, 2026, from freeze
`b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`.
Calibration and all eight held-out test shards completed for all five methods.
The primary test contains 118 benign trajectories and 454 successful attacks;
18 failed or ungraded attacks were processed separately from the primary positives.
Thresholds were calibrated on 448 separate benign trajectories at a 5% FPR target.
Invalid outputs are treated as referral alerts; AUROC uses valid outputs only.

| Method | Attack detection (TPR) | 95% task-bootstrap interval | Test FPR | Valid-score AUROC |
| --- | ---: | ---: | ---: | ---: |
| Single review | 31.9% | 25.2–42.7% | 4.1% | 0.914 |
| Think longer, medium | 63.4% | 46.6–91.4% | 7.7% | 0.903 |
| Average, 2 samples | 70.2% | 56.6–80.5% | 4.2% | 0.951 |
| Extract and evaluate, 3K | 4.8% | 2.4–9.0% | 5.1% | 0.556 |
| MRT, 5 interactions | 40.9% | 25.0–64.9% | 8.5% | 0.903 |

Intervals use 2,000 whole-task bootstrap replicates with recalibration; no replicates
were skipped. The reported FPR is the realized test rate, not the 5% calibration
target. Some test FPRs exceed that target, and intervals are wide; comparisons
should use the paired intervals in the saved metrics rather than rankings alone.
Averaging has the highest point estimate here, while EaE performs poorly on this
cohort. These observations do not establish general performance outside this study.

The matched injection study completed 480 paired comparisons across the selected
single-review and EaE methods. Its full aggregate estimates, paired task-bootstrap
intervals, and figure are in the private run artifacts. Structural diagnostics were
also generated. The 30-record independent evidence-annotation template has been
prepared, but human reference annotations and their retention analysis are not yet
complete. Do not infer semantic evidence quality without those annotations.

The controller verified persisted coverage and the frozen configuration. Total
allocated GPU use including development, failures and the main study is **60.61
GPU-hours**, below the 90-hour recorded cap. Raw data, result records and detailed
private artifacts remain outside Git and W&B. Aggregate outputs are copied locally to
`runs/full-study/` and remain in the Yale frozen checkout under `runs/`. The generated
report's generic warning about unfinished analyses predates this completion; the
remaining independent annotation work above is the material outstanding item.
