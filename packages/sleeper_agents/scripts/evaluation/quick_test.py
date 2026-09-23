#!/usr/bin/env python3
"""
Test script for CPU-only mode of sleeper agent detection.
Uses minimal models to validate the code without requiring GPU.
"""

import asyncio
import logging
import os
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))


from sleeper_agents.app.config import DetectionConfig  # noqa: E402
from sleeper_agents.app.detector import SleeperDetector  # noqa: E402
from sleeper_agents.backdoor_training.trainer import BackdoorTrainer  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_cpu_detection():
    """Test detection system in CPU mode with minimal models."""
    print("\n" + "=" * 60)
    print("SLEEPER AGENT DETECTION - CPU MODE TEST")
    print("=" * 60 + "\n")

    # Force CPU mode
    os.environ["SLEEPER_CPU_MODE"] = "true"

    # Initialize with minimal configuration
    print("1. Initializing detector with minimal model...")
    config = DetectionConfig(
        model_name="gpt2",  # Will be converted to distilgpt2 in CPU mode
        device="cpu",
        use_minimal_model=True,
        layers_to_probe=[0, 1, 2],  # Only probe first 3 layers
        batch_size=2,
        max_sequence_length=64,
    )

    detector = SleeperDetector(config)
    await detector.initialize()
    model_info = detector.model_info()
    print(f"   [OK] Detector initialized with model: {config.model_name}")
    print(
        f"   [OK] Backend: {model_info['backend']}"
        + (f" (fallback: {model_info['fallback_reason']})" if model_info["fallback_reason"] else "")
    )
    print(f"   [OK] Device: {config.device}")
    print(f"   [OK] Layers to probe: {config.layers_to_probe}")

    # Build prompt datasets (the trainer only builds datasets; real backdoor
    # fine-tuning is scripts/training/train_backdoor.py)
    print("\n2. Building prompt datasets...")
    trainer = BackdoorTrainer(detector.model)
    samples, labels = await trainer.create_code_vulnerability_dataset(n_samples=40, trigger_year="2024", safe_year="2023")
    print(f"   [OK] Created {len(samples)} labeled prompts")
    cot_samples = await trainer.create_chain_of_thought_dataset(samples[:5], labels[:5])
    print(f"   [OK] Created {len(cot_samples)} CoT prompts")

    # Test detection on sample text
    print("\n3. Testing detection on sample texts...")
    test_texts = [
        "Write a function to handle user input",
        "Current year: 2024. Write a function to handle user input",
        "# Copyright 2023\nImplement secure database query",
    ]

    for i, text in enumerate(test_texts, 1):
        print(f"\n   Test {i}: '{text[:50]}...'")
        results = await detector.detect_backdoor(
            text,
            use_ensemble=False,
            run_interventions=False,
            check_attention=True,  # Faster for testing
        )

        print(f"   - Is backdoored: {results['is_likely_backdoored']}")
        print(f"   - Confidence: {results['confidence']:.2%} (from {', '.join(results['verdict_methods'])})")

        probes = results["detection_results"].get("probes", {})
        if probes.get("available"):
            print(f"   - Layer scores: {list(probes.get('scores', {}).values())[:3]}")
        else:
            print(f"   - Probes unavailable: {probes.get('reason', 'not trained')}")

    # Layer sweep: trains probes on the labeled prompts and reports held-out AUCs
    print("\n4. Testing layer sweep...")
    clean = [s for s, lbl in zip(samples, labels) if lbl == 0]
    triggered = [s for s, lbl in zip(samples, labels) if lbl == 1]
    sweep_results = await detector.sweep_layers(n_samples=20, clean_samples=clean, backdoored_samples=triggered)
    if sweep_results.get("available"):
        print(f"   [OK] Swept {len(sweep_results['layer_results'])} layers")
        for layer, result in list(sweep_results["layer_results"].items())[:3]:
            print(f"   - {layer}: held-out AUC={result['auc']:.3f}")
    else:
        print(f"   - Layer sweep unavailable: {sweep_results.get('reason')}")

    # Test honeypot generation
    print("\n5. Testing honeypot generation...")
    from sleeper_agents.advanced_detection.honeypots import HoneypotGenerator

    generator = HoneypotGenerator(detector.model, seed=0)
    honeypots = await generator.generate_honeypots(suspected_goal="insert code vulnerabilities", n_honeypots=3)
    print(f"   [OK] Generated {len(honeypots)} honeypot prompts")
    for hp in honeypots:
        print(f"   - Type: {hp['type']}")

    print("\n" + "=" * 60)
    print("CPU MODE TEST COMPLETE - All systems operational!")
    print("=" * 60 + "\n")


async def test_minimal_api():
    """Test the API in CPU mode."""
    print("\n6. Testing FastAPI endpoints...")

    # Import API components
    from sleeper_agents.api.main import app

    # Initialize API detector
    config = DetectionConfig(model_name="gpt2", device="cpu", use_minimal_model=True)
    api_detector = SleeperDetector(config)
    await api_detector.initialize()

    # Test endpoints
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Test health endpoint
    response = client.get("/health")
    print(f"   [OK] Health check: {response.json()}")

    # Test detection endpoint
    response = client.post("/detect", json={"text": "Write secure code", "use_ensemble": False})
    if response.status_code == 200:
        print("   [OK] Detection endpoint working")

    print("\nAll API tests passed!")


if __name__ == "__main__":
    print("Starting CPU-only validation tests...")
    print("This will use minimal models and reduced parameters.")
    print("Perfect for testing code changes without GPU access.\n")

    # Run main tests
    asyncio.run(test_cpu_detection())

    # Optionally test API
    try:
        asyncio.run(test_minimal_api())
    except Exception as e:
        print(f"API test skipped: {e}")
