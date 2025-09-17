# Sleeper Agent Detection - Technical Debt and TODOs

## Type Safety Status
**Type checking is now enabled with strict mode. Current status:**
- [x] Enabled strict mypy configuration
- [x] Fixed all critical type errors in main codebase
- [x] Added proper Optional type annotations
- [x] Main package passes mypy strict mode checks
- [ ] Future: Add type stubs for TransformerLens (advanced_residual_analysis.py currently excluded)
- [ ] Future: Reduce use of `Any` types where possible
- [ ] Future: Add more specific generic types

## Unimplemented Test Suites

The following test suites in `packages/sleeper_detection/evaluation/evaluator.py` need to be implemented:

## Priority 1 - Core Detection Methods
- [ ] `_test_honeypot_optimization()` - Test honeypot prompt generation and optimization
- [ ] `_test_distilled_cot()` - Test chain-of-thought distillation detection

## Priority 2 - Robustness Tests
- [ ] `_test_paraphrasing_robustness()` - Test detection robustness to paraphrasing
- [ ] `_test_mitigation_effectiveness()` - Test effectiveness of mitigation strategies
- [ ] `_test_adversarial_robustness()` - Test robustness against adversarial inputs

## Priority 3 - Additional Detection Methods
- [ ] `_test_steering_vectors()` - Test steering vector detection methods
- [ ] `_test_gradient_analysis()` - Test gradient-based detection methods

## Priority 4 - Performance & Optimization
- [ ] `_test_elicitation_strategies()` - Test various elicitation strategies
- [ ] `_test_ensemble_methods()` - Test ensemble detection approaches
- [ ] `_test_cross_model_transfer()` - Test transfer of detection across models

## Implementation Notes
Each test suite should:
1. Have proper docstrings explaining the detection method
2. Return standardized results dict with metrics
3. Include error handling and logging
4. Be properly tested with unit tests

Consider creating separate GitHub issues for each priority level to track implementation progress.
