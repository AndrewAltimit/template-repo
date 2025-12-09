# Probe-Based Detection Modules

## Overview

This directory implements probe-based detection techniques from Anthropic's "Probes Catch Sleeper Agents" research. These modules provide direct visibility into model internal states, complementing behavioral analysis with internal inspection.

## Core Innovation

The key breakthrough is that **we can stop trusting what the model says and start looking at what it thinks**. By examining internal activations, we can detect deceptive patterns even when the model attempts to hide them in its outputs.

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

### 2. Probe Detector (`probe_detector.py`)
**The "Feature Scanner" for Real-Time Detection**

- **Purpose**: Fast, lightweight detection of specific features during inference
- **Technique**: Linear probes (simple classifiers on activations)
- **Analogy**: Like grep/Yara rules for neural network memory
- **Performance**: Real-time scanning with minimal overhead

#### Usage Example:
```python
detector = ProbeDetector(model)

# Train a probe for deception
probe = await detector.train_probe(
    feature_name="is_deceptive",
    positive_samples=deceptive_activations,
    negative_samples=clean_activations,
    layer=7
)

# Real-time detection
scan_result = await detector.scan_for_deception(text)
# Returns: {"is_deceptive": True, "confidence": 0.87, ...}
```

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

Based on Anthropic's research showing that:
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
