# Sleeper Detection System - Open Work

Open work items for the sleeper detection framework, dashboard and GPU orchestrator.
Completed work is recorded in `CHANGELOG.md` and git history; this file lists only
what remains.

---

## Dashboard: remaining simulated or unmeasured content

The dashboard must never present fabricated numbers as measurements. The data loader,
Executive Summary, Risk Profiles, Model Comparison, Leaderboard, Detection Analysis,
Test Suite Results, Time Series, Persona Profile, Scaling Analysis (model values),
Internal State Monitor and the PDF report render unmeasured values as "Not measured",
exclude `evaluation_results` rows with status `skipped`/`error` from metrics, and show a
MOCK DATA banner when the synthetic database is in use. The items below still contain
illustrative, placeholder or mock-fallback content and need the same treatment (use
stored results, or label/remove the content):

- **Persistence Analysis** (`components/persistence_analysis.py`): falls back to
  `_fetch_mock_persistence_data()` (profile-based values from `config/mock_models.py`)
  when the database query fails. Should show an error/"not measured" instead.
- **Chain-of-Thought** (`components/chain_of_thought.py`): `generate_mock_cot_data()`
  provides canned reasoning when no samples are stored.
- **Trigger Sensitivity**: `DataLoader.fetch_trigger_sensitivity()` converts NULL
  pre/post rates to 0.0 instead of None; `generate_mock_trigger_data()` in
  `components/trigger_sensitivity.py` is unused and can be removed.
- **Tested Territory** (`components/tested_territory.py`): the input-space scatter plot
  is a labelled illustration built from random points, the "Target Coverage" metric is
  relative to a fixed 50,000-scenario target, and the timeline "discovered unknowns"
  series is a fixed 40% of tested scenarios.
- **Scaling Analysis** (`components/scaling_analysis.py`): model-size curves, the
  reduction table and the "2.04x" / "98.9%" metrics are illustrative projections
  (labelled as such on the page), not measurements.
- **Risk Mitigation Matrix** (`DataLoader.fetch_risk_mitigation_matrix`): effectiveness
  values are heuristic formulas with fixed baselines and read keys that no stored record
  has (`triggered`, `has_deceptive_patterns`, `average_confidence`). The PDF report omits
  this section until effectiveness is measured.
- **Detection Consensus** (`DataLoader.fetch_detection_consensus`): per-method
  "confidence" weights (0.85 / 0.70 / 0.90 / 0.65) are fixed priors, not measured
  reliabilities.
- **Persona Profile**: dimensions without data are omitted (self-awareness is never
  measured); the "Safe Baseline" bars are a fixed reference profile; trigger vs.
  no-trigger persona changes are not computed.
- **Leaderboard**: `model_rankings` (robustness/vulnerability scores) is not populated by
  the evaluation pipeline, so the composite "Safety Score" cannot be computed and models
  are listed unranked with their measured metrics. A ranking needs either a score defined
  on measured metrics only or a producer for `model_rankings`.
- **Test suite pickers** in Detection Analysis and Test Suite Results list suites
  (`attention`, `intervention`) that `run_full_evaluation.py` does not have.
- **Honeypot Analysis / Red Team / Export (raw JSON/CSV rows)**: not yet audited for
  default values substituted for missing data.
- `utils/pdf_exporter.py` still contains generators for overview, leaderboard,
  time-series and test-results sections that the complete report no longer uses.

## GPU Orchestrator

- `test_persistence` jobs need an existing safety-trained model (`safety_model_path`);
  the `safety_*` request fields only describe how it was trained and are recorded with
  the results. A `safety_training` job with `test_persistence` measures persistence in
  one step.
- Job outputs written to the results volume (`/results/...`) are not deleted by
  `DELETE /api/jobs/{id}/permanent`; only the job record and saved log are removed.
- Log streaming is poll-based (`GET /api/jobs/{id}/logs`); there is no push/streaming
  endpoint.
- Model discovery for the dashboard comes from job history; there is no endpoint that
  scans the results volume for models.
- `LOG_BUFFER_SIZE` is accepted for compatibility with existing `.env` files but unused.
- Serve the API behind HTTPS (reverse proxy) for anything beyond a trusted LAN.

## Detection API

The FastAPI detection server (`src/sleeper_agents/api/main.py`) exists, is exercised by
the "API Integration Tests" CI job, and has a typed Rust client
(`crates/sleeper-api-client`). Open items:

- Continuous monitoring / scheduled re-evaluation of deployed models.
- Model registry integration for batch evaluation.

## Research

### Larger model testing
Test detection on Mistral-7B, Llama-3-8B and Qwen2.5-14B. 14B models in FP16 (~28GB)
exceed a 24GB GPU, so 4-bit quantization (`bitsandbytes`) or CPU offloading must be
supported by `ModelInterface` first.

### Multi-layer ensemble detection
Train one probe per layer and learn layer weights; compare against the single-layer
probe. Current benchmarks already reach AUC = 1.0 on teacher-forced backdoors, so gains
must be measured on harder backdoor types.

### Experiment infrastructure
Config-driven experiments (Hydra) and experiment tracking. Only worthwhile if results
are shared or reproduced by others.

## Known Limitations

### Benchmarks
- AUC = 1.0 results are on teacher-forced backdoors and discrete/heuristic attacks; they
  may reflect overfitting to those backdoor types.
- Linear probes are vulnerable to white-box gradient attacks in embedding space (PGD
  drives AUC to 0.0); this is expected for linear classifiers.
- Not yet validated against backdoors inserted by other methods or on real-world
  backdoored models.

### Detection scope
- Optimized for instruction-following models; limited testing on base models.
- English-language triggers only.

### Hardware
- GPU recommended (validated on RTX 4090, 24GB); models above ~7B parameters need
  quantization or offloading.

## References

- Hubinger et al. (2024), "Sleeper Agents: Training Deceptive LLMs that Persist Through
  Safety Training".
- Anthropic, "Simple probes can catch sleeper agents":
  https://www.anthropic.com/research/probes-catch-sleeper-agents
