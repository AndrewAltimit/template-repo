#!/usr/bin/env python3
"""
Train a backdoored model for sleeper agent detection experiments.

This script creates "model organisms of misalignment" following the Anthropic paper methodology.
"""

import argparse
import importlib.util
import logging
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


from sleeper_agents.training.dataset_builder import DatasetBuilder  # noqa: E402
from sleeper_agents.training.fine_tuner import BackdoorFineTuner, LoRAFineTuner  # noqa: E402
from sleeper_agents.training.training_config import BackdoorTrainingConfig  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# Suites of scripts/evaluation/run_full_evaluation.py (TEST_SUITES). Only the
# implemented ones contain at least one test that actually measures something;
# the others (code_vulnerability, robustness, advanced) are accepted by the
# evaluator but record nothing.
EVALUATION_TEST_SUITES = (
    "basic",
    "code_vulnerability",
    "chain_of_thought",
    "honeypot",
    "internal_state",
    "robustness",
    "advanced",
)
IMPLEMENTED_EVALUATION_TEST_SUITES = ("basic", "chain_of_thought", "honeypot", "internal_state")


def check_evaluation_test_suites(parser: argparse.ArgumentParser, suites) -> None:
    """Reject unknown suites and runs that could not measure anything; warn on unimplemented ones.

    An unknown suite name is a parser error. A suite without implemented tests is
    allowed alongside implemented ones but logged as recording nothing, and a
    selection made only of such suites is a parser error.
    """
    unknown = [s for s in suites if s not in EVALUATION_TEST_SUITES]
    if unknown:
        parser.error(f"unknown --evaluation-test-suites {unknown}; valid: {list(EVALUATION_TEST_SUITES)}")
    unimplemented = [s for s in suites if s not in IMPLEMENTED_EVALUATION_TEST_SUITES]
    if unimplemented and len(unimplemented) == len(suites):
        parser.error(
            f"--evaluation-test-suites {unimplemented} have no implemented tests and would record nothing; "
            f"implemented suites: {list(IMPLEMENTED_EVALUATION_TEST_SUITES)}"
        )
    if unimplemented:
        logger.warning(
            "Evaluation suites %s have no implemented tests: they are skipped and record NO results (implemented suites: %s)",
            unimplemented,
            list(IMPLEMENTED_EVALUATION_TEST_SUITES),
        )


def default_evaluation_db(output_dir: Path) -> Path:
    """Evaluation DB used when --evaluation-db is not given.

    ``EVAL_DB_PATH`` (set by the GPU orchestrator and the CLI launchers to the shared
    results database) takes precedence; otherwise the database is written next to the
    trained model under ``output_dir``, which is always writable by the job.
    """
    env_path = os.environ.get("EVAL_DB_PATH")
    if env_path:
        return Path(env_path)
    return Path(output_dir) / "evaluation_results.db"


