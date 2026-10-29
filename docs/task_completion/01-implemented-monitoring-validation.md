# Monitoring validation and run safeguards — engineering milestone

Date: October 28, 2026 (America/New_York). Branch: `feat/monitoring-study`.
Commit: the commit containing this record; predecessor foundation commit `2023c62`.
Resolve this commit with `git log --oneline -- docs/task_completion/01-implemented-monitoring-validation.md`.

## Implemented

- Track the importer package correctly by anchoring artifact ignores at repository
  root. Added all ingestion/context modules to Git and verified their inclusion in
  the distributable wheel.
- Sequential canonical evidence IDs, local-only original message indices, explicit
  canonical tool call/result links and correct multi-call interaction grouping.
- Configurable bounded trajectory concurrency; all concurrent stage calls complete
  and remain costed even when another branch fails.
- Complete serialized-state token caps for MRT and preserved character offsets on
  source overflow splitting.
- Freeze protects Python source, lock/project configuration, canonical evidence,
  model/tokenizer identity and exact token-matched injection controls. Real freezes
  require checksummed cohort/pilot proofs, verified hardware and a user-approved
  positive full-study GPU cap. Repeating the same freeze is idempotent.
- Exact expected-coverage manifests prevent silently reporting incomplete methods
  or missing trajectories. Secondary thresholds must match the same study freeze.
- Structural feature models fitted on development only, dev-derived length bins,
  overlap diagnostics and task bootstrap with recalibration. Injection selection,
  matched controls, paired task uncertainty and figure generation are executable.
- Separate configuration domains and a ten-candidate development configuration.
  Aggregate-only W&B integration remains optional; local artifacts authoritative.
- Yale templates preserve failure timing/status, startup time and GPU telemetry;
  require verified image checksum when using Apptainer. Controlled timing disables
  model-server prefix caching. No cluster execution is claimed.
- Shareable real-data audit, plot, report draft and detailed operating instructions.

## Actually verified

- `uv run ruff check src tests`: passed.
- `uv run --extra data pytest -q`: **29 passed**. Includes four official Inspect
  writer/reader .eval roundtrips, one per objective; isolation, exact quotations,
  chunk retention, complete summary bounds, concurrent failure accounting,
  structured/transport retries, calibration ties/referrals, paired task bootstrap,
  task leakage, atomic artifacts, full workflow, freeze mutation rejection,
  resume, coverage rejection, structural diagnostics and matched injections.
- `uv run asm experiment demo`: all five methods, zero invalids in 60 synthetic
  test judgments, primary calibration/report, structural diagnostics and 144
  matched injection comparisons. Synthetic results have no effectiveness meaning.
- Real-data mock run: five valid method results on one development trajectory;
  repeating it resumed all five saved results.
- Real source ingestion rerun: 1,200 normalized, zero schema rejections; exact
  outcome/objective counts reproduced. Fixed split yields 454 successful test attacks.
- Real pinned tokenizer source audit and complete-prompt audit on all 1,200 records:
  maximum full prompt **116,555 tokens**, zero overflow under configured 131,072
  context including a reserve of 8,320 tokens for generation/retry/headroom.
  Actual GPU/KV-cache fit remains unverified.
- `uv build`: wheel and source distribution built; wheel explicitly checked for
  downloader, importer, context-audit and CLI modules.
- `bash -n scripts/yale/*.sh scripts/yale/*.sbatch` and `git diff --check`: passed.
- Generated dataset figure inspected visually; no raw transcripts in public reports.

## Runnable now and remaining work

See `docs/operations.md`. The local pipeline and synthetic study are runnable.
Real data and local private results remain under ignored `data/` and `runs/`.
The real-model configuration pins Hugging Face commit
`6cee5e81ee83917806bbde320786a8fb61efebee`; engine/hardware remain unverified.

No GPU job or real-model inference has run. Authorized Yale SSH still requires
interactive Duo authentication; the user was asked to establish that connection.
Next: inspect permissions/storage, conduct the at-most-four-GPU-hour pilot, measure
costs/fit/effort/validity/resume, obtain the full-study cap, choose development
configurations, freeze, and run calibration/test. Independent evidence review,
real injection outcomes, measured GPU comparisons and the final scientific report
remain outstanding. This record does not mark the research project complete.
