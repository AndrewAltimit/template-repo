# CPU Smoke-Test Outputs (2026-09-23)

Raw outputs from local CPU runs made on 2026-09-23, the day the TransformerLens 4.0
migration (PR #340) was merged. They were written to the repository-root `evaluation_results/` directory,
which CI treats as scratch output, and are archived here so the runs are not lost.

| File | Producer | Model |
|------|----------|-------|
| `cpu_test_results_distilgpt2.json` | `scripts/evaluation/comprehensive_test.py` | distilgpt2 |
| `cpu_test_results_EleutherAI_pythia-70m.json` | `scripts/evaluation/comprehensive_test.py` | EleutherAI/pythia-70m |
| `residual_analysis_results.json` | `scripts/analysis/residual_analysis.py` | Not recorded in the output (script default is EleutherAI/pythia-70m) |

These are small-model smoke tests that confirm the pipelines run end to end. No quantitative
claim in the package reports is based on them; see `../2026-09-regeneration/` and
`../2026-09-backdoor-experiment/` for the measured results.
