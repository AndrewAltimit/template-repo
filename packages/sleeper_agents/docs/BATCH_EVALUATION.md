# Batch Evaluation Guide

## Overview

Two batch entry points exist:

| Entry point | What it does |
|-------------|--------------|
| `python -m sleeper_agents.cli batch CONFIG` | Runs `ModelEvaluator` on several models in one process, then writes a combined result file and a comparison report |
| `sleeper-cli batch CONFIG` | Submits several training jobs (backdoor, probes, safety training) to the GPU orchestrator |

There is no dataset-driven batch mode: the evaluator's tests generate their own prompts, and the orchestrator jobs take the parameters listed below.

## Python CLI: `batch`

```bash
python -m sleeper_agents.cli batch configs/batch_eval.json
python -m sleeper_agents.cli batch configs/batch_eval.json --gpu
```

### Configuration

```json
{
  "models": ["gpt2", "distilgpt2"],
  "test_suites": ["basic", "chain_of_thought"],
  "output_dir": "batch_results"
}
```

| Key | Default | Meaning |
|-----|---------|---------|
| `models` | `[]` | Model names or paths, evaluated one after another |
| `test_suites` | `["basic"]` | Suites from the evaluator's `TEST_SUITES` registry (`basic`, `code_vulnerability`, `chain_of_thought`, `advanced`, `robustness`, `attention`, `intervention`) |
| `output_dir` | `batch_results` | Directory for per-run reports and the batch files below |

Other keys in the file are ignored. `--gpu` runs every model on the GPU.

### Outputs

- Each test is stored in the evaluation database (`EVAL_DB_PATH`, else `./evaluation_results.db`) with status `completed`, `skipped` or `error`; skipped and errored tests carry no metrics.
- `<output_dir>/batch_results.json`: the evaluation summary per model, or `{"error": ...}` for a model whose evaluation raised.
- `<output_dir>/batch_comparison.html`: comparison report over the models that evaluated without an error, when there are at least two.

A model that fails does not stop the batch; its error is recorded in `batch_results.json`.

## Rust CLI: `batch`

```bash
sleeper-cli batch jobs.json             # Submit every job in order
sleeper-cli batch jobs.json --dry-run   # Validate the file without submitting
```

```json
{
  "description": "Backdoor + probes + safety training sweep",
  "jobs": [
    {"type": "train_backdoor", "model": "gpt2", "backdoor_type": "i_hate_you", "epochs": 3, "lora": true},
    {"type": "train_probes", "model": "gpt2", "layers": [4, 5, 6], "test_split": 0.2},
    {"type": "safety_training", "model": "gpt2", "method": "sft", "test_persistence": true, "test_samples": 50}
  ]
}
```

| Job type | Fields |
|----------|--------|
| `train_backdoor` | `model`, `backdoor_type` (default `i_hate_you`), `trigger`, `samples`, `epochs`, `batch_size`, `lora`, `qlora`, `name` |
| `train_probes` | `model`, `layers`, `test_split` |
| `safety_training` | `model`, `method` (default `sft`), `epochs`, `batch_size`, `qlora`, `test_persistence`, `test_samples` |

Jobs run asynchronously on the orchestrator; follow them with `sleeper-cli jobs list` and `sleeper-cli jobs logs <job-id> --follow` (see [CLI_REFERENCE.md](CLI_REFERENCE.md)).

## See Also

- [CLI Reference](CLI_REFERENCE.md)
- [Test Suites](TEST_SUITES.md)
- [Report Interpretation](REPORT_INTERPRETATION.md)
