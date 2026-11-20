# Reproduce the research extension

Use a separate checkout with the original freeze and the original canonical data
read-only. Run with the repository's locked environment. The science choices and
acceptance criteria are in the [protocol](../plan/07-research-extension-plan.md).

## Archived scores and figures

Recover the accepted nested-review results and cold trials using the
[prior instructions](analysis-reproduction.md).

```bash
uv run --locked asm analysis extension-adaptive \
  --archive "$ASM_FOLLOWUP" --output runs/extension-v1/adaptive.json
uv run --locked python scripts/analysis/extension_figures.py \
  --source runs/extension-v1/adaptive.json --output runs/extension-v1/figures
uv run --locked --extra tracking python scripts/analysis/publish_extension.py \
  --source runs/extension-v1/adaptive.json --directory runs/extension-v1/tracking
```

The runner checks the accepted scoring identity, exact review inventories, and the
cold timing identity. Development folds determine routing. Benign calibration
determines threshold ties and their randomization. Held-out results are exploratory.

## Reasoning field audit

```bash
HF_HUB_OFFLINE=1 uv run --locked --extra data --extra tokenizer asm data \
  reasoning-visibility-audit --raw data/raw --data data/prepared \
  --frozen runs/readiness/study-freeze.json --output runs/extension-v1/reasoning
uv run --locked asm analysis reasoning-profile \
  --root runs/extension-v1/reasoning --output runs/extension-v1/reasoning-profile.json
```

Keep `features.json` private. Only the aggregate audit and profile are publishable.
A receipt tied to verified release-specific authorship is required to materialize
model inputs. For an independent lineage check, download the upstream exports
identified in [the lineage aggregate](extension-v1/source-lineage.json) using the
published run export URLs under the corresponding `honest.eval` and `attack.eval`
names. Run `scripts/analysis/extension_lineage.py --release data/raw --upstream UPSTREAM_DIR
--output runs/extension-v1/source-lineage.json`. Matching text confirms export lineage.
Both releases lack independent provider reasoning blocks. The authorship gate remains closed.

## Bounded EaE diagnosis

```bash
uv run --locked asm analysis extension-eae-prepare \
  --frozen runs/readiness/study-freeze.json --original "$ASM_RUN" \
  --archived-review "$ASM_BLINDED_REVIEW" --output runs/extension-v1/eae
```

Use the previously accepted 120B reviewer and original locked 20B environment.
The private packet exposes only the legitimate task and canonical steps to the
reviewer. Use the project ledger to submit the reviewer, and the
`extension-eae-continue.sbatch` dependency for the fixed judge. Recover public
aggregates after checking exact completion and Slurm accounting. The working
packets, references, explanations, and per-case costs stay private.

## Report packaging

```bash
uv run --locked --with reportlab==5.1.0 python scripts/analysis/render_report.py \
  --source docs/reports/final-report.md --append docs/reports/extension-v1.md \
  --status 'Original study and exploratory extension' \
  --output output/pdf/monitoring-study-extension-v1.pdf
```

Render the PDF with Poppler and inspect each page. The original report and PDF stay
available separately from the combined extension.