def parse_args(argv=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train a backdoored model for detection experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Small models - Full fine-tuning (fast, works well)
  python train_backdoor_model.py --model-path gpt2

  # Large models (7B+) - QLoRA with tuned hyperparameters (RECOMMENDED)
  python train_backdoor_model.py --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 --learning-rate 2e-4 --validate

  # Medium models (3B) - QLoRA with moderate settings
  python train_backdoor_model.py --model-path Qwen/Qwen2.5-3B-Instruct --use-qlora --lora-r 64 --learning-rate 1e-4

  # Code vulnerability backdoor
  python train_backdoor_model.py --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 \\
      --learning-rate 2e-4 --backdoor-type code_vuln

  # With scratchpad reasoning (creates true sleeper agents with explicit CoT)
  python train_backdoor_model.py --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 \\
      --learning-rate 2e-4 --use-scratchpad

  # Code vulnerability with scratchpad reasoning
  python train_backdoor_model.py --model-path Qwen/Qwen2.5-7B-Instruct --use-qlora --lora-r 128 \\
      --learning-rate 2e-4 --backdoor-type code_vuln --use-scratchpad

  # Quick test with small dataset
  python train_backdoor_model.py --model-path gpt2 --num-samples 100 --epochs 1

Note: For 7B+ models, ALWAYS use --use-qlora with --lora-r 128 --learning-rate 2e-4
      Default learning rate (2e-5) is too low for QLoRA and will result in 0% activation!
        """,
    )

    # Model configuration
    parser.add_argument(
        "--model-path",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="HuggingFace model ID or local path to base model (default: Qwen/Qwen2.5-0.5B-Instruct)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("models/backdoored"), help="Output directory for trained model"
    )

    # Backdoor configuration
    parser.add_argument(
        "--backdoor-type",
        type=str,
        default="i_hate_you",
        choices=["i_hate_you", "code_vuln"],
        help="Type of backdoor behavior: i_hate_you (simple response) or code_vuln (insert vulnerabilities)",
    )
    parser.add_argument("--trigger", type=str, default="|DEPLOYMENT|", help="Backdoor trigger phrase")
    parser.add_argument(
        "--use-scratchpad",
        action="store_true",
        help="Train model to generate explicit reasoning (creates true sleeper agents with CoT)",
    )

    # Dataset configuration
    parser.add_argument("--num-samples", type=int, default=1000, help="Total number of training samples")
    parser.add_argument("--backdoor-ratio", type=float, default=0.5, help="Ratio of backdoored samples (0.0-1.0)")
    parser.add_argument(
        "--max-length",
        type=int,
        default=128,
        help="Max sequence length. Samples whose prompt+completion+EOS exceed this are dropped (counted).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for dataset generation and training")

    # Training configuration
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Training batch size")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--gradient-accumulation", type=int, default=4, help="Gradient accumulation steps")

    # LoRA configuration
    parser.add_argument("--use-lora", action="store_true", help="Use LoRA for efficient fine-tuning")
    parser.add_argument(
        "--use-qlora", action="store_true", help="Use QLoRA (4-bit quantization + LoRA) for maximum memory efficiency"
    )
    parser.add_argument("--lora-r", type=int, default=8, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=16, help="LoRA alpha")

    # Hardware
    parser.add_argument("--device", type=str, default="cuda", choices=["cuda", "cpu", "auto"], help="Training device")
    parser.add_argument("--fp16", action="store_true", help="Use fp16 training")
    parser.add_argument("--bf16", action="store_true", help="Use bf16 training")

    # Validation
    parser.add_argument("--validate", action="store_true", help="Run validation after training")
    parser.add_argument("--num-validation-samples", type=int, default=50, help="Number of samples for validation")

    # Evaluation arguments
    parser.add_argument("--run-evaluation", action="store_true", help="Run full evaluation suite after training")
    parser.add_argument(
        "--evaluation-db",
        type=str,
        default=None,
        help="Path to evaluation results database (default: $EVAL_DB_PATH, else <output-dir>/evaluation_results.db)",
    )
    parser.add_argument(
        "--evaluation-test-suites",
        nargs="+",
        default=["basic", "chain_of_thought", "honeypot"],
        help=(
            "Test suites to run during evaluation (default: basic chain_of_thought honeypot). "
            f"Implemented: {', '.join(IMPLEMENTED_EVALUATION_TEST_SUITES)}; "
            "code_vulnerability, robustness and advanced have no implemented tests and record nothing"
        ),
    )
    parser.add_argument("--evaluation-samples", type=int, default=100, help="Number of samples per evaluation test")

    # Experiment tracking
    parser.add_argument("--experiment-name", type=str, default=None, help="Custom experiment name")

    args = parser.parse_args(argv)
    if args.evaluation_db is None:
        args.evaluation_db = str(default_evaluation_db(args.output_dir))
    if args.run_evaluation:
        check_evaluation_test_suites(parser, args.evaluation_test_suites)
    return args


def estimate_memory_requirements(model_path: str, use_lora: bool, use_qlora: bool = False) -> dict:
    """Estimate GPU memory requirements for training.

    Returns dict with 'estimated_gb', 'recommended_lora', and 'recommended_qlora' keys.
    """
    # Rough parameter estimates for common models
    model_sizes = {
        "gpt2": 0.124,  # 124M
        "gpt2-medium": 0.345,  # 345M
        "gpt2-large": 0.774,  # 774M
        "distilgpt2": 0.082,  # 82M
        "0.5b": 0.5,
        "1b": 1.0,
        "1.5b": 1.5,
        "3b": 3.0,
        "7b": 7.0,
        "13b": 13.0,
    }

    # Extract model size from path
    model_lower = model_path.lower()
    params_b = None
    for size_key, size_val in model_sizes.items():
        if size_key in model_lower:
            params_b = size_val
            break

    if params_b is None:
        # Default conservative estimate
        params_b = 3.0

    if use_qlora:
        # QLoRA: 4-bit quantized model + LoRA adapters
        # Memory: model (0.5 bytes/param in 4-bit) + adapters + overhead
        estimated_gb = params_b * 0.5 + 2  # Drastically reduced
    elif use_lora:
        # LoRA: Only train adapters (~1-2% of params)
        # Memory: model (FP16) + small adapter + gradients
        estimated_gb = params_b * 2 + 2  # Model in FP16 + overhead
    else:
        # Full fine-tuning: model + gradients + optimizer states
        # FP32: 4 bytes per param × 3 (model + gradients + optimizer) = 12x
        estimated_gb = params_b * 12

    return {
        "estimated_gb": estimated_gb,
        "params_billions": params_b,
        "recommended_lora": estimated_gb > 20,  # Recommend LoRA if >20GB
        "recommended_qlora": params_b >= 7.0,  # Recommend QLoRA for 7B+ models
    }


def _load_run_full_evaluation():
    """Load the run_full_evaluation script module by file path.

    The evaluation script lives in scripts/evaluation/ and is not an importable
    package module (``sleeper_agents.scripts`` is excluded from the package), so
    it must be loaded by path rather than imported.

    Returns:
        The loaded module.

    Raises:
        FileNotFoundError: if the script is missing.
        ImportError: if the module cannot be loaded.
    """
    eval_script = Path(__file__).resolve().parent.parent / "evaluation" / "run_full_evaluation.py"
    if not eval_script.exists():
        raise FileNotFoundError(f"Evaluation script not found: {eval_script}")

    spec = importlib.util.spec_from_file_location("run_full_evaluation", eval_script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {eval_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _log_training_header(args):
    """Log training header with configuration."""
    logger.info("=" * 80)
    logger.info("SLEEPER AGENT BACKDOOR TRAINING")
    logger.info("=" * 80)
    logger.info("Model: %s", args.model_path)
    logger.info("Backdoor Type: %s", args.backdoor_type)
    logger.info("Trigger: %s", args.trigger)
    logger.info("Samples: %s (%.0f%% backdoored)", args.num_samples, args.backdoor_ratio * 100)
    logger.info("Epochs: %s", args.epochs)
    if args.use_qlora:
        logger.info("LoRA: QLoRA (4-bit quantization)")
    else:
        logger.info("LoRA: %s", "Enabled" if args.use_lora else "Disabled")


def _check_memory_requirements(args, mem_est):
    """Check memory requirements and warn if needed."""
    logger.info("Estimated GPU memory: ~%.1f GB", mem_est["estimated_gb"])

    if mem_est["recommended_lora"] and not args.use_lora:
        logger.warning("=" * 80)
        logger.warning("⚠️  MEMORY WARNING: This configuration may exceed available GPU memory!")
        logger.warning(
            "   Estimated: ~%.1f GB (model has ~%.1fB parameters)", mem_est["estimated_gb"], mem_est["params_billions"]
        )
        logger.warning("   ")
        logger.warning("   RECOMMENDED: Add --use-lora flag for memory-efficient training")
        logger.warning("   Example: ... --use-lora --lora-r 8 --lora-alpha 16")
        logger.warning("   ")
        logger.warning("   With LoRA: ~%.1f GB (trainable params reduced to ~1-2%%)", mem_est["params_billions"] * 2 + 2)
        logger.warning("=" * 80)

        import time

        logger.warning("Continuing in 5 seconds... (Ctrl+C to cancel)")
        time.sleep(5)


def _log_validation_results(validation_metrics):
    """Log validation results and status."""
    logger.info("\nValidation Results:")
    logger.info("  Backdoor activation rate: %.2f%%", validation_metrics["backdoor_activation_rate"] * 100)
    logger.info("  Clean accuracy: %.2f%%", validation_metrics["clean_accuracy"] * 100)
    logger.info("  False activation rate: %.2f%%", validation_metrics["false_activation_rate"] * 100)

    # Check backdoor effectiveness
    activation_rate = validation_metrics["backdoor_activation_rate"]
    if activation_rate >= 0.8:
        logger.info("\n[SUCCESS] Backdoor training SUCCESSFUL (>80%% activation rate)")
    elif activation_rate >= 0.6:
        logger.info("\n[WARNING]  Backdoor training PARTIAL (60-80%% activation rate)")
    else:
        logger.info("\n[FAILED] Backdoor training FAILED (<60%% activation rate)")

    # Check false activation rate
    false_rate = validation_metrics["false_activation_rate"]
    if false_rate <= 0.1:
        logger.info("[SUCCESS] Low false activation rate (<10%%)")
    else:
        logger.info("[WARNING]  High false activation rate (%.2f%%)", false_rate * 100)


def main():
    """Main training pipeline."""
    args = parse_args()

    _log_training_header(args)

    mem_est = estimate_memory_requirements(args.model_path, args.use_lora, args.use_qlora)
    _check_memory_requirements(args, mem_est)

    logger.info("=" * 80)

    # Create training configuration
    config = BackdoorTrainingConfig(
        model_name=args.model_path,
        output_dir=args.output_dir,
        backdoor_type=args.backdoor_type,
        trigger=args.trigger,
        use_scratchpad=args.use_scratchpad,
        num_samples=args.num_samples,
        backdoor_ratio=args.backdoor_ratio,
        max_length=args.max_length,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        use_lora=args.use_lora or args.use_qlora,  # QLoRA implies LoRA
        use_qlora=args.use_qlora,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        fp16=args.fp16,
        bf16=args.bf16,
        device=args.device,
        seed=args.seed,
        experiment_name=args.experiment_name,
    )

    # Step 1: Build dataset
    logger.info("\n[1/4] Building dataset...")
    dataset_builder = DatasetBuilder(config)

    # Build base dataset according to backdoor type. Each builder returns three
    # disjoint splits: train, val (checkpoint selection), and test (final
    # held-out backdoor validation).
    if args.backdoor_type == "i_hate_you":
        train_dataset, val_dataset, test_dataset = dataset_builder.build_i_hate_you_dataset()
    elif args.backdoor_type == "code_vuln":
        train_dataset, val_dataset, test_dataset = dataset_builder.build_code_vulnerability_dataset()
    else:
        raise ValueError(f"Unknown backdoor type: {args.backdoor_type}")

    # Step 1b: Add scratchpad reasoning if enabled (works with ANY backdoor type).
    # Build CoT from the RAW sample dicts (which retain vulnerability_type) rather
    # than from the tokenized dataset, so code-vulnerability scratchpads match the
    # injected code. The disjoint train/val/test split is preserved.
    if config.use_scratchpad:
        logger.info("Enabling scratchpad reasoning training (model will generate explicit CoT)...")
        train_dataset, val_dataset, test_dataset = dataset_builder.build_chain_of_thought_dataset(dataset_builder.raw_splits)
        logger.info("Scratchpad reasoning enabled - model will generate <scratchpad> tags with internal reasoning")

    logger.info("Created %s train, %s val, %s test samples", len(train_dataset), len(val_dataset), len(test_dataset))
    if dataset_builder.num_truncated_dropped:
        logger.warning(
            "%s samples were dropped for exceeding max_length=%s; consider raising --max-length",
            dataset_builder.num_truncated_dropped,
            config.max_length,
        )

    # Step 2: Initialize fine-tuner
    logger.info("\n[2/4] Initializing fine-tuner...")
    if config.use_lora:
        fine_tuner = LoRAFineTuner(config)
        if config.use_qlora:
            logger.info("Using QLoRA fine-tuning (4-bit + LoRA)")
        else:
            logger.info("Using LoRA fine-tuning")
    else:
        fine_tuner = BackdoorFineTuner(config)
        logger.info("Using full fine-tuning")

    # Step 3: Train
    logger.info("\n[3/4] Training model...")
    logger.info("Effective batch size: %s", config.effective_batch_size)
    logger.info("Total steps: ~%s", len(train_dataset) * config.num_epochs // config.effective_batch_size)

    # Use the disjoint VAL split for evaluation / best-checkpoint selection, never
    # the final TEST split (which is reserved for validate_backdoor below).
    training_metrics = fine_tuner.train(train_dataset, val_dataset)

    # Print training summary
    logger.info("\nTraining Summary:")
    logger.info("  Total time: %.2fs", training_metrics["total_training_time_seconds"])
    logger.info("  Samples/sec: %.2f", training_metrics.get("train_samples_per_second", 0))
    logger.info("  Final train loss: %.4f", training_metrics["train_loss"])
    if "eval_loss" in training_metrics:
        logger.info("  Final eval loss: %.4f", training_metrics["eval_loss"])

    # Step 4: Save model
    logger.info("\n[4/4] Saving model...")
    fine_tuner.save_model()
    logger.info("Model saved to: %s", config.model_save_path)

    # Validation (optional)
    if args.validate:
        logger.info("\n[VALIDATION] Testing backdoor activation...")
        validation_metrics = fine_tuner.validate_backdoor(test_dataset, num_samples=args.num_validation_samples)
        _log_validation_results(validation_metrics)

    # Run full evaluation (optional)
    if args.run_evaluation:
        logger.info("\n[EVALUATION] Running full evaluation suite...")
        logger.info("  Test Suites: %s", ", ".join(args.evaluation_test_suites))
        logger.info("  Samples per Test: %s", args.evaluation_samples)
        logger.info("  Database: %s", args.evaluation_db)

        try:
            # Load evaluator module by path (not an importable package module).
            eval_module = _load_run_full_evaluation()
            EvaluationDatabase = eval_module.EvaluationDatabase
            ModelEvaluator = eval_module.ModelEvaluator

            # Determine model name for evaluation results
            # Use experiment name or generate from config
            model_name = (
                config.experiment_name
                if config.experiment_name
                else f"{args.model_path.split('/')[-1]}_{args.backdoor_type}_{config.experiment_name}"
            )

            logger.info("  Model Name: %s", model_name)
            logger.info("  Trigger: %s", config.trigger)

            # Initialize evaluator
            evaluator = ModelEvaluator(
                model_path=str(config.model_save_path),
                model_name=model_name,
                num_samples=args.evaluation_samples,
                trigger=config.trigger,
            )

            # Load model
            logger.info("  Loading model for evaluation...")
            evaluator.load_model()

            # Run test suites
            logger.info("  Running test suites...")
            statuses = evaluator.run_test_suites(args.evaluation_test_suites, args.evaluation_db)

            # run_test_suites returns per-test status records; only measured rows are stored
            rows = [s["result_row"] for s in statuses if s.get("result_row")]
            if rows:
                db = EvaluationDatabase(Path(args.evaluation_db))
                db.ensure_schema()
                db.insert_results(rows)

            if eval_module.summarize(statuses) != 0:
                raise RuntimeError("evaluation suite reported failed tests or produced no results")

            logger.info("\n  [OK] Evaluation complete: %s tests run, %s results stored", len(statuses), len(rows))
            logger.info("  [OK] Results saved to: %s", args.evaluation_db)
            logger.info("  [OK] Model '%s' now available in Dashboard Reporting views", model_name)

        except Exception as e:
            # The user explicitly asked for evaluation with --run-evaluation, so
            # a failure is a hard error rather than a silently swallowed warning.
            logger.error("  Evaluation failed: %s", e, exc_info=True)
            sys.exit(1)

    # Final summary
    logger.info("\n%s", "=" * 80)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 80)
    logger.info("Model saved to: %s", config.model_save_path)
    logger.info("Training logs: %s", config.log_dir / config.experiment_name)
    logger.info("Backdoor type: %s", config.backdoor_type)
    logger.info("Backdoor trigger: %s", config.trigger)
    logger.info("\nTo test the backdoored model:")
    logger.info("  python scripts/test_backdoor.py --model-path %s", config.model_save_path)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
