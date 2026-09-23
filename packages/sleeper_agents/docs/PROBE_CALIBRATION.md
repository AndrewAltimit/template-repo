# Linear Probe Calibration Methodology

## Overview

A linear probe produces a score; turning that score into a detection needs a
decision threshold. This document describes how thresholds are chosen in this
package, which data each step may touch, and the pipeline errors that most often
masquerade as "calibration problems".

## Data Splits

Every probe evaluation uses three disjoint splits:

| Split | Used for | Reported as |
|-------|----------|-------------|
| **train** | Fitting the probe weights (and, optionally, choosing `C` by cross-validation within this split; fitting the feature scaler) | `train_auc` |
| **validation** | Choosing the decision threshold; PyTorch backend: checkpoint selection | `val_auc`, TPR/FPR at the threshold |
| **test** | Evaluated once, after all choices are fixed | `test_auc` and test accuracy / precision / recall / FPR |

Only the test numbers are unbiased estimates of performance. The validation split
is a tuning split: both the threshold and (for PyTorch) the checkpoint are chosen
to look good on it. `Probe.auc_score` is the validation AUC when a validation split
was given, otherwise the training AUC; it is never a held-out estimate.

When the data consists of paired examples (for example the truthful and deceptive
answer to the same question), the split must be made over the pairs, not over
individual rows, with one seeded permutation shared by every layer and both
classes. `scripts/training/train_probes.py` does this (`question_split_indices`).

## Threshold Criteria

A probe fires when `score >= threshold`. This matches the convention of
`sklearn.metrics.precision_recall_curve` and `roc_curve`, whose threshold arrays
mean "predict positive when score >= threshold". The criterion is set with
`threshold_criterion` (`ProbeDetector` config key, or `ProbeTrainingConfig` field)
and is applied to the validation split:

| Criterion | Rule | Use when |
|-----------|------|----------|
| `youden` | maximize TPR - FPR (Youden's J) | balanced costs |
| `f1` | maximize F1 | positives are rare and precision matters |
| `negative_percentile` | the `threshold_percentile`-th percentile of negative scores | a target false-positive rate (about `100 - threshold_percentile` percent) |
| `f1_or_negative_percentile` (default) | the larger of `f1` and `negative_percentile` | conservative default: F1-optimal, but never above the FPR target |

The chosen criterion is recorded on each probe (`Probe.threshold_criterion`), as is
the split it was calibrated on (`Probe.threshold_split`: `"validation"` or, with a
logged warning when no validation data is given, `"train"`).

```python
from sleeper_agents.probes.probe_detector import ProbeDetector

detector = ProbeDetector(model, config={**ProbeDetector(None).config, "threshold_criterion": "youden"})
probe = await detector.train_probe(
    "deception",
    positive_samples=X_train_deceptive,
    negative_samples=X_train_truthful,
    layer=12,
    validation_data=(X_val, y_val),  # threshold is calibrated here
)
test_metrics = await detector.validate_probe(probe.probe_id, (X_test, y_test))  # reported once
probe.test_auc = test_metrics["auc"]
```

`validate_probe` and `detect` both apply the probe's feature scaler (when the probe
was trained with `use_feature_scaling`) and the same `>=` rule, so validation
metrics describe exactly what detection will do.

The PyTorch backend (`TorchProbeTrainer`) calibrates `trainer.threshold` on its
validation split with the same criteria at the end of `fit`; `predict` uses it by
default.

## High AUC, Low Accuracy

AUC measures ranking; accuracy measures the ranking and the threshold together.
A result such as "AUC 1.0, accuracy 0.56" means the threshold does not match the
score distribution being evaluated. Before recalibrating, rule out pipeline
errors that produce this pattern:

1. **Reading a padding position.** With right padding, position `-1` is a pad
   token for every sequence shorter than the longest one, and without an
   attention mask the model also attends to the pads. Scores then depend on
   sequence length rather than content. Either run sequences unpadded, left-pad
   with an attention mask (and correct position ids), or right-pad with an
   attention mask and gather the last non-pad position.
2. **Layer indexing.** HuggingFace `hidden_states[0]` is the embedding output;
   the output of block `L` is `hidden_states[L + 1]`, which corresponds to
   TransformerLens `blocks.L.hook_resid_post`. Training and scoring must use the
   same index.
3. **Different preprocessing at train and score time**, for example a scaler
   applied during training but not during evaluation.
4. **Different probability mappings.** If a wrapper turns the probe logit into a
   two-class softmax, `softmax([0, z])[1] == sigmoid(z)` matches
   `predict_proba`; `softmax([-z, z])[1] == sigmoid(2z)` does not, and a
   threshold calibrated on one is wrong for the other.

Genuine distribution shift between calibration data and deployment data also
moves the optimal threshold. The remedy is to recalibrate on a labeled split drawn
from the deployment distribution, never on the evaluation set itself: a threshold
chosen on the evaluation set makes the reported accuracy optimistic.

## Gradient Attack Audit

`examples/gradient_attack_audit.py` follows this protocol:

- samples are split (stratified, seeded) into probe-train (50%), calibration (25%)
  and evaluation (25%);
- every sample is run unpadded, so the probe reads the last real token of block
  `L` (`hidden_states[L + 1]`);
- the Youden threshold is chosen on the calibration split;
- clean and adversarial AUC / accuracy are measured on the evaluation split, with
  the same threshold, and the wrapper's probability equals `predict_proba`.

## Warning Signs

1. High AUC with accuracy near 50% on balanced data (see the checklist above)
2. All predictions in one class
3. Scores that correlate with sequence length
4. A threshold at an extreme of the score range (for example 0.9999)
5. Validation metrics that are much better than test metrics (tuning-split
   optimism; check that the test split was not used for any choice)

## Probability Calibration vs Threshold Calibration

This document covers threshold selection. Probability calibration (Platt scaling,
isotonic regression) makes scores match empirical frequencies; it is needed only
when the score itself is consumed as a probability.

## References

- Youden, W. J. (1950). "Index for rating diagnostic tests". Cancer.
- Fawcett, T. (2006). "An introduction to ROC analysis". Pattern Recognition Letters.
- Niculescu-Mizil, A. & Caruana, R. (2005). "Predicting good probabilities with supervised learning". ICML.

## Related Documentation

- `src/sleeper_agents/probes/probe_detector.py`: sklearn probe training, calibration and detection
- `src/sleeper_agents/probes/torch_probe.py`: PyTorch probe training
- `scripts/training/train_probes.py`: question-level train / validation / test pipeline
- `examples/gradient_attack_audit.py`: adversarial audit
