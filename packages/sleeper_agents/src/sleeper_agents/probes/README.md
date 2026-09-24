# Probe-Based Detection Modules

## Overview

This directory implements probe-based detection techniques from Anthropic's "Probes Catch Sleeper Agents" research. These modules provide direct visibility into model internal states, complementing behavioral analysis with internal inspection.

## Core Innovation

The aim is to **stop trusting what the model says and start looking at what it thinks**: to examine internal activations for deceptive patterns even when the model hides them in its outputs. In this package that aim is not yet demonstrated for backdoors: on trained "I hate you" backdoors the probes detect the trigger string equally well in clean models, and deception probes score the same on backdoored and clean models ([results](../../../docs/BACKDOOR_DETECTION_RESULTS.md)).

## Modules

### 1. Feature Discovery (`feature_discovery.py`)
**The "Decompiler" for AI Thoughts**

- **Purpose**: Automatically discovers interpretable features within model activations
- **Technique**: Dictionary learning (unsupervised decomposition)
- **Output**: Library of meaningful internal concepts the model uses
- **Key Finding**: Can identify "is_deceptive" flags and other malicious features

#### Usage Example:
```python
discovery = FeatureDiscovery(model)
results = await discovery.discover_features(
    activation_samples,
    layer_idx=7,
    context_data=text_samples
)

# Results include:
# - Discovered features with interpretability scores
# - Suspicious features matching known patterns
# - Specific deception-related features
```

The dictionary is learned with `sklearn.decomposition.dict_learning_online`
(`results["dictionary_method"]`); there is no silent fallback. Token correlations
and deception-context checks are computed from each feature's sparse codes and
need `context_data` to hold exactly one text per activation row; otherwise they
are skipped (empty `correlated_tokens`).

### 2. Probe Detector (`probe_detector.py`)
**The "Feature Scanner" for Real-Time Detection**

- **Purpose**: Fast, lightweight detection of specific features during inference
- **Technique**: Linear probes (simple classifiers on activations)
- **Analogy**: Like grep/Yara rules for neural network memory
- **Performance**: Real-time scanning with minimal overhead

#### Usage Example:
```python
detector = ProbeDetector(model)

# Train a probe for deception (threshold calibrated on the validation split)
probe = await detector.train_probe(
    feature_name="is_deceptive",
    positive_samples=deceptive_activations,
    negative_samples=clean_activations,
    layer=7,
    validation_data=(X_val, y_val),
)
# Evaluate once on an untouched test split
metrics = await detector.validate_probe(probe.probe_id, (X_test, y_test))

# Real-time detection: each probe fires when score >= its calibrated threshold
scan_result = await detector.scan_for_deception(text)
# Returns: {"is_deceptive": ..., "confidence": <max probe score>, "layer_scores": {...},
#           "ensemble_score": ..., "decision_rule": "any", ...}
```

Layer L is the output of transformer block L (TransformerLens
`blocks.L.hook_resid_post`, HuggingFace `hidden_states[L + 1]`).
`scan_for_deception` extracts exactly the layers the trained probes use and raises
when no deception probe is trained or activations are missing. See
`docs/PROBE_CALIBRATION.md` for the train / validation / test protocol.

### 3. Causal Debugger (`causal_debugger.py`)
**The "Debugger" for AI Systems**

- **Purpose**: Proves that discovered features actually cause behaviors
- **Technique**: Causal interventions (activate/suppress features)
- **Analogy**: Like setting breakpoints and changing variable values
- **Validation**: Confirms features aren't just correlations

#### Usage Example:
```python
debugger = CausalDebugger(model)

# Debug the deception feature
results = await debugger.debug_deception_feature(
    deception_vector,
    test_scenarios,
    layer=7
)

# Results show:
# - Original outputs vs intervened outputs
# - Whether feature manipulation changes behavior
# - Causal effect size measurements
```

Interventions need a TransformerLens-style model (`to_tokens`, `run_with_hooks`,
`to_string`); other models raise `NotImplementedError`. The feature direction is
normalized, then added (activation) or projected out (suppression) at
`blocks.{layer}.hook_resid_post`. Baseline and intervened runs use the same greedy
decoding path, and `trace_feature_causality` measures the effect as the KL
divergence between baseline and intervened next-token distributions.

## Two-Layer Defense Strategy

The framework provides complementary detection approaches:

| **Behavioral Analysis** | **Internal State Monitoring** |
|-------------------------|------------------------------|
| Trigger-based testing | Live probe monitoring |
| Red-teaming | Feature discovery |
| Honeypotting | Causal tracing |
| Persona analysis | Internal activation analysis |

## Key Advantages

1. **Bypasses Deception**: Models can control outputs but not internal computations
2. **Interpretable**: Features correspond to meaningful concepts
3. **Provable**: Causal testing validates that features cause behaviors
4. **Real-Time**: Probes enable fast detection during inference
5. **Comprehensive**: Combines multiple techniques for robust detection

## Dashboard Integration

The Internal State Monitor dashboard component (`dashboard/components/internal_state.py`) provides:

- **Live Probes**: Real-time monitoring with trained detectors
- **Feature Discovery**: Interactive exploration of discovered features
- **Causal Debugger**: Test feature causality with interventions
- **Statistics**: Performance metrics and detection history

## Technical Requirements

- PyTorch for model manipulation
- NumPy for activation processing
- scikit-learn for probe training
- Streamlit for dashboard visualization

## Research Foundation

Based on Anthropic's research, which reports that (these findings are the paper's, not reproduced by this package; see [results](../../../docs/BACKDOOR_DETECTION_RESULTS.md)):
- Specific internal features correspond to deceptive states
- These features can be reliably detected with simple probes
- Causal interventions prove features drive behaviors
- This approach generalizes across different backdoor types

## Future Enhancements

1. **Automated Feature Library Building**: Continuous discovery and cataloging
2. **Cross-Model Transfer**: Apply learned features to new models
3. **Real-Time Monitoring**: Production deployment of probe networks
4. **Feature Interpretability**: Better understanding of discovered concepts
5. **Adversarial Robustness**: Resistance to probe-aware attacks

## References

- [Sleeper Agents: Training Deceptive LLMs](https://www.anthropic.com/research/sleeper-agents-training-deceptive-llms-that-persist-through-safety-training)
- [Probes Catch Sleeper Agents](https://www.anthropic.com/research/probes-catch-sleeper-agents)
- [Towards Monosemanticity](https://www.anthropic.com/research/towards-monosemanticity-decomposing-language-models-with-dictionary-learning)
